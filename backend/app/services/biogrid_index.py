from __future__ import annotations

import csv
from pathlib import Path
import sqlite3
import threading


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BIOGRID_SOURCE_PATH = PROJECT_ROOT / "Data" / "BioGrid" / "BIOGRID-ALL-5.0.258.mitab.txt"
BIOGRID_INDEX_PATH = PROJECT_ROOT / "Data" / "BioGrid" / "BIOGRID-ALL-5.0.258.sqlite3"
BIOGRID_INDEX_SCHEMA_VERSION = "3"

_INDEX_BUILD_LOCK = threading.Lock()


def _extract_first_matching_alt_id(raw_value: str, prefix: str) -> str:
    for alt_id in (raw_value or "").split("|"):
        if alt_id.startswith(prefix):
            return alt_id.split(":", 1)[1]
    return ""


def _extract_tax_id(raw_value: str) -> str:
    if not raw_value:
        return ""
    return raw_value.split(":", 1)[1]


def _extract_detection_method(raw_value: str) -> str:
    if "(" in raw_value and raw_value.endswith(")"):
        return raw_value.split("(", 1)[1][:-1]
    return raw_value


def _extract_interaction_type(raw_value: str) -> str:
    if "(" in raw_value and raw_value.endswith(")"):
        return raw_value.split("(", 1)[1][:-1]
    return raw_value


def _extract_confidence_score(raw_value: str) -> str:
    if ":" in raw_value and raw_value != "-":
        return raw_value.split(":", 1)[1]
    return raw_value


def _extract_gene_name(alt_ids: str, aliases: str) -> str:
    for alt_id in (alt_ids or "").split("|"):
        if not alt_id.startswith("entrez gene/locuslink:"):
            continue

        gene_name = alt_id.split(":", 1)[1].strip()
        if gene_name and not gene_name.isdigit():
            return gene_name

    for alias in (aliases or "").split("|"):
        if ":" not in alias or "(gene name)" not in alias:
            continue

        gene_name = alias.split(":", 1)[1].split("(", 1)[0].strip()
        if gene_name:
            return gene_name

    return ""


