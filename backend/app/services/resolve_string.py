from functools import lru_cache

import requests


URL = "https://version-12-0.string-db.org/api"
OUTPUT_FORMAT = "json"
METHOD1 = "get_string_ids"
METHOD2 = "network"
METHOD3 = "get_link"
URL1 = "https://rest.uniprot.org/taxonomy"
REQUEST_TIMEOUT = 15


def _error_response(message: str):
    return {"error": message, "interactions": [], "network_link": None}


def _request_json(method: str, url: str, **kwargs):
    response = requests.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=1024)
def taxon_id_to_name(tax_id: str):
    try:
        tax_id_to_name_json = _request_json("GET", f"{URL1}/{tax_id}")
        return tax_id_to_name_json.get("scientificName", str(tax_id))
    except (requests.RequestException, ValueError):
        return str(tax_id)


@lru_cache(maxsize=4096)
def _string_link(species: str, identifier: str):
    try:
        result = _request_json(
            "POST",
            f"{URL}/{OUTPUT_FORMAT}/{METHOD3}",
            data={"species": species, "identifiers": identifier},
        )
        if isinstance(result, list) and result and isinstance(result[0], str):
            return result[0]
        return result if isinstance(result, str) else None
    except (requests.RequestException, ValueError):
        return None


def get_string_interactions(input_id: str, tax_id: str):
    try:
        payload_conversion = {"species": tax_id, "identifiers": input_id}
        result_conversion_json = _request_json(
            "POST",
            f"{URL}/{OUTPUT_FORMAT}/{METHOD1}",
            data=payload_conversion,
        )
        if not result_conversion_json:
            return _error_response("Protein not found in STRING")

        string_id = result_conversion_json[0]["stringId"]
        database_link = _string_link(tax_id, string_id)

        result_interactions_json = _request_json(
            "POST",
            f"{URL}/{OUTPUT_FORMAT}/{METHOD2}",
            data={"identifiers": string_id},
        )
    except (requests.RequestException, ValueError, KeyError) as exc:
        return _error_response(f"STRING request failed: {exc}")

    interactions = []

    interactions.append(
        {
            "info": {
                "database": "STRING",
                "Input_UniProt": input_id,
                "organism": taxon_id_to_name(tax_id),
                "Database_Link": database_link,
            }
        }
    )

    direct_interactors = []
    indirect_interactors = []

    for data in result_interactions_json:
        ncbi_taxon_id = str(data.get("ncbiTaxonId", tax_id))
        organism_name = taxon_id_to_name(ncbi_taxon_id)

        if data.get("stringId_A") == string_id:
            interactor_a = data.get("preferredName_B", "-")
            interactor_b = data.get("preferredName_A", "-")
            direct_interactors.append(
                {
                    "Interactor_A": interactor_a,
                    "Interactor_B": interactor_b,
                    "Organism": organism_name,
                    "organism_tax_id": ncbi_taxon_id,
                    "combined_score": data.get("score"),
                    "gene_neighbourhood_score": data.get("nscore"),
                    "gene_fusion_score": data.get("fscore"),
                    "phylogenetic_profile_score": data.get("pscore"),
                    "experimental_score": data.get("escore"),
                    "coexpression_score": data.get("ascore"),
                    "textmining_score": data.get("tscore"),
                    "database_score": data.get("dscore"),
                    "Interactor_Link": _string_link(ncbi_taxon_id, interactor_a),
                }
            )
        elif data.get("stringId_B") == string_id:
            interactor_a = data.get("preferredName_A", "-")
            interactor_b = data.get("preferredName_B", "-")
            direct_interactors.append(
                {
                    "Interactor_A": interactor_a,
                    "Interactor_B": interactor_b,
                    "Organism": organism_name,
                    "organism_tax_id": ncbi_taxon_id,
                    "combined_score": data.get("score"),
                    "gene_neighbourhood_score": data.get("nscore"),
                    "gene_fusion_score": data.get("fscore"),
                    "phylogenetic_profile_score": data.get("pscore"),
                    "experimental_score": data.get("escore"),
                    "coexpression_score": data.get("ascore"),
                    "textmining_score": data.get("tscore"),
                    "database_score": data.get("dscore"),
                    "Interactor_Link": _string_link(ncbi_taxon_id, interactor_a),
                }
            )
        else:
            interactor_a = data.get("preferredName_A", "-")
            interactor_b = data.get("preferredName_B", "-")
            indirect_interactors.append(
                {
                    "Interactor_A": interactor_a,
                    "Interactor_B": interactor_b,
                    "Organism": organism_name,
                    "organism_tax_id": ncbi_taxon_id,
                    "combined_score": data.get("score"),
                    "gene_neighbourhood_score": data.get("nscore"),
                    "gene_fusion_score": data.get("fscore"),
                    "phylogenetic_profile_score": data.get("pscore"),
                    "experimental_score": data.get("escore"),
                    "coexpression_score": data.get("ascore"),
                    "textmining_score": data.get("tscore"),
                    "database_score": data.get("dscore"),
                    "Interactor_Link_A": _string_link(ncbi_taxon_id, interactor_a),
                    "Interactor_Link_B": _string_link(ncbi_taxon_id, interactor_b),
                }
            )

    interactions.append({"Direct_Interactions": direct_interactors})
    interactions.append({"Indirect_Interactions": indirect_interactors})

    return interactions
