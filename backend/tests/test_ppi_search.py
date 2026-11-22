"""PPI (pair) search, expanded-network neighbor limits, MITAB export and UniProt function lookup."""
import os; os.environ.setdefault("KLINKPPI_JOB_DB", ":memory:"); os.environ.setdefault("KLINKPPI_BUILD_EXAMPLE", "0")  # noqa: E702
import unittest
from threading import Event
from unittest.mock import Mock, patch

from fastapi import HTTPException
from app import main
from app.services import collection_mitab, collection_search as cs
from app.services.uniprot_lookup import parse_function


def node(accession, input=False):
    return {"id": accession, "gene": f"G{accession}", "gene_names": [], "species": "Homo sapiens", "tax_id": "9606",
            "input": input, "unresolved": False}


def edge(index, a, b, databases, publications=()):
    return {"id": f"e{index}", "source": a, "target": b, "expanded": True,
            "evidence": [{"database": db, "type": "direct", "score": None, "publications": list(publications), "methods": []}
                         for db in databases]}


class PairParsingTests(unittest.TestCase):
    def test_pairs_merge_reversed_duplicates_and_collect_tokens(self):
        pairs, tokens = cs.normalize_pairs([["TP53", "MDM2"], [" mdm2 ", "tp53"], ["TP53", "BRCA1"]])
        self.assertEqual(pairs, [["TP53", "MDM2"], ["TP53", "BRCA1"]])
        self.assertEqual(tokens, ["TP53", "MDM2", "BRCA1"])

    def test_pair_limits(self):
        with self.assertRaises(ValueError):
            cs.normalize_pairs([["A", "B", "C"]])
        with self.assertRaises(ValueError):
            cs.normalize_pairs([[f"A{i}", f"B{i}"] for i in range(cs.MAX_PAIRS + 1)])
        with patch.object(cs, "MAX_PAIR_INPUTS", 3):
            with self.assertRaises(ValueError):
                cs.normalize_pairs([["A", "B"], ["C", "D"]])

    @patch.object(cs.POOL, "submit")
    def test_ppi_job_stores_pairs_and_neighbor_settings(self, submit):
        job = cs.create_job([], "9606", "Homo sapiens", ["IntAct"], "auto", "expanded", Mock(),
                            pairs=[["TP53", "MDM2"]], neighbor_limit=5, neighbor_scope="pair")
        try:
            self.assertEqual(job["search_type"], "ppi")
            self.assertEqual(job["tokens"], ["TP53", "MDM2"])
            self.assertEqual((job["neighbor_limit"], job["neighbor_scope"]), (5, "pair"))
            with self.assertRaises(ValueError):
                cs.create_job(["TP53"], "9606", "Homo sapiens", ["IntAct"], "auto", "expanded", Mock(), neighbor_scope="pair")
        finally:
            cs.JOBS.pop(job["job_id"], None)

    @patch.object(cs.POOL, "submit")
    def test_induced_jobs_ignore_neighbor_limit(self, submit):
        job = cs.create_job(["TP53"], "9606", "Homo sapiens", ["IntAct"], "auto", "induced", Mock(), neighbor_limit=5)
        try:
            self.assertIsNone(job["neighbor_limit"])
            self.assertEqual(job["search_type"], "batch")
        finally:
            cs.JOBS.pop(job["job_id"], None)


