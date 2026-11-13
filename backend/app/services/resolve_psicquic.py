from __future__ import annotations

import re
from urllib.parse import quote

import requests


REQUEST_TIMEOUT = 45
PAGE_SIZE = 1000
PSICQUIC_SERVICES = {
    "Mint": "https://www.ebi.ac.uk/Tools/webservices/psicquic/mint/webservices/current/search",
}
DATABASE_LINKS = {
    "Reactome": "https://reactome.org/content/detail/interactor/{query}",
    "Mint": "https://mint.bio.uniroma2.it/",
}


def _tokens(value: str) -> list[str]:
    return [token.strip() for token in (value or "").split("|") if token.strip() and token != "-"]


def _uniprot_ids(primary: str, alternatives: str) -> list[str]:
    # MITAB alternative-ID columns contain aliases/secondary accessions for the
    # same participant, not additional participants. Prefer the primary column
    # and consult alternatives only when no primary UniProt accession exists.
    primary_tokens = _tokens(primary)
    candidate_tokens = primary_tokens if any(token.lower().startswith("uniprotkb:") for token in primary_tokens) else _tokens(alternatives)
    values: list[str] = []
    for token in candidate_tokens:
        if not token.lower().startswith("uniprotkb:"):
            continue
        value = token.split(":", 1)[1].split("(", 1)[0].strip()
        if value and value not in values:
            values.append(value)
    return values


def _gene_name(aliases: str, fallback: str | None = None) -> str | None:
    for token in _tokens(aliases):
        if "(gene name)" in token.lower() or "(display_short)" in token.lower() or "(shortlabel)" in token.lower():
            value = token.split(":", 1)[-1].split("(", 1)[0].strip()
            if value:
                return value
    return fallback


def _tax_id(value: str) -> str | None:
    match = re.search(r"taxid:(-?\d+)", value or "")
    return match.group(1) if match else None


def _pubmed_ids(value: str) -> list[str]:
    ids = []
    for token in _tokens(value):
        if token.lower().startswith("pubmed:"):
            ids.append(token.split(":", 1)[1].split("(", 1)[0])
    return ids


def _confidence(value: str) -> str | None:
    for token in _tokens(value):
        if ":" in token:
            return token.split(":", 1)[1]
    return None


def _fetch_rows(service_name: str, input_id: str) -> list[list[str]]:
    base_url = PSICQUIC_SERVICES[service_name]
    response = requests.get(
        f"{base_url}/interactor/{quote(input_id, safe='')}",
        params={"format": "tab25", "firstResult": 0, "maxResults": PAGE_SIZE},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return [line.split("\t") for line in response.text.splitlines() if line.strip()]


def resolve_psicquic(service_name: str, input_id: str, tax_id: str):
    database_link = DATABASE_LINKS[service_name].format(query=quote(input_id, safe=""))
    result = [{"info": {
        "database": service_name,
        "Input_UniProt": input_id,
        "organism_tax_id": tax_id,
        "Database_Link": database_link,
        "Evidence_Class": "pathway-derived/functional" if service_name == "Reactome" else "experimentally-curated",
        "Result_Limit": PAGE_SIZE,
        "Overlap_Warning": (
            "MINT records can also occur in IntAct/IMEx; matching evidence must not be counted twice."
            if service_name == "Mint" else None
        ),
    }}]

    try:
        rows = _fetch_rows(service_name, input_id)
    except (requests.RequestException, ValueError) as exc:
        result[0]["info"]["Error"] = f"{service_name} PSICQUIC request failed: {exc}"
        result.append({"Interactors": []})
        return result

    interactors: list[dict] = []
    by_partner: dict[str, dict] = {}
    for columns in rows:
        if len(columns) < 15:
            continue

        side_a = _uniprot_ids(columns[0], columns[2])
        side_b = _uniprot_ids(columns[1], columns[3])
        all_ids = side_a + [value for value in side_b if value not in side_a]
        partners = [value for value in all_ids if value != input_id]
        if input_id not in all_ids or not partners:
            continue

        for partner in partners:
            if partner in by_partner:
                existing = by_partner[partner]
                existing["PubMed_Ids"] = sorted(set(existing["PubMed_Ids"]) | set(_pubmed_ids(columns[8])))
                existing["Evidence_Record_Count"] += 1
                continue
            partner_side = "A" if partner in side_a else "B"
            aliases = columns[4] if partner_side == "A" else columns[5]
            partner_tax_id = _tax_id(columns[9] if partner_side == "A" else columns[10]) or tax_id
            interaction = {
                "Interactor_A": partner,
                "Interactor_B": input_id,
                "Interactor_Gene_Name": _gene_name(aliases),
                "organism_tax_id": partner_tax_id,
                "Interaction_Detection_Method": columns[6],
                "Publication_Identifiers_Raw": columns[8],
                "PubMed_Ids": _pubmed_ids(columns[8]),
                "Interaction_Type": columns[11],
                "Source_Database": columns[12],
                "Interaction_Identifiers": columns[13],
                "Confidence_Score": _confidence(columns[14]),
                "Evidence_Class": "pathway-derived/functional" if service_name == "Reactome" else "experimentally-curated",
                "Evidence_Record_Count": 1,
                "Interactor_Link": database_link,
            }
            by_partner[partner] = interaction
            interactors.append(interaction)

    result.append({"Interactors": interactors})
    return result


def resolve_reactome(input_id: str, tax_id: str):
    # Reactome's interactor pages are backed by its IntAct interactor overlay.
    # The Reactome PSICQUIC endpoint does not return that overlay consistently
    # (for example, it returns zero for P23818 while the Reactome page lists
    # mouse interactors). Use the same ContentService endpoint as that page.
    database_link = DATABASE_LINKS["Reactome"].format(query=quote(input_id, safe=""))
    result = [{"info": {
        "database": "Reactome",
        "Input_UniProt": input_id,
        "organism_tax_id": tax_id,
        "Database_Link": database_link,
        "Evidence_Class": "Reactome interactor overlay (IntAct evidence)",
        "Overlap_Warning": "Reactome interactor overlay evidence is supplied by IntAct and may duplicate the IntAct source.",
        "Evidence_Source": "IntAct via Reactome ContentService",
    }}]
    try:
        response = requests.get(
            f"https://reactome.org/ContentService/interactors/psicquic/molecule/IntAct/{quote(input_id, safe='')}/details",
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        result[0]["info"]["Error"] = f"Reactome interactor request failed: {exc}"
        result.append({"Interactors": []})
        return result

    entities = payload.get("entities") or []
    matching_entity = next((entity for entity in entities if entity.get("acc") == input_id), None)
    interactors = []
    if matching_entity:
        for partner in matching_entity.get("interactors", []):
            partner_id = partner.get("acc")
            if not partner_id or partner_id == input_id:
                continue
            interactors.append({
                "Interactor_A": partner_id,
                "Interactor_B": input_id,
                "Interactor_Gene_Name": partner.get("alias"),
                "organism_tax_id": tax_id,
                "Confidence_Score": partner.get("score"),
                "Evidence_Record_Count": partner.get("evidences"),
                "Evidence_Source": "IntAct",
                "Evidence_Class": "Reactome interactor overlay (IntAct evidence)",
                "Interactor_Link": partner.get("accURL") or database_link,
                "Evidence_Link": partner.get("evidencesURL"),
            })
    result.append({"Interactors": interactors})
    return result


def resolve_mint(input_id: str, tax_id: str):
    return resolve_psicquic("Mint", input_id, tax_id)
