from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

from app.services.species_index import get_species_by_tax_id


PROJECT_ROOT = Path(__file__).resolve().parents[3]
URL1 = "https://rest.uniprot.org/taxonomy"

HURI_PATH = PROJECT_ROOT / "Data" / "HuRI" / "HuRI.tsv"
HURI_UNIPROT_PATH = PROJECT_ROOT / "Data" / "HuRI" / "HuRI_uniprot.tsv"


def _clean_id(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    value = str(value).strip()
    return value or None


def _load_huri_rows() -> tuple[pd.DataFrame, dict[str, list[dict]], dict[str, list[dict]]]:
    if HURI_UNIPROT_PATH.exists():
        df = pd.read_csv(HURI_UNIPROT_PATH, sep="\t", dtype=str).fillna("")
        required = {
            "Interactor_A_Ensembl",
            "Interactor_B_Ensembl",
            "Interactor_A_UniProt",
            "Interactor_B_UniProt",
        }
        if required.issubset(df.columns):
            records = []
            for row in df.itertuples(index=False):
                record = {
                    "Interactor_A_Ensembl": _clean_id(row.Interactor_A_Ensembl),
                    "Interactor_B_Ensembl": _clean_id(row.Interactor_B_Ensembl),
                    "Interactor_A_UniProt": _clean_id(row.Interactor_A_UniProt),
                    "Interactor_B_UniProt": _clean_id(row.Interactor_B_UniProt),
                }
                records.append(record)
            return df, *_build_indexes(records)

    df = pd.read_csv(HURI_PATH, sep="\t", header=None, names=["interactorA", "interactorB"], dtype=str)
    records = []
    for row in df.itertuples(index=False):
        records.append(
            {
                "Interactor_A_Ensembl": _clean_id(row.interactorA),
                "Interactor_B_Ensembl": _clean_id(row.interactorB),
                "Interactor_A_UniProt": None,
                "Interactor_B_UniProt": None,
            }
        )
    return df, *_build_indexes(records)


def _build_indexes(records: list[dict]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    ensembl_index: dict[str, list[dict]] = defaultdict(list)
    uniprot_index: dict[str, list[dict]] = defaultdict(list)

    for record in records:
        ensembl_a = record["Interactor_A_Ensembl"]
        ensembl_b = record["Interactor_B_Ensembl"]
        uniprot_a = record["Interactor_A_UniProt"]
        uniprot_b = record["Interactor_B_UniProt"]

        if ensembl_a:
            ensembl_index[ensembl_a].append({**record, "query_side": "A"})
        if ensembl_b:
            ensembl_index[ensembl_b].append({**record, "query_side": "B"})
        if uniprot_a:
            uniprot_index[uniprot_a].append({**record, "query_side": "A"})
        if uniprot_b:
            uniprot_index[uniprot_b].append({**record, "query_side": "B"})

    return ensembl_index, uniprot_index


HURI_DF, HURI_ENSEMBL_INDEX, HURI_UNIPROT_INDEX = _load_huri_rows()


@lru_cache(maxsize=128)
def taxon_id_to_name(tax_id: str) -> str:
    species = get_species_by_tax_id(tax_id)
    if species is not None:
        return species["display_name"]

    tax_id_to_name_json = requests.get(f"{URL1}/{tax_id}", timeout=15).json()
    return tax_id_to_name_json["scientificName"]


def _format_interaction(record: dict, query_id: str) -> dict:
    if record["query_side"] == "A":
        partner_ensembl = record["Interactor_B_Ensembl"]
        partner_uniprot = record["Interactor_B_UniProt"]
        query_ensembl = record["Interactor_A_Ensembl"]
        query_uniprot = record["Interactor_A_UniProt"]
    else:
        partner_ensembl = record["Interactor_A_Ensembl"]
        partner_uniprot = record["Interactor_A_UniProt"]
        query_ensembl = record["Interactor_B_Ensembl"]
        query_uniprot = record["Interactor_B_UniProt"]

    display_partner = partner_uniprot or partner_ensembl
    display_query = query_uniprot or query_ensembl or query_id

    return {
        "Interactor_A": display_partner,
        "Interactor_B": display_query,
        "Interactor_A_UniProt": partner_uniprot,
        "Interactor_B_UniProt": query_uniprot,
        "Interactor_A_Ensembl": partner_ensembl,
        "Interactor_B_Ensembl": query_ensembl,
        "Interactor_Link": f"https://interactome-atlas.org/search/{partner_ensembl or display_partner}",
    }


def resolve_HuRI(input_id: str | None, tax_id: str, uniprot_id: str | None = None):
    database_query_id = input_id
    if not database_query_id and uniprot_id:
        mapped_records = HURI_UNIPROT_INDEX.get(uniprot_id, [])
        if mapped_records:
            first_record = mapped_records[0]
            database_query_id = (
                first_record["Interactor_A_Ensembl"]
                if first_record["query_side"] == "A"
                else first_record["Interactor_B_Ensembl"]
            )

    interactions = [
        {
            "info": {
                "database": "HuRI",
                "Input_UniProt": uniprot_id,
                "Input_Ensembl": database_query_id,
                "organism": taxon_id_to_name(tax_id),
                "Database_Link": f"https://interactome-atlas.org/search/{quote(database_query_id or uniprot_id or '', safe='')}",
            }
        }
    ]

    records = []
    query_id = uniprot_id or input_id
    if uniprot_id:
        records = HURI_UNIPROT_INDEX.get(uniprot_id, [])
    if not records and input_id:
        records = HURI_ENSEMBL_INDEX.get(input_id, [])
        query_id = input_id

    interactors = []
    seen = set()
    for record in records:
        interaction = _format_interaction(record, query_id)
        key = (
            interaction.get("Interactor_A_UniProt"),
            interaction.get("Interactor_A_Ensembl"),
            interaction.get("Interactor_B_UniProt"),
            interaction.get("Interactor_B_Ensembl"),
        )
        if key in seen:
            continue
        seen.add(key)
        interactors.append(interaction)

    interactions.append({"Interactors": interactors})
    return interactions
