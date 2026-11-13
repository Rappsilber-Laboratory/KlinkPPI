from __future__ import annotations

from collections import defaultdict
from csv import DictReader
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUPPORTED_ORGANISM_DIR = PROJECT_ROOT / "Supported_Organisms"

SUPPORTED_ORGANISM_FILES = {
    "String": SUPPORTED_ORGANISM_DIR / "AllSpeciesString.csv",
    "BioGrid": SUPPORTED_ORGANISM_DIR / "AllSpeciesBioGrid.csv",
    "IntAct": SUPPORTED_ORGANISM_DIR / "AllSpeciesIntact.csv",
    "Corum": SUPPORTED_ORGANISM_DIR / "AllSpeciesCorum.csv",
    "Predictomes": SUPPORTED_ORGANISM_DIR / "AllSpeciesPredictomes.csv",
    "HuRI": SUPPORTED_ORGANISM_DIR / "AllSpeciesHuRI.csv",
    "ComplexPortal": SUPPORTED_ORGANISM_DIR / "AllSpeciesComplexPortal.csv",
    "Reactome": SUPPORTED_ORGANISM_DIR / "AllSpeciesReactome.csv",
    "Signor": SUPPORTED_ORGANISM_DIR / "AllSpeciesSignor.csv",
    "Hippie": SUPPORTED_ORGANISM_DIR / "AllSpeciesHippie.csv",
    "HuMap": SUPPORTED_ORGANISM_DIR / "AllSpeciesHuMap.csv",
    "Mint": SUPPORTED_ORGANISM_DIR / "AllSpeciesMint.csv",
}

COMMON_SPECIES_ALIASES = {
    "9606": {"human", "humans", "h. sapiens"},
    "10090": {"mouse", "mice", "murine", "m. musculus"},
    "10116": {"rat", "rats", "r. norvegicus"},
    "9913": {"cow", "cattle", "bovine", "b. taurus"},
    "9823": {"pig", "pigs", "porcine", "s. scrofa"},
    "9986": {"rabbit", "rabbits", "o. cuniculus"},
    "9615": {"dog", "dogs", "canine", "c. lupus familiaris"},
    "60711": {"green monkey", "african green monkey"},
    "559292": {"yeast", "baker's yeast", "bakers yeast", "s. cerevisiae"},
    "7227": {"fruit fly", "fly", "drosophila", "d. melanogaster"},
    "6239": {"worm", "nematode", "c. elegans"},
    "3702": {"arabidopsis", "thale cress", "a. thaliana"},
    "7955": {"zebrafish", "danio rerio", "d. rerio"},
    "9031": {"chicken", "gallus gallus", "g. gallus"},
    "8355": {"frog", "xenopus", "x. laevis"},
    "83333": {"e. coli", "ecoli", "escherichia coli", "k-12"},
}


