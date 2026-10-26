"""Data analysis matching the collection web UI, without rendering dependencies."""
from collections import Counter
from itertools import combinations
from statistics import mean, median


def analyze(job, databases=None, evidence_type="all", method="", score_database="", min_score=None, min_publications=0):
    if job["status"] != "completed":
        raise ValueError("Analysis requires a completed collection.")
    databases = list(dict.fromkeys(job["databases"] if databases is None else databases))
    if any(db not in job["databases"] for db in databases):
        raise ValueError("Choose databases included in this collection.")
    if score_database and score_database not in job["databases"]:
        raise ValueError("Choose a score database included in this collection.")
    raw = job["graph"]
    active = {n["id"] for n in raw["nodes"] if n.get("input")}
    edges = []
    for edge in raw["edges"]:
        evidence = [ev for ev in edge.get("evidence", [])
                    if ev["database"] in databases
                    and (evidence_type == "all" or ev.get("type") == evidence_type)
                    and (not method or any(method.lower() in value.lower() for value in ev.get("methods", [])))
                    and (not score_database or ev["database"] != score_database or min_score is None
                         or (ev.get("score") is not None and ev["score"] >= min_score))]
        publications = list(dict.fromkeys(p for ev in evidence for p in ev.get("publications", [])))
        if not evidence or len(publications) < min_publications:
            continue
        edges.append({**edge, "evidence": evidence, "publications": publications,
                      "databases": list(dict.fromkeys(ev["database"] for ev in evidence))})
        active.update((edge["source"], edge["target"]))
    graph = {**raw, "nodes": [n for n in raw["nodes"] if n["id"] in active], "edges": edges}
    filters = {"databases": databases, "type": evidence_type, "method": method,
               "scoreDatabase": score_database, "minScore": "" if min_score is None else min_score,
               "minPublications": min_publications}
    return {**graph, "statistics": statistics(graph, job["databases"]),
            "analysis": {"species": job["species"], "tax_id": job["tax_id"], "mode": job["mode"],
                         "filters": filters, "resolution": job.get("resolution", []),
                         "selections": job.get("selections", {}), "warnings": job.get("warnings", [])}}


def statistics(graph, databases):
    adj = {n["id"]: set() for n in graph["nodes"]}
    node_dbs = {key: set() for key in adj}
    db_edges = {db: set() for db in databases}
    distributions = {db: {} for db in databases}
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        adj[a].add(b)
        adj[b].add(a)
        for db in edge["databases"]:
            db_edges[db].add(edge["id"])
            node_dbs[a].add(db)
            node_dbs[b].add(db)
        for ev in edge["evidence"]:
            scores = ev.get("scores")
            if scores is None:
                scores = {} if ev.get("score") is None else {ev.get("score_name") or "score": ev["score"]}
            for name, value in scores.items():
                distributions[ev["database"]].setdefault(name, []).append(value)
    visited, components = set(), []
    for key in adj:
        if key in visited:
            continue
        visited.add(key)
        stack, size = [key], 0
        while stack:
            current = stack.pop()
            size += 1
            neighbors = adj[current] - visited
            visited.update(neighbors)
            stack.extend(neighbors)
        components.append(size)
    # Sparse degree-oriented triangle enumeration, as in the web worker.
    forward = {a: {b for b in ns if (len(ns), a) < (len(adj[b]), b)} for a, ns in adj.items()}
    triangles = Counter()
    for a, ns in forward.items():
        for b in ns:
            for c in ns & forward[b]:
                triangles.update((a, b, c))
    degrees = []
    for node in graph["nodes"]:
        key = node["id"]
        degree = len(adj[key])
        degrees.append({**node, "degree": degree,
                        "clustering": 0 if degree < 2 else 2 * triangles[key] / (degree * (degree - 1)),
                        "databases": [db for db in databases if db in node_dbs[key]]})
    degrees.sort(key=lambda n: (-n["degree"], n["id"]))
    by_database = [{"database": db, "edges": len(db_edges[db]),
                    "unique": sum(e["databases"] == [db] for e in graph["edges"]),
                    "shared": sum(len(e["databases"]) > 1 and db in e["databases"] for e in graph["edges"])}
                   for db in databases]
    jaccard = []
    for a, b in combinations(databases, 2):
        intersection, union = len(db_edges[a] & db_edges[b]), len(db_edges[a] | db_edges[b])
        jaccard.append({"a": a, "b": b, "intersection": intersection, "union": union,
                        "value": intersection / union if union else None})
    scores = []
    for db, series in distributions.items():
        for name, values in series.items():
            low, high = min(values), max(values)
            bins = [0] * 8
            for value in values:
                bins[0 if high == low else min(7, int((value - low) / (high - low) * 8))] += 1
            scores.append({"database": db, "name": name, "count": len(values), "min": low, "max": high,
                           "median": median(values), "mean": mean(values), "bins": bins})
    return {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
            "components": sorted(components, reverse=True),
            "clustering": mean(n["clustering"] for n in degrees) if degrees else 0,
            "degrees": degrees, "hubs": [n for n in degrees if n["degree"]][:10],
            "byDatabase": by_database, "jaccard": jaccard, "scores": scores,
            "sharedInteractors": [n for n in degrees if len(n["databases"]) > 1][:10],
            "databaseOnlyInteractors": {db: [n for n in degrees if n["databases"] == [db]][:10] for db in databases}}