def _index_is_current() -> bool:
    if not BIOGRID_INDEX_PATH.exists():
        return False
    if BIOGRID_INDEX_PATH.stat().st_mtime < BIOGRID_SOURCE_PATH.stat().st_mtime:
        return False

    try:
        connection = sqlite3.connect(BIOGRID_INDEX_PATH)
        try:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = ?",
                ("schema_version",),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return False

    return row is not None and row[0] == BIOGRID_INDEX_SCHEMA_VERSION


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS interactions;
        DROP TABLE IF EXISTS metadata;

        CREATE TABLE interactions (
            query_uniprot TEXT NOT NULL,
            interactor_a TEXT NOT NULL,
            interactor_b TEXT NOT NULL,
            interactor_gene_name TEXT NOT NULL,
            organism_tax_id TEXT NOT NULL,
            interaction_detection_method TEXT NOT NULL,
            interaction_type TEXT NOT NULL,
            confidence_score TEXT NOT NULL,
            interactor_biogrid_id TEXT NOT NULL
        );

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def _flush_batch(connection: sqlite3.Connection, batch: list[tuple[str, ...]]) -> None:
    if not batch:
        return
    connection.executemany(
        """
        INSERT INTO interactions (
            query_uniprot,
            interactor_a,
            interactor_b,
            interactor_gene_name,
            organism_tax_id,
            interaction_detection_method,
            interaction_type,
            confidence_score,
            interactor_biogrid_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        batch,
    )
    batch.clear()


def build_biogrid_index() -> None:
    BIOGRID_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_index_path = BIOGRID_INDEX_PATH.with_suffix(".sqlite3.tmp")

    if temp_index_path.exists():
        temp_index_path.unlink()

    connection = sqlite3.connect(temp_index_path)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            PRAGMA temp_store = MEMORY;
            PRAGMA cache_size = -200000;
            """
        )
        _create_schema(connection)
        batch: list[tuple[str, ...]] = []

        with BIOGRID_SOURCE_PATH.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")

            for row in reader:
                uniprot_a = _extract_first_matching_alt_id(
                    row["Alt IDs Interactor A"], "uniprot/swiss-prot:"
                )
                uniprot_b = _extract_first_matching_alt_id(
                    row["Alt IDs Interactor B"], "uniprot/swiss-prot:"
                )

                if not uniprot_a or not uniprot_b:
                    continue

                biogrid_id_a = _extract_first_matching_alt_id(
                    row["Alt IDs Interactor A"], "biogrid:"
                )
                biogrid_id_b = _extract_first_matching_alt_id(
                    row["Alt IDs Interactor B"], "biogrid:"
                )
                tax_id_a = _extract_tax_id(row["Taxid Interactor A"])
                tax_id_b = _extract_tax_id(row["Taxid Interactor B"])
                detection_method = _extract_detection_method(
                    row["Interaction Detection Method"]
                )
                interaction_type = _extract_interaction_type(row["Interaction Types"])
                confidence_score = _extract_confidence_score(row["Confidence Values"])
                gene_name_a = _extract_gene_name(
                    row["Alt IDs Interactor A"], row["Aliases Interactor A"]
                )
                gene_name_b = _extract_gene_name(
                    row["Alt IDs Interactor B"], row["Aliases Interactor B"]
                )

                batch.append(
                    (
                        uniprot_a,
                        uniprot_b,
                        uniprot_a,
                        gene_name_b,
                        tax_id_b,
                        detection_method,
                        interaction_type,
                        confidence_score,
                        biogrid_id_b,
                    )
                )
                batch.append(
                    (
                        uniprot_b,
                        uniprot_a,
                        uniprot_b,
                        gene_name_a,
                        tax_id_a,
                        detection_method,
                        interaction_type,
                        confidence_score,
                        biogrid_id_a,
                    )
                )

                if len(batch) >= 10000:
                    _flush_batch(connection, batch)

        _flush_batch(connection, batch)
        connection.execute(
            "CREATE INDEX idx_interactions_query_uniprot ON interactions (query_uniprot)"
        )
        connection.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            ("source_mtime", str(BIOGRID_SOURCE_PATH.stat().st_mtime)),
        )
        connection.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            ("schema_version", BIOGRID_INDEX_SCHEMA_VERSION),
        )
        connection.commit()
    finally:
        connection.close()

    temp_index_path.replace(BIOGRID_INDEX_PATH)


def ensure_biogrid_index() -> Path:
    if _index_is_current():
        return BIOGRID_INDEX_PATH

    with _INDEX_BUILD_LOCK:
        if _index_is_current():
            return BIOGRID_INDEX_PATH
        build_biogrid_index()
        return BIOGRID_INDEX_PATH


def get_biogrid_interactions(input_id: str) -> list[dict]:
    index_path = ensure_biogrid_index()
    connection = sqlite3.connect(index_path)
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(
            """
            SELECT
                interactor_a,
                interactor_b,
                interactor_gene_name,
                organism_tax_id,
                interaction_detection_method,
                interaction_type,
                confidence_score,
                interactor_biogrid_id
            FROM interactions
            WHERE query_uniprot = ?
            """,
            (input_id,),
        ).fetchall()
    finally:
        connection.close()

    interactions = []
    for row in rows:
        interactions.append(
            {
                "Interactor_A": row["interactor_a"],
                "Interactor_B": row["interactor_b"],
                "Interactor_Gene_Name": row["interactor_gene_name"],
                "organism_tax_id": row["organism_tax_id"],
                "Interaction_Detection_Method": row["interaction_detection_method"],
                "Interaction_Type": row["interaction_type"],
                "Confidence_Score": row["confidence_score"],
                "Interactor_Link": f"https://thebiogrid.org/{row['interactor_biogrid_id']}/table.html",
            }
        )

    return interactions
