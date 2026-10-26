"""Bounded background pairwise alignments of on-demand UniProt sequences."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import lru_cache
from threading import Lock
from time import time
from uuid import uuid4

import Bio
from Bio import Align
from Bio.Align import substitution_matrices
import requests

from app.services.collection_go import validate_unknown_pair

API = "https://rest.uniprot.org/uniprotkb"
MATRIX = substitution_matrices.load("BLOSUM62")
PARAMETERS = {
    "algorithm": "Gotoh global alignment (Needleman–Wunsch with affine gaps)",
    "mode": "global", "matrix": "BLOSUM62", "gap_open": 10, "gap_extend": 0.5,
    "gap_cost": "10 + (gap length − 1) × 0.5", "terminal_gaps": "penalized equally",
    "implementation": f"Biopython {Bio.__version__} PairwiseAligner",
    "identity_denominator": "all alignment columns, including gaps",
    "ambiguous_residues": "U and O scored as X; B, Z and X use BLOSUM62 scores",
}
MAX_CELLS = 25_000_000
MAX_LENGTH = 20_000
MAX_TASKS = 64
TTL = 3600
TASKS = {}
LOCK = Lock()
POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pair-alignment")


class SequenceLookupError(Exception):
    pass


@lru_cache(maxsize=512)
def protein_sequence(accession, tax_id, cache_hour):
    try:
        response = requests.get(f"{API}/{accession}.json", params={"fields": "accession,organism_id,sequence"}, timeout=25)
        response.raise_for_status()
        entry = response.json()
        if str(entry.get("organism", {}).get("taxonId")) != str(tax_id):
            raise SequenceLookupError(f"UniProt species does not match for {accession}.")
        if entry.get("primaryAccession") != accession:
            raise SequenceLookupError(f"UniProt returned a different accession for {accession}. Resolve your inputs again.")
        sequence = entry.get("sequence", {}).get("value", "").upper()
        if not sequence:
            raise SequenceLookupError(f"UniProt did not report a sequence for {accession}.")
        if len(sequence) > MAX_LENGTH:
            raise SequenceLookupError(f"{accession} exceeds the interactive limit of {MAX_LENGTH:,} residues.")
        if any(residue not in MATRIX.alphabet + "UO" for residue in sequence):
            raise SequenceLookupError(f"The sequence for {accession} contains unsupported residue symbols.")
        return sequence
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SequenceLookupError(f"Could not fetch the UniProt sequence for {accession}. Please retry.") from exc


def align_sequences(source_sequence, target_sequence):
    if not source_sequence or not target_sequence:
        raise ValueError("Both protein sequences must contain residues.")
    if len(source_sequence) * len(target_sequence) > MAX_CELLS:
        raise ValueError("This pair is too large for interactive alignment (25 million sequence-position pairs maximum).")
    aligner = Align.PairwiseAligner(mode="global", substitution_matrix=MATRIX, open_gap_score=-10, extend_gap_score=-0.5)
    # Selenocysteine and pyrrolysine do not have dedicated BLOSUM62 scores.
    # Score them as X while retaining their original letters in the output.
    translation = str.maketrans({"U": "X", "O": "X"})
    alignment = aligner.align(source_sequence.translate(translation), target_sequence.translate(translation))[0]
    sequences = [source_sequence, target_sequence]
    rows = [[], []]
    for index in range(alignment.coordinates.shape[1] - 1):
        starts, ends = alignment.coordinates[:, index], alignment.coordinates[:, index + 1]
        width = max(ends - starts)
        for side in (0, 1):
            rows[side].append(sequences[side][starts[side]:ends[side]] if ends[side] > starts[side] else "-" * width)
    left, right = ["".join(row) for row in rows]
    identities = sum(a == b and a != "-" for a, b in zip(left, right))
    gaps = sum(a == "-" or b == "-" for a, b in zip(left, right))
    return {"score": float(alignment.score), "identity_percent": 100 * identities / len(left),
            "identities": identities, "alignment_length": len(left), "gap_columns": gaps,
            "source_length": len(source_sequence), "target_length": len(target_sequence),
            "aligned_source": left, "aligned_target": right, "parameters": deepcopy(PARAMETERS)}


def snapshot(task_id, job_id):
    with LOCK:
        task = TASKS[task_id]
        if task["job_id"] != job_id:
            raise KeyError(task_id)
        return deepcopy(task)


def update(task_id, **values):
    with LOCK:
        TASKS[task_id].update(values)


def start(job, source, target):
    validate_unknown_pair(job, source, target)
    now = time()
    with LOCK:
        for key in list(TASKS):
            if now - TASKS[key]["created_at"] > TTL and TASKS[key]["status"] in {"completed", "failed"}:
                del TASKS[key]
        for task in TASKS.values():
            if (task["job_id"] == job["job_id"] and task["generation"] == job["created_at"]
                    and task["source"] == source and task["target"] == target and task["status"] in {"queued", "running"}):
                return deepcopy(task)
        if len(TASKS) >= MAX_TASKS:
            raise RuntimeError("Alignment capacity reached. Please retry after previous alignments expire.")
        task_id = uuid4().hex
        TASKS[task_id] = {"alignment_id": task_id, "job_id": job["job_id"], "generation": job["created_at"],
                          "created_at": now, "source": source, "target": target, "status": "queued",
                          "progress": "Waiting to fetch sequences…", "completed_steps": 0, "total_steps": 3,
                          "result": None, "error": None}
    POOL.submit(_run, task_id, job["tax_id"])
    return snapshot(task_id, job["job_id"])


def _run(task_id, tax_id):
    try:
        task = snapshot(task_id, TASKS[task_id]["job_id"])
        hour = int(time() // TTL)
        update(task_id, status="running", progress=f"Fetching UniProt sequence for {task['source']}…")
        left = protein_sequence(task["source"], tax_id, hour)
        update(task_id, completed_steps=1, progress=f"Fetching UniProt sequence for {task['target']}…")
        right = protein_sequence(task["target"], tax_id, hour)
        update(task_id, completed_steps=2, progress="Computing global alignment…")
        result = align_sequences(left, right)
        update(task_id, completed_steps=3, progress="Alignment complete", status="completed", result=result)
    except Exception as exc:
        update(task_id, status="failed", progress="Alignment failed", error=str(exc))
