from __future__ import annotations

import csv
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
import threading
from typing import Iterator, Optional
from uuid import uuid4

import pandas as pd

from app.services.resolve_corum import CORUM_COMPLEXES_DF
from app.services.resolve_huri import HURI_DF
from app.services.species_ppi_remote import (
    SpeciesJobCancelled,
    SpeciesRemoteDataNotFound,
    ensure_intact_species_bundle,
    ensure_string_species_bundle,
)
from app.services.species_index import get_species_by_tax_id, get_supported_databases


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BIOGRID_SOURCE_PATH = PROJECT_ROOT / "Data" / "BioGrid" / "BIOGRID-ALL-5.0.258.mitab.txt"
PREDICTOMES_SOURCE_PATH = PROJECT_ROOT / "Data" / "Predictomes" / "Predictomes.csv"

SUPPORTED_COMPLETE_SPECIES_DATABASES = {"BioGrid", "Corum", "Predictomes", "HuRI", "String", "IntAct"}

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()

PREDICTOMES_DF = pd.read_csv(PREDICTOMES_SOURCE_PATH)


CORUM_SPECIES_BY_TAX_ID = {
    "9606": {"complex_organisms": {"Human", "Mammalia"}, "subunit_organism": "Homo sapiens (Human)"},
    "10090": {"complex_organisms": {"Mouse", "Mammalia"}, "subunit_organism": "Mus musculus (Mouse)"},
    "10116": {"complex_organisms": {"Rat", "Mammalia"}, "subunit_organism": "Rattus norvegicus (Rat)"},
    "9913": {"complex_organisms": {"Bovine", "Mammalia"}, "subunit_organism": "Bos taurus (Bovine)"},
    "9823": {"complex_organisms": {"Pig", "Mammalia"}, "subunit_organism": "Sus scrofa (Pig)"},
    "9986": {"complex_organisms": {"Rabbit", "Mammalia"}, "subunit_organism": "Oryctolagus cuniculus (Rabbit)"},
    "9615": {"complex_organisms": {"Dog", "Mammalia"}, "subunit_organism": "Canis lupus familiaris (Dog)"},
    "10030": {"complex_organisms": {"Hamster", "Mammalia"}, "subunit_organism": "Cricetus cricetus (Black-bellied hamster)"},
    "60711": {"complex_organisms": {"Mammalia"}, "subunit_organism": "Chlorocebus sabaeus (Green monkey)"},
    "10036": {"complex_organisms": {"Hamster", "Mammalia"}, "subunit_organism": "Mesocricetus auratus (Golden hamster)"},
    "9940": {"complex_organisms": {"Mammalia"}, "subunit_organism": "Ovis aries (Sheep)"},
    "9544": {"complex_organisms": {"Mammalia"}, "subunit_organism": "Macaca mulatta (Rhesus macaque)"},
    "89462": {"complex_organisms": {"Mammalia"}, "subunit_organism": "Bubalus bubalis (Domestic water buffalo)"},
    "10141": {"complex_organisms": {"Mammalia"}, "subunit_organism": "Cavia porcellus (Guinea pig)"},
    "10029": {"complex_organisms": {"Hamster", "Mammalia"}, "subunit_organism": "Cricetulus griseus (Chinese hamster)"},
    "452646": {"complex_organisms": {"MINK"}, "subunit_organism": "Neovison vison (American mink)"},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_first_matching_alt_id(raw_value: str, prefix: str) -> str:
    for alt_id in (raw_value or "").split("|"):
        if alt_id.startswith(prefix):
            return alt_id.split(":", 1)[1]
    return ""


def _extract_tax_id(raw_value: str) -> str:
    if not raw_value:
        return ""
    return raw_value.split(":", 1)[1]


def _extract_gene_name(raw_value: str) -> str:
    for alias in (raw_value or "").split("|"):
        if ":" not in alias:
            continue
        value = alias.split(":", 1)[1]
        if "(" in value:
            value = value.split("(", 1)[0]
        value = value.strip()
        if value:
            return value
    return ""


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


def _extract_predictomes_gene_names(complex_name: str) -> tuple[str | None, str | None]:
    parts = str(complex_name).split("__")
    if len(parts) < 2:
        return None, None

    def normalize(value: str) -> str | None:
        token = value.split("_", 1)[0].strip()
        return token or None

    return normalize(parts[0]), normalize(parts[1])


def _set_job_status(job_id: str, db_name: str, **updates) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job["database_statuses"][db_name].update(updates)
        job["updated_at"] = _now_iso()


def _mark_job_complete(job_id: str, success: bool, error: Optional[str] = None) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job["status"] = "completed" if success else "failed"
        job["updated_at"] = _now_iso()
        if error:
            job["error"] = error


def _mark_job_cancelled(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job["status"] = "cancelled"
        job["updated_at"] = _now_iso()
        job["error"] = "Species PPI job was cancelled"


def _is_cancel_requested(job_id: str) -> bool:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return True
        return bool(job.get("cancel_requested"))


def _raise_if_cancelled(job_id: str) -> None:
    if _is_cancel_requested(job_id):
        raise SpeciesJobCancelled("Species PPI job was cancelled")


def _iter_biogrid_species_rows(tax_id: str) -> Iterator[dict]:
    with BIOGRID_SOURCE_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            tax_id_a = _extract_tax_id(row["Taxid Interactor A"])
            tax_id_b = _extract_tax_id(row["Taxid Interactor B"])
            if tax_id_a != tax_id or tax_id_b != tax_id:
                continue

            uniprot_a = _extract_first_matching_alt_id(row["Alt IDs Interactor A"], "uniprot/swiss-prot:")
            uniprot_b = _extract_first_matching_alt_id(row["Alt IDs Interactor B"], "uniprot/swiss-prot:")
            if not uniprot_a or not uniprot_b:
                continue

            yield {
                "Interactor_A": uniprot_a,
                "Interactor_B": uniprot_b,
                "Interactor_Gene_Name_A": _extract_gene_name(row["Aliases Interactor A"]),
                "Interactor_Gene_Name_B": _extract_gene_name(row["Aliases Interactor B"]),
                "organism": tax_id,
                "Interaction_Detection_Method": _extract_detection_method(row["Interaction Detection Method"]),
                "Interaction_Type": _extract_interaction_type(row["Interaction Types"]),
                "Confidence_Score": _extract_confidence_score(row["Confidence Values"]),
            }


def _build_biogrid_species_rows(tax_id: str) -> list[dict]:
    return list(_iter_biogrid_species_rows(tax_id))


def _iter_predictomes_species_rows(tax_id: str) -> Iterator[dict]:
    if tax_id != "9606":
        return

    for row in PREDICTOMES_DF.itertuples(index=False):
        interaction = row.uniprot_ids.split(":")
        if len(interaction) != 2:
            continue
        uniprot_a = interaction[0].strip()
        uniprot_b = interaction[1].strip()
        gene_name_a, gene_name_b = _extract_predictomes_gene_names(row.complex_name)
        yield {
            "Interactor_A": uniprot_a,
            "Interactor_B": uniprot_b,
            "Interactor_Gene_Name_A": gene_name_a,
            "Interactor_Gene_Name_B": gene_name_b,
            "spoc_score": float(row.spoc_score),
            "kirc_score": float(row.kirc_score),
            "num_unique_contacts": int(row.num_unique_contacts),
        }


def _build_predictomes_species_rows(tax_id: str) -> list[dict]:
    return list(_iter_predictomes_species_rows(tax_id))


def _iter_huri_species_rows(tax_id: str) -> Iterator[dict]:
    if tax_id != "9606":
        return

    if {"Interactor_A_Ensembl", "Interactor_B_Ensembl"}.issubset(HURI_DF.columns):
        for row in HURI_DF.itertuples(index=False):
            interactor_a_uniprot = getattr(row, "Interactor_A_UniProt", None)
            interactor_b_uniprot = getattr(row, "Interactor_B_UniProt", None)
            interactor_a_ensembl = getattr(row, "Interactor_A_Ensembl")
            interactor_b_ensembl = getattr(row, "Interactor_B_Ensembl")
            yield {
                "Interactor_A": interactor_a_uniprot or interactor_a_ensembl,
                "Interactor_B": interactor_b_uniprot or interactor_b_ensembl,
                "Interactor_A_UniProt": interactor_a_uniprot or None,
                "Interactor_B_UniProt": interactor_b_uniprot or None,
                "Interactor_A_Ensembl": interactor_a_ensembl,
                "Interactor_B_Ensembl": interactor_b_ensembl,
            }
        return

    for row in HURI_DF.itertuples(index=False):
        yield {"Interactor_A": row.interactorA, "Interactor_B": row.interactorB}


def _build_huri_species_rows(tax_id: str) -> list[dict]:
    return list(_iter_huri_species_rows(tax_id))


def _iter_corum_species_rows(tax_id: str) -> Iterator[dict]:
    species_config = CORUM_SPECIES_BY_TAX_ID.get(tax_id)
    if not species_config:
        return

    complex_organisms = species_config["complex_organisms"]
    subunit_organism = species_config["subunit_organism"]
    complexes = CORUM_COMPLEXES_DF.loc[CORUM_COMPLEXES_DF["organism"].isin(complex_organisms)]
    for complex_row in complexes.itertuples(index=False):
        subunits = []
        for subunit in complex_row.subunits:
            swissprot = subunit.get("swissprot") or {}
            if swissprot.get("organism") != subunit_organism:
                continue
            interactor_id = swissprot.get("uniprot_id")
            if not interactor_id:
                continue
            subunits.append(
                {
                    "uniprot_id": interactor_id,
                    "gene_name": swissprot.get("gene_name"),
                    "organism": swissprot.get("organism"),
                }
            )

        for interactor_a, interactor_b in combinations(subunits, 2):
            yield {
                "Interactor_A": interactor_a["uniprot_id"],
                "Interactor_B": interactor_b["uniprot_id"],
                "Interactor_Gene_Name_A": interactor_a.get("gene_name"),
                "Interactor_Gene_Name_B": interactor_b.get("gene_name"),
                "Organism": interactor_a.get("organism"),
                "complex_name": complex_row.complex_name,
                "cell_line": complex_row.cell_line if not pd.isna(complex_row.cell_line) else None,
                "Purification_Method": [
                    method.get("name")
                    for method in complex_row.purification_methods
                    if method.get("name")
                ],
            }


def _build_corum_species_rows(tax_id: str) -> list[dict]:
    return list(_iter_corum_species_rows(tax_id))


def _build_species_database_rows(db_name: str, tax_id: str) -> list[dict]:
    return list(iter_species_database_rows(db_name, tax_id))


def iter_species_database_rows(db_name: str, tax_id: str) -> Iterator[dict]:
    if db_name == "BioGrid":
        yield from _iter_biogrid_species_rows(tax_id)
        return
    if db_name == "Predictomes":
        yield from _iter_predictomes_species_rows(tax_id)
        return
    if db_name == "HuRI":
        yield from _iter_huri_species_rows(tax_id)
        return
    if db_name == "Corum":
        yield from _iter_corum_species_rows(tax_id)


def _run_species_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        selected_databases = list(job["selected_databases"])
        tax_id = job["tax_id"]
        supported_databases = set(get_supported_databases(tax_id))

    try:
        for db_name in selected_databases:
            _raise_if_cancelled(job_id)
            if db_name not in supported_databases:
                _set_job_status(
                    job_id,
                    db_name,
                    status="not_supported",
                    message=f"{db_name} does not support taxonomy ID {tax_id}",
                    pair_count=0,
                )
                continue

            if db_name not in SUPPORTED_COMPLETE_SPECIES_DATABASES:
                _set_job_status(
                    job_id,
                    db_name,
                    status="not_available",
                    message="Complete-species export is not implemented for this database yet",
                    pair_count=0,
                )
                continue

            _set_job_status(job_id, db_name, status="running", message=f"{db_name} is processing")
            try:
                if db_name == "String":
                    rows = ensure_string_species_bundle(tax_id, cancel_requested=lambda: _is_cancel_requested(job_id))
                elif db_name == "IntAct":
                    rows = ensure_intact_species_bundle(tax_id, cancel_requested=lambda: _is_cancel_requested(job_id))
                else:
                    rows = _build_species_database_rows(db_name, tax_id)
                    _raise_if_cancelled(job_id)
            except SpeciesRemoteDataNotFound:
                _set_job_status(
                    job_id,
                    db_name,
                    status="not_available",
                    message=f"{db_name} species file was not found for taxonomy ID {tax_id}",
                    pair_count=0,
                )
                continue

            with JOBS_LOCK:
                JOBS[job_id]["data"][db_name] = rows

            _set_job_status(
                job_id,
                db_name,
                status="completed",
                message=f"{db_name} finished",
                pair_count=rows.get("pair_count", 0) if isinstance(rows, dict) else len(rows),
            )

        _mark_job_complete(job_id, success=True)
    except SpeciesJobCancelled:
        for db_name in selected_databases:
            with JOBS_LOCK:
                status = JOBS[job_id]["database_statuses"][db_name]["status"]
            if status == "running" or status == "pending":
                _set_job_status(job_id, db_name, status="cancelled", message="Cancelled", pair_count=0)
        _mark_job_cancelled(job_id)
    except Exception as exc:
        _mark_job_complete(job_id, success=False, error=str(exc))


def create_species_ppi_job(tax_id: str, species_name: str, selected_databases: list[str]) -> dict:
    job_id = uuid4().hex
    database_statuses = {
        db_name: {"status": "pending", "message": "Waiting to start", "pair_count": 0}
        for db_name in selected_databases
    }

    job = {
        "job_id": job_id,
        "mode": "complete_species",
        "status": "running",
        "species_name": species_name,
        "tax_id": tax_id,
        "selected_databases": selected_databases,
        "database_statuses": database_statuses,
        "data": {},
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "error": None,
        "cancel_requested": False,
    }

    with JOBS_LOCK:
        JOBS[job_id] = job

    thread = threading.Thread(target=_run_species_job, args=(job_id,), daemon=True)
    thread.start()
    return get_species_ppi_job(job_id)


def get_species_ppi_job(job_id: str) -> dict:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise KeyError(job_id)

        available_databases = [
            db_name
            for db_name, status in job["database_statuses"].items()
            if status["status"] == "completed"
        ]

        return {
            "job_id": job["job_id"],
            "mode": job["mode"],
            "status": job["status"],
            "species_name": job["species_name"],
            "tax_id": job["tax_id"],
            "selected_databases": list(job["selected_databases"]),
            "available_databases": available_databases,
            "database_statuses": {key: dict(value) for key, value in job["database_statuses"].items()},
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
            "error": job["error"],
        }


def get_species_ppi_job_rows(job_id: str) -> tuple[dict, dict[str, list[dict]]]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise KeyError(job_id)
        summary = {
            "job_id": job["job_id"],
            "species_name": job["species_name"],
            "tax_id": job["tax_id"],
            "status": job["status"],
            "database_statuses": {key: dict(value) for key, value in job["database_statuses"].items()},
        }
        data = {
            key: (dict(value) if isinstance(value, dict) else list(value))
            for key, value in job["data"].items()
        }
    return summary, data


def get_species_display_name(tax_id: str, species_name: str | None = None) -> str:
    species = get_species_by_tax_id(tax_id)
    if species is not None:
        return species["display_name"]
    return species_name or tax_id


def cancel_species_ppi_job(job_id: str) -> dict:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return get_species_ppi_job(job_id)
        job["cancel_requested"] = True
        job["updated_at"] = _now_iso()
    return get_species_ppi_job(job_id)