class NeighborLimitTests(unittest.TestCase):
    def setUp(self):
        self.graph = {"nodes": [node("A", True), node("B", True), node("N1"), node("N2"), node("N3")],
                      "edges": [edge(0, "A", "B", ["IntAct"]), edge(1, "A", "N1", ["IntAct"]),
                                edge(2, "A", "N2", ["IntAct", "BioGrid"]), edge(3, "B", "N3", ["IntAct"], ["1", "2"]),
                                edge(4, "B", "N1", ["IntAct"])]}

    def test_per_protein_keeps_best_supported_neighbors(self):
        graph = cs.limit_neighbors(self.graph, 1)
        self.assertEqual({n["id"] for n in graph["nodes"]}, {"A", "B", "N2", "N3"})
        self.assertEqual({e["id"] for e in graph["edges"]}, {"e0", "e2", "e3"})
        self.assertEqual(graph["neighbor_limit"], {"limit": 1, "scope": "protein", "shown": 2, "hidden": 1})

    def test_per_pair_prefers_shared_neighbors(self):
        graph = cs.limit_neighbors(self.graph, 1, "pair", [("A", "B")])
        self.assertEqual({n["id"] for n in graph["nodes"]}, {"A", "B", "N1"})
        self.assertEqual({e["id"] for e in graph["edges"]}, {"e0", "e1", "e4"})

    def test_preselection_keeps_rows_among_inputs(self):
        seeds = {"A": {}, "B": {}}
        canonical = {"A": {"id": "A"}, "B": {"id": "B"}}
        records = [("IntAct", "A", {"Interactor_A": "A", "Interactor_B": "B"}, {}),
                   ("IntAct", "A", {"Interactor_A": "X", "Interactor_B": "A"}, {}),
                   ("BioGrid", "A", {"Interactor_A": "Y", "Interactor_B": "A"}, {}),
                   ("IntAct", "A", {"Interactor_A": "Y", "Interactor_B": "A"}, {})]
        kept, dropped = cs.preselect_neighbors(records, canonical, seeds, 1)
        self.assertEqual(dropped, 1)
        self.assertNotIn("X", {r[2]["Interactor_A"] for r in kept})

    def test_expanded_job_applies_limit(self):
        a, b = cs.entry_candidate({"primaryAccession": "P00001", "genes": [{"geneName": {"value": "AAA"}}], "organism": {"taxonId": 9606}}), \
            cs.entry_candidate({"primaryAccession": "P00002", "genes": [{"geneName": {"value": "BBB"}}], "organism": {"taxonId": 9606}})
        neighbors = [cs.entry_candidate({"primaryAccession": f"Q0000{i}", "genes": [{"geneName": {"value": f"N{i}"}}], "organism": {"taxonId": 9606}}) for i in range(4)]
        rows = [{"Interactor_A": n["id"], "Interactor_B": a["id"]} for n in neighbors] + [{"Interactor_A": b["id"], "Interactor_B": a["id"]}]
        resolver = Mock(side_effect=lambda db, seed, tax: [{"info": {}}, {"Interactors": rows if seed == a["id"] else []}])
        job_id = "test-ppi-expanded"
        cs.JOBS[job_id] = {"resolution": [{"input": c["gene"], "candidates": [c]} for c in (a, b)],
                           "selections": {"AAA": a["id"], "BBB": b["id"]}, "pairs": [["AAA", "BBB"], ["AAA", "MISSING"]],
                           "databases": ["IntAct"], "resolver": resolver, "mode": "expanded", "neighbor_limit": 2,
                           "neighbor_scope": "pair", "tax_id": "9606", "species": "Homo sapiens", "cancel": Event(), "status": "running"}
        try:
            with patch.object(cs, "resolve_tokens", return_value=({n["id"]: [n] for n in neighbors}, {})):
                cs._network_job(job_id)
            job = cs.JOBS[job_id]
            self.assertEqual(job["status"], "completed", job.get("progress"))
            self.assertEqual(sum(not n["input"] for n in job["graph"]["nodes"]), 2)
            queried = job["graph"]["queried_pairs"]
            self.assertEqual([p["status"] for p in queried], ["known", "unresolved"])
            known = next(e for e in job["graph"]["edges"] if e["id"] == queried[0]["edge"])
            self.assertTrue(known["queried"])
        finally:
            del cs.JOBS[job_id]


class PairAnnotationTests(unittest.TestCase):
    def test_statuses(self):
        graph = {"nodes": [node("A", True), node("B", True), node("C", True)], "edges": [edge(0, "A", "B", ["IntAct"])]}
        cs.annotate_pairs(graph, [["a", "b"], ["b", "c"], ["a", "x"], ["a", "a2"]], {"a": "A", "b": "B", "c": "C", "a2": "A"})
        self.assertEqual([p["status"] for p in graph["queried_pairs"]], ["known", "unknown", "unresolved", "same_protein"])
        self.assertEqual(graph["queried_pairs"][0]["edge"], "e0")


