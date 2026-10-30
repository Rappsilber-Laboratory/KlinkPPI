"""On-demand comparison of GO cross-references reported by UniProt."""
from functools import lru_cache
from time import time
import re

import requests

API = "https://rest.uniprot.org/uniprotkb"
ASPECTS = {"P": "Biological process", "F": "Molecular function", "C": "Cellular component"}


class GOLookupError(Exception):
    pass


def parse_go(entry):
    terms = {}
    for ref in entry.get("uniProtKBCrossReferences", []):
        if ref.get("database") != "GO" or not re.fullmatch(r"GO:\d{7}", ref.get("id", "")):
            continue
        properties = {prop["key"]: prop.get("value", "") for prop in ref.get("properties", [])}
        label = properties.get("GoTerm", "")
        aspect, _, name = label.partition(":")
        term = terms.setdefault(ref["id"], {
            "id": ref["id"], "name": name or ref["id"],
            "category": ASPECTS.get(aspect, "Other"), "evidence": [],
        })
        evidence = properties.get("GoEvidenceType")
        if evidence and evidence not in term["evidence"]:
            term["evidence"].append(evidence)
    return terms


@lru_cache(maxsize=512)
def protein_go(accession, tax_id, cache_hour):
    # Bound memory and refresh cached annotations hourly. Failed lookups are
    # never cached, allowing a user to retry transient UniProt errors.
    try:
        response = requests.get(f"{API}/{accession}.json", params={"fields": "accession,organism_id,go"}, timeout=25)
        response.raise_for_status()
        entry = response.json()
        if str(entry.get("organism", {}).get("taxonId")) != str(tax_id):
            raise GOLookupError(f"UniProt species does not match the selected species for {accession}.")
        if entry.get("primaryAccession") != accession and accession not in entry.get("secondaryAccessions", []):
            raise GOLookupError(f"UniProt returned a different accession for {accession}; resolve your inputs again.")
        return parse_go(entry)
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise GOLookupError(f"Could not retrieve GO annotations for {accession} from UniProt. Please retry.") from exc


def validate_unknown_pair(job, source, target):
    if job["status"] != "completed" or job["mode"] != "induced":
        raise ValueError("Pair comparison requires a completed induced network.")
    graph = job["graph"]
    nodes = {node["id"]: node for node in graph["nodes"] if node.get("input") and not node.get("unresolved")}
    if source == target or source not in nodes or target not in nodes:
        raise ValueError("Choose two distinct resolved input proteins from this network.")
    if any({edge["source"], edge["target"]} == {source, target} for edge in graph["edges"]):
        raise ValueError("This pair already has interaction evidence in the search results.")


def shared_go(job, source, target):
    validate_unknown_pair(job, source, target)
    hour = int(time() // 3600)
    left, right = [protein_go(accession, job["tax_id"], hour) for accession in (source, target)]
    shared = [{"id": term_id, "name": left[term_id]["name"], "category": left[term_id]["category"],
               "source_evidence": left[term_id]["evidence"], "target_evidence": right[term_id]["evidence"]}
              for term_id in left.keys() & right.keys()]
    shared.sort(key=lambda term: (term["category"], term["name"], term["id"]))
    return {"source": source, "target": target, "source_term_count": len(left), "target_term_count": len(right),
            "shared_terms": shared, "provider": "UniProt", "comparison": "Exact GO IDs reported on both UniProt entries; no ancestor expansion."}
