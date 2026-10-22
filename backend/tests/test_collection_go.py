import unittest
from unittest.mock import Mock, patch

import requests
from app.services import collection_go as go


def annotation(term_id, label, evidence="IDA:UniProtKB"):
    return {"database": "GO", "id": term_id, "properties": [
        {"key": "GoTerm", "value": label}, {"key": "GoEvidenceType", "value": evidence},
    ]}


def response(accession, refs, tax_id=9606):
    return Mock(json=Mock(return_value={"primaryAccession": accession, "organism": {"taxonId": tax_id}, "uniProtKBCrossReferences": refs}))


class SharedGOTests(unittest.TestCase):
    def setUp(self):
        go.protein_go.cache_clear()
        self.job = {"status": "completed", "mode": "induced", "tax_id": "9606", "graph": {
            "nodes": [{"id": accession, "input": True} for accession in ("P04637", "P38398", "Q00987")]
                     + [{"id": "unknown:0", "input": True, "unresolved": True}, {"id": "Q00001", "input": False}],
            "edges": [{"source": "P04637", "target": "Q00987"}],
        }}

    def tearDown(self):
        go.protein_go.cache_clear()

    @patch.object(go.requests, "get")
    def test_exact_shared_ids_categories_evidence_and_cached_reverse_pair(self, get):
        left = [annotation("GO:0005634", "C:nucleus"), annotation("GO:0005634", "C:nucleus", "IEA:UniProtKB-KW"),
                annotation("GO:0003677", "F:DNA binding"), annotation("GO:0006281", "P:DNA repair"),
                annotation("GO:0006355", "P:regulation of DNA-templated transcription")]
        right = [annotation("GO:0005634", "C:nucleus", "IDA:BHF-UCL"), annotation("GO:0003677", "F:DNA binding"),
                 annotation("GO:0006281", "P:DNA repair"), annotation("GO:0006351", "P:DNA-templated transcription")]
        get.side_effect = [response("P04637", left), response("P38398", right)]
        with patch.object(go, "time", return_value=3600):
            result = go.shared_go(self.job, "P04637", "P38398")
            reverse = go.shared_go(self.job, "P38398", "P04637")
        self.assertEqual(get.call_count, 2)
        self.assertEqual(result["source_term_count"], 4)
        self.assertEqual(len(result["shared_terms"]), 3)
        self.assertEqual({term["category"] for term in result["shared_terms"]}, set(go.ASPECTS.values()))
        nucleus = next(term for term in result["shared_terms"] if term["id"] == "GO:0005634")
        self.assertEqual(nucleus["source_evidence"], ["IDA:UniProtKB", "IEA:UniProtKB-KW"])
        self.assertEqual(nucleus["target_evidence"], ["IDA:BHF-UCL"])
        self.assertEqual(next(term for term in reverse["shared_terms"] if term["id"] == "GO:0005634")["target_evidence"], nucleus["source_evidence"])
        self.assertIn("organism_id", get.call_args.kwargs["params"]["fields"])

    @patch.object(go.requests, "get")
    def test_empty_annotations_and_no_overlap_are_successful_results(self, get):
        for refs in ([], [annotation("GO:0003677", "F:DNA binding")]):
            go.protein_go.cache_clear()
            get.side_effect = [response("P04637", refs), response("P38398", [annotation("GO:0005634", "C:nucleus")])]
            result = go.shared_go(self.job, "P04637", "P38398")
            self.assertEqual(result["shared_terms"], [])
            self.assertEqual(result["source_term_count"], len(refs))

    @patch.object(go.requests, "get")
    def test_invalid_pairs_and_job_states_never_query_uniprot(self, get):
        for source, target in [("P04637", "P04637"), ("P04637", "Q00987"), ("Q00987", "P04637"),
                               ("unknown:0", "P04637"), ("Q00001", "P04637"), ("FAKE", "P04637")]:
            with self.assertRaises(ValueError):
                go.shared_go(self.job, source, target)
        for field, value in [("status", "running"), ("mode", "expanded")]:
            with self.assertRaises(ValueError):
                go.shared_go({**self.job, field: value}, "P04637", "P38398")
        get.assert_not_called()

    @patch.object(go.requests, "get")
    def test_upstream_failure_is_retryable_not_empty_overlap(self, get):
        get.side_effect = [requests.Timeout(), response("P04637", []), response("P38398", [])]
        with self.assertRaises(go.GOLookupError):
            go.shared_go(self.job, "P04637", "P38398")
        self.assertEqual(go.shared_go(self.job, "P04637", "P38398")["shared_terms"], [])
        self.assertEqual(get.call_count, 3)

    @patch.object(go.requests, "get")
    def test_wrong_species_or_accession_is_rejected(self, get):
        for upstream in [response("P04637", [], tax_id=10090), response("Q00987", [])]:
            get.return_value = upstream
            with self.assertRaises(go.GOLookupError):
                go.shared_go(self.job, "P04637", "P38398")


if __name__ == "__main__":
    unittest.main()
