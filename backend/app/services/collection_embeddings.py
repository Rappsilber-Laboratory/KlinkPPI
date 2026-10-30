"""On-demand, bounded embedding comparisons using the bundled PLMs framework."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Lock
from time import perf_counter, time
from uuid import uuid4

from app.services.collection_alignment import protein_sequence, TTL
from app.services.collection_go import validate_unknown_pair

# Deliberately match examples/test_two_seqs_mem.py; larger framework models are not exposed.
MODELS = ("esm2-8m", "esm2-35m", "esm2-150m", "esm2-650m", "esm1b-650m",
          "esm1v-650m-1", "esm1v-650m-2", "esm1v-650m-3", "esm1v-650m-4", "esm1v-650m-5",
          "esmc-300m", "esmc-600m")
METRICS = {
    "sequence.length_ratio": "Shorter sequence length divided by longer length (0–1); higher means more similar lengths.",
    "sequence.sequence_identity": "Identical residues divided by all columns of a global alignment with match +1, mismatch −1 and gap −1 (0–1); higher means more sequence identity.",
    "sequence.kmer_jaccard": "Intersection divided by union of unique amino-acid 3-mers (0–1); higher means more shared short sequence fragments.",
    "sequence.blosum62_global": "Global BLOSUM62 alignment score with linear gap −4, divided by the geometric mean of self-alignment scores; higher means more sequence similarity.",
    "sequence.blosum62_local": "Best local BLOSUM62 alignment score with linear gap −4, divided by the geometric mean of self-alignment scores; higher means a stronger shared region.",
}
VECTOR_DESCRIPTIONS = {
    "cosine_similarity": "Cosine of the angle between vectors (−1 to 1); higher means more similar embedding directions.",
    "cosine_distance": "One minus cosine similarity (0–2); lower means more similar embedding directions.",
    "angular_distance": "Angle between vectors divided by pi (0–1); lower means more similar embedding directions.",
    "correlation_distance": "One minus cosine similarity after centering vector components (0–2); lower means more similar component patterns. Constant vectors use similarity zero.",
    "euclidean_distance": "Straight-line distance between L2-normalized vectors (0–2); lower means more similar embeddings.",
}
for method in ("mean", "max"):
    pooling = "Mean of residue embeddings" if method == "mean" else "Component-wise maximum of residue embeddings"
    for metric, description in VECTOR_DESCRIPTIONS.items():
        METRICS[f"{method}.{metric}"] = f"{pooling}, then L2 normalization. {description}"
METRICS.update({
    "residue.global_alignment": "Global alignment of residue cosine similarities with gap −0.5, divided by alignment path length; higher means stronger similarity across the full proteins.",
    "residue.local_alignment": "Best local alignment of residue cosine similarities with gap −0.5, divided by its path length; higher means a stronger matching region. Coverage is not reflected in this value.",
    "residue.best_match": "Average of each residue's best cosine match in the other protein, averaged in both directions; higher means more similar residue embeddings, without preserving order.",
    "residue.optimal_transport": "One minus balanced entropic transport cost using residue cosine distance, uniform residue mass, epsilon 0.1 and 100 Sinkhorn iterations; higher means more similar residue distributions.",
})
TASKS = {}
LOCK = Lock()
MAX_TASKS = 32
# One model task at a time bounds simultaneous accelerator/model memory usage.
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pair-embedding")


def catalog():
    return {"models": list(MODELS), "metrics": METRICS,
            "note": "Embedding similarity does not establish a protein interaction. First use downloads model weights. Sequences are never truncated."}


def snapshot(embedding_id, job_id):
    with LOCK:
        task = TASKS[embedding_id]
        if task["job_id"] != job_id:
            raise KeyError(embedding_id)
        result = deepcopy(task)
    if result["status"] == "running":
        result["runtime_seconds"] = max(0, time() - result["started_at"])
    return result


def update(embedding_id, **values):
    with LOCK:
        TASKS[embedding_id].update(values)


def start(job, source, target, models):
    validate_unknown_pair(job, source, target)
    if not models or len(models) != len(set(models)) or any(model not in MODELS for model in models):
        raise ValueError("Select one or more distinct supported embedding models from /collection/embedding-models.")
    # Stable order makes duplicate requests independent of checkbox order.
    models = [model for model in MODELS if model in models]
    now = time()
    with LOCK:
        for key in list(TASKS):
            if now - TASKS[key]["created_at"] > TTL and TASKS[key]["status"] in {"completed", "failed"}:
                del TASKS[key]
        for task in TASKS.values():
            if (task["job_id"] == job["job_id"] and task["generation"] == job["created_at"]
                    and {task["source"], task["target"]} == {source, target}
                    and task["models"] == models and task["status"] in {"queued", "running"}):
                return deepcopy(task)
        if len(TASKS) >= MAX_TASKS:
            raise RuntimeError("Embedding capacity reached. Retry after previous tasks expire.")
        embedding_id = uuid4().hex
        TASKS[embedding_id] = {
            "embedding_id": embedding_id, "job_id": job["job_id"], "generation": job["created_at"],
            "source": source, "target": target, "models": models, "created_at": now,
            "status": "queued", "progress": "Waiting for embedding worker…", "completed_steps": 0,
            "total_steps": 2 + len(models), "runtime_seconds": 0, "result": None, "error": None,
        }
    POOL.submit(_run, embedding_id, job["tax_id"])
    return snapshot(embedding_id, job["job_id"])


def score_model(left, right, model):
    # Use the framework's public API/metrics so a separately cloned upstream
    # framework works without KlinkPPI-specific additions to its wheel.
    from plms_framework import Pipeline
    from plms_framework.serialization import request_from_dict
    from plms_framework.metrics import (SEQUENCE_METRICS, VECTOR_METRICS, align_similarity,
                                        residue_similarity, sinkhorn_similarity, symmetric_best_match)
    request = request_from_dict({
        "models": [model],
        "sequences": [{"id": "reference", "sequence": left}, {"id": "target", "sequence": right}],
        "representations": [{"method": method, "normalize": "l2"} for method in ("mean", "max", "residue")],
        "execution": {"device": "auto", "precision": "auto", "on_long_sequence": "error", "allow_partial": False},
    }, compare=False)
    output = Pipeline().embed(request)["models"][model]
    representations = {(item["method"], item["sequence_id"]): item["values"] for item in output["representations"]}
    scores = {f"sequence.{name}": metric(left, right) for name, metric in SEQUENCE_METRICS.items()}
    for method in ("mean", "max"):
        for name, metric in VECTOR_METRICS.items():
            scores[f"{model}.{method}.{name}"] = metric(representations[(method, "reference")], representations[(method, "target")])
    similarity = residue_similarity(representations[("residue", "reference")], representations[("residue", "target")])
    scores.update({
        f"{model}.residue.global_alignment": align_similarity(similarity, local=False)["normalized_score"],
        f"{model}.residue.local_alignment": align_similarity(similarity, local=True)["normalized_score"],
        f"{model}.residue.best_match": symmetric_best_match(similarity),
        f"{model}.residue.optimal_transport": sinkhorn_similarity(similarity)["similarity"],
    })
    return scores


def validate_lengths(left, right, models):
    from plms_framework.registry import default_registry
    for model in models:
        limit = default_registry.manifest(model).max_native_length
        if limit and max(len(left), len(right)) > limit:
            raise ValueError(f"{model} supports at most {limit} residues per sequence; this pair has {len(left)} and {len(right)}. Sequences were not truncated.")


def _run(embedding_id, tax_id):
    started = perf_counter()
    try:
        with LOCK:
            task = deepcopy(TASKS[embedding_id])
        update(embedding_id, status="running", started_at=time(), progress=f"Fetching UniProt sequence for {task['source']}…")
        hour = int(time() // TTL)
        left = protein_sequence(task["source"], tax_id, hour)
        update(embedding_id, completed_steps=1, progress=f"Fetching UniProt sequence for {task['target']}…")
        right = protein_sequence(task["target"], tax_id, hour)
        validate_lengths(left, right, task["models"])
        scores, runtimes = {}, {}
        for index, model in enumerate(task["models"]):
            update(embedding_id, completed_steps=2 + index, progress=f"Computing {model} (first use may download weights)…")
            model_started = perf_counter()
            scores.update(score_model(left, right, model))
            runtimes[model] = perf_counter() - model_started
        descriptions = {key: METRICS[key if key.startswith('sequence.') else key.split('.', 1)[1]] for key in scores}
        update(embedding_id, status="completed", progress="Embedding comparison complete", completed_steps=task["total_steps"],
               result={"scores": scores, "descriptions": descriptions, "model_runtime_seconds": runtimes,
                       "source_length": len(left), "target_length": len(right), "normalization": "l2",
                       "interpretation": "These scores measure sequence or embedding similarity; they do not establish a protein interaction."})
    except Exception as exc:
        message = str(exc)
        if isinstance(exc, ImportError):
            message = "Embedding backend is unavailable. Run npm run setup with Python 3.12+. " + message
        update(embedding_id, status="failed", progress="Embedding comparison failed", error=message)
    finally:
        update(embedding_id, runtime_seconds=perf_counter() - started)
