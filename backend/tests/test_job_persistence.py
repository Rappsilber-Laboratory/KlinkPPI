"""Durable jobs, bookmarkable results, queue limits and fair-use rate limits."""
import os; os.environ.setdefault("KLINKPPI_JOB_DB", ":memory:"); os.environ.setdefault("KLINKPPI_BUILD_EXAMPLE", "0")  # noqa: E702
import tempfile
import unittest
from pathlib import Path
from time import time
from unittest.mock import Mock, patch

from app.services import collection_search as cs
from app.services import job_store
from app.services.rate_limit import RateLimiter


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.store = job_store.JobStore(":memory:")
        job_store.set_store(self.store)
        cs.JOBS.clear()

    def tearDown(self):
        cs.JOBS.clear()
        job_store.set_store(None)


class JobStoreTests(StoreTestCase):
    def test_save_load_purge_and_pinned(self):
        self.store.save("collection", {"job_id": "old", "status": "completed", "created_at": 10})
        self.store.save("collection", {"job_id": "keep", "status": "completed", "created_at": 10}, pinned=True)
        self.store.save("collection", {"job_id": "running", "status": "running", "created_at": 10})
        self.assertEqual(self.store.load("collection", "old")["status"], "completed")
        self.assertEqual(self.store.purge("collection", 100, keep_statuses={"running"}), 1)
        self.assertIsNone(self.store.load("collection", "old"))
        self.assertIsNotNone(self.store.load("collection", "keep"))
        self.assertEqual([job["job_id"] for job in self.store.load_by_status("collection", {"running"})], ["running"])

    def test_file_database_survives_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.sqlite3"
            job_store.JobStore(path).save("collection", {"job_id": "a", "status": "completed", "created_at": time()})
            self.assertEqual(job_store.JobStore(path).load("collection", "a")["job_id"], "a")


class PersistenceTests(StoreTestCase):
    @patch.object(cs.POOL, "submit")
    def test_job_reloads_after_memory_loss_with_expiry(self, submit):
        job = cs.create_job(["TP53", "BRCA1"], "9606", "Homo sapiens", ["IntAct"], "auto", "induced", Mock(), client="1.2.3.4")
        self.assertNotIn("client", job)
        self.assertAlmostEqual(job["expires_at"], job["created_at"] + job_store.retention_seconds(), places=3)
        stored = self.store.load("collection", job["job_id"])
        self.assertNotIn("client", stored)          # client addresses are never persisted
        self.assertNotIn("cancel", stored)
        cs.JOBS.clear()                               # simulate a server restart
        reloaded = cs.snapshot(job["job_id"])
        self.assertEqual(reloaded["tokens"], ["TP53", "BRCA1"])
        cs.patch(job["job_id"], status="awaiting_selection", resolution=[])
        cs.JOBS.clear()
        self.assertEqual(cs.snapshot(job["job_id"])["status"], "awaiting_selection")

    def test_expired_results_are_deleted(self):
        self.store.save("collection", {"job_id": "stale", "status": "completed", "created_at": time() - job_store.retention_seconds() - 5})
        with self.assertRaises(KeyError):
            cs.snapshot("stale")
        self.assertIsNone(self.store.load("collection", "stale"))
        with self.assertRaises(KeyError):
            cs.snapshot("never-existed")

    @patch.dict(os.environ, {"KLINKPPI_RESULT_RETENTION_DAYS": "7"})
    def test_retention_is_configurable(self):
        self.assertEqual(job_store.retention_seconds(), 7 * 86400)

    @patch.object(cs.POOL, "submit")
    def test_queue_limits_count_only_active_jobs(self, submit):
        with patch.object(cs, "MAX_ACTIVE_PER_CLIENT", 1):
            first = cs.create_job(["A1"], "9606", "Human", ["IntAct"], "auto", "induced", Mock(), client="c1")
            with self.assertRaisesRegex(ValueError, "already have 1"):
                cs.create_job(["A2"], "9606", "Human", ["IntAct"], "auto", "induced", Mock(), client="c1")
            cs.create_job(["A3"], "9606", "Human", ["IntAct"], "auto", "induced", Mock(), client="c2")
            cs.patch(first["job_id"], status="completed")
            cs.create_job(["A4"], "9606", "Human", ["IntAct"], "auto", "induced", Mock(), client="c1")
        with patch.object(cs, "MAX_ACTIVE_JOBS", 2), self.assertRaisesRegex(ValueError, "server is busy"):
            cs.create_job(["A5"], "9606", "Human", ["IntAct"], "auto", "induced", Mock(), client="c3")
        # Many finished results never block new submissions.
        for job in cs.JOBS.values():
            job["status"] = "completed"
        with patch.object(cs, "MAX_ACTIVE_JOBS", 1):
            cs.create_job(["A6"], "9606", "Human", ["IntAct"], "auto", "induced", Mock())

    @patch.object(cs.POOL, "submit")
    def test_example_is_pinned_and_read_only(self, submit):
        cs.create_job(cs.EXAMPLE_IDENTIFIERS, "9606", "Homo sapiens", ["IntAct"], "UniProtKB", "induced", Mock(),
                      job_id=cs.EXAMPLE_JOB_ID, pinned=True)
        cs.patch(cs.EXAMPLE_JOB_ID, status="completed", created_at=0)
        cs.JOBS.clear()
        example = cs.snapshot(cs.EXAMPLE_JOB_ID)    # pinned: never expires
        self.assertIsNone(example["expires_at"])
        for action in (cs.rerun_job, cs.cancel_job):
            with self.assertRaisesRegex(ValueError, "read-only"):
                action(cs.EXAMPLE_JOB_ID)
        cs.rerun_job(cs.EXAMPLE_JOB_ID, internal=True)
        self.assertEqual(self.store.purge("collection", time() + 10**9), 0)

    def test_example_choices_prefer_reviewed(self):
        rows = [{"input": "A", "candidates": [{"id": "X", "reviewed": False}, {"id": "Y", "reviewed": True}]},
                {"input": "B", "candidates": [{"id": "Z", "reviewed": True}]}]
        self.assertEqual(cs.example_choices(rows), {"A": "Y"})

    def test_recover_resumes_unfinished_jobs(self):
        self.store.save("collection", {"job_id": "r1", "status": "resolving", "created_at": time()})
        self.store.save("collection", {"job_id": "r2", "status": "running", "created_at": time()})
        self.store.save("collection", {"job_id": "done", "status": "completed", "created_at": time()})
        with patch.object(cs.POOL, "submit") as submit:
            self.assertEqual(cs.recover(), 2)
        targets = {call.args[0].__name__: call.args[1] for call in submit.call_args_list}
        self.assertEqual(targets, {"_resolve_job": "r1", "_network_job": "r2"})


