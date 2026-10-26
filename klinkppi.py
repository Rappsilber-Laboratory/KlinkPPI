"""Python client for all KlinkPPI data workflows. Requires only requests.

Use the backend URL (usually port 8000), or a reverse-proxy URL ending in /api.
No requests run at import time. POST requests are never automatically retried.
"""
from __future__ import annotations

import csv
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests


class KlinkPPIError(RuntimeError):
    """API or transport error; job preserves resumable progress where available."""
    def __init__(self, message, *, status_code=None, job=None):
        super().__init__(str(message))
        self.status_code = status_code
        self.job = job


class KlinkPPIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 60, session=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        self._owns_session = session is None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Close owned connections; caller-supplied sessions remain caller-owned."""
        if self._owns_session:
            self.session.close()

    def _send(self, method, path, **kwargs):
        try:
            return self.session.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise KlinkPPIError(f"KlinkPPI request failed: {exc}") from exc

    @staticmethod
    def _check(response):
        if not response.ok:
            try:
                payload = response.json()
                detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
            except ValueError:
                detail = response.text[:1000]
            raise KlinkPPIError(f"HTTP {response.status_code}: {detail}", status_code=response.status_code)

    def _request(self, method: str, path: str, **kwargs):
        response = self._send(method, path, **kwargs)
        try:
            self._check(response)
            try:
                return response.json()
            except ValueError as exc:
                raise KlinkPPIError(f"KlinkPPI returned non-JSON HTTP {response.status_code}") from exc
        finally:
            response.close()

    @staticmethod
    def _job_path(kind, job_id):
        return f"/{kind}/jobs/{quote(str(job_id), safe='')}"

    def health(self):
        return self._request("GET", "/health")

    def supported_organisms(self):
        """Coverage summary used by the web app's organism coverage plots."""
        return self._request("GET", "/supported-organisms/summary")

    def search_species(self, query: str, limit: int = 10):
        return self._request("GET", "/species/search", params={"q": query, "limit": limit})["results"]

    def search_genes(self, query: str, *, tax_id=None, species_name=None, limit=10):
        """Inspect candidates before selecting a UniProt accession; never auto-pick."""
        return self._request("GET", "/gene-name/search", params={
            "query": query, "tax_id": tax_id, "species_name": species_name, "limit": limit})

    def single_search(self, identifier: str, input_type: str = "UniProtKB", *, tax_id=None,
                      species_name=None, databases: Iterable[str] | None = None):
        params = {"id_value": identifier, "from_database": input_type,
                  "tax_id": tax_id, "species_name": species_name}
        if databases is not None:
            selected = list(databases)
            if not selected:
                raise ValueError("Select at least one database, or use None for every supported source.")
            params["selected_databases"] = selected
        return self._request("GET", "/search", params=params)

    def start_species(self, *, tax_id=None, species_name=None, databases: Iterable[str]):
        return self._request("POST", "/species-ppi/jobs", json={"tax_id": tax_id,
            "species_name": species_name, "selected_databases": list(databases)})

    def get_species(self, job_id):
        return self._request("GET", self._job_path("species-ppi", job_id))

    def cancel_species(self, job_id):
        return self._request("POST", self._job_path("species-ppi", job_id) + "/cancel")

    def species_search(self, *, tax_id=None, species_name=None, databases: Iterable[str],
                       poll_interval=1.0, max_wait=3600, on_progress=None):
        self._validate_wait(poll_interval, max_wait)
        job = self.start_species(tax_id=tax_id, species_name=species_name, databases=databases)
        return self.wait_species(job, poll_interval=poll_interval, max_wait=max_wait, on_progress=on_progress)

    @staticmethod
    def normalize_identifiers(identifiers):
        """Trim and merge duplicates before enforcing the web app's 20-ID limit."""
        if isinstance(identifiers, str):
            raise ValueError("Pass a list of identifiers, or use read_identifiers for a file.")
        values = list(identifiers)
        if any(not isinstance(value, str) for value in values):
            raise ValueError("Every identifier must be a string.")
        ids = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not 1 <= len(ids) <= 20:
            raise ValueError("Use 1–20 distinct identifiers per collection; duplicates are merged.")
        if any(len(value) > 100 for value in ids):
            raise ValueError("Identifiers must be at most 100 characters each.")
        return ids

    @classmethod
    def read_identifiers(cls, path: str | Path):
        """Read headerless, single-column CSV/TSV/TXT (UTF-8, optional BOM)."""
        text = Path(path).read_text(encoding="utf-8-sig")
        ids = []
        for line in text.splitlines():
            if not line.strip():
                continue
            delimiter = '\t' if '\t' in line else ','
            row = [cell.strip() for cell in next(csv.reader([line], delimiter=delimiter, skipinitialspace=True)) if cell.strip()]
            if len(row) > 1:
                raise ValueError("Use one identifier per line, without a header or extra columns.")
            ids.extend(row)
        return cls.normalize_identifiers(ids)

    def start_collection(self, identifiers, *, species_name: str, tax_id=None,
                         databases: Iterable[str], input_type="auto", mode="induced"):
        return self._request("POST", "/collection/jobs", json={
            "identifiers": self.normalize_identifiers(identifiers), "species_name": species_name,
            "tax_id": tax_id, "selected_databases": list(databases), "input_type": input_type, "mode": mode})

    def get_collection(self, job_id):
        return self._request("GET", self._job_path("collection", job_id))

    def run_collection(self, job_id, choices=None):
        """Run reviewed mappings: {original_input: accession}; None explicitly skips an ID."""
        return self._request("POST", self._job_path("collection", job_id) + "/run", json={"choices": choices or {}})

    def rerun_collection(self, job_id):
        """Start again with the same reviewed mappings; returns immediately."""
        return self._request("POST", self._job_path("collection", job_id) + "/rerun")

    def cancel_collection(self, job_id):
        return self._request("POST", self._job_path("collection", job_id) + "/cancel")

    def collection_search(self, identifiers, *, species_name: str, tax_id=None, databases: Iterable[str],
                          input_type="auto", mode="induced", choices=None, poll_interval=1.0,
                          max_wait=3600, on_progress=None):
        """Convenience workflow; ambiguous mappings raise with error.job for review/resume."""
        self._validate_wait(poll_interval, max_wait)
        job = self.start_collection(identifiers, species_name=species_name, tax_id=tax_id,
                                   databases=databases, input_type=input_type, mode=mode)
        job = self.wait_collection(job, poll_interval=poll_interval, max_wait=max_wait,
                                   on_progress=on_progress, until_review=True)
        ambiguous = [row["input"] for row in job["resolution"]
                     if len(row["candidates"]) > 1 and row["input"] not in (choices or {})]
        if ambiguous:
            raise KlinkPPIError(f"Ambiguous identifiers require choices: {', '.join(ambiguous)}", job=job)
        job = self.run_collection(job["job_id"], choices)
        return self.wait_collection(job, poll_interval=poll_interval, max_wait=max_wait, on_progress=on_progress)

    @staticmethod
    def _validate_wait(interval, max_wait):
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("poll_interval must be positive and finite.")
        if max_wait is not None and (not math.isfinite(max_wait) or max_wait <= 0):
            raise ValueError("max_wait must be positive and finite, or None.")

    def _wait(self, path, job, interval=1.0, extra_done=None, *, max_wait=3600, on_progress=None):
        self._validate_wait(interval, max_wait)
        deadline = None if max_wait is None else time.monotonic() + max_wait
        done = {"completed", "failed", "cancelled"} | (extra_done or set())
        while True:
            if on_progress:
                on_progress(job)
            if job.get("status") in done:
                break
            if job.get("status") == "awaiting_selection":
                raise KlinkPPIError("Review mappings and call run_collection before waiting for completion.", job=job)
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise KlinkPPIError("Polling timed out; the server job is still available to resume or cancel.", job=job)
            time.sleep(interval if remaining is None else min(interval, remaining))
            try:
                job = self._request("GET", path)
            except KlinkPPIError as exc:
                if exc.job is None:
                    exc.job = job
                raise
        if job.get("status") in {"failed", "cancelled"}:
            raise KlinkPPIError(job.get("error") or job.get("progress") or f"Job {job['status']}", job=job)
        return job

    def wait_species(self, job, *, poll_interval=1.0, max_wait=3600, on_progress=None):
        return self._wait(self._job_path("species-ppi", job["job_id"]), job, poll_interval,
                          max_wait=max_wait, on_progress=on_progress)

    def wait_collection(self, job, *, poll_interval=1.0, max_wait=3600, on_progress=None, until_review=False):
        return self._wait(self._job_path("collection", job["job_id"]), job, poll_interval,
                          {"awaiting_selection"} if until_review else None, max_wait=max_wait, on_progress=on_progress)

    def collection_analysis(self, job_id, *, databases=None, evidence_type="all", method="",
                            score_database="", min_score=None, min_publications=0):
        """Filtered graph + statistics, with the same evidence semantics as the UI."""
        params = {"evidence_type": evidence_type, "method": method, "score_database": score_database,
                  "min_score": min_score, "min_publications": min_publications}
        if databases is not None:
            params["databases"] = list(databases) or [""]
        return self._request("GET", self._job_path("collection", job_id) + "/analysis", params=params)

    def shared_go(self, job_id, source, target):
        return self._request("GET", self._job_path("collection", job_id) + "/shared-go",
                             params={"source": source, "target": target})

    def protein_sequence(self, job_id, accession):
        """Validated accession, species, gene, sequence and FASTA; server caches successes."""
        return self._request("GET", self._job_path("collection", job_id) + "/sequence", params={"accession": accession})

    def start_alignment(self, job_id, source, target):
        return self._request("POST", self._job_path("collection", job_id) + "/alignments",
                             json={"source": source, "target": target})

    def get_alignment(self, job_id, alignment_id):
        path = self._job_path("collection", job_id) + "/alignments/" + quote(str(alignment_id), safe="")
        return self._request("GET", path)

    def wait_alignment(self, job_id, task, *, poll_interval=1.0, max_wait=3600, on_progress=None):
        path = self._job_path("collection", job_id) + "/alignments/" + quote(str(task["alignment_id"]), safe="")
        return self._wait(path, task, poll_interval, max_wait=max_wait, on_progress=on_progress)

    def align_pair(self, job_id, source, target, *, poll_interval=1.0, max_wait=3600, on_progress=None):
        self._validate_wait(poll_interval, max_wait)
        task = self.start_alignment(job_id, source, target)
        return self.wait_alignment(job_id, task, poll_interval=poll_interval, max_wait=max_wait, on_progress=on_progress)

    def _download(self, endpoint, path, payload):
        """Stream to an adjacent temporary file; replace destination only on success."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        response = self._send("POST", endpoint, json=payload, stream=True)
        temporary = None
        try:
            self._check(response)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".part", delete=False) as handle:
                temporary = Path(handle.name)
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
            os.replace(temporary, path)
            return path
        except requests.RequestException as exc:
            raise KlinkPPIError(f"Download interrupted: {exc}") from exc
        finally:
            response.close()
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _format(output_format):
        if output_format not in {"mitab", "parquet"}:
            raise ValueError("output_format must be 'mitab' or 'parquet'.")
        return output_format

    def download_species(self, job, path, output_format="parquet", databases=None, columns=None):
        return self._download(self._job_path("species-ppi", job["job_id"]) + "/" + self._format(output_format), path,
            {"selected_databases": list(job.get("available_databases", []) if databases is None else databases),
             "selected_columns": list(columns or [])})

    def download_single(self, result, path, output_format="parquet", databases=None, columns=None):
        """Use the same MITAB/Parquet builders as the web app's Download panel."""
        context = result[0]["Input"]
        available = [db for section in result[1].get("output", []) for db, data in section.items() if isinstance(data, list)]
        return self._download("/" + self._format(output_format), path, {"results": result,
            "selected_databases": available if databases is None else list(databases),
            "selected_columns": list(columns or []), "uniprot_id": context["UniProtId"], "tax_id": context["TaxonomyId"]})

    @staticmethod
    def export_json(result: Any, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def export_collection_csv(job: dict, directory: str | Path):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        graph = job.get("graph") or {}
        KlinkPPIClient._csv(directory / "nodes.csv", graph.get("nodes", []))
        edges = [{**edge, "databases": "|".join(ev["database"] for ev in edge.get("evidence", [])),
                  "evidence": json.dumps(edge.get("evidence", []))} for edge in graph.get("edges", [])]
        KlinkPPIClient._csv(directory / "edges.csv", edges)
        return directory

    @staticmethod
    def export_single_csv(result: list, path: str | Path):
        rows = []
        for item in result[1].get("output", []):
            database, payload = next(iter(item.items()))
            if not isinstance(payload, list):
                continue
            for section in payload[1:]:
                for key in ("Direct_Interactions", "Indirect_Interactions", "Interactions", "Interactors"):
                    rows.extend({"database": database, **row} for row in section.get(key, []))
        KlinkPPIClient._csv(Path(path), rows)
        return Path(path)

    @staticmethod
    def _csv(path: Path, rows: list[dict]):
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()} for row in rows]
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            if fields:
                writer.writeheader()
                writer.writerows(rows)

    @staticmethod
    def unknown_pairs(job):
        from klinkppi_network import unknown_pairs
        return unknown_pairs(job)

    @staticmethod
    def export_network(analysis, path, output_format="json"):
        from klinkppi_network import export_network
        return export_network(analysis, path, output_format)

    @staticmethod
    def write_protein_search_page(protein, species, path):
        from klinkppi_network import write_protein_search_page
        return write_protein_search_page(protein, species, path)
