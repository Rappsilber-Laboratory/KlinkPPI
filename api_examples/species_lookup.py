"""Discover species and source coverage before choosing a search workflow."""
if __package__:
    from ._common import OUTPUT_DIR, client
else:
    from _common import OUTPUT_DIR, client


def main():
    with client() as api:
        print(api.health())
        matches = api.search_species("human", limit=10)
        for species in matches:
            print(species["display_name"], species["tax_id"], species.get("supported_databases", []))
        api.export_json(matches, OUTPUT_DIR / "species_matches.json")
        # This is the same source/species coverage data used by the organism plots.
        api.export_json(api.supported_organisms(), OUTPUT_DIR / "organism_coverage.json")
        # Species availability does not imply support for complete-species exports.
        # Complete-species jobs report each requested source's actual status.


if __name__ == "__main__":
    main()
