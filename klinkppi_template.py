#!/usr/bin/env python3
"""KlinkPPI web-service template script.

A single, self-contained file (needs only Python 3.9+ and `requests`) showing
how to call several KlinkPPI web services and parse their output:

    1. service limits             GET  /limits
    2. species lookup             GET  /species/search
    3. single entry search        GET  /search                       -> TSV
    4. MITAB export               POST /mitab                        -> .mitab.txt
       UniProt function           GET  /uniprot/function             -> printed text
    5. batch search               POST /collection/jobs, GET /collection/jobs/{id},
                                  POST /collection/jobs/{id}/run      -> nodes/edges TSV
                                  GET  /collection/jobs/{id}/mitab    -> .mitab.txt
    6. filtered network statistics GET /collection/jobs/{id}/analysis
    7. pair follow-ups            GET  /collection/jobs/{id}/shared-go
                                  POST /collection/jobs/{id}/alignments (+ polling)
       optional PLM embeddings    POST /collection/jobs/{id}/embeddings (+ polling)
    8. PPI search                 POST /collection/ppi-jobs (then the job endpoints above)
                                  -> requested-pairs TSV and MITAB

Run everything with the built-in example data:

    pip install requests
    python klinkppi_template.py
    python klinkppi_template.py --steps single collection --ids TP53 MDM2 BRCA1 --species "Homo sapiens"
    python klinkppi_template.py --steps ppi --pairs TP53-MDM2 BRCA1-BARD1 --species "Homo sapiens"
    python klinkppi_template.py --steps collection --mode expanded --neighbor-limit 5

Every step is a small function; copy the one you need into your own pipeline.
The full help, including all endpoints, is at <server>/web-services.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import requests

# Filled in automatically when the script is downloaded from a KlinkPPI server.
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
BASE_URL = os.environ.get("KLINKPPI_API_URL", DEFAULT_BASE_URL).rstrip("/")
TIMEOUT = 120
EXAMPLE_PROTEIN = "P04637"  # TP53, human
EXAMPLE_IDS = ["P38398", "Q99728", "Q86YC2", "P51587", "Q06609", "O15315", "O43502", "O75771", "O43543", "O43542", "Q9BXW9", "Q9NVI1", "O15360", "Q14565"]  # human DNA-repair module
EXAMPLE_DATABASES = ["String", "IntAct", "BioGrid", "Corum", "Reactome", "Signor"]
# Same pairs as the web app's PPI example: known pairs and pairs without evidence.
EXAMPLE_PAIRS = ["P38398-Q99728", "Q86YC2-P51587", "Q06609-O43502", "Q9BXW9-Q9NVI1", "P04637-Q00987", "O43502-Q14565", "Q99728-O43542"]


# ---------------------------------------------------------------- helpers
def call(method, path, **kwargs):
    """Send one request and return parsed JSON; raise with the server's message."""
    response = requests.request(method, f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)
    if response.status_code == 429:
        wait = int(response.headers.get("Retry-After", "30"))
        print(f"  fair-use limit reached, waiting {wait}s ...")
        time.sleep(wait)
        return call(method, path, **kwargs)
    if not response.ok:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text[:500]
        raise RuntimeError(f"{method} {path} -> HTTP {response.status_code}: {detail}")
    return response.json()


def poll(path, done=("completed", "failed", "cancelled"), interval=2.0, max_wait=3600):
    """Poll a job/task URL until its status is in `done` and return it."""
    deadline = time.time() + max_wait
    while True:
        state = call("GET", path)
        print(f"  {state.get('status')}: {state.get('progress', '')}")
        if state.get("status") in done:
            return state
        if time.time() > deadline:
            raise TimeoutError(f"{path} did not finish within {max_wait}s")
        time.sleep(interval)


def write_tsv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {len(rows)} rows -> {path}")


# ---------------------------------------------------------------- services
def show_limits():
    limits = call("GET", "/limits")
    print(f"  up to {limits['collection_max_identifiers']} identifiers per batch search, "
          f"{limits['ppi_max_pairs']} pairs per PPI search; results kept {limits['result_retention_days']} days")
    return limits


def find_species(query):
    results = call("GET", "/species/search", params={"q": query, "limit": 5})["results"]
    for species in results:
        print(f"  {species['display_name']} (taxonomy {species['tax_id']}): {', '.join(species['supported_databases'])}")
    if not results:
        raise SystemExit(f"No supported species matches '{query}'")
    return results[0]


