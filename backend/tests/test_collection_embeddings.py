"""Embedding job boundaries and numerical parity with the bundled example."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from app import main
from app.services import collection_embeddings as ce
from plms_framework.scoring import score_two_sequences


class EmbeddingTests(unittest.TestCase):
    def setUp(self):
        ce.TASKS.clear()
        self.job = {"job_id": "collection", "created_at": 10, "status": "completed", "mode": "induced", "tax_id": "9606",
                    "graph": {"nodes": [{"id": accession, "input": True} for accession in ("P04637", "P38398", "Q00987")],
                              "edges": [{"source": "P04637", "target": "Q00987"}]}}

    def test_catalog_matches_example_models_exactly(self):
        example = Path(__file__).resolve().parents[2] / "embedding_FW/examples/test_two_seqs_mem.py"
        tree = ast.parse(example.read_text())
        selected = next(ast.literal_eval(keyword.value) for node in ast.walk(tree) if isinstance(node, ast.Call)
                        for keyword in node.keywords if keyword.arg == 'models')
        self.assertEqual(tuple(main.collection_embedding_models()["models"]), selected)

    def test_upstream_public_api_scoring_matches_example(self):
        from plms_framework.registry import default_registry
        expected = score_two_sequences('MKTAYIAK', 'MKTAYIAQ', models=('reference',), device='cpu')
        registry = default_registry
        with patch('plms_framework.pipeline.default_registry', registry):
            actual = ce.score_model('MKTAYIAK', 'MKTAYIAQ', 'reference-deterministic-v1')
        self.assertEqual(actual, expected)

    @patch.object(ce.POOL, "submit")
    def test_selection_unknown_pairs_deduplication_and_capacity(self, submit):
        for models in ([], ['reference'], ['esm2-3b'], ['esm2-8m', 'esm2-8m']):
            with self.assertRaises(ValueError):
                ce.start(self.job, 'P04637', 'P38398', models)
        with self.assertRaises(ValueError):
            ce.start(self.job, 'P04637', 'Q00987', ['esm2-8m'])
        first = ce.start(self.job, 'P04637', 'P38398', ['esm2-8m'])
        duplicate = ce.start(self.job, 'P38398', 'P04637', ['esm2-8m'])
        self.assertEqual(first['embedding_id'], duplicate['embedding_id'])
        submit.assert_called_once()
        with patch.object(ce, 'MAX_TASKS', 1), self.assertRaises(RuntimeError):
            ce.start(self.job, 'P04637', 'P38398', ['esm2-35m'])
        ce.update(first['embedding_id'], status='completed', created_at=0)
        ce.start(self.job, 'P04637', 'P38398', ['esm2-35m'])
        self.assertNotIn(first['embedding_id'], ce.TASKS)

    @patch.object(ce.POOL, "submit")
    @patch.object(ce, 'protein_sequence', side_effect=['MKTAYIAK', 'MKTAYIAQ'])
    def test_worker_scores_match_framework_and_every_metric_has_meaning(self, sequence, submit):
        expected = score_two_sequences('MKTAYIAK', 'MKTAYIAQ', models=('reference',), device='cpu')
        def deterministic(left, right, model):
            return {key.replace('reference-deterministic-v1.', model + '.'): value for key, value in expected.items()}
        task = ce.start(self.job, 'P04637', 'P38398', ['esm2-8m', 'esm2-35m'])
        sequence.assert_not_called()
        with patch.object(ce, 'score_model', side_effect=deterministic):
            ce._run(task['embedding_id'], '9606')
        result = ce.snapshot(task['embedding_id'], 'collection')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['completed_steps'], 4)
        self.assertEqual(len(result['result']['scores']), 33)
        self.assertEqual(set(result['result']['scores']), set(result['result']['descriptions']))
        self.assertEqual(len(result['result']['model_runtime_seconds']), 2)
        self.assertGreaterEqual(result['runtime_seconds'], 0)
        with self.assertRaises(KeyError):
            ce.snapshot(task['embedding_id'], 'other-job')

    @patch.object(ce.POOL, "submit")
    @patch.object(ce, 'protein_sequence', side_effect=['A' * 1023, 'ACDE'])
    @patch.object(ce, 'score_model')
    def test_length_failure_happens_before_model_load_and_can_retry(self, scorer, sequence, submit):
        task = ce.start(self.job, 'P04637', 'P38398', ['esm2-8m'])
        ce._run(task['embedding_id'], '9606')
        result = ce.snapshot(task['embedding_id'], 'collection')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('1022', result['error'])
        self.assertIsNone(result['result'])
        scorer.assert_not_called()
        retry = ce.start(self.job, 'P04637', 'P38398', ['esm2-8m'])
        self.assertNotEqual(task['embedding_id'], retry['embedding_id'])

    def test_native_esmc_limits(self):
        ce.validate_lengths('A' * 2046, 'ACDE', ['esmc-300m', 'esmc-600m'])
        with self.assertRaisesRegex(ValueError, '2046'):
            ce.validate_lengths('A' * 2047, 'ACDE', ['esmc-300m'])

    @patch.object(main.collection_search, 'snapshot', side_effect=KeyError)
    def test_api_missing_collection(self, snapshot):
        with self.assertRaises(main.HTTPException) as caught:
            main.start_pair_embedding('missing', main.PairEmbeddingRequest(source='A', target='B'))
        self.assertEqual(caught.exception.status_code, 404)

    @patch.object(main.collection_search, 'snapshot')
    def test_api_bad_models_and_capacity(self, snapshot):
        snapshot.return_value = self.job
        request = main.PairEmbeddingRequest(source='P04637', target='P38398', models=['bad'])
        with self.assertRaises(main.HTTPException) as caught:
            main.start_pair_embedding('collection', request)
        self.assertEqual(caught.exception.status_code, 400)
        with patch.object(ce, 'MAX_TASKS', 0), self.assertRaises(main.HTTPException) as caught:
            main.start_pair_embedding('collection', main.PairEmbeddingRequest(source='P04637', target='P38398'))
        self.assertEqual(caught.exception.status_code, 429)
        with self.assertRaises(main.HTTPException) as caught:
            main.pair_embedding_status('collection', 'missing')
        self.assertEqual(caught.exception.status_code, 404)


class EmbeddingClientTests(unittest.TestCase):
    def test_client_selects_models_polls_and_preserves_results(self):
        from klinkppi import KlinkPPIClient
        client = KlinkPPIClient("http://localhost:8000")
        queued = {"embedding_id": "task", "status": "queued"}
        complete = {"embedding_id": "task", "status": "completed", "runtime_seconds": 2,
                    "result": {"scores": {"esm2-8m.mean.cosine_similarity": 0.9}}}
        with patch.object(client, '_request', side_effect=[queued, complete]) as request, patch('klinkppi.time.sleep'):
            result = client.embed_pair('job', 'P04637', 'P38398', models=['esm2-8m', 'esmc-300m'])
        self.assertEqual(result, complete)
        self.assertEqual(request.call_args_list[0].kwargs['json']['models'], ['esm2-8m', 'esmc-300m'])
        self.assertEqual(request.call_args_list[1].args, ('GET', '/collection/jobs/job/embeddings/task'))

    def test_http_embedding_contract(self):
        from fastapi.testclient import TestClient
        with TestClient(main.app) as client:
            response = client.get('/collection/embedding-models')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()['models']), 12)
            with patch.object(main.collection_search, 'snapshot', return_value={'job_id': 'job'}), patch.object(ce, 'start', return_value={'embedding_id': 'task', 'status': 'queued'}) as start:
                response = client.post('/collection/jobs/job/embeddings', json={'source': 'P04637', 'target': 'P38398', 'models': ['esm2-8m']})
                self.assertEqual(response.status_code, 202)
                start.assert_called_once_with({'job_id': 'job'}, 'P04637', 'P38398', ['esm2-8m'])
            self.assertEqual(client.post('/collection/jobs/job/embeddings', json={'source': 'A', 'target': 'B', 'models': []}).status_code, 422)