class MitabTests(unittest.TestCase):
    def test_one_row_per_evidence_with_standard_columns(self):
        graph = {"nodes": [node("P04637", True), node("Q00987", True)], "edges": [{
            "id": "e0", "source": "P04637", "target": "Q00987", "evidence": [
                {"database": "IntAct", "type": "direct", "score": 0.9, "score_name": "Interaction_Score_Intact",
                 "scores": {"Interaction_Score_Intact": 0.9}, "publications": ["123"], "methods": ["two hybrid"],
                 "interaction_type": "physical association"},
                {"database": "String", "type": "functional", "score": 0.7, "scores": {"combined_score": 0.7},
                 "publications": [], "methods": [], "interaction_type": ""}]}]}
        lines = collection_mitab.build_mitab(graph, "9606", "Homo sapiens").splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("#ID(s) interactor A"))
        row = lines[1].split("\t")
        self.assertEqual(len(row), len(lines[0].split("\t")))
        self.assertEqual(row[:2], ["uniprotkb:P04637", "uniprotkb:Q00987"])
        self.assertIn('MI:0018', row[6])
        self.assertEqual(row[8], "pubmed:123")
        self.assertIn("intact", row[9])
        self.assertIn("intact-Interaction_Score_Intact:0.9", row[10])
        self.assertEqual(collection_mitab.build_mitab(graph, "9606", "", edge_ids=set()).count("\n"), 1)

    @patch.object(main.collection_search, "snapshot")
    def test_endpoint_filters_and_rejects_pair_export_for_batch(self, snapshot):
        graph = {"nodes": [node("A", True), node("B", True)], "edges": [edge(0, "A", "B", ["IntAct", "BioGrid"])]}
        snapshot.return_value = {"job_id": "abcdef1234", "status": "completed", "databases": ["IntAct", "BioGrid"],
                                 "graph": graph, "tax_id": "9606", "species": "Homo sapiens", "mode": "induced"}
        response = main.collection_mitab_export("abcdef1234", databases=["IntAct"], evidence_type="all", method="",
                                                score_database="", min_score=None, min_publications=0, queried_pairs_only=False)
        self.assertEqual(response.body.decode().count("\n"), 2)
        self.assertIn("klinkppi_batch_induced", response.headers["content-disposition"])
        with self.assertRaises(HTTPException) as caught:
            main.collection_mitab_export("abcdef1234", databases=None, evidence_type="all", method="", score_database="",
                                         min_score=None, min_publications=0, queried_pairs_only=True)
        self.assertEqual(caught.exception.status_code, 400)


class PPIEndpointTests(unittest.TestCase):
    @patch.object(main.collection_search, "create_job", return_value={"job_id": "fixture"})
    @patch.object(main, "get_supported_databases", return_value=["IntAct"])
    @patch.object(main, "resolve_species_context", return_value=("9606", None, {"display_name": "Homo sapiens"}))
    def test_ppi_endpoint_passes_pairs(self, species, databases, create):
        request = main.PPIRequest(pairs=[["TP53", "MDM2"], ["MDM2", "TP53"]], species_name="Homo sapiens",
                                  selected_databases=["IntAct"], mode="expanded", neighbor_limit=3, neighbor_scope="pair")
        self.assertEqual(main.start_ppi_search(request)["job_id"], "fixture")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["pairs"], [["TP53", "MDM2"]])
        self.assertEqual((kwargs["neighbor_limit"], kwargs["neighbor_scope"]), (3, "pair"))
        with self.assertRaises(HTTPException) as caught:
            main.start_ppi_search(main.PPIRequest(pairs=[["TP53"]], species_name="Homo sapiens", selected_databases=["IntAct"]))
        self.assertEqual(caught.exception.status_code, 400)


class UniProtFunctionTests(unittest.TestCase):
    def test_parse_function_text_and_citations(self):
        result = parse_function({
            "primaryAccession": "P04637", "uniProtkbId": "P53_HUMAN", "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "proteinDescription": {"recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}}},
            "genes": [{"geneName": {"value": "TP53"}}], "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
            "comments": [{"commentType": "FUNCTION", "texts": [{"value": "Acts as a tumor suppressor.",
                          "evidences": [{"source": "PubMed", "id": "111"}, {"source": "PubMed", "id": "111"}]}]},
                         {"commentType": "SUBUNIT", "texts": [{"value": "Ignored"}]}]})
        self.assertEqual(result["protein_name"], "Cellular tumor antigen p53")
        self.assertEqual(result["gene"], "TP53")
        self.assertEqual(result["function"], [{"text": "Acts as a tumor suppressor.", "pubmed": ["111"]}])
        self.assertTrue(result["url"].endswith("/P04637/entry"))

    def test_endpoint_validates_input(self):
        for kwargs in ({"accession": "not an id"}, {"gene": "TP53"}, {}):
            with self.assertRaises(HTTPException) as caught:
                main.uniprot_function(**{"accession": "", "gene": "", "tax_id": "", **kwargs})
            self.assertEqual(caught.exception.status_code, 400)

    @patch.object(main, "protein_function", return_value={"accession": "P04637"})
    def test_endpoint_strips_isoform(self, lookup):
        main.uniprot_function(accession="p04637-2", gene="", tax_id="")
        self.assertEqual(lookup.call_args.args[:3], ("P04637", None, None))


class GoValidationTests(unittest.TestCase):
    def test_ppi_jobs_compare_pairs_in_expanded_mode(self):
        from app.services.collection_go import validate_unknown_pair
        graph = {"nodes": [node("A", True), node("B", True)], "edges": []}
        validate_unknown_pair({"status": "completed", "mode": "expanded", "pairs": [["a", "b"]], "graph": graph}, "A", "B")
        with self.assertRaises(ValueError):
            validate_unknown_pair({"status": "completed", "mode": "expanded", "graph": graph}, "A", "B")


if __name__ == "__main__":
    unittest.main()