def single_search(identifier, tax_id, databases, out_dir):
    """Interactions of one protein in every selected source, flattened to rows."""
    params = {"id_value": identifier, "from_database": "UniProtKB", "tax_id": tax_id,
              "selected_databases": databases}
    result = call("GET", "/search", params=params)
    query = result[0]["Input"]
    rows = []
    for source in result[1]["output"]:
        (database, payload), = source.items()
        if isinstance(payload, str):           # e.g. "X does not support taxonomy ID ..."
            print(f"  {database}: {payload}")
            continue
        info = payload[0].get("info", {})
        if info.get("Error"):
            print(f"  {database}: {info['Error']}")
        count = 0
        for part in payload[1:]:
            for key in ("Direct_Interactions", "Interactors", "Interactions"):
                for row in part.get(key, []):
                    rows.append({"database": database, "query": query["UniProtId"], **row})
                    count += 1
        print(f"  {database}: {count} interaction rows")
    write_tsv(Path(out_dir) / f"{identifier}_single_search.tsv", rows)
    return result


def export_mitab(result, databases, out_dir):
    query = result[0]["Input"]
    body = {"results": result, "selected_databases": databases, "selected_columns": [],
            "uniprot_id": query["UniProtId"], "tax_id": query["TaxonomyId"]}
    response = requests.post(f"{BASE_URL}/mitab", json=body, timeout=TIMEOUT)
    response.raise_for_status()
    path = Path(out_dir) / f"{query['UniProtId']}.mitab.txt"
    path.write_bytes(response.content)
    print(f"  wrote PSI-MI TAB 2.8-compatible file -> {path}")


def protein_function(accession):
    """UniProt protein name and Function section (what "Show function" displays)."""
    entry = call("GET", "/uniprot/function", params={"accession": accession})
    print(f"  {entry['accession']} {entry['gene']}: {entry['protein_name']}")
    for paragraph in entry["function"][:1]:
        print(f"  {paragraph['text'][:300]}{'…' if len(paragraph['text']) > 300 else ''}")
    return entry


def collection_analysis(identifiers, species, databases, mode, out_dir, neighbor_limit=None):
    """Batch search: resolve IDs, review ambiguous mappings, run the network analysis."""
    job = call("POST", "/collection/jobs", json={
        "identifiers": identifiers, "species_name": species["display_name"], "tax_id": species["tax_id"],
        "selected_databases": databases, "input_type": "auto", "mode": mode, "neighbor_limit": neighbor_limit})
    print(f"  job {job['job_id']} - bookmarkable result: {BASE_URL.removesuffix('/api')}/results/{job['job_id']}")
    job = review_and_run(job)
    write_network_tsv(job, out_dir, "collection")
    return job


def split_pair(text):
    """ "A-B", "A,B", "A;B" or "A B"; a hyphen only when one split leaves two IDs (P04637-2-Q00987 works)."""
    for separator in ("\t", ",", ";", " "):
        if separator in text:
            return [part.strip() for part in text.split(separator) if part.strip() not in ("", "-")]
    options = [[text[:i], text[i + 1:]] for i, char in enumerate(text)
               if char == "-" and 0 < i < len(text) - 1 and not text[i + 1:].split("-")[0].isdigit()]
    if len(options) != 1:
        raise SystemExit(f"Cannot split '{text}' into two IDs; use a comma, e.g. HLA-A,HLA-B")
    return options[0]


def ppi_search(pairs, species, databases, mode, out_dir, neighbor_limit=None, neighbor_scope="protein"):
    """PPI search: check specific pairs; pairs are "A-B" strings or [A, B] lists."""
    pairs = [split_pair(pair) if isinstance(pair, str) else list(pair) for pair in pairs]
    job = call("POST", "/collection/ppi-jobs", json={
        "pairs": pairs, "species_name": species["display_name"], "tax_id": species["tax_id"],
        "selected_databases": databases, "input_type": "auto", "mode": mode,
        "neighbor_limit": neighbor_limit, "neighbor_scope": neighbor_scope})
    print(f"  job {job['job_id']} - bookmarkable result: {BASE_URL.removesuffix('/api')}/ppi-results/{job['job_id']}")
    job = review_and_run(job)
    edges = {edge["id"]: edge for edge in job["graph"]["edges"]}
    rows = []
    for pair in job["graph"]["queried_pairs"]:     # status: known | unknown | unresolved | same_protein
        edge = edges.get(pair["edge"])
        rows.append({"input_a": pair["inputs"][0], "input_b": pair["inputs"][1], "uniprot_a": pair["source"],
                     "uniprot_b": pair["target"], "status": pair["status"],
                     "databases": ";".join(sorted({ev["database"] for ev in edge["evidence"]})) if edge else "",
                     "publications": ";".join(sorted({p for ev in edge["evidence"] for p in ev.get("publications", [])})) if edge else ""})
        print(f"  {'-'.join(pair['inputs'])}: {pair['status']} {rows[-1]['databases']}")
    write_tsv(Path(out_dir) / f"ppi_{job['job_id']}_pairs.tsv", rows)
    write_network_tsv(job, out_dir, "ppi")
    collection_mitab(job["job_id"], out_dir, queried_pairs_only=True)
    return job


