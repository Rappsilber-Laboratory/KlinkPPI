from functools import lru_cache
import math
from urllib.parse import quote

import requests


URL = "https://www.ebi.ac.uk/intact/ws"
METHOD1 = "interactor/findInteractor/body"
METHOD3 = "interaction/findInteractions"
METHOD2 = "interaction/countInteractionResult"
URL1 = "https://rest.uniprot.org/taxonomy"
REQUEST_TIMEOUT = 20
PAGE_SIZE = 100


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


def resolve_intact(input_id: str, tax_id: str):
    try:
        result_conversion_json = _request_json(
            "POST",
            f"{URL}/{METHOD1}",
            json={"page": 0, "pageSize": 10, "query": input_id},
        )

        intact_id = ""
        for data in result_conversion_json.get("content", []):
            if data.get("interactorPreferredIdentifier") == input_id:
                intact_id = data.get("interactorAc", "")
                break

        if not intact_id:
            return _error_response("Protein not found in IntAct")

        count_payload = {
            "query": "*",
            "batchSearch": False,
            "advancedSearch": False,
            "intraSpeciesFilter": False,
            "interactorSpeciesFilter": [],
            "interactorTypesFilter": [],
            "interactionDetectionMethodsFilter": [],
            "participantDetectionMethodsFilter": [],
            "interactionTypesFilter": [],
            "interactionHostOrganismsFilter": [],
            "negativeFilter": "POSITIVE_ONLY",
            "mutationFilter": False,
            "expansionFilter": False,
            "minMIScore": 0,
            "maxMIScore": 1,
            "binaryInteractionIds": None,
            "interactorAcs": None,
        }
        result_num_interactions_json = _request_json(
            "POST",
            f"{URL}/{METHOD2}/{intact_id}",
            json=count_payload,
        )

        all_interactions = []
        iterations = math.ceil(int(result_num_interactions_json) / PAGE_SIZE)
        for page in range(iterations):
            result_interactions = _request_json(
                "GET",
                f"{URL}/{METHOD3}/{intact_id}",
                params={"page": page, "size": PAGE_SIZE, "sort": []},
            )
            all_interactions.extend(result_interactions.get("content", []))
    except (requests.RequestException, ValueError, TypeError) as exc:
        return _error_response(f"IntAct request failed: {exc}")

    all_interactions_refined = []
    for data in all_interactions:
        if data.get("uniqueIdA") == data.get("uniqueIdB"):
            continue
        all_interactions_refined.append(data)

    all_interactions_more_refined = []
    for data in all_interactions_refined:
        unique_id_a = data.get("uniqueIdA")
        unique_id_b = data.get("uniqueIdB")
        if unique_id_a and unique_id_b and unique_id_b < unique_id_a:
            data["uniqueIdA"] = unique_id_b
            data["uniqueIdB"] = unique_id_a
        all_interactions_more_refined.append(data)

    raw_response_data = {}
    for data in all_interactions_more_refined:
        unique_id_a = data.get("uniqueIdA")
        unique_id_b = data.get("uniqueIdB")
        if not unique_id_a or not unique_id_b:
            continue

        key = (unique_id_a, unique_id_b)
        if key not in raw_response_data:
            confidence_values = data.get("confidenceValues") or [""]
            raw_response_data[key] = {
                "num_interactions": 0,
                "identification_method": set(),
                "publication_id": set(),
                "feature_count": [],
                "confidence_value": confidence_values[0],
                "moleculeA": data.get("moleculeA", "-"),
                "TaxIdA": data.get("taxIdA", tax_id),
                "moleculeB": data.get("moleculeB", "-"),
                "TaxIdB": data.get("taxIdB", tax_id),
            }

        raw_response_data[key]["num_interactions"] += 1
        if data.get("detectionMethod"):
            raw_response_data[key]["identification_method"].add(data["detectionMethod"])
        if data.get("publicationPubmedIdentifier"):
            raw_response_data[key]["publication_id"].add(data["publicationPubmedIdentifier"])
        if data.get("featureCount") is not None:
            raw_response_data[key]["feature_count"].append(data["featureCount"])

    interactions = []
    interactions.append(
        {
            "info": {
                "database": "IntAct",
                "Input_Uniprot": input_id,
                "organism": taxon_id_to_name(tax_id),
                "Database_Link": f"https://www.ebi.ac.uk/intact/search?query={quote(input_id, safe='')}",
            }
        }
    )
    interactors = []

    for key, record in raw_response_data.items():
        confidence_value = record["confidence_value"]
        score = confidence_value[15:] if len(confidence_value) > 15 else confidence_value
        feature_counts = record["feature_count"] or [0]

        if key[0] == input_id:
            interactors.append(
                {
                    "Interactor_A": key[1],
                    "Interactor_B": key[0],
                    "Interactor_Gene_Name": record["moleculeB"],
                    "organism": taxon_id_to_name(str(record["TaxIdB"])),
                    "organism_tax_id": str(record["TaxIdB"]),
                    "Num_Interaction_IntAct": record["num_interactions"],
                    "Minimum_feature_count": min(feature_counts),
                    "Maximum_feature_count": max(feature_counts),
                    "Interaction_Score_Intact": score,
                    "Unique_Identification_Methods": sorted(record["identification_method"]),
                    "PubMed_Ids": sorted(record["publication_id"]),
                    "Interactor_Link": f"https://www.ebi.ac.uk/intact/search?query={key[1]}",
                }
            )
        if key[1] == input_id:
            interactors.append(
                {
                    "Interactor_A": key[0],
                    "Interactor_B": key[1],
                    "Interactor_Gene_Name": record["moleculeA"],
                    "organism": taxon_id_to_name(str(record["TaxIdA"])),
                    "organism_tax_id": str(record["TaxIdA"]),
                    "Num_Interaction_IntAct": record["num_interactions"],
                    "Minimum_feature_count": min(feature_counts),
                    "Maximum_feature_count": max(feature_counts),
                    "Interaction_Score_Intact": score,
                    "Unique_Identification_Methods": sorted(record["identification_method"]),
                    "PubMed_Ids": sorted(record["publication_id"]),
                    "Interactor_Link": f"https://www.ebi.ac.uk/intact/search?query={key[0]}",
                }
            )

    interactions.append({"Interactions": interactors})
    return interactions
