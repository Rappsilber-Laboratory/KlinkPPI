from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote


PROJECT_ROOT = Path(__file__).resolve().parents[3]
HUMAP_INDEX_PATH = PROJECT_ROOT / "Data" / "HuMap" / "humap3.sqlite3"
HUMAP_202305_SOURCE_PAIR_COUNT = 25_992_007


def ensure_humap_bundle(tax_id: str) -> dict:
    if tax_id != "9606":
        raise FileNotFoundError("hu.MAP 3.0 is human-only")
    if not HUMAP_INDEX_PATH.exists():
        raise FileNotFoundError(
            "hu.MAP index is not installed. Run: python scripts/update_extended_databases.py --source humap"
        )
    with sqlite3.connect(HUMAP_INDEX_PATH) as connection:
        metadata_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'"
        ).fetchone()
        if metadata_table:
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            pair_count = int(metadata.get("source_pair_count", 0))
        else:
            # Compatibility with indexes built before metadata was added.
            pair_count = HUMAP_202305_SOURCE_PAIR_COUNT
    return {
        "kind": "humap_sqlite_bundle",
        "tax_id": tax_id,
        "sqlite_path": str(HUMAP_INDEX_PATH),
        "pair_count": pair_count,
    }


def iter_humap_species_rows(bundle: dict):
    with sqlite3.connect(bundle["sqlite_path"]) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            """
            SELECT protein, partner, probability
            FROM interactions
            WHERE protein < partner
            """
        )
        for row in cursor:
            yield {
                "Database": "HuMap",
                "Interactor_A": row["protein"],
                "Interactor_B": row["partner"],
                "Taxid_A": "9606",
                "Taxid_B": "9606",
                "Confidence_Score": row["probability"],
                "Interaction_Type": "hu.MAP 3.0 ML-predicted interaction",
                "Evidence_Class": "predicted-interaction",
            }


def resolve_humap(input_id: str, tax_id: str):
    database_link = f"https://humap3.proteincomplexes.org/search?search={quote(input_id, safe='')}"
    result = [{"info": {
        "database": "hu.MAP 3.0",
        "Input_UniProt": input_id,
        "organism_tax_id": tax_id,
        "Database_Link": database_link,
        "Evidence_Class": "predicted-interaction",
        "License": "CC0",
    }}]
    if not HUMAP_INDEX_PATH.exists():
        result[0]["info"]["Error"] = (
            "hu.MAP index is not installed. Run: python scripts/update_extended_databases.py --source humap"
        )
        result.append({"Interactors": []})
        return result

    with sqlite3.connect(HUMAP_INDEX_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT partner, MAX(probability) AS probability
            FROM interactions
            WHERE protein = ?
            GROUP BY partner
            ORDER BY probability DESC
            """,
            (input_id,),
        ).fetchall()
    result.append({"Interactors": [
        {
            "Interactor_A": row["partner"],
            "Interactor_B": input_id,
            "Confidence_Score": row["probability"],
            "Interaction_Type": "hu.MAP 3.0 ML-predicted interaction",
            "Evidence_Class": "predicted-interaction",
            "Interactor_Link": database_link,
        }
        for row in rows
    ]})
    return result
