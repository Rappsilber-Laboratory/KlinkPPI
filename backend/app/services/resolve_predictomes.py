from __future__ import annotations

from collections import defaultdict
from urllib.parse import quote

import pandas as pd


PREDICTOMES_DF = pd.read_csv("../Data/Predictomes/Predictomes.csv")
PREDICTOMES_INDEX: dict[str, list[dict]] = defaultdict(list)


def _extract_predictomes_gene_names(complex_name: str) -> tuple[str | None, str | None]:
    parts = str(complex_name).split("__")
    if len(parts) < 2:
        return None, None

    def normalize(value: str) -> str | None:
        token = value.split("_", 1)[0].strip()
        return token or None

    return normalize(parts[0]), normalize(parts[1])

for row in PREDICTOMES_DF.itertuples(index=False):
    interaction = row.uniprot_ids.split(":")
    if len(interaction) != 2:
        continue

    uniprot_a = interaction[0].strip()
    uniprot_b = interaction[1].strip()
    gene_name_a, gene_name_b = _extract_predictomes_gene_names(row.complex_name)
    entry_ab = {
        "Interactor_A": uniprot_b,
        "Interactor_B": uniprot_a,
        "Interactor_Gene_Name": gene_name_b,
        "spoc_score": float(row.spoc_score),
        "kirc_score": float(row.kirc_score),
        "num_unique_contacts": int(row.num_unique_contacts),
        "Interactor_Link": f"https://predictomes.org/hp/?pid={uniprot_b}",
    }
    entry_ba = {
        "Interactor_A": uniprot_a,
        "Interactor_B": uniprot_b,
        "Interactor_Gene_Name": gene_name_a,
        "spoc_score": float(row.spoc_score),
        "kirc_score": float(row.kirc_score),
        "num_unique_contacts": int(row.num_unique_contacts),
        "Interactor_Link": f"https://predictomes.org/hp/?pid={uniprot_a}",
    }
    PREDICTOMES_INDEX[uniprot_a].append(entry_ab)
    PREDICTOMES_INDEX[uniprot_b].append(entry_ba)


def resolve_predictomes(input_id: str, tax_id: str):
    interactions = [
        {
            "info": {
                "database": "Predictomes",
                "Input_UniProt": input_id,
                "organism": "Human",
                "Database_Link": f"https://predictomes.org/hp/?pid={quote(input_id, safe='')}",
            }
        }
    ]

    interactors_list = sorted(
        [item for item in PREDICTOMES_INDEX.get(input_id, []) if item["spoc_score"] > 0.0],
        key=lambda item: item["spoc_score"],
        reverse=True,
    )

    if len(interactors_list) == 0:
        return "The input doesn't exist on Predictomes"

    interactions.append({"Interactors": interactors_list})
    return interactions