class RateLimitTests(unittest.TestCase):
    def test_buckets_and_limits(self):
        limiter = RateLimiter(limits={"job": (2, 60), "default": (100, 60), "search": (1, 60), "embedding": (1, 60),
                                      "alignment": (1, 60), "export": (1, 60), "lookup": (1, 60)}, scale=1, enabled=True)
        self.assertEqual(limiter.bucket("POST", "/collection/jobs"), "job")
        self.assertEqual(limiter.bucket("POST", "/collection/jobs/abc/run"), "job")
        self.assertEqual(limiter.bucket("POST", "/collection/jobs/abc/embeddings"), "embedding")
        self.assertEqual(limiter.bucket("GET", "/collection/jobs/abc"), "default")
        self.assertTrue(limiter.check("a", "POST", "/collection/jobs")[0])
        self.assertTrue(limiter.check("a", "POST", "/collection/jobs")[0])
        allowed, retry, bucket = limiter.check("a", "POST", "/collection/jobs")
        self.assertFalse(allowed)
        self.assertGreater(retry, 0)
        self.assertEqual(bucket, "job")
        self.assertTrue(limiter.check("b", "POST", "/collection/jobs")[0])   # per client
        self.assertTrue(limiter.check("a", "GET", "/health")[0])            # exempt

    def test_disabled(self):
        limiter = RateLimiter(limits={"default": (1, 60)}, enabled=False)
        self.assertTrue(all(limiter.check("a", "GET", "/x")[0] for _ in range(5)))


class EndpointTests(StoreTestCase):
    def test_limits_and_template_download(self):
        from fastapi.testclient import TestClient
        from app import main
        client = TestClient(main.app)
        limits = client.get("/limits").json()
        self.assertEqual(limits["collection_max_identifiers"], 50)
        self.assertEqual(limits["example_job_id"], "example")
        response = client.get("/downloads/klinkppi_template.py")
        self.assertEqual(response.status_code, 200)
        self.assertIn('DEFAULT_BASE_URL = "http://testserver"', response.text)
        self.assertEqual(client.get("/downloads/secrets.py").status_code, 404)
        self.assertEqual(client.get("/downloads/..%2Fmain.py").status_code, 404)


if __name__ == "__main__":
    unittest.main()
