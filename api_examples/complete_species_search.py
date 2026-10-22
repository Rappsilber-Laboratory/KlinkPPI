"""Run a complete-species job and download its server-generated export."""
from _common import OUTPUT_DIR, client


def main() -> None:
    api = client()
    job = api.species_search(
        tax_id="9606",
        databases=["String", "IntAct", "BioGrid", "ComplexPortal"],
        poll_interval=1.0,
    )

    print(f"Species job {job['job_id']}: {job['status']}")
    for database, status in job["database_statuses"].items():
        print(f"- {database}: {status['status']} ({status.get('pair_count', 0):,} pairs)")

    summary_path = api.export_json(job, OUTPUT_DIR / "complete_species_job.json")
    print(f"Wrote {summary_path}")

    if job.get("available_databases"):
        export_path = api.download_species(
            job,
            OUTPUT_DIR / "complete_species_interactions.parquet",
            output_format="parquet",
        )
        print(f"Wrote {export_path}")
    else:
        print("No completed databases were available for export.")


if __name__ == "__main__":
    main()
