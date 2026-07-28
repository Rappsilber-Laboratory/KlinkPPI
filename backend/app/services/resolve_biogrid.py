from functools import lru_cache
from urllib.parse import quote

import requests

from app.services.biogrid_index import get_biogrid_interactions
from app.services.species_index import get_species_by_tax_id


URL1 = "https://rest.uniprot.org/taxonomy"


@lru_cache(maxsize=1024)
def taxon_id_to_name(tax_id: str) -> str:
    species = get_species_by_tax_id(tax_id)
    if species is not None:
        return species["display_name"]

    tax_id_to_name_json = requests.get(f"{URL1}/{tax_id}").json()
    return tax_id_to_name_json["scientificName"]


def resolve_biogrid(input_id: str, tax_id: str):
    source_interactions = get_biogrid_interactions(input_id)
    database_link = f"https://thebiogrid.org/search.php?search={quote(input_id, safe='')}"

    interactions = []
    interactions.append(
        {
            "info": {
                "database": "BioGrid",
                "Input_UniProt": input_id,
                "organism": taxon_id_to_name(tax_id),
                "Database_Link": database_link,
            }
        }
    )

    interactors = []
    for interactor in source_interactions:
        interactors.append(
            {
                "Interactor_A": interactor["Interactor_A"],
                "Interactor_B": interactor["Interactor_B"],
                "Interactor_Gene_Name": interactor["Interactor_Gene_Name"] or None,
                "organism": taxon_id_to_name(interactor["organism_tax_id"]),
                "organism_tax_id": interactor["organism_tax_id"],
                "Interaction_Detection_Method": interactor["Interaction_Detection_Method"],
                "Interaction_Type": interactor["Interaction_Type"],
                "Confidence_Score": interactor["Confidence_Score"],
                "Interactor_Link": interactor["Interactor_Link"],
            }
        )

    interactions.append({"Interactors": interactors})
    return interactions
