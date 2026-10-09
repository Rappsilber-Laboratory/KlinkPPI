"""Find supported organisms before starting another search workflow."""
from _common import OUTPUT_DIR, client


def main() -> None:
    api = client()
    matches = api.search_species("human")

    print(f"Found {len(matches)} supported species matches:")
    for species in matches:
        databases = species.get("supported_databases") or species.get("databases") or []
        print(f"- {species['display_name']} (taxon {species['tax_id']}): {', '.join(databases)}")

    output = api.export_json(matches, OUTPUT_DIR / "species_matches.json")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
