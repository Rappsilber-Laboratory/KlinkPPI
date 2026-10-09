from __future__ import annotations

from urllib.parse import quote

import requests


HIPPIE_BASE_URL = "https://cbdm-01.zdv.uni-mainz.de/hippienew"


def resolve_hippie(input_id: str, tax_id: str):
    database_link = f"{HIPPIE_BASE_URL}/?q={quote(input_id, safe='')}"
    result = [{"info": {
        "database": "HIPPIE",
        "Input_UniProt": input_id,
        "organism_tax_id": tax_id,
        "Database_Link": database_link,
        "Evidence_Class": "integrated-confidence",
        "Overlap_Warning": "HIPPIE integrates BioGRID, IntAct and MINT; it is not independent support.",
    }}]
    try:
        response = requests.get(
            f"{HIPPIE_BASE_URL}/api/query/",
            params={"q": input_id, "show": "interactions"},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        result[0]["info"]["Error"] = f"HIPPIE request failed: {exc}"
        result.append({"Interactors": []})
        return result

    interactors = []
    for interaction in payload.get("interactions", []):
        partner = interaction.get("partner") or {}
        partner_id = partner.get("uniprot_id") or partner.get("name")
        if not partner_id:
            continue
        detail_url = interaction.get("detail_url") or ""
        interactors.append({
            "Interactor_A": partner_id,
            "Interactor_B": input_id,
            "Interactor_Gene_Name": partner.get("symbol") or partner.get("name"),
            "NCBI_Gene_ID": partner.get("gene_id"),
            "Confidence_Score": interaction.get("score"),
            "Source_Count": interaction.get("source_count"),
            "Experiment_Count": interaction.get("experiment_count"),
            "Interaction_Type": "integrated physical interaction",
            "Evidence_Class": "integrated-confidence",
            "Interactor_Link": f"{HIPPIE_BASE_URL}{detail_url}" if detail_url.startswith("/") else database_link,
        })
    result.append({"Interactors": interactors})
    return result
