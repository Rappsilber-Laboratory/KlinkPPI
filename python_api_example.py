from klinkppi import KlinkPPIClient

client = KlinkPPIClient("http://127.0.0.1:8000")

# Single-protein search and tabular export.
single = client.single_search("Q07889", tax_id="9606", databases=["String", "IntAct"])
client.export_single_csv(single, "single_interactions.csv")

# Complete-species job and server-generated Parquet export.
species = client.species_search(tax_id="9606", databases=["String", "IntAct"])
client.download_species(species, "human_interactions.parquet")

# Collection job and node/edge CSV exports (no visualization).
collection = client.collection_search(
    ["P00533", "P62993", "Q07889"], species_name="Homo sapiens", tax_id="9606",
    databases=["String", "IntAct"], mode="induced",
)
client.export_collection_csv(collection, "collection_output")
