"""Search one protein across selected interaction databases and export rows."""
from _common import OUTPUT_DIR, client


def main() -> None:
    api = client()
    result = api.single_search(
        "Q07889",
        input_type="UniProtKB",
        tax_id="9606",
        databases=["String", "IntAct", "BioGrid"],
    )

    searched = [next(iter(item)) for item in result[1].get("output", [])]
    print(f"Resolved input: {result[0]['Input']['UniProtId']}")
    print(f"Returned database sections: {', '.join(searched)}")

    json_path = api.export_json(result, OUTPUT_DIR / "single_search.json")
    csv_path = api.export_single_csv(result, OUTPUT_DIR / "single_search_interactions.csv")
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
