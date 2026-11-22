"""Check specific protein pairs (PPI search): known pairs, pairs without evidence, MITAB export."""
import argparse
import json
from pathlib import Path
if __package__:
    from ._common import OUTPUT_DIR, client, progress, report_coverage
else:
    from _common import OUTPUT_DIR, client, progress, report_coverage

# Same pairs as the web app's PPI example: known (BRCA1–BARD1, PALB2–BRCA2, RAD51–RAD51C,
# FANCD2–FANCI, TP53–MDM2) and without evidence (RAD51C–DMC1, BARD1–XRCC3).
PAIRS = ["P38398-Q99728", "Q86YC2-P51587", "Q06609-O43502", "Q9BXW9-Q9NVI1", "P04637-Q00987",
         "O43502-Q14565", "Q99728-O43542"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", nargs="+", help="Pairs such as TP53-MDM2 (default: the web app's example)")
    parser.add_argument("--file", type=Path, help="Headerless UTF-8 file, one pair per line: A-B, or A<tab>B / A,B / A B")
    parser.add_argument("--tax-id", default="9606")
    parser.add_argument("--species-name", default="Homo sapiens")
    parser.add_argument("--mode", choices=["induced", "expanded"], default="induced")
    parser.add_argument("--neighbor-limit", type=int, help="Expanded mode: neighbors shown per protein or PPI (server default 10)")
    parser.add_argument("--neighbor-scope", choices=["protein", "pair"], default="protein")
    parser.add_argument("--input-type", choices=["auto", "UniProtKB", "Gene_Name", "Ensembl", "GeneID"], default="auto")
    parser.add_argument("--databases", nargs="+", default=["String", "IntAct", "BioGrid"])
    parser.add_argument("--job-id", help="Resume/review an existing PPI job (e.g. ppi-example)")
    parser.add_argument("--choices", type=Path, help='JSON object: {"original_input": "accession", "skip_this": null}')
    args = parser.parse_args(argv)
    with client() as api:
        if args.job_id:
            job = api.get_collection(args.job_id)
        else:
            pairs = api.read_pairs(args.file) if args.file else api.normalize_pairs(args.pairs or PAIRS)
            job = api.start_ppi(pairs, species_name=args.species_name, tax_id=args.tax_id, databases=args.databases,
                                input_type=args.input_type, mode=args.mode, neighbor_limit=args.neighbor_limit,
                                neighbor_scope=args.neighbor_scope)
        api.export_json(job, OUTPUT_DIR / "ppi_job_started.json")
        print("Resume with --job-id", job["job_id"])
        job = api.wait_collection(job, until_review=True, on_progress=progress)
        if job["status"] == "awaiting_selection":
            api.export_json(job, OUTPUT_DIR / "ppi_resolution.json")
            choices = json.loads(args.choices.read_text()) if args.choices else {}
            missing = [r["input"] for r in job["resolution"] if len(r["candidates"]) > 1 and r["input"] not in choices]
            if missing:
                print("Review ppi_resolution.json; provide --job-id and --choices to resume:", missing)
                return
            job = api.run_collection(job["job_id"], choices)
            job = api.wait_collection(job, on_progress=progress)
        report_coverage(job)
        api.export_json(job, OUTPUT_DIR / "ppi_search.json")
        edges = {edge["id"]: edge for edge in job["graph"]["edges"]}
        for pair in api.queried_pairs(job):
            edge = edges.get(pair["edge"])
            sources = sorted({ev["database"] for ev in edge["evidence"]}) if edge else []
            print(f"{'-'.join(pair['inputs']):30} {pair['status']:13} {', '.join(sources)}")
        # Requested pairs only, then the whole network; both use the same filters as the web app.
        api.download_collection_mitab(job["job_id"], OUTPUT_DIR / "ppi_requested_pairs.mitab.txt", queried_pairs_only=True)
        api.download_collection_mitab(job["job_id"], OUTPUT_DIR / "ppi_network.mitab.txt")
        print("MITAB written to", OUTPUT_DIR)
        # Pairs with status "unknown" accept the same follow-ups as batch search:
        # api.shared_go(job_id, source, target), api.align_pair(...), api.embed_pair(...).


if __name__ == "__main__":
    main()
