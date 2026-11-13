from __future__ import annotations

import csv
import io
from urllib.parse import quote

import requests


SIGNOR_URL = "https://signor.uniroma2.it/getData.php"
SIGNOR_COLUMNS = [
    "ENTITYA", "TYPEA", "IDA", "DATABASEA", "ENTITYB", "TYPEB", "IDB", "DATABASEB",
    "EFFECT", "MECHANISM", "RESIDUE", "SEQUENCE", "TAX_ID", "CELL_DATA", "TISSUE_DATA",
    "MODULATOR_COMPLEX", "TARGET_COMPLEX", "MODIFICATIONA", "MODASEQ", "MODIFICATIONB",
    "MODBSEQ", "PMID", "DIRECT", "NOTES", "ANNOTATOR", "SENTENCE", "SIGNOR_ID", "SCORE",
]


def resolve_signor(input_id: str, tax_id: str):
    database_link = f"https://signor.uniroma2.it/?q={quote(input_id, safe='')}"
    result = [{"info": {
        "database": "SIGNOR",
        "Input_UniProt": input_id,
        "organism_tax_id": tax_id,
        "Database_Link": database_link,
        "Evidence_Class": "directed-causal",
        "License": "CC BY 4.0",
    }}]
    try:
        response = requests.get(SIGNOR_URL, params={"organism": tax_id, "id": input_id}, timeout=45)
        response.raise_for_status()
    except requests.RequestException as exc:
        result[0]["info"]["Error"] = f"SIGNOR request failed: {exc}"
        result.append({"Interactors": []})
        return result

    interactors = []
    seen = set()
    reader = csv.reader(io.StringIO(response.text), delimiter="\t")
    for values in reader:
        if len(values) < 8:
            continue
        values += [""] * (len(SIGNOR_COLUMNS) - len(values))
        row = dict(zip(SIGNOR_COLUMNS, values))
        if row["TYPEA"].lower() != "protein" or row["TYPEB"].lower() != "protein":
            continue
        if row["IDA"] == input_id:
            partner_id, partner_name = row["IDB"], row["ENTITYB"]
        elif row["IDB"] == input_id:
            partner_id, partner_name = row["IDA"], row["ENTITYA"]
        else:
            continue
        key = row["SIGNOR_ID"] or (row["IDA"], row["IDB"], row["PMID"], row["MECHANISM"])
        if key in seen:
            continue
        seen.add(key)
        interactors.append({
            "Interactor_A": partner_id,
            "Interactor_B": input_id,
            "Interactor_Gene_Name": partner_name,
            "Regulator": row["IDA"],
            "Regulator_Gene_Name": row["ENTITYA"],
            "Target": row["IDB"],
            "Target_Gene_Name": row["ENTITYB"],
            "Directed": True,
            "Effect": row["EFFECT"],
            "Mechanism": row["MECHANISM"],
            "Residue": row["RESIDUE"],
            "Sequence": row["SEQUENCE"],
            "organism_tax_id": row["TAX_ID"] or tax_id,
            "Cell_Data": row["CELL_DATA"],
            "Tissue_Data": row["TISSUE_DATA"],
            "PubMed_Ids": [row["PMID"]] if row["PMID"] else [],
            "Direct": row["DIRECT"].lower() in {"t", "true", "1"},
            "SIGNOR_ID": row["SIGNOR_ID"],
            "Confidence_Score": row["SCORE"],
            "Interaction_Type": "directed causal interaction",
            "Evidence_Class": "directed-causal",
            "Interactor_Link": f"https://signor.uniroma2.it/relation_result.php?id={row['SIGNOR_ID']}",
        })
    result.append({"Interactors": interactors})
    return result
