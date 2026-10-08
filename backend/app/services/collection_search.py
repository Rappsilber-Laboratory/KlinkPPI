"""Bounded, cancellable collection searches with explicit ID disambiguation.

Jobs are local to this server process and expire after one hour. No source score
is treated as a probability or combined across incompatible database scales.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from threading import Event, Lock
from time import time
from uuid import uuid4
import math
import re

import requests

API = "https://rest.uniprot.org/uniprotkb"
MAX_INPUTS = 200
MAX_EDGES = 50000
MAX_ENDPOINTS = 10000
MAX_JOBS = 12
TTL = 3600
POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="collection-jobs")
JOBS = {}
LOCK = Lock()
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


def resolve_tokens(tokens, tax_id, input_type="auto", cancel=None):
    """Batch exact search, paginate all candidates and validate organism."""
    matches = {token: [] for token in tokens}
    errors = {}
    for offset in range(0, len(tokens), 25):
        if cancel and cancel.is_set():
            break
        chunk = tokens[offset:offset + 25]
        valid = [token for token in chunk if TOKEN.fullmatch(token)]
        for token in set(chunk) - set(valid):
            errors[token] = "Invalid identifier characters"
        if not valid:
            continue
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
    for token in tokens:
        matches[token] = sorted({c["id"]: c for c in matches[token]}.values(), key=lambda c: (not c["reviewed"], c["id"]))
    return matches, errors


def snapshot(job_id):
    with LOCK:
        job = JOBS[job_id]
        return deepcopy({k: v for k, v in job.items() if k not in {"cancel", "resolver"}})


def patch(job_id, **values):
    with LOCK:
        JOBS[job_id].update(values)


def create_job(tokens, tax_id, species, databases, input_type, mode, resolver):
    with LOCK:
        now = time()
        for key in list(JOBS):
            if now - JOBS[key]["created_at"] > TTL and JOBS[key]["status"] not in {"resolving", "running"}:
                del JOBS[key]
        if len(JOBS) >= MAX_JOBS:
            raise ValueError("Collection job capacity reached. Cancel unused jobs or retry after jobs expire.")
        job_id = uuid4().hex
        JOBS[job_id] = {"job_id": job_id, "created_at": now, "tax_id": tax_id, "species": species,
                        "databases": databases, "mode": mode, "status": "resolving", "progress": "Resolving identifiers…",
                        "tokens": tokens, "input_type": input_type, "cancel": Event(), "resolver": resolver,
                        "resolution": [], "warnings": [], "graph": None,
                        "database_statuses": {db: {"status": "pending", "completed": 0, "total": 0, "errors": 0} for db in databases}}
    POOL.submit(_resolve_job, job_id)
    return snapshot(job_id)


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


def run_job(job_id, choices):
    with LOCK:
        job = JOBS[job_id]
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
    POOL.submit(_network_job, job_id)
    return snapshot(job_id)


def cancel_job(job_id):
    with LOCK:
        job = JOBS[job_id]
        job["cancel"].set()
        if job["status"] in {"resolving", "running", "awaiting_selection"}:
            job.update(status="cancelled", progress="Cancelled")
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
        with ThreadPoolExecutor(max_workers=min(12, len(tasks) or 1), thread_name_prefix="collection-db") as executor:
            futures = {executor.submit(job["resolver"], db, seed, job["tax_id"]): (db, seed) for db, seed in tasks}
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
                    room = max(0, MAX_EDGES * 4 - len(records))
                    records.extend((db, seed, {**row, "Interactor_B_UniProt": seed} if db == "String" else row, info) for row in rows[:room])
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
        if job["cancel"].is_set():
            return
        graph = build_graph(seeds, records, canonical, job["mode"], job["tax_id"], job["species"], unresolved)
        if graph["unmapped_evidence_rows"]:
            warnings.append(f"{graph['unmapped_evidence_rows']} evidence rows excluded because endpoint IDs could not be uniquely resolved.")
        graph["truncated"] = graph["truncated"] or any("analysis is partial" in warning for warning in warnings)
        if len(graph["edges"]) >= MAX_EDGES:
            warnings.append(f"Network capped at {MAX_EDGES:,} edges; analysis is partial.")
        with LOCK:
            if not job["cancel"].is_set():
                job.update(graph=graph, warnings=warnings, status="completed", progress="Analysis complete")
    except Exception as exc:
        if not job["cancel"].is_set():
            patch(job_id, status="failed", progress=str(exc))