def collection_mitab(job_id, out_dir, queried_pairs_only=False, **filters):
    """PSI-MI TAB of a batch/PPI network; filters as for /analysis (e.g. evidence_type="direct")."""
    response = requests.get(f"{BASE_URL}/collection/jobs/{job_id}/mitab", timeout=TIMEOUT,
                            params={**filters, "queried_pairs_only": str(queried_pairs_only).lower()})
    response.raise_for_status()
    path = Path(out_dir) / f"{job_id}_{'requested_pairs' if queried_pairs_only else 'network'}.mitab.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    print(f"  wrote PSI-MI TAB -> {path}")
    return path


def review_and_run(job):
    """Wait for ID resolution, choose ambiguous mappings, run and wait for the network."""
    job_id = job["job_id"]
    job = poll(f"/collection/jobs/{job_id}", done=("awaiting_selection", "failed", "cancelled"))
    if job["status"] != "awaiting_selection":
        raise RuntimeError(job["progress"])
    choices = {}
    for row in job["resolution"]:
        if len(row["candidates"]) > 1:        # ambiguous: choose explicitly (here: first reviewed entry)
            best = next((c for c in row["candidates"] if c["reviewed"]), row["candidates"][0])
            choices[row["input"]] = best["id"]
            print(f"  {row['input']}: chose {best['id']} of {len(row['candidates'])} candidates")
        elif not row["candidates"]:
            print(f"  {row['input']}: unresolved ({row.get('error') or 'no match'})")
    call("POST", f"/collection/jobs/{job_id}/run", json={"choices": choices})
    job = poll(f"/collection/jobs/{job_id}")
    if job["status"] != "completed":
        raise RuntimeError(job["progress"])
    for warning in job.get("warnings", []):
        print(f"  coverage warning: {warning}")
    if job["graph"].get("neighbor_limit"):
        limit = job["graph"]["neighbor_limit"]
        print(f"  top {limit['limit']} neighbors per {limit['scope']}: {limit['shown']} shown, {limit['hidden']} hidden")
    return job


def write_network_tsv(job, out_dir, prefix):
    job_id, graph = job["job_id"], job["graph"]
    write_tsv(Path(out_dir) / f"{prefix}_{job_id}_nodes.tsv",
              [{key: node.get(key) for key in ("id", "gene", "input", "unresolved", "species")} for node in graph["nodes"]])
    write_tsv(Path(out_dir) / f"{prefix}_{job_id}_edges.tsv", [
        {"source": edge["source"], "target": edge["target"], "database": ev["database"], "evidence_type": ev["type"],
         "score_name": ev.get("score_name"), "score": ev.get("score"), "publications": ";".join(ev.get("publications", [])),
         "methods": ";".join(ev.get("methods", []))}
        for edge in graph["edges"] for ev in edge["evidence"]])


def network_statistics(job_id, evidence_type="all"):
    analysis = call("GET", f"/collection/jobs/{job_id}/analysis", params={"evidence_type": evidence_type})
    stats = analysis["statistics"]
    print(f"  {stats['nodes']} nodes, {stats['edges']} edges, components {stats['components']}, "
          f"mean clustering {stats['clustering']:.3f}")
    for hub in stats["hubs"][:5]:
        print(f"  hub {hub.get('gene') or hub['id']}: degree {hub['degree']}")
    return analysis


def unknown_pairs(job):
    """Resolved input pairs without interaction evidence (as in the web app)."""
    proteins = [n["id"] for n in job["graph"]["nodes"] if n.get("input") and not n.get("unresolved")]
    proteins = list(dict.fromkeys(proteins))
    known = {frozenset((e["source"], e["target"])) for e in job["graph"]["edges"]}
    return [(a, b) for i, a in enumerate(proteins) for b in proteins[i + 1:] if frozenset((a, b)) not in known]


