from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys
import time
from typing import Iterable

from app.services.species_index import SUPPORTED_ORGANISM_FILES, get_species_by_tax_id, get_supported_databases
from app.services.species_ppi_export import write_species_mitab, write_species_parquet
from app.services.species_ppi_jobs import (
    SUPPORTED_COMPLETE_SPECIES_DATABASES,
    iter_species_database_rows,
)
from app.services.species_ppi_remote import (
    SpeciesRemoteDataNotFound,
    ensure_intact_species_bundle,
    ensure_string_species_bundle,
)


SUPPORTED_OUTPUT_FORMATS = {"mitab", "parquet"}
DATABASE_NAME_BY_KEY = {name.lower(): name for name in SUPPORTED_ORGANISM_FILES}


@dataclass
class SpeciesDatabaseDownloadResult:
    database: str
    status: str
    path: str | None
    pair_count: int
    elapsed_seconds: float
    message: str


@dataclass
class SpeciesDownloadSummary:
    tax_id: str
    species_name: str
    output_format: str
    output_dir: str
    elapsed_seconds: float
    results: list[SpeciesDatabaseDownloadResult]

    @property
    def files(self) -> list[str]:
        return [result.path for result in self.results if result.path]

    @property
    def total_pair_count(self) -> int:
        return sum(result.pair_count for result in self.results if result.status == "completed")


def _format_elapsed(elapsed_seconds: float) -> str:
    if elapsed_seconds < 60:
        return f"{elapsed_seconds:.2f}s"
    minutes, seconds = divmod(elapsed_seconds, 60)
    return f"{int(minutes)}m {seconds:.1f}s"


class _ConsoleProgress:
    def __init__(self, label: str, total: int | None):
        self.label = label
        self.total = total if total and total > 0 else None
        self.current = 0
        self.last_rendered_at = 0.0
        self._render(force=True)

    def update(self, delta: int) -> None:
        self.current += delta
        self._render()

    def close(self, written_count: int) -> None:
        if self.total:
            self.current = max(self.current, self.total)
        self._render(force=True, suffix=f" wrote {written_count} rows")
        sys.stderr.write("\n")
        sys.stderr.flush()

    def _render(self, force: bool = False, suffix: str = "") -> None:
        now = time.monotonic()
        if not force and now - self.last_rendered_at < 0.25:
            return
        self.last_rendered_at = now

        if self.total:
            ratio = min(self.current / self.total, 1.0)
            filled = int(ratio * 28)
            bar = "#" * filled + "-" * (28 - filled)
            text = f"\r{self.label:12} [{bar}] {ratio:6.1%} {min(self.current, self.total)}/{self.total}{suffix}"
        else:
            text = f"\r{self.label:12} {self.current} rows{suffix}"

        sys.stderr.write(text)
        sys.stderr.flush()


