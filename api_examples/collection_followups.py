"""Analyze a saved collection; inspect unknown pairs, sequences, GO and alignments."""
import argparse
import json
from pathlib import Path
if __package__:
    from ._common import OUTPUT_DIR, client, progress
else:
    from _common import OUTPUT_DIR, client, progress
from klinkppi import KlinkPPIError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=OUTPUT_DIR / "collection_search.json")
    parser.add_argument("--pair-index", type=int, help="Explicitly choose an unknown pair from the printed list")
    args = parser.parse_args(argv)
    saved = json.loads(args.result.read_text())
    with client() as api:
        # Followups need a live job in the same server process. Collection jobs
        # expire after one hour; restart/expiration requires a new collection.
        job = api.get_collection(saved["job_id"])
        # Same filter rules as the web UI: score cutoffs affect only that source's
        # evidence; other sources may still support the pair. Isolated inputs stay.
        filtered = api.collection_analysis(job["job_id"], databases=job["databases"],
            evidence_type="all", method="", score_database="String" if "String" in job["databases"] else "",
            min_score=0.7, min_publications=0)
        api.export_network(filtered, OUTPUT_DIR / "collection_filtered.json")
        print("Filtered statistics:", filtered["statistics"])
        if job["mode"] != "induced":
            print("Unknown pair comparisons require an induced collection.")
            return
        # Always enumerate unknown pairs from the full result before filtering.
        pairs = api.unknown_pairs(job)
        api.export_json(pairs, OUTPUT_DIR / "unknown_pairs.json")
        for index, pair in enumerate(pairs):
            print(index, pair["source"]["gene"], pair["source"]["id"], "↔", pair["target"]["gene"], pair["target"]["id"])
        if args.pair_index is None:
            print("Choose --pair-index to fetch sequences, GO annotations and an alignment on demand.")
            return
        if not 0 <= args.pair_index < len(pairs):
            parser.error("--pair-index is outside the printed unknown-pair list")
        pair = pairs[args.pair_index]
        source, target = pair["source"]["id"], pair["target"]["id"]
        # Each independent lookup can fail/retry without discarding other results.
        for accession in (source, target):
            try:
                protein = api.protein_sequence(job["job_id"], accession)
                fasta_path = OUTPUT_DIR / f"{accession}.fasta"
                fasta_path.parent.mkdir(parents=True, exist_ok=True)
                fasta_path.write_text(protein["fasta"], encoding="utf-8")
                # Open this local HTML file, then click Search BLASTP. It uses a
                # form POST (long sequences supported); you configure/start BLAST.
                api.write_protein_search_page(protein, job["species"], OUTPUT_DIR / f"{accession}_searches.html")
            except KlinkPPIError as error:
                print(accession, error, "Rerun this command to retry.")
        try:
            api.export_json(api.shared_go(job["job_id"], source, target), OUTPUT_DIR / "shared_go.json")
            # Exact shared GO IDs, no ancestor expansion; this is not PPI evidence.
        except KlinkPPIError as error:
            print("GO:", error)
        try:
            task = api.align_pair(job["job_id"], source, target, on_progress=progress)
            api.export_json(task, OUTPUT_DIR / "pair_alignment.json")
            print("Alignment:", task["result"])
            # Result includes aligned sequences, score, identity, gaps and all
            # parameters. Failed or oversized alignments can be retried separately.
        except KlinkPPIError as error:
            print("Alignment:", error)


if __name__ == "__main__":
    main()