def follow_up_pair(job_id, source, target, embedding_model=None):
    go = call("GET", f"/collection/jobs/{job_id}/shared-go", params={"source": source, "target": target})
    print(f"  shared GO terms {source}-{target}: {len(go['shared_terms'])}")
    task = call("POST", f"/collection/jobs/{job_id}/alignments", json={"source": source, "target": target})
    task = poll(f"/collection/jobs/{job_id}/alignments/{task['alignment_id']}", done=("completed", "failed"), interval=1)
    if task["status"] == "completed":
        result = task["result"]
        print(f"  global alignment: score {result['score']:.1f}, identity {result['identity_percent']:.1f}%")
    if embedding_model:
        task = call("POST", f"/collection/jobs/{job_id}/embeddings",
                    json={"source": source, "target": target, "models": [embedding_model]})
        task = poll(f"/collection/jobs/{job_id}/embeddings/{task['embedding_id']}", done=("completed", "failed"), interval=3)
        if task["status"] == "completed":
            key = f"{embedding_model}.mean.cosine_similarity"
            print(f"  {key}: {task['result']['scores'].get(key)}")


# ---------------------------------------------------------------- main
def main(argv=None):
    global BASE_URL
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default=BASE_URL, help=f"API URL (default {BASE_URL})")
    parser.add_argument("--steps", nargs="+", default=["limits", "single", "collection", "followups", "ppi"],
                        choices=["limits", "single", "collection", "followups", "ppi"])
    parser.add_argument("--protein", default=EXAMPLE_PROTEIN, help="UniProt accession for the single search")
    parser.add_argument("--ids", nargs="+", default=EXAMPLE_IDS, help="identifiers for the collection analysis")
    parser.add_argument("--species", default="Homo sapiens")
    parser.add_argument("--databases", nargs="+", default=EXAMPLE_DATABASES)
    parser.add_argument("--pairs", nargs="+", default=EXAMPLE_PAIRS, help="pairs for the PPI search, e.g. TP53-MDM2")
    parser.add_argument("--mode", choices=["induced", "expanded"], default="induced")
    parser.add_argument("--neighbor-limit", type=int, default=None, help="expanded mode: neighbors per protein/PPI (server default 10)")
    parser.add_argument("--neighbor-scope", choices=["protein", "pair"], default="protein", help="PPI search: count neighbors per protein or per PPI")
    parser.add_argument("--embedding-model", default=None, help="e.g. esm2-8m (optional, slower)")
    parser.add_argument("--out", default="klinkppi_output")
    args = parser.parse_args(argv)
    BASE_URL = args.base_url.rstrip("/")
    print(f"KlinkPPI API: {BASE_URL}")

    if "limits" in args.steps:
        print("\n[1] Service limits"); show_limits()
    print("\n[2] Species"); species = find_species(args.species)
    databases = [db for db in args.databases if db in species["supported_databases"]]
    if "single" in args.steps:
        print(f"\n[3] Single search for {args.protein}")
        result = single_search(args.protein, species["tax_id"], databases, args.out)
        print("\n[4] MITAB export and UniProt function"); export_mitab(result, databases, args.out)
        protein_function(result[0]["Input"]["UniProtId"])
    if {"collection", "followups"} & set(args.steps):
        print(f"\n[5] Batch search of {len(args.ids)} identifiers ({args.mode})")
        job = collection_analysis(args.ids, species, databases, args.mode, args.out, args.neighbor_limit)
        collection_mitab(job["job_id"], args.out)
        print("\n[6] Network statistics"); network_statistics(job["job_id"])
        pairs = unknown_pairs(job) if args.mode == "induced" else []
        if "followups" in args.steps and pairs:
            print(f"\n[7] Follow-up of the first of {len(pairs)} pairs without interaction evidence")
            follow_up_pair(job["job_id"], *pairs[0], embedding_model=args.embedding_model)
    if "ppi" in args.steps:
        print(f"\n[8] PPI search of {len(args.pairs)} pairs ({args.mode})")
        job = ppi_search(args.pairs, species, databases, args.mode, args.out, args.neighbor_limit, args.neighbor_scope)
        unknown = [p for p in job["graph"]["queried_pairs"] if p["status"] == "unknown"]
        if unknown:   # requested pairs without evidence accept the same follow-ups
            print(f"  follow-up of {'-'.join(unknown[0]['inputs'])} (no interaction evidence)")
            follow_up_pair(job["job_id"], unknown[0]["source"], unknown[0]["target"])
    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, requests.RequestException) as exc:
        sys.exit(f"Error: {exc}")
