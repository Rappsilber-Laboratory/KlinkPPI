import unittest
from unittest.mock import Mock, patch

import requests
from app.services import collection_alignment as ca


def sequence_response(accession, sequence="ACDE", tax_id=9606):
    return Mock(json=Mock(return_value={"primaryAccession": accession, "organism": {"taxonId": tax_id}, "sequence": {"value": sequence}}))


class AlignmentTests(unittest.TestCase):
    def setUp(self):
        ca.TASKS.clear()
        ca.protein_sequence.cache_clear()
        self.job = {"job_id": "collection", "created_at": 10, "status": "completed", "mode": "induced", "tax_id": "9606",
                    "graph": {"nodes": [{"id": accession, "input": True} for accession in ("P04637", "P38398", "Q00987")],
                              "edges": [{"source": "P04637", "target": "Q00987"}]}}

    def tearDown(self):
        ca.TASKS.clear()
        ca.protein_sequence.cache_clear()

    @patch.object(ca.requests, "get")
    def test_collection_fasta_is_validated_wrapped_and_shared_across_actions(self, get):
        self.job["graph"]["nodes"][0]["gene"] = "TP53"
        get.return_value = sequence_response("P04637", "A" * 80)
        first = ca.collection_sequence(self.job, "P04637")
        second = ca.collection_sequence(self.job, "P04637")
        self.assertEqual(first, second)
        self.assertTrue(first["fasta"].startswith(">P04637 TP53\n"))
        self.assertEqual([len(line) for line in first["fasta"].splitlines()[1:]], [60, 20])
        self.assertEqual(get.call_count, 1)
        with self.assertRaises(ValueError):
            ca.collection_sequence(self.job, "P99999")
        self.job["status"] = "running"
        with self.assertRaises(ValueError):
            ca.collection_sequence(self.job, "P04637")

    @patch.object(ca.requests, "get")
    def test_fasta_lookup_accepts_sequences_above_alignment_limit(self, get):
        get.return_value = sequence_response("P04637", "A" * (ca.MAX_LENGTH + 1))
        result = ca.collection_sequence(self.job, "P04637")
        self.assertEqual(len(result["sequence"]), ca.MAX_LENGTH + 1)

    def test_identical_sequences_have_expected_blosum_score_and_identity(self):
        result = ca.align_sequences("ACDE", "ACDE")
        self.assertEqual(result["score"], 24)
        self.assertEqual(result["identity_percent"], 100)
        self.assertEqual(result["gap_columns"], 0)
        self.assertEqual(result["alignment_length"], 4)
        self.assertEqual(result["parameters"]["gap_open"], 10)
        self.assertEqual(result["parameters"]["gap_extend"], 0.5)
        self.assertIn("Gotoh", result["parameters"]["algorithm"])

    def test_internal_gaps_identity_denominator_and_traceback(self):
        result = ca.align_sequences("ACDE", "ACE")
        self.assertEqual(result["score"], 8)
        self.assertEqual(result["aligned_source"], "ACDE")
        self.assertEqual(result["aligned_target"], "AC-E")
        self.assertEqual(result["identity_percent"], 75)
        self.assertEqual(result["gap_columns"], 1)

    def test_affine_gap_cost_and_penalized_terminal_gaps_are_symmetric(self):
        forward = ca.align_sequences("AAA", "A")
        reverse = ca.align_sequences("A", "AAA")
        self.assertEqual(forward["score"], -6.5)  # A/A = 4; gap length 2 costs 10.5.
        self.assertEqual(reverse["score"], -6.5)
        self.assertEqual(forward["gap_columns"], 2)
        self.assertAlmostEqual(forward["identity_percent"], 100 / 3)

    def test_rare_residues_are_preserved_but_scored_as_x(self):
        result = ca.align_sequences("UO", "XX")
        self.assertEqual(result["score"], ca.align_sequences("XX", "XX")["score"])
        self.assertEqual(result["aligned_source"], "UO")
        self.assertEqual(result["identities"], 0)

    def test_empty_or_oversized_pairs_fail_explicitly(self):
        with self.assertRaises(ValueError):
            ca.align_sequences("", "A")
        with patch.object(ca, "MAX_CELLS", 3), self.assertRaisesRegex(ValueError, "too large"):
            ca.align_sequences("AA", "AA")

    @patch.object(ca.requests, "get")
    def test_sequences_are_species_checked_and_cached(self, get):
        get.return_value = sequence_response("P04637")
        self.assertEqual(ca.protein_sequence("P04637", "9606", 1), "ACDE")
        self.assertEqual(ca.protein_sequence("P04637", "9606", 1), "ACDE")
        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs["params"]["fields"], "accession,organism_id,sequence")
        ca.protein_sequence("P04637", "9606", 2)
        self.assertEqual(get.call_count, 2)

    @patch.object(ca.requests, "get")
    def test_wrong_species_accession_missing_sequence_and_invalid_residues_fail(self, get):
        for response in (sequence_response("P04637", tax_id=10090), sequence_response("P38398"),
                         sequence_response("P04637", ""), sequence_response("P04637", "AC?E")):
            get.return_value = response
            with self.assertRaises(ca.SequenceLookupError):
                ca.protein_sequence("P04637", "9606", 1)
        get.return_value = sequence_response("P04637", "AAAA")
        with patch.object(ca, "MAX_LENGTH", 3), self.assertRaisesRegex(ValueError, "limited"):
            ca.align_sequences("AAAA", "AA")

    @patch.object(ca.requests, "get")
    def test_failed_sequence_fetch_can_be_retried(self, get):
        get.side_effect = [requests.Timeout(), sequence_response("P04637")]
        with self.assertRaises(ca.SequenceLookupError):
            ca.protein_sequence("P04637", "9606", 1)
        self.assertEqual(ca.protein_sequence("P04637", "9606", 1), "ACDE")

    @patch.object(ca.POOL, "submit")
    @patch.object(ca, "protein_sequence", side_effect=["ACDE", "ACE"])
    def test_background_job_reports_real_stages_then_result(self, sequence, submit):
        task = ca.start(self.job, "P04637", "P38398")
        self.assertEqual(task["status"], "queued")
        sequence.assert_not_called()  # Fetching only happens after the click queues work.
        submit.assert_called_once_with(ca._run, task["alignment_id"], "9606")
        with patch.object(ca, "update", wraps=ca.update) as update:
            ca._run(task["alignment_id"], "9606")
        updates = [call.kwargs for call in update.call_args_list]
        self.assertIn("P04637", updates[0]["progress"])
        self.assertEqual([row.get("completed_steps", 0) for row in updates], [0, 1, 2, 3])
        self.assertIn("Computing", updates[2]["progress"])
        completed = ca.snapshot(task["alignment_id"], "collection")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["result"]["score"], 8)
        with self.assertRaises(KeyError):
            ca.snapshot(task["alignment_id"], "another-collection")

    @patch.object(ca.POOL, "submit")
    def test_invalid_pair_rejected_and_duplicate_active_work_not_enqueued(self, submit):
        for source, target in [("P04637", "P04637"), ("P04637", "Q00987"), ("P04637", "FAKE")]:
            with self.assertRaises(ValueError):
                ca.start(self.job, source, target)
        submit.assert_not_called()
        first = ca.start(self.job, "P04637", "P38398")
        second = ca.start(self.job, "P04637", "P38398")
        self.assertEqual(first["alignment_id"], second["alignment_id"])
        submit.assert_called_once()

    @patch.object(ca.POOL, "submit")
    @patch.object(ca, "protein_sequence", side_effect=ca.SequenceLookupError("UniProt unavailable"))
    def test_failed_job_reports_error_and_retry_creates_new_work(self, sequence, submit):
        task = ca.start(self.job, "P04637", "P38398")
        ca._run(task["alignment_id"], "9606")
        failed = ca.snapshot(task["alignment_id"], "collection")
        self.assertEqual(failed["status"], "failed")
        self.assertIsNone(failed["result"])
        self.assertEqual(failed["error"], "UniProt unavailable")
        retry = ca.start(self.job, "P04637", "P38398")
        self.assertNotEqual(retry["alignment_id"], task["alignment_id"])

    @patch.object(ca.POOL, "submit")
    def test_capacity_and_expired_task_cleanup(self, submit):
        first = ca.start(self.job, "P04637", "P38398")
        with patch.object(ca, "MAX_TASKS", 1), self.assertRaises(RuntimeError):
            ca.start(self.job, "P38398", "Q00987")
        ca.update(first["alignment_id"], status="completed", created_at=0)
        with patch.object(ca, "MAX_TASKS", 1):
            second = ca.start(self.job, "P38398", "Q00987")
        self.assertNotIn(first["alignment_id"], ca.TASKS)
        self.assertIn(second["alignment_id"], ca.TASKS)


if __name__ == "__main__":
    unittest.main()
