"""Bounded, cancellable collection searches with explicit ID disambiguation.

Every job is written through to a durable SQLite store (see job_store.py), so
results survive restarts and remain reachable at their bookmarkable link for the
retention period (KLINKPPI_RESULT_RETENTION_DAYS, default 14 days). Only active
jobs and recently viewed results are kept in memory. No source score is treated
as a probability or combined across incompatible database scales.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from threading import BoundedSemaphore, Event, Lock
from time import sleep, time
from uuid import uuid4
import logging
import math
import os
import re

import requests

from app.services.job_store import get_store, retention_seconds

LOGGER = logging.getLogger(__name__)
API = "https://rest.uniprot.org/uniprotkb"
MAX_INPUTS = 50
# PPI (pair) search: up to MAX_PAIRS pairs over at most MAX_PAIR_INPUTS distinct proteins.
MAX_PAIRS = 100
MAX_PAIR_INPUTS = 2 * MAX_INPUTS
# Expanded networks keep at most this many first neighbors per protein or per pair.
DEFAULT_NEIGHBOR_LIMIT = 10
MAX_NEIGHBOR_LIMIT = 200
MAX_EDGES = 50000
MAX_ENDPOINTS = 10000
# Queue limits: only resolving/running jobs count, so finished results never
# block new submissions (the former "12 retained jobs" limit).
MAX_ACTIVE_JOBS = int(os.environ.get("KLINKPPI_MAX_ACTIVE_COLLECTION_JOBS", "8"))
MAX_ACTIVE_PER_CLIENT = int(os.environ.get("KLINKPPI_MAX_ACTIVE_COLLECTION_JOBS_PER_CLIENT", "3"))
MEMORY_TTL = 3600  # finished jobs leave memory after an hour without access; SQLite keeps them
KIND = "collection"
ACTIVE = {"resolving", "running"}
PRIVATE = {"cancel", "resolver", "client", "accessed_at"}
EXAMPLE_JOB_ID = "example"
# Human homologous-recombination / Fanconi anaemia module: BRCA1, BARD1, PALB2, BRCA2,
# RAD51 and its paralogues (RAD51B/C/D, XRCC2, XRCC3, meiotic DMC1), FANCD2, FANCI, FANCA.
EXAMPLE_IDENTIFIERS = ["P38398", "Q99728", "Q86YC2", "P51587", "Q06609", "O15315", "O43502", "O75771", "O43543", "O43542", "Q9BXW9", "Q9NVI1", "O15360", "Q14565"]
EXAMPLE_DATABASES = ["String", "IntAct", "BioGrid", "Corum", "HuRI", "Predictomes", "ComplexPortal", "Reactome", "Signor", "Hippie", "HuMap", "Mint"]
# Permanent PPI example over the same module: known pairs (BRCA1–BARD1, PALB2–BRCA2,
# RAD51–RAD51C, FANCD2–FANCI, TP53–MDM2) and pairs without evidence (RAD51C–DMC1, BARD1–XRCC3).
PPI_EXAMPLE_JOB_ID = "ppi-example"
PPI_EXAMPLE_PAIRS = [["P38398", "Q99728"], ["Q86YC2", "P51587"], ["Q06609", "O43502"], ["Q9BXW9", "Q9NVI1"],
                     ["P04637", "Q00987"], ["O43502", "Q14565"], ["Q99728", "O43542"]]
DEFAULT_RESOLVER = None
POOL = ThreadPoolExecutor(max_workers=int(os.environ.get("KLINKPPI_COLLECTION_WORKERS", "2")), thread_name_prefix="collection-jobs")
# Per-job database queries run in parallel; a per-source cap keeps any single
# remote service from receiving more than DB_CONCURRENCY requests at once.
DB_WORKERS = int(os.environ.get("KLINKPPI_COLLECTION_DB_WORKERS", "24"))
DB_CONCURRENCY = int(os.environ.get("KLINKPPI_COLLECTION_DB_CONCURRENCY", "6"))
# UniProt ID lookups are batched (25 IDs per query) and the batches run in parallel.
UNIPROT_WORKERS = int(os.environ.get("KLINKPPI_UNIPROT_WORKERS", "4"))
UNIPROT_BATCH = 25
JOBS = {}
LOCK = Lock()
SOURCE_SLOTS = {}
ACCESSION = re.compile(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-\d+)?$", re.I)
TOKEN = re.compile(r"[A-Za-z0-9_.:/-]{1,100}$")
FIELDS = "accession,id,gene_names,protein_name,organism_name,organism_id,reviewed,xref_ensembl,xref_geneid"


def clean(value):
    if value is None:
        return ""
    result = str(value).strip()
    return "" if result.lower() in {"", "-", "none", "nan", "null"} else result


def entry_candidate(entry):
    genes = []
    for gene in entry.get("genes", []):
        for key in ("geneName", "synonyms", "orderedLocusNames", "orfNames"):
            values = gene.get(key, [])
            if isinstance(values, dict):
                values = [values]
            genes.extend(item["value"] for item in values if item.get("value"))
    organism = entry.get("organism", {})
    return {
        "id": entry["primaryAccession"], "gene_names": list(dict.fromkeys(genes)),
        "gene": genes[0] if genes else entry["primaryAccession"],
        "species": organism.get("scientificName", ""), "tax_id": str(organism.get("taxonId", "")),
        "reviewed": entry.get("entryType") == "UniProtKB reviewed (Swiss-Prot)",
    }


def identify(token, input_type="auto"):
    if input_type != "auto":
        return input_type
    if ACCESSION.fullmatch(token) or re.fullmatch(r"[A-Za-z0-9]+_[A-Za-z0-9]+", token):
        return "UniProtKB"
    if re.match(r"^ENS[A-Z]*[GPT]\d+", token, re.I):
        return "Ensembl"
    if token.isdigit():
        return "GeneID"
    return "Gene_Name"


def clause(token, input_type):
    # Tokens are restricted to literal ID characters, never query operators.
    if input_type == "UniProtKB":
        if ACCESSION.fullmatch(token):
            primary = re.sub(r"-\d+$", "", token)
            return f"accession:{primary}"
        return f"id:{token}"
    if input_type == "Ensembl":
        return f'xref:ensembl-{token.split(".")[0]}'
    if input_type == "GeneID":
        return f'xref:geneid-{token}'
    return f'gene_exact:"{token}"'


def aliases(entry):
    names = {entry["primaryAccession"].upper(), entry.get("uniProtkbId", "").upper()}
    names.update(value.upper() for value in entry.get("secondaryAccessions", []))
    names.update(value.upper() for value in entry_candidate(entry)["gene_names"])
    for ref in entry.get("uniProtKBCrossReferences", []):
        if ref.get("database") in {"Ensembl", "GeneID"}:
            names.add(ref.get("id", "").split(".")[0].upper())
            for prop in ref.get("properties", []):
                if prop.get("key") in {"GeneId", "ProteinId"}:
                    names.add(prop.get("value", "").split(".")[0].upper())
    return names


def _resolve_chunk(chunk, tax_id, input_type, cancel):
    """Resolve one batch of up to UNIPROT_BATCH tokens with a single paginated query."""
    matches = {token: [] for token in chunk}
    errors = {}
    valid = [token for token in chunk if TOKEN.fullmatch(token)]
    for token in set(chunk) - set(valid):
        errors[token] = "Invalid identifier characters"
    if not valid:
        return matches, errors
    query = " OR ".join(clause(token, identify(token, input_type)) for token in valid)
    url = f"{API}/search"
    params = {"query": f"({query}) AND organism_id:{tax_id}", "format": "json", "fields": FIELDS, "size": 500}
    try:
        while url:
            if cancel and cancel.is_set():
                break
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            for entry in response.json().get("results", []):
                candidate = entry_candidate(entry)
                if candidate["tax_id"] != str(tax_id):
                    continue
                entry_aliases = aliases(entry)
                for token in valid:
                    kind = identify(token, input_type)
                    key = token.split(".")[0].upper() if kind == "Ensembl" else re.sub(r"-\d+$", "", token).upper() if kind == "UniProtKB" and ACCESSION.fullmatch(token) else token.upper()
                    if key in entry_aliases:
                        matches[token].append(candidate)
            url = response.links.get("next", {}).get("url")
            params = None
    except (requests.RequestException, ValueError, KeyError) as exc:
        # A failed page must not leave a partial candidate list appearing unique.
        for token in valid:
            matches[token] = []
            errors[token] = f"ID lookup failed: {exc}"
    return matches, errors


def resolve_tokens(tokens, tax_id, input_type="auto", cancel=None):
    """Batch exact search, paginate all candidates and validate organism.

    Batches are independent UniProt queries, so they run in parallel.
    """
    matches = {token: [] for token in tokens}
    errors = {}
    chunks = [tokens[offset:offset + UNIPROT_BATCH] for offset in range(0, len(tokens), UNIPROT_BATCH)]
    if len(chunks) <= 1:
        results = [_resolve_chunk(chunk, tax_id, input_type, cancel) for chunk in chunks if not (cancel and cancel.is_set())]
    else:
        with ThreadPoolExecutor(max_workers=min(UNIPROT_WORKERS, len(chunks)), thread_name_prefix="uniprot-lookup") as executor:
            futures = [executor.submit(_resolve_chunk, chunk, tax_id, input_type, cancel) for chunk in chunks]
            results = [future.result() for future in futures]
    for chunk_matches, chunk_errors in results:
        for token, candidates in chunk_matches.items():
            matches[token].extend(candidates)
        errors.update(chunk_errors)
    for token in tokens:
        matches[token] = sorted({c["id"]: c for c in matches[token]}.values(), key=lambda c: (not c["reviewed"], c["id"]))
    return matches, errors


def configure(resolver):
    """Resolver used for jobs reloaded from the durable store after a restart."""
    global DEFAULT_RESOLVER
    DEFAULT_RESOLVER = resolver


def _expired(job, now=None):
    if job.get("pinned") or job.get("status") in ACTIVE:
        return False
    created = job.get("created_at")
    return created is not None and (now or time()) - created > retention_seconds()


def _public(job):
    data = {k: v for k, v in job.items() if k not in PRIVATE}
    if data.get("created_at") is not None:
        data["expires_at"] = None if job.get("pinned") else data["created_at"] + retention_seconds()
    return data


def _persist_locked(job_id):
    """Write a job through to SQLite; the caller holds LOCK."""
    job = JOBS.get(job_id)
    if not job or "job_id" not in job:
        return
    try:
        get_store().save(KIND, {k: v for k, v in job.items() if k not in PRIVATE}, pinned=bool(job.get("pinned")))
    except Exception:  # Persistence failure must not break a running analysis.
        LOGGER.exception("Could not persist collection job %s", job_id)


def _load_locked(job_id):
    """Return the in-memory job, reloading it from SQLite when needed."""
    job = JOBS.get(job_id)
    if job is None:
        stored = get_store().load(KIND, job_id)
        if stored is None:
            raise KeyError(job_id)
        stored.pop("expires_at", None)
        job = JOBS[job_id] = {**stored, "cancel": Event(), "resolver": DEFAULT_RESOLVER}
    if _expired(job):
        JOBS.pop(job_id, None)
        get_store().delete(KIND, job_id)
        raise KeyError(job_id)
    job["accessed_at"] = time()
    return job


def _housekeeping_locked(now):
    for key, job in list(JOBS.items()):
        if job.get("status") in ACTIVE or job.get("pinned"):
            continue
        if _expired(job, now) or now - job.get("accessed_at", job.get("created_at", now)) > MEMORY_TTL:
            del JOBS[key]
    try:
        get_store().purge(KIND, now - retention_seconds(), keep_statuses=ACTIVE)
    except Exception:
        LOGGER.exception("Could not purge expired collection jobs")


def snapshot(job_id):
    with LOCK:
        return deepcopy(_public(_load_locked(job_id)))


def patch(job_id, **values):
    with LOCK:
        JOBS[job_id].update(values)
        _persist_locked(job_id)


def normalize_pairs(pairs):
    """Trim pairs, merge A-B / B-A duplicates and return (pairs, distinct tokens)."""
    result, seen = [], set()
    for pair in pairs or []:
        if len(pair) != 2:
            raise ValueError("Each PPI must name exactly two identifiers.")
        a, b = (str(value).strip() for value in pair)
        if not a or not b:
            raise ValueError("Each PPI must name exactly two identifiers.")
        key = tuple(sorted((a.upper(), b.upper())))
        if key not in seen:
            seen.add(key)
            result.append([a, b])
    if not result or len(result) > MAX_PAIRS:
        raise ValueError(f"Use 1–{MAX_PAIRS} distinct PPIs per search; duplicates are merged.")
    tokens = list(dict.fromkeys(token for pair in result for token in pair))
    if len(tokens) > MAX_PAIR_INPUTS:
        raise ValueError(f"Your PPIs name {len(tokens)} distinct proteins; use up to {MAX_PAIR_INPUTS}.")
    return result, tokens


def create_job(tokens, tax_id, species, databases, input_type, mode, resolver, *, client=None, job_id=None, pinned=False,
               pairs=None, neighbor_limit=None, neighbor_scope="protein"):
    if pairs:
        pairs, tokens = normalize_pairs(pairs)
    else:
        pairs = None
        tokens = list(dict.fromkeys(token.strip() for token in tokens if token.strip()))
        if not tokens or len(tokens) > MAX_INPUTS:
            raise ValueError(f"Use 1–{MAX_INPUTS} distinct identifiers per collection; duplicates are merged.")
    if neighbor_scope not in {"protein", "pair"} or (neighbor_scope == "pair" and not pairs):
        raise ValueError("Neighbor limits apply per protein, or per PPI in a PPI search.")
    if mode == "expanded":
        neighbor_limit = DEFAULT_NEIGHBOR_LIMIT if neighbor_limit is None else int(neighbor_limit)
        if not 1 <= neighbor_limit <= MAX_NEIGHBOR_LIMIT:
            raise ValueError(f"Show 1–{MAX_NEIGHBOR_LIMIT} neighbors per protein or PPI.")
    else:
        neighbor_limit, neighbor_scope = None, "protein"
    with LOCK:
        now = time()
        _housekeeping_locked(now)
        if not pinned:
            active = [job for job in JOBS.values() if job.get("status") in ACTIVE]
            if len(active) >= MAX_ACTIVE_JOBS:
                raise ValueError(f"The server is busy ({len(active)} collection analyses are running). Please retry in a minute; finished results are not affected.")
            if client and sum(job.get("client") == client for job in active) >= MAX_ACTIVE_PER_CLIENT:
                raise ValueError(f"You already have {MAX_ACTIVE_PER_CLIENT} collection analyses running. Wait for one to finish or cancel it.")
        job_id = job_id or uuid4().hex
        JOBS[job_id] = {"job_id": job_id, "created_at": now, "tax_id": tax_id, "species": species,
                        "databases": databases, "mode": mode, "status": "resolving", "progress": "Resolving identifiers…",
                        "search_type": "ppi" if pairs else "batch", "pairs": pairs,
                        "neighbor_limit": neighbor_limit, "neighbor_scope": neighbor_scope,
                        "tokens": tokens, "input_type": input_type, "cancel": Event(), "resolver": resolver,
                        "client": client, "pinned": pinned, "accessed_at": now,
                        "resolution": [], "warnings": [], "graph": None,
                        "database_statuses": {db: {"status": "pending", "completed": 0, "total": 0, "errors": 0} for db in databases}}
        _persist_locked(job_id)
    POOL.submit(_resolve_job, job_id)
    return snapshot(job_id)


def _read_only(job, internal):
    if job.get("pinned") and not internal:
        raise ValueError("The example result is read-only. Load the example into the form to run your own copy.")


def _resolve_job(job_id):
    job = JOBS[job_id]
    try:
        matches, errors = resolve_tokens(job["tokens"], job["tax_id"], job["input_type"], job["cancel"])
        resolution = [{"input": token, "input_type": identify(token, job["input_type"]), "candidates": matches[token],
                       "status": "resolved" if len(matches[token]) == 1 else "ambiguous" if matches[token] else "unresolved",
                       "error": errors.get(token)} for token in job["tokens"]]
        patch(job_id, resolution=resolution, status="cancelled" if job["cancel"].is_set() else "awaiting_selection",
              progress="Cancelled" if job["cancel"].is_set() else "Review ID resolution before running the analysis.")
    except Exception as exc:
        if not job["cancel"].is_set():
            patch(job_id, status="failed", progress=str(exc))


def run_job(job_id, choices, *, internal=False):
    with LOCK:
        job = _load_locked(job_id)
        _read_only(job, internal)
        if job["status"] != "awaiting_selection":
            raise ValueError("Job is not ready for analysis")
        selections = {}
        for row in job["resolution"]:
            candidates = row["candidates"]
            selected = choices.get(row["input"])
            if len(candidates) == 1 and row["input"] not in choices:
                selected = candidates[0]["id"]
            if selected and selected not in {candidate["id"] for candidate in candidates}:
                raise ValueError(f"Invalid candidate for {row['input']}")
            if len(candidates) > 1 and row["input"] not in choices:
                raise ValueError(f"Choose a candidate or explicitly skip {row['input']}")
            selections[row["input"]] = selected or None
        job.update(status="running", progress="Querying selected databases…", selections=selections)
        _persist_locked(job_id)
    POOL.submit(_network_job, job_id)
    return snapshot(job_id)


def rerun_job(job_id, *, internal=False):
    """Repeat database queries with the original inputs and reviewed mappings."""
    with LOCK:
        job = _load_locked(job_id)
        _read_only(job, internal)
        if job["status"] != "completed":
            raise ValueError("Only a completed collection can be rerun")
        job.update(status="running", progress="Querying selected databases again…", graph=None,
                   warnings=[], cancel=Event(), created_at=time(),
                   database_statuses={db: {"status": "pending", "completed": 0, "total": 0, "errors": 0}
                                      for db in job["databases"]})
        _persist_locked(job_id)
    POOL.submit(_network_job, job_id)
    return snapshot(job_id)


def cancel_job(job_id):
    with LOCK:
        job = _load_locked(job_id)
        _read_only(job, False)
        job["cancel"].set()
        if job["status"] in {"resolving", "running", "awaiting_selection"}:
            job.update(status="cancelled", progress="Cancelled")
            _persist_locked(job_id)
    return snapshot(job_id)


def recover():
    """Resume jobs that were queued or running when the server stopped."""
    try:
        stored_jobs = get_store().load_by_status(KIND, ACTIVE)
    except Exception:
        LOGGER.exception("Could not read unfinished collection jobs")
        return 0
    resumed = 0
    for stored in stored_jobs:
        job_id = stored["job_id"]
        stored.pop("expires_at", None)
        with LOCK:
            if job_id in JOBS:
                continue
            JOBS[job_id] = {**stored, "cancel": Event(), "resolver": DEFAULT_RESOLVER, "accessed_at": time(),
                            "progress": "Resumed after a server restart…"}
            _persist_locked(job_id)
        POOL.submit(_resolve_job if stored["status"] == "resolving" else _network_job, job_id)
        resumed += 1
    return resumed


def example_choices(resolution):
    """Deterministic mapping review for the example: first reviewed match, else skip."""
    choices = {}
    for row in resolution:
        if len(row["candidates"]) > 1:
            reviewed = [c for c in row["candidates"] if c.get("reviewed")]
            choices[row["input"]] = (reviewed or row["candidates"])[0]["id"]
    return choices


def ensure_example(resolver, species, *, tax_id="9606", databases=None, force=False, timeout=1800, search_type="batch"):
    """Build a permanent, read-only example result used by the tutorial.

    ``search_type`` selects the batch example (EXAMPLE_JOB_ID) or the PPI
    example (PPI_EXAMPLE_JOB_ID). Examples are pinned (never expire), cannot be
    rerun or cancelled through the API, and are rebuilt only when missing,
    failed, or when ``force`` is set.
    """
    job_id = PPI_EXAMPLE_JOB_ID if search_type == "ppi" else EXAMPLE_JOB_ID
    stored = get_store().load(KIND, job_id)
    if stored and not force and stored.get("status") in ACTIVE | {"completed", "awaiting_selection"}:
        if stored["status"] != "awaiting_selection":
            return stored
    else:
        with LOCK:
            JOBS.pop(job_id, None)
        create_job(EXAMPLE_IDENTIFIERS, tax_id, species, list(databases or EXAMPLE_DATABASES), "UniProtKB",
                   "induced", resolver, job_id=job_id, pinned=True,
                   pairs=PPI_EXAMPLE_PAIRS if search_type == "ppi" else None)
    deadline = time() + timeout
    while time() < deadline:
        job = snapshot(job_id)
        if job["status"] == "awaiting_selection":
            run_job(job_id, example_choices(job["resolution"]), internal=True)
        elif job["status"] not in ACTIVE:
            return job
        sleep(2)
    return snapshot(job_id)


def values(value):
    if isinstance(value, (list, tuple, set)):
        return sorted({clean(v) for v in value if clean(v)})
    return [v.strip() for v in re.split(r"[|;,]", clean(value)) if v.strip() and v.strip() != "-"]


def numeric(value):
    try:
        number = float(str(value).split(":")[-1])
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def canonical_key(value):
    """Normalize resolver endpoint labels without changing the displayed ID."""
    return clean(value).upper()


def endpoint_candidate(candidates):
    """Choose an endpoint only when UniProt provides an unambiguous primary record.

    STRING returns preferred gene symbols rather than UniProt accessions. A symbol
    commonly matches one reviewed record plus several unreviewed fragments, so
    requiring exactly one result drops otherwise valid STRING interactions.
    """
    if len(candidates) == 1:
        return candidates[0]
    reviewed = [candidate for candidate in candidates if candidate["reviewed"]]
    return reviewed[0] if len(reviewed) == 1 else None


def evidence(db, row, info):
    score_key = next((key for key in ("combined_score", "Interaction_Score_Intact", "Confidence_Score", "spoc_score") if numeric(row.get(key)) is not None), None)
    kind = "functional" if db in {"String", "Reactome", "Corum", "ComplexPortal"} else "predicted" if db in {"Predictomes", "HuMap"} else "direct"
    if db == "Signor" and row.get("Direct") is False:
        kind = "functional"
    if "predicted" in str(row.get("Complex_Type", "")).lower():
        kind = "predicted"
    if db == "BioGrid" and "genetic" in str(row.get("Interaction_Type", "")).lower():
        kind = "functional"
    return {"database": db, "type": kind, "score": numeric(row.get(score_key)), "score_name": score_key,
            "publications": sorted({value.removeprefix("pubmed:") for value in values(row.get("PubMed_Ids") or row.get("Publication_Identifiers_Raw"))}),
            "methods": values(row.get("Unique_Identification_Methods") or row.get("Interaction_Detection_Method") or info.get("Purification_Method") or row.get("Mechanism")),
            "interaction_type": clean(row.get("Interaction_Type")),
            "directed": bool(row.get("Directed")), "regulator": clean(row.get("Regulator")),
            "target": clean(row.get("Target")), "effect": clean(row.get("Effect")),
            "source_id": clean(row.get("SIGNOR_ID") or row.get("Complex_ID") or row.get("complex_id")),
            "scores": {key: numeric(row[key]) for key in ("combined_score", "Interaction_Score_Intact", "Confidence_Score", "spoc_score", "kirc_score", "experimental_score", "coexpression_score", "textmining_score", "database_score", "gene_neighbourhood_score", "gene_fusion_score", "phylogenetic_profile_score") if numeric(row.get(key)) is not None},
            "link": clean(row.get("Interactor_Link") or info.get("Database_Link"))}


def extract_rows(db, payload):
    if isinstance(payload, dict):
        return [], {}, payload.get("error")
    if not isinstance(payload, list) or not payload:
        return [], {}, None
    info = payload[0].get("info", {})
    rows = []
    for part in payload[1:]:
        # STRING neighbor-neighbor edges are deliberately excluded: one hop only.
        for key in ("Direct_Interactions", "Interactors", "Interactions"):
            rows.extend(part.get(key, []))
    return rows, info, info.get("Error")


def build_graph(seeds, records, canonical, mode, tax_id, species, unresolved):
    nodes = {key: {**candidate, "input": True, "unresolved": False} for key, candidate in seeds.items()}
    edges = {}
    evidence_seen = {}
    unknown_pairs = 0
    capped = False
    for db, seed, row, info in records:
        if clean(row.get("organism_tax_id")) and clean(row["organism_tax_id"]) != tax_id:
            continue
        a = clean(row.get("Interactor_A_UniProt") or row.get("Interactor_A"))
        b = clean(row.get("Interactor_B_UniProt") or row.get("Interactor_B"))
        ca, cb = canonical.get(canonical_key(a)), canonical.get(canonical_key(b))
        if not ca or not cb:
            unknown_pairs += 1
            continue
        a, b = ca["id"], cb["id"]
        if a == b or (a not in seeds and b not in seeds):
            continue
        if mode == "induced" and (a not in seeds or b not in seeds):
            continue
        key = tuple(sorted((a, b)))
        if key not in edges and len(edges) >= MAX_EDGES:
            capped = True
            continue
        for candidate in (ca, cb):
            nodes.setdefault(candidate["id"], {**candidate, "input": candidate["id"] in seeds, "unresolved": False})
        edge = edges.setdefault(key, {"id": f"e{len(edges)}", "source": key[0], "target": key[1], "expanded": a not in seeds or b not in seeds, "evidence": []})
        ev = evidence(db, row, info)
        signature = repr({field: value for field, value in ev.items() if field != "link"})
        seen = evidence_seen.setdefault(key, set())
        if signature not in seen:
            seen.add(signature)
            edge["evidence"].append(ev)
    for index, token in enumerate(unresolved):
        nodes[f"unknown:{index}"] = {"id": f"unknown:{index}", "gene": token, "gene_names": [], "species": species,
                                    "tax_id": tax_id, "input": True, "unresolved": True}
    return {"nodes": list(nodes.values()), "edges": list(edges.values()), "unmapped_evidence_rows": unknown_pairs, "truncated": capped}


def _source_slot(db):
    """Shared per-source semaphore: at most DB_CONCURRENCY parallel calls to one database."""
    with LOCK:
        return SOURCE_SLOTS.setdefault(db, BoundedSemaphore(DB_CONCURRENCY))


def query_source(resolver, db, seed, tax_id):
    with _source_slot(db):
        return resolver(db, seed, tax_id)


def _endpoint_labels(row):
    return [clean(row.get(f"Interactor_{side}_UniProt") or row.get(f"Interactor_{side}")) for side in ("A", "B")]


def _outside_label(row, canonical, seeds):
    """(seed, neighbor label) when exactly one endpoint is an input protein, else None."""
    labels = _endpoint_labels(row)
    inside = [canonical.get(canonical_key(label), {}).get("id") for label in labels]
    inside = [value if value in seeds else None for value in inside]
    if bool(inside[0]) == bool(inside[1]):
        return None
    return (inside[0], labels[1]) if inside[0] else (inside[1], labels[0])


def preselect_neighbors(records, canonical, seeds, keep):
    """Keep each input's `keep` best-supported neighbor labels before UniProt validation.

    Labels are ranked by the number of supporting databases, then rows. The
    caller keeps a generous buffer above the final limit, because one protein
    can appear under several labels (accession, gene symbol) before validation.
    """
    support = {}
    for db, _, row, _ in records:
        found = _outside_label(row, canonical, seeds)
        if found:
            entry = support.setdefault(found[0], {}).setdefault(found[1], [set(), 0])
            entry[0].add(db)
            entry[1] += 1
    allowed = set()
    for labels in support.values():
        ranked = sorted(labels.items(), key=lambda item: (-len(item[1][0]), -item[1][1], item[0]))
        allowed.update(label for label, _ in ranked[:keep])
    kept = [record for record in records
            if (found := _outside_label(record[2], canonical, seeds)) is None or found[1] in allowed]
    return kept, len(records) - len(kept)


def _edge_support(edge):
    evidence = edge["evidence"]
    return (len({ev["database"] for ev in evidence}),
            len({p for ev in evidence for p in ev.get("publications", [])}),
            len(evidence))


def limit_neighbors(graph, limit, scope="protein", pairs=()):
    """Keep the best-supported first neighbors per input protein or per PPI.

    Neighbors are ranked by supporting databases, then publications, then
    evidence records. Per PPI, neighbors shared by both proteins come first.
    Input proteins and edges among them are never removed.
    """
    seeds = {n["id"] for n in graph["nodes"] if n.get("input") and not n.get("unresolved")}
    support = {}
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if (a in seeds) == (b in seeds):
            continue
        seed, other = (a, b) if a in seeds else (b, a)
        support.setdefault(seed, {})[other] = _edge_support(edge)
    keep = set()
    if scope == "pair":
        empty = (0, 0, 0)
        for a, b in pairs:
            left, right = support.get(a, {}), support.get(b, {})
            def rank(node):
                both = node in left and node in right
                total = [x + y for x, y in zip(left.get(node, empty), right.get(node, empty))]
                return (not both, *(-value for value in total), node)
            keep.update(sorted(left.keys() | right.keys(), key=rank)[:limit])
    else:
        for neighbors in support.values():
            keep.update(sorted(neighbors, key=lambda node: (*(-value for value in neighbors[node]), node))[:limit])
    neighbors = {n["id"] for n in graph["nodes"] if not n.get("input")}
    hidden = neighbors - keep
    return {**graph, "nodes": [n for n in graph["nodes"] if n["id"] not in hidden],
            "edges": [e for e in graph["edges"] if e["source"] not in hidden and e["target"] not in hidden],
            "neighbor_limit": {"limit": limit, "scope": scope, "shown": len(neighbors - hidden), "hidden": len(hidden)}}


def annotate_pairs(graph, pairs, selections):
    """Report each requested PPI as known, unknown, unresolved or same protein."""
    edges = {frozenset((edge["source"], edge["target"])): edge for edge in graph["edges"]}
    queried = []
    for a_input, b_input in pairs:
        a, b = selections.get(a_input), selections.get(b_input)
        edge = edges.get(frozenset((a, b))) if a and b and a != b else None
        status = "unresolved" if not a or not b else "same_protein" if a == b else "known" if edge else "unknown"
        if edge:
            edge["queried"] = True
        queried.append({"inputs": [a_input, b_input], "source": a, "target": b, "status": status,
                        "edge": edge["id"] if edge else None})
    graph["queried_pairs"] = queried
    return graph


def _network_job(job_id):
    job = JOBS[job_id]
    try:
        seeds = {}
        canonical = {}
        unresolved = []
        for row in job["resolution"]:
            selected = job["selections"].get(row["input"])
            candidate = next((c for c in row["candidates"] if c["id"] == selected), None)
            if candidate:
                seeds[candidate["id"]] = candidate
                # Database adapters use a mixture of accessions and preferred
                # gene symbols. Index every validated alias up front so STRING
                # edges among collection inputs do not depend on a second,
                # potentially multi-hit gene lookup.
                for alias in (row["input"], candidate["id"], candidate["gene"], *candidate["gene_names"]):
                    canonical[canonical_key(alias)] = candidate
            else:
                unresolved.append(row["input"])
        warnings, records = [], []
        # Interleave databases so every selected source starts promptly instead
        # of filling the pool with one source's seeds first.
        tasks = [(db, seed) for seed in seeds for db in job["databases"]]
        database_statuses = {db: {"status": "running" if seeds else "completed", "completed": 0, "total": len(seeds), "errors": 0} for db in job["databases"]}
        patch(job_id, database_statuses=deepcopy(database_statuses))
        with ThreadPoolExecutor(max_workers=min(DB_WORKERS, len(tasks) or 1), thread_name_prefix="collection-db") as executor:
            futures = {executor.submit(query_source, job["resolver"], db, seed, job["tax_id"]): (db, seed) for db, seed in tasks}
            for completed_count, future in enumerate(as_completed(futures), 1):
                if job["cancel"].is_set():
                    return
                db, seed = futures[future]
                try:
                    rows, info, error = extract_rows(db, future.result())
                    if info.get("Overlap_Warning") and info["Overlap_Warning"] not in warnings:
                        warnings.append(info["Overlap_Warning"])
                    if error:
                        warnings.append(f"{db} / {seed}: {error}")
                        database_statuses[db]["errors"] += 1
                    if db == "String":
                        rows = [{**row, "Interactor_B_UniProt": seed} for row in rows]
                    if job["mode"] == "induced":
                        # Inputs and their aliases were already species-validated.
                        # Discard outside interactors before applying evidence limits
                        # so they neither consume capacity nor trigger UniProt lookups.
                        rows = [row for row in rows if all(
                            canonical.get(canonical_key(row.get(f"Interactor_{side}_UniProt") or row.get(f"Interactor_{side}")), {}).get("id") in seeds
                            for side in ("A", "B")
                        )]
                    room = max(0, MAX_EDGES * 4 - len(records))
                    records.extend((db, seed, row, info) for row in rows[:room])
                    if len(rows) > room and "Evidence row limit reached; analysis is partial." not in warnings:
                        warnings.append("Evidence row limit reached; analysis is partial.")
                except Exception as exc:
                    warnings.append(f"{db} / {seed}: {exc}")
                    database_statuses[db]["errors"] += 1
                database_statuses[db]["completed"] += 1
                if database_statuses[db]["completed"] >= database_statuses[db]["total"]:
                    database_statuses[db]["status"] = "failed" if database_statuses[db]["errors"] else "completed"
                patch(job_id, database_statuses=deepcopy(database_statuses),
                      progress=f"Queried {completed_count} / {len(tasks)} protein/database combinations", warnings=warnings.copy())
        if job["cancel"].is_set():
            return
        limit = job.get("neighbor_limit")
        if job["mode"] == "expanded" and limit:
            # Validate only plausible top neighbors; the exact cut follows after validation.
            records, dropped = preselect_neighbors(records, canonical, seeds, max(3 * limit, limit + 20))
            if dropped:
                LOGGER.info("Job %s: %d lower-ranked neighbor rows skipped before validation", job_id, dropped)
        if job["mode"] == "expanded":
            endpoint_ids = list(dict.fromkeys(clean(row.get(f"Interactor_{side}_UniProt") or row.get(f"Interactor_{side}")) for _, _, row, _ in records for side in ("A", "B")))
            missing = [token for token in endpoint_ids if token and canonical_key(token) not in canonical]
            if len(missing) > MAX_ENDPOINTS:
                warnings.append(f"Interactor validation capped at {MAX_ENDPOINTS:,} IDs; analysis is partial.")
                missing = missing[:MAX_ENDPOINTS]
            patch(job_id, progress=f"Validating {len(missing)} interactor IDs against the selected species…")
            matches, errors = resolve_tokens(missing, job["tax_id"], cancel=job["cancel"])
            for token, candidates in matches.items():
                candidate = endpoint_candidate(candidates)
                if candidate:
                    canonical[canonical_key(token)] = candidate
            if errors:
                warnings.append(f"Interactor ID lookup failed for {len(errors)} identifiers; affected evidence is excluded.")
        patch(job_id, progress="Building network from collected interactions…")
        if job["cancel"].is_set():
            return
        graph = build_graph(seeds, records, canonical, job["mode"], job["tax_id"], job["species"], unresolved)
        pairs = job.get("pairs") or []
        if job["mode"] == "expanded" and limit:
            resolved_pairs = [(job["selections"].get(a), job["selections"].get(b)) for a, b in pairs]
            graph = limit_neighbors(graph, limit, job.get("neighbor_scope") or "protein",
                                    [pair for pair in resolved_pairs if all(pair)])
        if pairs:
            annotate_pairs(graph, pairs, job["selections"])
        if graph["unmapped_evidence_rows"]:
            warnings.append(f"{graph['unmapped_evidence_rows']} evidence rows excluded because endpoint IDs could not be uniquely resolved.")
        graph["truncated"] = graph["truncated"] or any("analysis is partial" in warning for warning in warnings)
        if len(graph["edges"]) >= MAX_EDGES:
            warnings.append(f"Network capped at {MAX_EDGES:,} edges; analysis is partial.")
        with LOCK:
            if not job["cancel"].is_set():
                job.update(graph=graph, warnings=warnings, status="completed", progress="Analysis complete")
                _persist_locked(job_id)
    except Exception as exc:
        if not job["cancel"].is_set():
            patch(job_id, status="failed", progress=str(exc))
