"""Start, monitor, resume or cancel a potentially large complete-species job."""
import argparse
if __package__:
    from ._common import OUTPUT_DIR, client, progress, report_coverage
else:
    from _common import OUTPUT_DIR, client, progress, report_coverage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tax-id", default="9606")
    parser.add_argument("--databases", nargs="+", default=["IntAct", "BioGrid"])
    parser.add_argument("--job-id", help="Resume an existing job instead of starting another")
    parser.add_argument("--cancel", action="store_true", help="Cancel --job-id and exit")
    parser.add_argument("--max-wait", type=float, default=3600)
    args = parser.parse_args(argv)
    if args.cancel and not args.job_id:
        parser.error("--cancel requires --job-id")
    with client() as api:
        if args.cancel:
            print(api.cancel_species(args.job_id))
            return
        job = api.get_species(args.job_id) if args.job_id else api.start_species(tax_id=args.tax_id, databases=args.databases)
        # Persist the ID immediately so interrupted scripts can resume without
        # creating a second job. Polling timeouts do not cancel server jobs.
        api.export_json(job, OUTPUT_DIR / "species_job_started.json")
        print("Resume with --job-id", job["job_id"])
        job = api.wait_species(job, max_wait=args.max_wait, on_progress=progress)
        report_coverage(job)
        api.export_json(job, OUTPUT_DIR / "complete_species_job.json")
        if not job.get("available_databases"):
            print("No completed sources are available for export.")
            return
        # Downloads stream to disk; a failed transfer preserves any existing file.
        # databases=None selects only available/completed sources from this job.
        api.download_species(job, OUTPUT_DIR / "complete_species.parquet", "parquet")
        api.download_species(job, OUTPUT_DIR / "complete_species.mitab.txt", "mitab",
                             columns=["PubMed_Ids", "Interaction_Detection_Method"])


if __name__ == "__main__":
    main()
