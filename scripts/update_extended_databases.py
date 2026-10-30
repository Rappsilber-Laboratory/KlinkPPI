#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import sqlite3
import sys

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HUMAP_URL = "https://humap3.proteincomplexes.org/static/downloads/humap3/humap3_all_ppis_202305.pairsWprob.gz"
HUMAP_DIR = PROJECT_ROOT / "Data" / "HuMap"
HUMAP_SOURCE = HUMAP_DIR / "humap3_all_ppis_202305.pairsWprob.gz"
HUMAP_INDEX = HUMAP_DIR / "humap3.sqlite3"


def download(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        print(f"Using existing {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    handle.write(chunk)
    temporary.replace(destination)


def build_humap(force: bool = False) -> None:
    if HUMAP_INDEX.exists() and HUMAP_INDEX.stat().st_size > 0 and not force:
        print(f"Using existing hu.MAP index: {HUMAP_INDEX}")
        return
    download(HUMAP_URL, HUMAP_SOURCE)
    temporary_index = HUMAP_INDEX.with_suffix(".sqlite3.part")
    if temporary_index.exists():
        temporary_index.unlink()

    connection = sqlite3.connect(temporary_index)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("CREATE TABLE interactions (protein TEXT NOT NULL, partner TEXT NOT NULL, probability REAL NOT NULL)")
    batch = []
    inserted = 0
    with gzip.open(HUMAP_SOURCE, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            columns = line.rstrip("\n").split("\t")
            if len(columns) != 3:
                continue
            protein_a, protein_b, probability = columns
            try:
                score = float(probability)
            except ValueError:
                continue
            batch.extend(((protein_a, protein_b, score), (protein_b, protein_a, score)))
            if len(batch) >= 500_000:
                connection.executemany("INSERT INTO interactions VALUES (?, ?, ?)", batch)
                inserted += len(batch)
                batch.clear()
                print(f"Indexed {inserted:,} directed lookup rows", file=sys.stderr)
    if batch:
        connection.executemany("INSERT INTO interactions VALUES (?, ?, ?)", batch)
        inserted += len(batch)
    connection.execute("CREATE INDEX interactions_protein_idx ON interactions(protein)")
    # hu.MAP contains repeated pairs in a small number of cases. The resolver
    # groups those records and uses their maximum probability.
    connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.executemany("INSERT INTO metadata VALUES (?, ?)", [
        ("source_url", HUMAP_URL),
        ("directed_lookup_row_count", str(inserted)),
        ("source_pair_count", str(inserted // 2)),
    ])
    connection.commit()
    connection.close()
    temporary_index.replace(HUMAP_INDEX)
    print(f"hu.MAP index ready: {HUMAP_INDEX}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and index KlinkPPI extended bulk sources")
    parser.add_argument("--source", choices=["humap", "all"], default="all")
    parser.add_argument("--force", action="store_true", help="Rebuild an existing local index")
    args = parser.parse_args()
    if args.source in {"humap", "all"}:
        build_humap(force=args.force)


if __name__ == "__main__":
    main()
