"""Offline HTTP-contract checks: actual ASGI routing, no external service calls."""
import asyncio
from contextlib import ExitStack, redirect_stdout
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from klinkppi import KlinkPPIClient, KlinkPPIError
from app import main
from app.services.collection_analysis import analyze


class ASGISession:
    """Translate requests into real FastAPI ASGI calls without an extra test dependency."""
    def request(self, method, url, **kwargs):
        prepared = requests.Request(method, url, params=kwargs.get("params"), json=kwargs.get("json")).prepare()
        url = urlsplit(prepared.url)
        body = prepared.body or b""
        if isinstance(body, str):
            body = body.encode()
        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"}, "http_version": "1.1", "method": method,
                 "scheme": "http", "path": url.path, "raw_path": url.path.encode(), "query_string": url.query.encode(),
                 "root_path": "", "headers": [(k.lower().encode(), v.encode()) for k, v in prepared.headers.items()],
                 "client": ("127.0.0.1", 1234), "server": ("test", 80)}
        messages = []
        async def invoke():
            sent = False
            async def receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await asyncio.Event().wait()
            async def send(message):
                messages.append(message)
            # Fixture handlers are synchronous and deterministic. Run them inline
            # so these routing/serialization tests do not depend on worker timing.
            # Production concurrency is not exercised by this contract adapter.
            async def inline_run_sync(func, *args, **kwargs):
                return func(*args)
            with patch("anyio.to_thread.run_sync", new=inline_run_sync):
                await asyncio.wait_for(main.app(scope, receive, send), timeout=10)
        asyncio.run(invoke())
        response = requests.Response()
        response.status_code = next(m["status"] for m in messages if m["type"] == "http.response.start")
        response._content = b"".join(m.get("body", b"") for m in messages)
        response._content_consumed = True
        return response


def fixture_job():
    nodes = [{"id": key, "gene": key, "input": True, "species": "Homo sapiens", "tax_id": "9606"}
             for key in ("P04637", "P38398", "Q00987", "P00533")]
    nodes += [{"id": "P01009", "gene": "A1AT", "input": False},
              {"id": "unknown:0", "gene": "missing", "input": True, "unresolved": True}]
    def edge(index, a, b, dbs):
        return {"id": f"e{index}", "source": nodes[a]["id"], "target": nodes[b]["id"],
                "evidence": [{"database": db, "type": "direct", "methods": ["two hybrid"],
                              "publications": ["123"], "score": .8, "score_name": "score"} for db in dbs]}
    return {"job_id": "fixture", "status": "completed", "created_at": 10, "species": "Homo sapiens", "tax_id": "9606",
            "mode": "induced", "databases": ["IntAct", "BioGrid"], "warnings": [], "progress": "Complete",
            "tokens": [n["id"] for n in nodes], "database_statuses": {}, "selections": {},
            "resolution": [{"input": n["id"], "status": "resolved", "candidates": [n]} for n in nodes],
            "graph": {"nodes": nodes, "edges": [edge(0, 0, 1, ["IntAct", "BioGrid"]),
                       edge(1, 0, 2, ["IntAct"]), edge(2, 1, 2, ["BioGrid"]), edge(3, 0, 4, ["IntAct"])]}}


