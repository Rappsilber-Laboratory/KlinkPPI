from __future__ import annotations

import csv
from itertools import combinations
from pathlib import Path
import re
from typing import Iterator

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = PROJECT_ROOT / "Data" / "SpeciesPPICache" / "ComplexPortal" / "current"
DOWNLOAD_URL = "https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/{tax_id}.tsv"
PREDICTED_DOWNLOAD_URL = "https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/{tax_id}_predicted.tsv"
UNIPROT_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{4,14}$")


def ensure_complex_portal_file(tax_id: str, predicted: bool = False) -> Path:
    filename = f"{tax_id}_predicted.tsv" if predicted else f"{tax_id}.tsv"
    source_url = PREDICTED_DOWNLOAD_URL if predicted else DOWNLOAD_URL
    destination = CACHE_DIR / filename
    if destination.exists() and destination.stat().st_size > 0:
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tsv.part")
    try:
        with requests.get(source_url.format(tax_id=tax_id), stream=True, timeout=90) as response:
            if response.status_code == 404:
                raise FileNotFoundError(f"Complex Portal has no ComplexTab file {filename}")
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        temporary.replace(destination)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return destination


def _participants(value: str) -> list[dict]:
    participants = []
    for token in (value or "").split("|"):
        token = token.strip()
        match = re.match(r"^(.+?)\(([^()]*)\)$", token)
        identifier = (match.group(1) if match else token).strip()
        stoichiometry = (match.group(2) if match else None)
        if UNIPROT_PATTERN.match(identifier) and identifier not in {item["id"] for item in participants}:
            participants.append({"id": identifier, "stoichiometry": stoichiometry})
    return participants


def _pubmed_ids(value: str) -> list[str]:
    ids = []
    for token in (value or "").split("|"):
        if token.lower().startswith("pubmed:"):
            ids.append(token.split(":", 1)[1].split("(", 1)[0])
    return ids


def _iter_complex_portal_file(path: Path, predicted: bool = False) -> Iterator[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            participants = _participants(
                row.get("Expanded participant list")
                or row.get("Identifiers (and stoichiometry) of molecules in complex")
                or ""
            )
            if len(participants) < 2:
                continue
            yield {
                "complex_id": row.get("#Complex ac"),
                "complex_name": row.get("Recommended name"),
                "participants": participants,
                "Evidence_Code": row.get("Evidence Code"),
                "Experimental_Evidence": row.get("Experimental evidence"),
                "PubMed_Ids": _pubmed_ids(row.get("Cross references", "")),
                "Description": row.get("Description"),
                "Source_Database": row.get("Source") or "complex portal",
                "Complex_Type": "machine-learning predicted" if predicted else "curated",
            }


def iter_complex_portal_complexes(tax_id: str) -> Iterator[dict]:
    yield from _iter_complex_portal_file(ensure_complex_portal_file(tax_id))
    # The human predicted release is published as a separate ComplexTab file.
    # It contains CPX accessions such as hu.MAP-derived complexes, including
    # some proteins absent from the curated-only file.
    if tax_id == "9606":
        try:
            predicted_path = ensure_complex_portal_file(tax_id, predicted=True)
        except FileNotFoundError:
            return
        yield from _iter_complex_portal_file(predicted_path, predicted=True)


def iter_complex_portal_species_rows(tax_id: str) -> Iterator[dict]:
    for complex_record in iter_complex_portal_complexes(tax_id):
        for participant_a, participant_b in combinations(complex_record["participants"], 2):
            yield {
                "Database": "ComplexPortal",
                "Interactor_A": participant_a["id"],
                "Interactor_B": participant_b["id"],
                "Taxid_A": tax_id,
                "Taxid_B": tax_id,
                "Interaction_Type": "complex-portal-complex-co-membership",
                "Evidence_Class": "complex-co-membership",
                "Stoichiometry_A": participant_a["stoichiometry"],
                "Stoichiometry_B": participant_b["stoichiometry"],
                **{key: value for key, value in complex_record.items() if key != "participants"},
            }


def resolve_complex_portal(input_id: str, tax_id: str):
    database_link = f"https://www.ebi.ac.uk/complexportal/search?query={input_id}"
    result = [{"info": {
        "database": "Complex Portal",
        "Input_UniProt": input_id,
        "organism_tax_id": tax_id,
        "Database_Link": database_link,
        "Evidence_Class": "complex-co-membership",
        "Source_Release": "Complex Portal current ComplexTab",
        "Source_URL": DOWNLOAD_URL.format(tax_id=tax_id),
        "Includes_Predicted_Human_Complexes": tax_id == "9606",
    }}]
    interactors = []
    seen = set()
    try:
        for complex_record in iter_complex_portal_complexes(tax_id):
            query_participant = next((item for item in complex_record["participants"] if item["id"] == input_id), None)
            if not query_participant:
                continue
            for participant in complex_record["participants"]:
                if participant["id"] == input_id:
                    continue
                key = (participant["id"], complex_record["complex_id"])
                if key in seen:
                    continue
                seen.add(key)
                interactors.append({
                    "Interactor_A": participant["id"],
                    "Interactor_B": input_id,
                    "organism_tax_id": tax_id,
                    "Interaction_Type": "complex-portal-complex-co-membership",
                    "Evidence_Class": "complex-co-membership",
                    "Stoichiometry_A": participant["stoichiometry"],
                    "Stoichiometry_B": query_participant["stoichiometry"],
                    "Interactor_Link": f"https://www.ebi.ac.uk/complexportal/complex/{complex_record['complex_id']}",
                    **{key: value for key, value in complex_record.items() if key != "participants"},
                })
    except (requests.RequestException, OSError) as exc:
        result[0]["info"]["Error"] = f"Complex Portal data could not be loaded: {exc}"
    result.append({"Interactors": interactors})
    return result
