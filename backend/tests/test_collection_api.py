"""API boundary checks for collection limits and sequence errors."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from app import main


class CollectionAPITests(unittest.TestCase):
    def setUp(self):
        self.payload = {"identifiers": [f"gene{i}" for i in range(20)],
                        "species_name": "Homo sapiens", "tax_id": "9606",
                        "selected_databases": ["IntAct"]}

    @patch.object(main.collection_search, "create_job", return_value={"job_id": "fixture"})
    @patch.object(main, "get_supported_databases", return_value=["IntAct"])
    @patch.object(main, "resolve_species_context", return_value=("9606", None, {"display_name": "Homo sapiens"}))
    def test_api_merges_duplicates_before_limit_and_rejects_21(self, species, databases, create):
        self.payload["identifiers"] *= 2
        response = main.start_collection(main.CollectionRequest(**self.payload))
        self.assertEqual(response["job_id"], "fixture")
        self.assertEqual(len(create.call_args.args[0]), 20)
        self.payload["identifiers"].append("extra")
        with self.assertRaises(HTTPException) as caught:
            main.start_collection(main.CollectionRequest(**self.payload))
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("20 distinct", caught.exception.detail)
        self.assertEqual(create.call_count, 1)

    @patch.object(main.collection_search, "snapshot", side_effect=KeyError)
    def test_sequence_rejects_missing_job(self, snapshot):
        with self.assertRaises(HTTPException) as caught:
            main.collection_sequence("missing", "P04637")
        self.assertEqual(caught.exception.status_code, 404)

    @patch.object(main.collection_search, "snapshot", return_value={})
    @patch.object(main.collection_alignment, "collection_sequence", side_effect=main.collection_alignment.SequenceLookupError("Species mismatch"))
    def test_sequence_lookup_failure_is_reported(self, sequence, snapshot):
        with self.assertRaises(HTTPException) as caught:
            main.collection_sequence("fixture", "P04637")
        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(caught.exception.detail, "Species mismatch")
