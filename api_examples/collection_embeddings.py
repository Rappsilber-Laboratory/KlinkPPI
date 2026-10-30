"""Compute PLM scores for an unknown pair, using one or multiple API models.

First run without --pair-index to list unknown pairs in a saved collection.
Then select a pair and optionally pass multiple model IDs with --models.
"""
import argparse
import csv
import json
import math
import re
from pathlib import Path

if __package__:
    from ._common import OUTPUT_DIR, client, progress
else:
    from _common import OUTPUT_DIR, client, progress
from klinkppi import KlinkPPIError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=OUTPUT_DIR / "collection_search.json",
                        help="Saved collection result; used when --job-id is omitted")
    parser.add_argument("--job-id", help="Use a live collection job instead of reading --result")
    parser.add_argument("--pair-index", type=int, help="Choose an unknown pair from the printed list")
    parser.add_argument("--models", nargs="+", default=["esm2-8m"],
                        help="One or multiple supported model IDs (default: esm2-8m)")
    parser.add_argument("--list-models", action="store_true", help="Print supported models and exit")
    parser.add_argument("--max-wait", type=float, default=3600, help="Polling deadline in seconds")
    args = parser.parse_args(argv)
    if args.max_wait <= 0 or not math.isfinite(args.max_wait):
        parser.error("--max-wait must be positive and finite")
    with client() as api:
        catalog = api.embedding_models()
        if args.list_models:
            print("Supported embedding models:", *catalog["models"], sep="\n")
            return
        if len(args.models) != len(set(args.models)) or any(model not in catalog["models"] for model in args.models):
            parser.error("--models must contain distinct supported IDs; use --list-models")
        job_id = args.job_id or json.loads(args.result.read_text(encoding="utf-8"))["job_id"]
        # Refresh the live job: saved exports survive backend restarts, jobs do not.
        job = api.get_collection(job_id)
        if job["status"] != "completed" or job["mode"] != "induced":
            parser.error("Embedding comparisons require a completed induced collection")
        pairs = api.unknown_pairs(job)
        for index, pair in enumerate(pairs):
            print(index, pair["source"]["gene"], pair["source"]["id"], "↔", pair["target"]["gene"], pair["target"]["id"])
        if args.pair_index is None:
            print("Choose --pair-index to compute embeddings; --models accepts multiple model IDs.")
            return
        if not 0 <= args.pair_index < len(pairs):
            parser.error("--pair-index is outside the printed unknown-pair list")
        pair = pairs[args.pair_index]
        source, target = pair["source"], pair["target"]
        pair_name = "_".join(re.sub(r"[^a-zA-Z0-9._-]+", "_", protein.get("gene") or protein["id"])
                             for protein in (source, target))
        json_path = OUTPUT_DIR / f"{pair_name}_plm_scores.json"
        tsv_path = OUTPUT_DIR / f"{pair_name}_plm_scores.tsv"
        # The API accepts multiple models per request; the UI selects one model.
        # The server computes models sequentially and reports progress and runtime.
        task = api.start_embedding(job_id, source["id"], target["id"], models=args.models)
        api.export_json(task, json_path)
        print("Embedding task:", task["embedding_id"], "Models:", ", ".join(args.models))
        try:
            task = api.wait_embedding(job_id, task, max_wait=args.max_wait, on_progress=progress)
        except KlinkPPIError as error:
            if error.job is not None:
                api.export_json(error.job, json_path)
            raise
        api.export_json(task, json_path)
        # Same two columns and full-precision values as the web UI download.
        tsv_path.parent.mkdir(parents=True, exist_ok=True)
        with tsv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(["metric", "value"])
            writer.writerows(task["result"]["scores"].items())
        print(f"Total runtime: {task['runtime_seconds']:.2f} s (queue time excluded)")
        for model, seconds in task["result"]["model_runtime_seconds"].items():
            print(f"  {model}: {seconds:.2f} s")
        print("Scores TSV:", tsv_path)
        print("Scores, explanations and runtime JSON:", json_path)
        print(task["result"]["interpretation"])


if __name__ == "__main__":
    main()
