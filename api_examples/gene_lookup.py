"""Review gene matches before searching; never silently select an ambiguous hit."""
import argparse
if __package__:
    from ._common import OUTPUT_DIR, client
else:
    from _common import OUTPUT_DIR, client


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gene", default="TP53")
    parser.add_argument("--tax-id", default="9606")
    parser.add_argument("--accession", help="Explicitly select one of the printed candidates and run a search")
    args = parser.parse_args(argv)
    with client() as api:
        lookup = api.search_genes(args.gene, tax_id=args.tax_id)
        for hit in lookup["candidates"]:
            print(hit["primary_accession"], hit["gene_names"], hit["protein_name"], hit["reviewed"])
        api.export_json(lookup, OUTPUT_DIR / "gene_candidates.json")
        if args.accession:
            if args.accession not in {hit["primary_accession"] for hit in lookup["candidates"]}:
                parser.error("--accession must match one of the returned candidates")
            result = api.single_search(args.accession, tax_id=args.tax_id, databases=["IntAct", "BioGrid"])
            api.export_json(result, OUTPUT_DIR / "gene_selected_search.json")
        else:
            print("Review the list, then rerun with --accession YOUR_CHOICE to search.")


if __name__ == "__main__":
    main()
