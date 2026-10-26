"""Portable network exports and external-search launchers (Python standard library)."""
from html import escape
from itertools import combinations
import json
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET


def unknown_pairs(job):
    """Use the full induced result before display filters, exactly as the web app."""
    if job.get("status") != "completed" or job.get("mode") != "induced":
        raise ValueError("Unknown pairs require a completed induced collection.")
    graph = job["graph"]
    nodes = {n["id"]: n for n in graph["nodes"] if n.get("input") and not n.get("unresolved")}
    known = {frozenset((e["source"], e["target"])) for e in graph["edges"]}
    return [{"source": a, "target": b} for a, b in combinations(nodes.values(), 2)
            if frozenset((a["id"], b["id"])) not in known]


def export_network(analysis, path, output_format="json"):
    """Export an API analysis (graph + metadata); SIF retains topology only."""
    nodes, edges = analysis["nodes"], analysis["edges"]
    if output_format == "json":
        content = json.dumps(analysis, indent=2, ensure_ascii=False)
    elif output_format == "sif":
        linked = {key for e in edges for key in (e["source"], e["target"])}
        content = "\n".join([f"{e['source']}\tinteracts_with\t{e['target']}" for e in edges]
                            + [n["id"] for n in nodes if n["id"] not in linked]) + "\n"
    elif output_format == "graphml":
        ns = "http://graphml.graphdrawing.org/xmlns"
        ET.register_namespace("", ns)
        tag = lambda name: f"{{{ns}}}{name}"
        root = ET.Element(tag("graphml"))
        for key, scope in [(k, "node") for k in ("label", "uniprot", "species", "input", "unresolved")] + [(k, "edge") for k in ("databases", "evidence")]:
            ET.SubElement(root, tag("key"), {"id": key, "for": scope, "attr.name": key, "attr.type": "string"})
        graph = ET.SubElement(root, tag("graph"), id="KlinkPPI", edgedefault="undirected")
        for node in nodes:
            elem = ET.SubElement(graph, tag("node"), id=node["id"])
            values = {"label": node.get("gene", node["id"]), "uniprot": "" if node.get("unresolved") else node["id"],
                      "species": node.get("species", ""), "input": str(bool(node.get("input"))).lower(),
                      "unresolved": str(bool(node.get("unresolved"))).lower()}
            for key, value in values.items():
                ET.SubElement(elem, tag("data"), key=key).text = str(value)
        for edge in edges:
            elem = ET.SubElement(graph, tag("edge"), id=edge["id"], source=edge["source"], target=edge["target"])
            ET.SubElement(elem, tag("data"), key="databases").text = "|".join(edge["databases"])
            ET.SubElement(elem, tag("data"), key="evidence").text = json.dumps(edge["evidence"])
        content = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode()
    elif output_format == "cx":
        ids = {node["id"]: index for index, node in enumerate(nodes)}
        metadata = analysis.get("analysis", {})
        aspects = {
            "nodes": [{"@id": ids[n["id"]], "n": n.get("gene", n["id"]),
                       "r": n.get("gene", n["id"]) if n.get("unresolved") else f"uniprot:{n['id']}"} for n in nodes],
            "edges": [{"@id": i, "s": ids[e["source"]], "t": ids[e["target"]], "i": "interacts_with"} for i, e in enumerate(edges)],
            "nodeAttributes": [{"po": ids[n["id"]], "n": key, "v": str(n.get(key, ""))}
                               for n in nodes for key in ("species", "tax_id", "input", "unresolved")],
            "edgeAttributes": [attr for i, e in enumerate(edges) for attr in (
                {"po": i, "n": "databases", "v": e["databases"], "d": "list_of_string"},
                {"po": i, "n": "evidence", "v": json.dumps(e["evidence"])})],
            "networkAttributes": [{"n": "name", "v": f"KlinkPPI {metadata.get('species', '')} {metadata.get('mode', '')}"},
                                  {"n": "analysis", "v": json.dumps(metadata)}],
        }
        content = json.dumps([{"numberVerification": [{"longNumber": 281474976710655}]},
            {"metaData": [{"name": k, "version": "1.0", "elementCount": len(v), "consistencyGroup": 1} for k, v in aspects.items()]},
            *[{k: v} for k, v in aspects.items()], {"status": [{"error": "", "success": True}]}], indent=2)
    else:
        raise ValueError("output_format must be json, graphml, sif or cx.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_protein_search_page(protein, species, path):
    """Save a launcher. User clicks to POST FASTA to BLAST and then selects settings.

    The sequence is kept in a local file until the user submits the form. This
    does not run BLAST or Foldseek and does not depend on clipboard permission.
    """
    fields = {"PAGE": "Proteins", "PROGRAM": "blastp", "CMD": "Web", "PAGE_TYPE": "BlastSearch",
              "QUERY": protein["fasta"],
              "JOB_TITLE": f"KlinkPPI: {protein['gene']} ({protein['accession']}) — {species}"}
    inputs = "".join(f'<input type="hidden" name="{key}" value="{escape(value, quote=True)}">' for key, value in fields.items())
    url = "https://www.alphafold.ebi.ac.uk/entry/" + quote(protein["accession"], safe="")
    content = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>KlinkPPI protein searches</title>
<h1>{escape(protein['gene'])} ({escape(protein['accession'])})</h1>
<form method="post" action="https://blast.ncbi.nlm.nih.gov/Blast.cgi" target="_blank" rel="noopener noreferrer">
{inputs}<button type="submit">Search BLASTP ↗</button></form>
<p>Choose settings and start the search on NCBI Protein BLAST.</p>
<p><a href="{url}" target="_blank" rel="noopener noreferrer">Find similar structures ↗</a>:
choose “Similar structures” on AlphaFold to search with Foldseek. If no model is available,
copy the FASTA below and paste it into the <a href="https://search.foldseek.com/" target="_blank" rel="noopener noreferrer">Foldseek server</a>.</p>
<label>FASTA (select and copy)<br><textarea rows="12" cols="80" readonly>{escape(protein['fasta'])}</textarea></label></html>'''
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
