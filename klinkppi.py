"""Small Python client for the KlinkPPI HTTP API (no plotting dependencies)."""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any, Iterable

import requests


class KlinkPPIError(RuntimeError):
    pass


class KlinkPPIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: int = 60, session=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def _request(self, method: str, path: str, **kwargs):
        response = self.session.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        try:
            payload = response.json()
        except ValueError as exc:
            raise KlinkPPIError(f"KlinkPPI returned non-JSON HTTP {response.status_code}") from exc
        if not response.ok:
            raise KlinkPPIError(payload.get("detail", f"HTTP {response.status_code}"))
        return payload

    def single_search(self, identifier: str, input_type: str = "UniProtKB", *, tax_id: str | None = None,
                      species_name: str | None = None, databases: Iterable[str] | None = None):
        params: list[tuple[str, str]] = [("id_value", identifier), ("from_database", input_type)]
        if tax_id:
            params.append(("tax_id", str(tax_id)))
        if species_name:
            params.append(("species_name", species_name))
        params.extend(("selected_databases", db) for db in (databases or []))
        return self._request("GET", "/search", params=params)

    def search_species(self, query: str, limit: int = 10):
        """Return the same supported-species suggestions used by the web UI."""
        return self._request("GET", "/species/search", params={"q": query, "limit": limit})["results"]

    def species_search(self, *, tax_id: str | None = None, species_name: str | None = None,
                       databases: Iterable[str], poll_interval: float = 1.0):
        job = self._request("POST", "/species-ppi/jobs", json={"tax_id": tax_id, "species_name": species_name,
                            "selected_databases": list(databases)})
        return self._wait(f"/species-ppi/jobs/{job['job_id']}", job, poll_interval)

    def collection_search(self, identifiers: Iterable[str], *, species_name: str, tax_id: str | None = None,
                          databases: Iterable[str], input_type: str = "auto", mode: str = "induced",
                          choices: dict[str, str | None] | None = None, poll_interval: float = 1.0):
        job = self._request("POST", "/collection/jobs", json={"identifiers": list(identifiers),
            "species_name": species_name, "tax_id": tax_id, "selected_databases": list(databases),
            "input_type": input_type, "mode": mode})
        job = self._wait(f"/collection/jobs/{job['job_id']}", job, poll_interval, {"awaiting_selection"})
        selected = dict(choices or {})
        ambiguous = []
        for row in job["resolution"]:
            if len(row["candidates"]) == 1:
                selected.setdefault(row["input"], row["candidates"][0]["id"])
            elif len(row["candidates"]) > 1 and row["input"] not in selected:
                ambiguous.append(row["input"])
        if ambiguous:
            raise KlinkPPIError(f"Ambiguous identifiers require choices: {', '.join(ambiguous)}")
        job = self._request("POST", f"/collection/jobs/{job['job_id']}/run", json={"choices": selected})
        return self._wait(f"/collection/jobs/{job['job_id']}", job, poll_interval)

    def _wait(self, path: str, job: dict, interval: float, extra_done: set[str] | None = None):
        done = {"completed", "failed", "cancelled"} | (extra_done or set())
        while job.get("status") not in done:
            time.sleep(interval)
            job = self._request("GET", path)
        if job.get("status") == "failed":
            raise KlinkPPIError(job.get("error") or job.get("progress") or "KlinkPPI job failed")
        if job.get("status") == "cancelled":
            raise KlinkPPIError("KlinkPPI job was cancelled")
        return job

    def download_species(self, job: dict, path: str | Path, output_format: str = "parquet",
                         databases: Iterable[str] | None = None, columns: Iterable[str] | None = None):
        selected = list(databases or job.get("available_databases", []))
        response = self.session.request("POST", f"{self.base_url}/species-ppi/jobs/{job['job_id']}/{output_format}",
            timeout=self.timeout, json={"selected_databases": selected, "selected_columns": list(columns or [])})
        if not response.ok:
            raise KlinkPPIError(response.text)
        Path(path).write_bytes(response.content)
        return Path(path)

    @staticmethod
    def export_json(result: Any, path: str | Path):
        path = Path(path)
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
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            if fields:
                writer.writeheader()
                writer.writerows(rows)