class SpeciesPPIDownloader:
    """Python API for complete-species PPI downloads.

    This class reuses the backend species download/cache builders and streams
    each database export directly to disk. It intentionally exports every
    supported column; API callers do not select columns.
    """

    def __init__(self, show_progress: bool = True, parquet_batch_size: int = 50000):
        self.show_progress = show_progress
        self.parquet_batch_size = parquet_batch_size

    def download_species(
        self,
        tax_id: str | int,
        output_dir: str | Path,
        output_format: str = "mitab",
        databases: Iterable[str] | None = None,
    ) -> SpeciesDownloadSummary:
        normalized_tax_id = str(tax_id).strip()
        species = get_species_by_tax_id(normalized_tax_id)
        if species is None:
            raise ValueError(f"Taxonomy ID {normalized_tax_id} is not supported by the configured organism list")

        normalized_format = output_format.strip().lower()
        if normalized_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError("output_format must be 'mitab' or 'parquet'")

        selected_databases = self._resolve_databases(normalized_tax_id, databases)
        destination_dir = Path(output_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        started_at = time.monotonic()
        results: list[SpeciesDatabaseDownloadResult] = []
        for db_name in selected_databases:
            result = self._download_database(
                db_name=db_name,
                tax_id=normalized_tax_id,
                species_name=species["display_name"],
                output_dir=destination_dir,
                output_format=normalized_format,
            )
            results.append(result)

        elapsed_seconds = time.monotonic() - started_at
        summary = SpeciesDownloadSummary(
            tax_id=normalized_tax_id,
            species_name=species["display_name"],
            output_format=normalized_format,
            output_dir=str(destination_dir),
            elapsed_seconds=elapsed_seconds,
            results=results,
        )

        if self.show_progress:
            self._print(
                f"Taxon {normalized_tax_id} total pairs: {summary.total_pair_count} "
                f"in {_format_elapsed(summary.elapsed_seconds)}"
            )

        return summary

    def _resolve_databases(self, tax_id: str, databases: Iterable[str] | None) -> list[str]:
        supported_for_species = get_supported_databases(tax_id)
        if databases is None:
            return sorted(supported_for_species & SUPPORTED_COMPLETE_SPECIES_DATABASES)

        if isinstance(databases, str):
            normalized = [databases.strip()] if databases.strip() else []
        else:
            normalized = [str(database).strip() for database in databases if str(database).strip()]
        if not normalized:
            return sorted(supported_for_species & SUPPORTED_COMPLETE_SPECIES_DATABASES)

        selected = []
        unknown = []
        for database in normalized:
            db_name = DATABASE_NAME_BY_KEY.get(database.lower())
            if db_name is None:
                unknown.append(database)
                continue
            if db_name not in selected:
                selected.append(db_name)

        if unknown:
            allowed = ", ".join(sorted(SUPPORTED_ORGANISM_FILES))
            raise ValueError(f"Unknown database(s): {', '.join(unknown)}. Supported database names: {allowed}")

        return selected

    def _download_database(
        self,
        db_name: str,
        tax_id: str,
        species_name: str,
        output_dir: Path,
        output_format: str,
    ) -> SpeciesDatabaseDownloadResult:
        started_at = time.monotonic()
        supported_for_species = get_supported_databases(tax_id)
        if db_name not in supported_for_species:
            result = SpeciesDatabaseDownloadResult(
                database=db_name,
                status="not_supported",
                path=None,
                pair_count=0,
                elapsed_seconds=time.monotonic() - started_at,
                message=f"{db_name} does not support taxonomy ID {tax_id}",
            )
            self._print_database_result(tax_id, result)
            return result

        if db_name not in SUPPORTED_COMPLETE_SPECIES_DATABASES:
            result = SpeciesDatabaseDownloadResult(
                database=db_name,
                status="not_available",
                path=None,
                pair_count=0,
                elapsed_seconds=time.monotonic() - started_at,
                message=f"Complete-species export is not implemented for {db_name}",
            )
            self._print_database_result(tax_id, result)
            return result

        try:
            db_data, expected_pairs = self._load_database_data(db_name, tax_id)
        except SpeciesRemoteDataNotFound:
            result = SpeciesDatabaseDownloadResult(
                database=db_name,
                status="not_available",
                path=None,
                pair_count=0,
                elapsed_seconds=time.monotonic() - started_at,
                message=f"{db_name} species file was not found for taxonomy ID {tax_id}",
            )
            self._print_database_result(tax_id, result)
            return result
        except FileNotFoundError as exc:
            result = SpeciesDatabaseDownloadResult(
                database=db_name,
                status="not_available",
                path=None,
                pair_count=0,
                elapsed_seconds=time.monotonic() - started_at,
                message=str(exc),
            )
            self._print_database_result(tax_id, result)
            return result

        output_path = output_dir / self._output_filename(species_name, tax_id, db_name, output_format)
        progress = _ConsoleProgress(db_name, expected_pairs) if self.show_progress else None
        progress_update = progress.update if progress else None

        if output_format == "mitab":
            written_count = write_species_mitab(db_name, db_data, tax_id, output_path, progress_update=progress_update)
        else:
            written_count = write_species_parquet(
                db_name,
                db_data,
                output_path,
                progress_update=progress_update,
                batch_size=self.parquet_batch_size,
            )

        if progress:
            progress.close(written_count)

        result = SpeciesDatabaseDownloadResult(
            database=db_name,
            status="completed",
            path=str(output_path),
            pair_count=written_count,
            elapsed_seconds=time.monotonic() - started_at,
            message=f"{db_name} exported {written_count} rows",
        )
        self._print_database_result(tax_id, result)
        return result

    def _load_database_data(self, db_name: str, tax_id: str):
        if db_name == "String":
            bundle = ensure_string_species_bundle(tax_id)
            return bundle, int(bundle.get("pair_count", 0))

        if db_name == "IntAct":
            bundle = ensure_intact_species_bundle(tax_id)
            return bundle, int(bundle.get("pair_count", 0))

        expected_pairs = sum(1 for _row in iter_species_database_rows(db_name, tax_id))
        return iter_species_database_rows(db_name, tax_id), expected_pairs

    def _output_filename(self, species_name: str, tax_id: str, db_name: str, output_format: str) -> str:
        safe_species = re.sub(r"[^A-Za-z0-9]+", "_", species_name).strip("_") or tax_id
        extension = "mitab.txt" if output_format == "mitab" else "parquet"
        return f"{safe_species}_{tax_id}_{db_name}.ppi.{extension}"

    def _print_database_result(self, tax_id: str, result: SpeciesDatabaseDownloadResult) -> None:
        if not self.show_progress:
            return
        self._print(
            f"Taxon {tax_id} {result.database}: {result.pair_count} pairs "
            f"in {_format_elapsed(result.elapsed_seconds)} ({result.status})"
        )

    def _print(self, message: str) -> None:
        sys.stderr.write(message + "\n")
        sys.stderr.flush()
