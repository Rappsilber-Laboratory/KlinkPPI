#!/usr/bin/env python3
"""Prepare a public KlinkPPI server so users never install or preprocess anything.

Run once after deployment (and after data updates) from the repository root:

    .venv/bin/python scripts/prepare_server.py            # data + example result
    .venv/bin/python scripts/prepare_server.py --models   # also pre-download PLM weights
    .venv/bin/python scripts/prepare_server.py --check    # report readiness only

Steps (each is skipped when its output already exists):
  1. hu.MAP 3.0 SQLite index           (scripts/update_extended_databases.py)
  2. HuRI Ensembl -> UniProt mapping   (scripts/preprocess_huri_uniprot.py)
  3. BioGRID SQLite lookup index       (built from the bundled MITAB file)
  4. Complex Portal caches for human and common model organisms
  5. Embedding model weights           (--models; avoids a slow first request)
  6. The permanent example result used by the tutorial (--rebuild-example forces it)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("KLINKPPI_BUILD_EXAMPLE", "0")  # built explicitly below

MODEL_ORGANISMS = ["9606", "10090", "10116", "7227", "6239", "559292", "284812", "3702", "7955", "83333"]


def step(title):
    print(f"\n== {title}")


def run_script(*args):
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def report():
    from app.main import data_readiness
    readiness = data_readiness()
    print("\nReadiness:")
    for name, ready in readiness["local_sources"].items():
        print(f"  {'OK     ' if ready else 'MISSING'} {name}")
    print(f"  {'OK     ' if readiness['embedding_backend'] else 'MISSING'} embedding backend (plms_framework)")
    print(f"  {'OK     ' if readiness['example_result'] == 'completed' else 'MISSING'} example result ({readiness['example_result']})")
    return all(readiness["local_sources"].values()) and readiness["embedding_backend"] and readiness["example_result"] == "completed"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="only report readiness")
    parser.add_argument("--models", action="store_true", help="pre-download all enabled embedding models")
    parser.add_argument("--rebuild-example", action="store_true", help="recompute the tutorial example result")
    args = parser.parse_args()
    if args.check:
        sys.exit(0 if report() else 1)

    step("1. hu.MAP 3.0 index")
    run_script("scripts/update_extended_databases.py", "--source", "humap")

    step("2. HuRI UniProt mapping")
    if (ROOT / "Data" / "HuRI" / "HuRI_uniprot.tsv").exists():
        print("Using existing Data/HuRI/HuRI_uniprot.tsv")
    else:
        run_script("scripts/preprocess_huri_uniprot.py")

    step("3. BioGRID lookup index")
    from app.services.biogrid_index import ensure_biogrid_index
    print(f"Index ready: {ensure_biogrid_index()}")

    step("4. Complex Portal caches")
    from app.services.resolve_complex_portal import ensure_complex_portal_file
    from app.services.species_index import get_supported_databases
    for tax_id in MODEL_ORGANISMS:
        if "ComplexPortal" not in get_supported_databases(tax_id):
            continue
        try:
            print(f"  {tax_id}: {ensure_complex_portal_file(tax_id)}")
        except Exception as exc:  # optional: the resolver retries on first use
            print(f"  {tax_id}: skipped ({exc})")

    if args.models:
        step("5. Embedding model weights")
        from app.services import collection_embeddings
        for model in collection_embeddings.ENABLED_MODELS:
            print(f"  {model} ...", flush=True)
            collection_embeddings.score_model("MKTAYIAKQRQISFVKSHFSRQ", "MKTAYIAKQRQISFVKSHFSRA", model)
    else:
        step("5. Embedding model weights: skipped (use --models)")

    step("6. Example result for the tutorial")
    from app.main import resolve_collection_database
    from app.services import collection_search
    from app.services.species_index import get_species_by_tax_id
    collection_search.configure(resolve_collection_database)
    databases = [db for db in collection_search.EXAMPLE_DATABASES if db in get_supported_databases("9606")]
    job = collection_search.ensure_example(resolve_collection_database, get_species_by_tax_id("9606")["display_name"],
                                           databases=databases, force=args.rebuild_example)
    print(f"Example result: {job['status']} ({len((job.get('graph') or {}).get('edges', []))} edges)")
    for warning in job.get("warnings", []):
        print(f"  warning: {warning}")

    sys.exit(0 if report() else 1)


if __name__ == "__main__":
    main()
