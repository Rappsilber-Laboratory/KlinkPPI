from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.services.species_ppi_api import SpeciesPPIDownloader


def main() -> None:
    downloader = SpeciesPPIDownloader(show_progress=True)

    tax_id = "10090"
    output_format = "parquet"  # "mitab" or "parquet"
    databases = []  # Empty means every supported source for this species. Example: ["String", "IntAct"]

    summary = downloader.download_species(
        tax_id=tax_id,
        output_format=output_format,
        output_dir=PROJECT_ROOT / "api_downloads",
        databases=databases,
    )

    print(
        f"Downloaded {summary.species_name} ({summary.tax_id}): "
        f"{summary.total_pair_count} pairs in {summary.elapsed_seconds:.2f}s"
    )
    for result in summary.results:
        if result.status == "completed":
            print(f"{result.database}: {result.pair_count} pairs in {result.elapsed_seconds:.2f}s -> {result.path}")
        else:
            print(f"{result.database}: {result.status} in {result.elapsed_seconds:.2f}s - {result.message}")


if __name__ == "__main__":
    main()
