"""Search a protein; export raw evidence, CSV, MITAB and Parquet."""
if __package__:
    from ._common import OUTPUT_DIR, client
else:
    from _common import OUTPUT_DIR, client


def main():
    with client() as api:
        # Use exact API source keys: String, IntAct, BioGrid, Corum, HuRI,
        # Predictomes, ComplexPortal, Reactome, Signor, Hippie, HuMap, Mint.
        # Omit databases (None) to query all sources supported by the species.
        result = api.single_search("Q07889", input_type="UniProtKB", tax_id="9606",
                                   databases=["String", "IntAct", "BioGrid"])
        print("Resolved input:", result[0]["Input"])
        for section in result[1]["output"]:
            for database, data in section.items():
                # A successful HTTP response can still contain a source failure.
                print(database, data if isinstance(data, str) else data[0].get("info", {}))
        api.export_json(result, OUTPUT_DIR / "single_search.json")
        api.export_single_csv(result, OUTPUT_DIR / "single_search.csv")
        # MITAB uses the web Download panel's common columns. Optional source
        # field keys enrich those columns; Parquet always includes all fields.
        api.download_single(result, OUTPUT_DIR / "single_search.mitab.txt", "mitab",
                            columns=["PubMed_Ids", "Interaction_Detection_Method"])
        api.download_single(result, OUTPUT_DIR / "single_search.parquet", "parquet")
        # For another input type, use Gene_Name, Ensembl or GeneID. For genes,
        # review candidates first (see gene_lookup.py) and use the chosen accession.


if __name__ == "__main__":
    main()
