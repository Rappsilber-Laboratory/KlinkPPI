from functools import lru_cache

import requests


UNIPROT_ENTRY_API = "https://rest.uniprot.org/uniprotkb"
REQUEST_TIMEOUT = 15


def _extract_primary_gene_name(entry: dict) -> str | None:
    for gene in entry.get("genes", []):
        gene_name = gene.get("geneName", {}).get("value")
        if gene_name:
            return gene_name
        for synonym in gene.get("synonyms", []):
            value = synonym.get("value")
            if value:
                return value
    return None


def get_uniprot_taxonomy_id(uniprot_id: str) -> str | None:
    response = requests.get(f"{UNIPROT_ENTRY_API}/{uniprot_id}.json", timeout=REQUEST_TIMEOUT)
    if not response.ok:
        return None

    response_json = response.json()
    organism = response_json.get("organism", {})
    taxon_id = organism.get("taxonId")
    if taxon_id is None:
        return None
    return str(taxon_id)


@lru_cache(maxsize=8192)
def get_uniprot_gene_name(uniprot_id: str | None) -> str | None:
    if not uniprot_id:
        return None

    try:
        response = requests.get(
            f"{UNIPROT_ENTRY_API}/{uniprot_id}.json",
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            return None
        return _extract_primary_gene_name(response.json())
    except (requests.RequestException, ValueError):
        return None


def get_uniprot_gene_names(uniprot_ids: list[str | None]) -> dict[str, str]:
    gene_names = {}
    unique_ids = list(dict.fromkeys(item for item in uniprot_ids if item))

    for index in range(0, len(unique_ids), 100):
        chunk = unique_ids[index:index + 100]
        try:
            response = requests.get(
                f"{UNIPROT_ENTRY_API}/accessions",
                params={
                    "accessions": ",".join(chunk),
                    "fields": "accession,gene_names",
                    "format": "json",
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            for entry in response.json().get("results", []):
                accession = entry.get("primaryAccession")
                gene_name = _extract_primary_gene_name(entry)
                if accession and gene_name:
                    gene_names[accession] = gene_name
        except (requests.RequestException, ValueError):
            for uniprot_id in chunk:
                gene_name = get_uniprot_gene_name(uniprot_id)
                if gene_name:
                    gene_names[uniprot_id] = gene_name
    return gene_names
