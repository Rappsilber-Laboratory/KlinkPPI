from __future__ import annotations

import pandas as pd
from urllib.parse import quote


CORUM_MAPPING_DF = pd.read_csv("../Data/Corum/corum_uniprotCorumMapping.txt", sep="\t")
CORUM_COMPLEXES_DF = pd.read_json("../Data/Corum/corum_allComplexes.json")


def _clean_value(value):
    if isinstance(value, list):
        return [_clean_value(item) for item in value]

    if isinstance(value, dict):
        return {key: _clean_value(item) for key, item in value.items()}

    if pd.isna(value):
        return None

    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass

    return value


def resolve_corum(input_id: str, tax_id: str):
    matches = CORUM_MAPPING_DF.loc[
        CORUM_MAPPING_DF["UniProtKB_accession_number"] == input_id, "corum_id"
    ]
    if matches.empty:
        return "this input does not exist in the Corum Database"

    corum_id = matches.iloc[0]
    complex_rows = CORUM_COMPLEXES_DF.loc[CORUM_COMPLEXES_DF["complex_id"] == corum_id]
    if complex_rows.empty:
        return "this input does not exist in the Corum Database"

    complex_row = complex_rows.iloc[0]
    purification_methods_name = [
        _clean_value(method.get("name"))
        for method in complex_row["purification_methods"]
        if method.get("name")
    ]

    interactions = [
        {
            "info": {
                "database": "CORUM",
                "Input_UniProt": input_id,
                "organism": _clean_value(complex_row["organism"]),
                "Database_Link": f"https://mips.helmholtz-muenchen.de/corum/?query={quote(input_id, safe='')}",
                "complex_name": _clean_value(complex_row["complex_name"]),
                "cell_line": _clean_value(complex_row["cell_line"]),
                "Purification_Method": purification_methods_name,
            }
        }
    ]

    interactors_list = []
    for subunit in complex_row["subunits"]:
        swissprot = subunit.get("swissprot") or {}
        interactor_id = _clean_value(swissprot.get("uniprot_id"))
        if interactor_id == input_id or not interactor_id:
            continue

        interactors_list.append(
            {
                "Interactor_A": interactor_id,
                "Interactor_B": input_id,
                "Interactor_Gene_Name": _clean_value(swissprot.get("gene_name")),
                "Organism": _clean_value(swissprot.get("organism")),
                "Interactor_Link": f"https://mips.helmholtz-muenchen.de/corum/?query={interactor_id}",
            }
        )

    interactions.append({"Interactors": interactors_list})
    return interactions
