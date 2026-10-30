"""Resolve, review and analyze up to 20 distinct gene/protein identifiers."""
import argparse
import json
from pathlib import Path
if __package__:
    from ._common import OUTPUT_DIR, client, progress, report_coverage
else:
    from _common import OUTPUT_DIR, client, progress, report_coverage

PROTEINS = ["P00533", "P62993", "Q07889", "P29353", "Q06124"]  # EGFR/GRB2/SOS1/SHC1/PTPN11


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, help="Headerless, single-column UTF-8 CSV/TSV/TXT")
    parser.add_argument("--tax-id", default="9606")
    parser.add_argument("--species-name", default="Homo sapiens")
    parser.add_argument("--mode", choices=["induced", "expanded"], default="induced")
    parser.add_argument("--input-type", choices=["auto", "UniProtKB", "Gene_Name", "Ensembl", "GeneID"], default="auto")
    parser.add_argument("--databases", nargs="+", default=["String", "IntAct", "BioGrid"])
    parser.add_argument("--job-id", help="Resume/review an existing job")
    parser.add_argument("--choices", type=Path, help='JSON object: {"original_input": "accession", "skip_this": null}')
    parser.add_argument("--cancel", action="store_true", help="Cancel --job-id and exit")
    parser.add_argument("--rerun", action="store_true", help="Rerun completed --job-id with its reviewed mappings")
    args = parser.parse_args(argv)
    if (args.cancel or args.rerun) and not args.job_id:
        parser.error("--cancel/--rerun requires --job-id")
    if args.cancel and args.rerun:
        parser.error("Choose either --cancel or --rerun")
    with client() as api:
        if args.cancel:
            print(api.cancel_collection(args.job_id))
            return
        if args.job_id:
            job = api.rerun_collection(args.job_id) if args.rerun else api.get_collection(args.job_id)
        else:
            ids = api.read_identifiers(args.file) if args.file else PROTEINS
            # Duplicate rows merge before the 20 distinct ID limit, as in the UI.
            # Species name should match --tax-id when using another organism.
            job = api.start_collection(ids, species_name=args.species_name, tax_id=args.tax_id,
                                       databases=args.databases, mode=args.mode, input_type=args.input_type)
        api.export_json(job, OUTPUT_DIR / "collection_job_started.json")
        print("Resume with --job-id", job["job_id"])
        job = api.wait_collection(job, until_review=True, on_progress=progress)
        if job["status"] == "awaiting_selection":
            api.export_json(job, OUTPUT_DIR / "collection_resolution.json")
            choices = json.loads(args.choices.read_text()) if args.choices else {}
            if not isinstance(choices, dict):
                parser.error("--choices must contain a JSON object")
            for row in job["resolution"]:
                print(row["input"], row["status"], [(c["id"], c["gene"]) for c in row["candidates"]])
            missing = [r["input"] for r in job["resolution"] if len(r["candidates"]) > 1 and r["input"] not in choices]
            if missing:
                print("Review collection_resolution.json; provide --job-id and --choices to resume:", missing)
                return
            # Single candidates are selected by the server; ambiguous inputs need
            # an explicit accession or null to skip. Forged choices are rejected.
            job = api.run_collection(job["job_id"], choices)
            job = api.wait_collection(job, on_progress=progress)
        report_coverage(job)
        api.export_json(job, OUTPUT_DIR / "collection_search.json")
        api.export_collection_csv(job, OUTPUT_DIR / "collection_search")
        analysis = api.collection_analysis(job["job_id"])
        print("Network:", analysis["statistics"]["nodes"], "nodes,", analysis["statistics"]["edges"], "edges")
        for format_name in ("json", "graphml", "sif", "cx"):
            api.export_network(analysis, OUTPUT_DIR / f"collection_network.{format_name}", format_name)
        # Expanded mode includes validated first neighbors. Unknown pair tools
        # operate on induced collections only; see collection_followups.py.


if __name__ == "__main__":
    main()
