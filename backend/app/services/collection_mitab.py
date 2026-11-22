"""PSI-MI TAB export of batch and PPI search networks.

One row per evidence record, using the same standard columns as the single
search export. Source scores keep their original database scales.
"""
from app.services.populate_mitab import (COMMON_COLUMNS, EXTENDED_SOURCE_NAMES, _format_biogrid_type,
                                         _format_methods, _join, _pubmed_values)

SOURCE_DATABASES = {
    "String": 'psi-mi:"MI:1014"(string)',
    "IntAct": 'psi-mi:"MI:0469"(intact)',
    "BioGrid": 'psi-mi:"MI:0463"(biogrid)',
    "Predictomes": "predictomes",
    "HuRI": "huri",
    "Corum": "corum",
    **EXTENDED_SOURCE_NAMES,
}


def _interactor(node):
    return f"uniprotkb:{node['id']}"


def _alias(node):
    gene = node.get("gene")
    return f"uniprotkb:{gene}(gene name)" if gene and gene != node["id"] else "-"


def _confidence(ev):
    prefix = ev["database"].lower()
    values = [f"{prefix}-{name}:{value}" for name, value in (ev.get("scores") or {}).items()]
    if not values and ev.get("score") is not None:
        values.append(f"{prefix}-{ev.get('score_name') or 'score'}:{ev['score']}")
    values.append(f"klinkppi-evidence-category:{ev['type']}")
    if ev.get("source_id"):
        values.append(f"{prefix}-record:{ev['source_id']}")
    if ev.get("directed"):
        values.append(f"{prefix}-direction:{ev.get('regulator') or '?'}->{ev.get('target') or '?'}")
    if ev.get("effect"):
        values.append(f"{prefix}-effect:{ev['effect']}")
    return _join(values)


def build_mitab(graph, tax_id, species, edge_ids=None):
    """Return MITAB text for the graph's edges (optionally only ``edge_ids``)."""
    nodes = {node["id"]: node for node in graph["nodes"]}
    taxid = f"taxid:{tax_id}({species})" if species else f"taxid:{tax_id}"
    lines = ["\t".join(COMMON_COLUMNS)]
    for edge in graph["edges"]:
        if edge_ids is not None and edge["id"] not in edge_ids:
            continue
        a, b = nodes[edge["source"]], nodes[edge["target"]]
        for ev in edge["evidence"]:
            row = {
                "#ID(s) interactor A": _interactor(a), "ID(s) interactor B": _interactor(b),
                "Alias(es) interactor A": _alias(a), "Alias(es) interactor B": _alias(b),
                "Taxid interactor A": taxid, "Taxid interactor B": taxid,
                "Interaction detection method(s)": _format_methods(ev.get("methods")),
                "Interaction type(s)": _format_biogrid_type(ev.get("interaction_type")),
                "Publication Identifier(s)": _pubmed_values(ev.get("publications")),
                "Source database(s)": SOURCE_DATABASES.get(ev["database"], ev["database"].lower()),
                "Confidence value(s)": _confidence(ev),
            }
            lines.append("\t".join(str(row[column]).replace("\t", " ").replace("\n", " ") for column in COMMON_COLUMNS))
    return "\n".join(lines) + "\n"
