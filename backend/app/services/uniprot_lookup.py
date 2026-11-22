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


FUNCTION_FIELDS = "accession,id,protein_name,gene_names,organism_name,organism_id,reviewed,cc_function"


class ProteinLookupError(Exception):
    pass


def _protein_name(entry: dict) -> str | None:
    description = entry.get("proteinDescription", {})
    names = [description.get("recommendedName")] + description.get("submissionNames", [])
    return next((name["fullName"]["value"] for name in names if name and name.get("fullName")), None)


def parse_function(entry: dict) -> dict:
    """The FUNCTION comments shown first on a UniProt entry page, with their PubMed citations."""
    paragraphs = []
    for comment in entry.get("comments", []):
        if comment.get("commentType") != "FUNCTION":
            continue
        for text in comment.get("texts", []):
            if text.get("value"):
                pubmed = [ev["id"] for ev in text.get("evidences", []) if ev.get("source") == "PubMed" and ev.get("id")]
                paragraphs.append({"text": text["value"], "pubmed": list(dict.fromkeys(pubmed))})
    organism = entry.get("organism", {})
    return {
        "accession": entry.get("primaryAccession"),
        "entry_name": entry.get("uniProtkbId"),
        "protein_name": _protein_name(entry),
        "gene": _extract_primary_gene_name(entry),
        "organism": organism.get("scientificName"),
        "tax_id": str(organism.get("taxonId", "")) or None,
        "reviewed": entry.get("entryType") == "UniProtKB reviewed (Swiss-Prot)",
        "function": paragraphs,
        "url": f"https://www.uniprot.org/uniprotkb/{entry.get('primaryAccession')}/entry",
    }


@lru_cache(maxsize=2048)
def protein_function(accession: str | None, gene: str | None, tax_id: str | None, cache_hour: int) -> dict:
    """Look up an entry by accession, or by exact gene name within a species.

    ``cache_hour`` refreshes cached entries hourly; failed lookups raise and are
    therefore never cached.
    """
    try:
        if accession:
            response = requests.get(f"{UNIPROT_ENTRY_API}/{accession}.json", params={"fields": FUNCTION_FIELDS}, timeout=REQUEST_TIMEOUT)
            if response.status_code in {400, 404}:
                raise ProteinLookupError(f"UniProt has no entry for {accession}.")
            response.raise_for_status()
            return parse_function(response.json())
        # Prefer a reviewed (Swiss-Prot) entry for gene symbols such as STRING's.
        for reviewed in (" AND reviewed:true", ""):
            response = requests.get(f"{UNIPROT_ENTRY_API}/search", timeout=REQUEST_TIMEOUT, params={
                "query": f'gene_exact:"{gene}" AND organism_id:{tax_id}{reviewed}', "fields": FUNCTION_FIELDS,
                "format": "json", "size": 1})
            response.raise_for_status()
            results = response.json().get("results", [])
            if results:
                return parse_function(results[0])
        raise ProteinLookupError(f"No UniProt entry matches gene {gene} in taxonomy {tax_id}.")
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise ProteinLookupError("UniProt could not be reached. Please retry.") from exc