class ClientContractTests(unittest.TestCase):
    def setUp(self):
        self.api = KlinkPPIClient("http://test", session=ASGISession())
        self.job = fixture_job()

    def test_analysis_matches_web_statistics_and_filtering(self):
        # Feed exactly the same fixtures to the existing JS implementation.
        for filters in ({}, {"databases": ["IntAct"], "method": "two", "min_publications": 1},
                        {"score_database": "IntAct", "min_score": .9}, {"databases": []},
                        {"evidence_type": "predicted"}, {"min_publications": 2}, {"method": "missing"}):
            result = analyze(self.job, **filters)
            js_filters = result["analysis"]["filters"]
            script = '''import {filterGraph, computeStatistics} from './frontend/src/collection/analysis.js';
let input=''; for await (const chunk of process.stdin) input+=chunk;
const {job,filters}=JSON.parse(input);const graph=filterGraph(job.graph, filters);
console.log(JSON.stringify({...graph,statistics:computeStatistics(graph,job.databases)}));'''
            run = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT,
                input=json.dumps({"job": self.job, "filters": js_filters}), text=True, capture_output=True, check=True)
            web = json.loads(run.stdout)
            # Database sets in node statistics have no meaningful ordering.
            for stats in (web["statistics"], result["statistics"]):
                for key in ("degrees", "hubs", "sharedInteractors"):
                    for n in stats[key]:
                        n["databases"].sort()
                for rows in stats["databaseOnlyInteractors"].values():
                    for n in rows:
                        n["databases"].sort()
            self.assertEqual(web["nodes"], result["nodes"])
            self.assertEqual(web["edges"], result["edges"])
            def numeric_precision(value):
                # JS sums binary floats; Python's statistics.mean uses a more
                # precise accumulator. Compare numerical results to 12 decimals.
                if isinstance(value, float):
                    return round(value, 12)
                if isinstance(value, list):
                    return [numeric_precision(item) for item in value]
                if isinstance(value, dict):
                    return {key: numeric_precision(item) for key, item in value.items()}
                return value
            self.assertEqual(numeric_precision(web["statistics"]), numeric_precision(result["statistics"]))
        self.assertNotIn("databases", self.job["graph"]["edges"][0])  # No mutation.

    def test_real_routes_accept_all_client_workflows(self):
        species = {"job_id": "species", "status": "completed", "available_databases": ["IntAct"], "database_statuses": {}}
        review = {**self.job, "status": "awaiting_selection"}
        task = {"alignment_id": "alignment", "status": "completed", "result": {"score": 1}}
        protein = {"accession": "P04637", "gene": "TP53", "sequence": "ACDE", "fasta": ">P04637 TP53\nACDE\n"}
        result = [{"Input": {"UniProtId": "P04637", "TaxonomyId": "9606"}}, {"output": [{"IntAct": [{"info": {}}, {"Interactions": []}]}]}]
        with ExitStack() as stack:
            patches = [
                (main, "resolve_species_context", ("9606", "", {"display_name": "Homo sapiens"})),
                (main, "get_supported_databases", ["String", "IntAct", "BioGrid"]),
                (main, "search_species", [{"display_name": "Homo sapiens", "tax_id": "9606"}]),
                (main, "get_supported_organism_summary", {"fixture": True}),
                (main, "search_gene_name_candidates", [{"primary_accession": "P04637", "gene_names": ["TP53"], "protein_name": "Cellular tumor antigen p53", "reviewed": True}]),
                (main, "create_species_ppi_job", species), (main, "get_species_ppi_job", species),
                (main, "cancel_species_ppi_job", {**species, "status": "cancelled"}),
                (main.collection_search, "create_job", review), (main.collection_search, "snapshot", self.job),
                (main.collection_search, "run_job", self.job), (main.collection_search, "rerun_job", self.job),
                (main.collection_search, "cancel_job", {**self.job, "status": "cancelled"}),
                (main.collection_alignment, "collection_sequence", protein),
                (main.collection_alignment, "start", task), (main.collection_alignment, "snapshot", task),
                (main.collection_go, "shared_go", {"shared_terms": []}),
                (main, "get_job_id", "P04637"), (main, "resolve_database_safely", result[1]["output"][0]["IntAct"]),
                (main, "get_species_ppi_job_rows", ({**species, "tax_id": "9606", "species_name": "Homo sapiens",
                    "database_statuses": {"IntAct": {"status": "completed"}}}, {})),
                (main, "build_species_mitab", io.StringIO("header\n")),
                (main, "build_species_parquet", io.BytesIO(b"PAR1fixture")),
                (main, "flatten_results", [{"source": "P04637", "target": "P38398"}]),
            ]
            for owner, name, value in patches:
                stack.enter_context(patch.object(owner, name, return_value=value))
            def resolve_fixture(database, *args):
                if database == "String":
                    return [{"info": {}}, {"Direct_Interactions": []}, {"Indirect_Interactions": []}]
                key = "Interactions" if database == "IntAct" else "Interactors"
                return [{"info": {}}, {key: []}]
            main.resolve_database_safely.side_effect = resolve_fixture
            main.build_species_mitab.side_effect = lambda *args: io.StringIO("header\n")
            main.build_species_parquet.side_effect = lambda *args: io.BytesIO(b"PAR1fixture")
            self.assertEqual(self.api.health(), {"status": "ok"})
            self.assertTrue(self.api.supported_organisms()["fixture"])
            self.assertEqual(self.api.search_species("human")[0]["tax_id"], "9606")
            self.assertEqual(self.api.search_genes("TP53", tax_id="9606")["candidates"][0]["primary_accession"], "P04637")
            single = self.api.single_search("P04637", databases=["IntAct"], tax_id="9606")
            self.assertEqual(single[0]["Input"]["UniProtId"], "P04637")
            self.assertEqual(self.api.species_search(tax_id="9606", databases=["IntAct"]), species)
            self.assertEqual(self.api.get_species("species"), species)
            self.assertEqual(self.api.cancel_species("species")["status"], "cancelled")
            job = self.api.collection_search(["P04637"], species_name="Homo sapiens", databases=["IntAct"])
            self.assertEqual(job, self.job)
            self.assertEqual(self.api.get_collection("fixture"), self.job)
            self.assertEqual(self.api.rerun_collection("fixture"), self.job)
            self.assertEqual(self.api.cancel_collection("fixture")["status"], "cancelled")
            self.assertEqual(self.api.protein_sequence("fixture", "P04637"), protein)
            self.assertEqual(self.api.shared_go("fixture", "P04637", "P00533"), {"shared_terms": []})
            self.assertEqual(self.api.align_pair("fixture", "P04637", "P00533"), task)
            self.assertEqual(self.api.get_alignment("fixture", "alignment"), task)
            self.assertEqual(self.api.collection_analysis("fixture")["statistics"]["edges"], 4)
            self.assertEqual(self.api.collection_analysis("fixture", databases=[])["edges"], [])
            with self.assertRaises(KlinkPPIError) as caught:
                self.api.collection_analysis("fixture", min_publications=-1)
            self.assertEqual(caught.exception.status_code, 422)
            with tempfile.TemporaryDirectory() as directory:
                for format_name in ("mitab", "parquet"):
                    for kind, value in (("single", single), ("species", species)):
                        path = Path(directory) / f"{kind}.{format_name}"
                        getattr(self.api, f"download_{kind}")(value, path, format_name)
                        self.assertGreater(path.stat().st_size, 0)

            # Run the actual documented examples against these same ASGI routes.
            # This checks their orchestration, field names and file paths together.
            with tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                for module_name, argv in (
                    ("species_lookup", None), ("gene_lookup", ["--accession", "P04637"]),
                    ("single_search", None), ("complete_species_search", []),
                    ("collection_search", ["--databases", "IntAct", "BioGrid"]),
                    ("collection_followups", ["--result", str(folder / "collection_search.json"), "--pair-index", "0"]),
                ):
                    module = importlib.import_module(f"api_examples.{module_name}")
                    with patch.object(module, "OUTPUT_DIR", folder), patch.object(module, "client", return_value=self.api), redirect_stdout(io.StringIO()):
                        module.main() if argv is None else module.main(argv)
                self.assertTrue((folder / "collection_network.graphml").exists())
                self.assertTrue((folder / "shared_go.json").exists())
                self.assertTrue((folder / "pair_alignment.json").exists())
                self.assertTrue(list(folder.glob("*_searches.html")))

    def test_file_limit_duplicates_exports_and_launchers(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for suffix, delimiter in (("csv", "\n"), ("tsv", "\r\n"), ("txt", "\n")):
                path = folder / f"ids.{suffix}"
                ids = [f"gene{i}" for i in range(20)]
                path.write_text('\ufeff' + delimiter.join(ids + ids))
                self.assertEqual(self.api.read_identifiers(path), ids)
                path.write_text(delimiter.join(ids + ["extra"]))
                with self.assertRaisesRegex(ValueError, "20 distinct"):
                    self.api.read_identifiers(path)
            path.write_text("gene,extra\nTP53,value")
            with self.assertRaisesRegex(ValueError, "one identifier"):
                self.api.read_identifiers(path)
            pairs = self.api.unknown_pairs(self.job)
            self.assertEqual(len(pairs), 3)
            analysis = analyze(self.job)
            for fmt in ("json", "graphml", "sif", "cx"):
                output = self.api.export_network(analysis, folder / f"network.{fmt}", fmt)
                self.assertGreater(output.stat().st_size, 0)
            text = self.api.write_protein_search_page({"gene": '<TP53>', "accession": "P04637", "fasta": ">P04637 TP53\nACDE"},
                                                      "Homo sapiens", folder / "search.html").read_text()
            self.assertIn('method="post"', text)
            self.assertIn('&lt;TP53&gt;', text)
            self.assertIn('name="CMD" value="Web"', text)
            self.assertIn("search.foldseek.com", text)
            self.api.export_collection_csv(self.job, folder / "csv")
            self.assertTrue((folder / "csv" / "edges.csv").exists())

    def test_ambiguous_timeout_failures_and_stream_interruption_are_resumable(self):
        ambiguous = {**self.job, "status": "awaiting_selection", "resolution": [{"input": "gene", "candidates": [{"id": "A"}, {"id": "B"}]}]}
        with patch.object(self.api, "start_collection", return_value=ambiguous), self.assertRaises(KlinkPPIError) as caught:
            self.api.collection_search(["gene"], species_name="Homo sapiens", databases=["IntAct"])
        self.assertEqual(caught.exception.job["job_id"], "fixture")
        with patch('klinkppi.time.monotonic', side_effect=[0, 2]), self.assertRaises(KlinkPPIError) as caught:
            self.api.wait_collection({"job_id": "fixture", "status": "running"}, max_wait=1)
        self.assertEqual(caught.exception.job["status"], "running")
        with self.assertRaises(KlinkPPIError):
            self.api.wait_collection({"job_id": "fixture", "status": "failed", "error": "failed source"})
        with patch.object(self.api, "_send", side_effect=KlinkPPIError("offline")), self.assertRaises(KlinkPPIError):
            self.api.health()
        response = Mock(ok=True)
        def chunks(**kwargs):
            yield b"partial"
            raise requests.ConnectionError("interrupted")
        response.iter_content.side_effect = chunks
        with tempfile.TemporaryDirectory() as directory, patch.object(self.api, "_send", return_value=response):
            path = Path(directory) / "existing.parquet"
            path.write_bytes(b"original")
            with self.assertRaises(KlinkPPIError):
                self.api.download_species({"job_id": "fixture"}, path)
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(list(Path(directory).glob("*.part")), [])
            response.close.assert_called_once()

    def test_main_dispatcher_forwards_workflow_help_without_running_other_workflows(self):
        entry = importlib.import_module("python_api_example")
        example = Mock()
        with patch.object(entry, "import_module", return_value=example) as load:
            entry.main(["collection", "--help"])
            load.assert_called_once_with("api_examples.collection_search")
            example.main.assert_called_once_with(["--help"])

    def test_examples_import_without_requests_or_output_creation(self):
        with patch.object(requests.Session, 'request', side_effect=AssertionError("Unexpected request")), patch.object(Path, 'mkdir', side_effect=AssertionError("Unexpected output directory")):
            for name in ("python_api_example", "api_example", "api_examples.species_lookup", "api_examples.single_search",
                         "api_examples.gene_lookup", "api_examples.collection_search", "api_examples.collection_followups",
                         "api_examples.complete_species_search", "api_examples.local_species_download"):
                importlib.import_module(name)