def _normalize_text(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _add_alias(aliases: set[str], raw_value: str) -> None:
    normalized = _normalize_text(raw_value)
    if not normalized:
        return

    aliases.add(normalized)
    aliases.add(normalized.replace(" ", ""))

    without_parenthetical = re.sub(r"\s*\([^)]*\)", "", raw_value).strip()
    normalized_without_parenthetical = _normalize_text(without_parenthetical)
    if normalized_without_parenthetical:
        aliases.add(normalized_without_parenthetical)
        aliases.add(normalized_without_parenthetical.replace(" ", ""))


def _pick_display_name(names: set[str]) -> str:
    def sort_key(name: str) -> tuple[int, int, int, str]:
        normalized = _normalize_text(name)
        return (
            0 if " " in name else 1,
            1 if "(" in name else 0,
            len(normalized),
            normalized,
        )

    return sorted(names, key=sort_key)[0]


def _load_species_index() -> tuple[dict[str, dict], list[dict], dict[str, set[str]]]:
    combined: dict[str, dict] = {}

    for database_name, file_path in SUPPORTED_ORGANISM_FILES.items():
        with file_path.open(newline="", encoding="utf-8") as handle:
            reader = DictReader(handle)
            if not reader.fieldnames:
                continue

            name_field = next(
                field for field in reader.fieldnames if field.lower() != "taxon_id"
            )

            for row in reader:
                tax_id = str(row.get("Taxon_id", "")).strip()
                raw_name = str(row.get(name_field, "")).strip()
                if not tax_id or not raw_name:
                    continue

                entry = combined.setdefault(
                    tax_id,
                    {
                        "tax_id": tax_id,
                        "names": set(),
                        "aliases": set(),
                        "supported_databases": set(),
                    },
                )
                entry["names"].add(raw_name)
                entry["supported_databases"].add(database_name)
                _add_alias(entry["aliases"], raw_name)

    exact_aliases: dict[str, set[str]] = defaultdict(set)
    records: list[dict] = []

    for tax_id, entry in combined.items():
        for alias in COMMON_SPECIES_ALIASES.get(tax_id, set()):
            _add_alias(entry["aliases"], alias)

        display_name = _pick_display_name(entry["names"])
        record = {
            "tax_id": tax_id,
            "display_name": display_name,
            "supported_databases": sorted(entry["supported_databases"]),
            "aliases": tuple(sorted(entry["aliases"])),
        }
        combined[tax_id] = record
        records.append(record)

        for alias in record["aliases"]:
            exact_aliases[alias].add(tax_id)

    records.sort(key=lambda item: item["display_name"].lower())
    return combined, records, exact_aliases


SPECIES_BY_TAX_ID, SPECIES_RECORDS, SPECIES_EXACT_ALIASES = _load_species_index()


def get_species_by_tax_id(tax_id: str | None) -> dict | None:
    if not tax_id:
        return None
    return SPECIES_BY_TAX_ID.get(str(tax_id).strip())


def get_supported_databases(tax_id: str | None) -> set[str]:
    record = get_species_by_tax_id(tax_id)
    if record is None:
        return set()
    return set(record["supported_databases"])


def _load_supported_tax_id_sets() -> dict[str, set[str]]:
    tax_ids_by_database: dict[str, set[str]] = {}

    for database_name, file_path in SUPPORTED_ORGANISM_FILES.items():
        tax_ids: set[str] = set()
        with file_path.open(newline="", encoding="utf-8") as handle:
            reader = DictReader(handle)
            for row in reader:
                tax_id = str(row.get("Taxon_id", "")).strip()
                if tax_id:
                    tax_ids.add(tax_id)
        tax_ids_by_database[database_name] = tax_ids

    return tax_ids_by_database


def get_supported_organism_summary() -> dict:
    tax_ids_by_database = _load_supported_tax_id_sets()
    database_order = list(SUPPORTED_ORGANISM_FILES.keys())
    all_tax_ids = set().union(*tax_ids_by_database.values())
    shared_by_all = set.intersection(*(tax_ids_by_database[name] for name in database_order))

    exact_overlap_counts: dict[tuple[str, ...], int] = defaultdict(int)
    for tax_id in all_tax_ids:
        databases = tuple(
            database_name
            for database_name in database_order
            if tax_id in tax_ids_by_database[database_name]
        )
        if databases:
            exact_overlap_counts[databases] += 1

    pairwise_overlaps = []
    for index, database_name in enumerate(database_order):
        for other_database_name in database_order[index + 1:]:
            pairwise_overlaps.append(
                {
                    "databases": [database_name, other_database_name],
                    "count": len(tax_ids_by_database[database_name] & tax_ids_by_database[other_database_name]),
                }
            )

    pairwise_overlaps.sort(key=lambda item: item["count"], reverse=True)

    return {
        "database_counts": [
            {
                "database": database_name,
                "count": len(tax_ids_by_database[database_name]),
            }
            for database_name in database_order
        ],
        "union_count": len(all_tax_ids),
        "shared_all_count": len(shared_by_all),
        "exact_overlap_counts": [
            {
                "databases": list(databases),
                "count": count,
            }
            for databases, count in sorted(
                exact_overlap_counts.items(),
                key=lambda item: (-len(item[0]), -item[1], item[0]),
            )
        ],
        "pairwise_overlaps": pairwise_overlaps,
    }


def _score_species_record(record: dict, normalized_query: str, compact_query: str) -> tuple[int, int] | None:
    best_score: tuple[int, int] | None = None

    for alias in record["aliases"]:
        compact_alias = alias.replace(" ", "")

        if alias == normalized_query or compact_alias == compact_query:
            score = (0, abs(len(compact_alias) - len(compact_query)))
        elif alias.startswith(normalized_query) or compact_alias.startswith(compact_query):
            score = (1, abs(len(compact_alias) - len(compact_query)))
        elif normalized_query in alias or compact_query in compact_alias:
            score = (2, abs(len(compact_alias) - len(compact_query)))
        else:
            continue

        if best_score is None or score < best_score:
            best_score = score

    return best_score


def search_species(query: str, limit: int = 8) -> list[dict]:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return []

    compact_query = normalized_query.replace(" ", "")
    matches: list[tuple[tuple[int, int], dict]] = []

    for record in SPECIES_RECORDS:
        score = _score_species_record(record, normalized_query, compact_query)
        if score is None:
            continue
        matches.append((score, record))

    matches.sort(
        key=lambda item: (
            item[0],
            -len(item[1]["supported_databases"]),
            len(item[1]["display_name"]),
            item[1]["display_name"].lower(),
        )
    )

    results = []
    for score, record in matches[:limit]:
        results.append(
            {
                "tax_id": record["tax_id"],
                "display_name": record["display_name"],
                "supported_databases": record["supported_databases"],
                "match_rank": score[0],
            }
        )
    return results


def resolve_species_name(query: str) -> dict | None:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return None

    compact_query = normalized_query.replace(" ", "")
    exact_matches = set()
    exact_matches.update(SPECIES_EXACT_ALIASES.get(normalized_query, set()))
    exact_matches.update(SPECIES_EXACT_ALIASES.get(compact_query, set()))

    if len(exact_matches) == 1:
        tax_id = next(iter(exact_matches))
        return SPECIES_BY_TAX_ID[tax_id]

    candidate_matches = search_species(query, limit=5)
    if not candidate_matches:
        return None

    best_rank = candidate_matches[0]["match_rank"]
    best_tax_ids = [
        match["tax_id"] for match in candidate_matches if match["match_rank"] == best_rank
    ]

    if len(best_tax_ids) == 1 and best_rank <= 1:
        return SPECIES_BY_TAX_ID[best_tax_ids[0]]

    return None
