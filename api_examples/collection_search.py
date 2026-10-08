"""Create a collection interaction network and export its data without plotting."""
from _common import OUTPUT_DIR, client


PROTEINS = [
    "P00533",  # EGFR
    "P62993",  # GRB2
    "Q07889",  # SOS1
    "P29353",  # SHC1
    "Q06124",  # PTPN11
]


def main() -> None:
    api = client()
    job = api.collection_search(
        PROTEINS,
        species_name="Homo sapiens",
        tax_id="9606",
        databases=["String", "IntAct", "BioGrid"],
        input_type="UniProtKB",
        mode="induced",  # Use "expanded" to include first neighbors.
        # choices={"AMBIGUOUS_INPUT": "CHOSEN_UNIPROT_ACCESSION"},
        poll_interval=1.0,
    )

    graph = job["graph"]
    print(f"Collection job {job['job_id']}: {job['status']}")
    print(f"Network: {len(graph['nodes']):,} nodes and {len(graph['edges']):,} edges")
    for database, status in job.get("database_statuses", {}).items():
        print(f"- {database}: {status['status']} ({status['completed']}/{status['total']} queries)")

    json_path = api.export_json(job, OUTPUT_DIR / "collection_search.json")
    csv_directory = api.export_collection_csv(job, OUTPUT_DIR / "collection_search")
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_directory / 'nodes.csv'}")
    print(f"Wrote {csv_directory / 'edges.csv'}")


if __name__ == "__main__":
    main()
