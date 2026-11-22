"""UniProt protein name and Function section, as shown by "Show function" in the web app."""
import argparse
import textwrap
if __package__:
    from ._common import OUTPUT_DIR, client
else:
    from _common import OUTPUT_DIR, client


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accessions", nargs="*", default=["P04637"], help="UniProtKB accessions (default P04637)")
    parser.add_argument("--gene", help="Look up a gene name instead (best match, reviewed entries first)")
    parser.add_argument("--tax-id", default="9606", help="Species for --gene")
    args = parser.parse_args(argv)
    with client() as api:
        entries = [api.protein_function(gene=args.gene, tax_id=args.tax_id)] if args.gene else \
            [api.protein_function(accession) for accession in args.accessions]
        for entry in entries:
            print(f"\n{entry['accession']} · {entry['gene']} · {entry['protein_name']} ({entry['organism']})\n{entry['url']}")
            for paragraph in entry["function"] or [{"text": "No function annotation in UniProt.", "pubmed": []}]:
                print(textwrap.fill(paragraph["text"], 100))
        api.export_json(entries, OUTPUT_DIR / "protein_function.json")


if __name__ == "__main__":
    main()
