# KlinkPPI Python API examples

The HTTP examples use the same backend routes as the web app. They require Python
3.10+ and `requests`; they do not import backend datasets or plotting libraries.
The server needs the normal backend dependencies, configured datasets, and access
to upstream services. Run the server from the repository root:

```bash
npm run dev
```

Run one workflow at a time. The main entry points are equivalent:

```bash
.venv/bin/python python_api_example.py species
.venv/bin/python api_example.py single
.venv/bin/python python_api_example.py gene --gene TP53 --tax-id 9606
.venv/bin/python python_api_example.py collection
.venv/bin/python python_api_example.py complete-species --tax-id 9606 --databases IntAct BioGrid
```

`python_api_example.py` defaults to a single-protein search. Importing it does not
run searches. Complete-species searches can take much longer and are run only when
selected. Modules and direct script invocation also work:

```bash
.venv/bin/python -m api_examples.collection_search --help
.venv/bin/python api_examples/collection_search.py --help
```

Configure the backend origin, HTTP timeout, and output directory with environment
variables. A reverse proxy URL must include its API prefix; do not include `/api`
when connecting directly to the default backend on port 8000.

```bash
KLINKPPI_API_URL=http://127.0.0.1:8000 \
KLINKPPI_HTTP_TIMEOUT=120 \
KLINKPPI_OUTPUT_DIR=/tmp/klinkppi-results \
.venv/bin/python python_api_example.py single
```

Default output goes to `api_example_outputs/`. Direct client calls accept any
output path. JSON/CSV exports create parent directories. HTTP downloads stream to
an adjacent temporary file and replace the destination only after success.

| Web app workflow | Python example | Client methods / HTTP routes |
| --- | --- | --- |
| Supported species and organism coverage | `species_lookup.py` | `health`, `search_species`, `supported_organisms`; `GET /health`, `/species/search`, `/supported-organisms/summary` |
| Gene candidate review | `gene_lookup.py` | `search_genes`; `GET /gene-name/search` |
| Single protein and source selection | `single_search.py` | `single_search`; `GET /search` |
| Single-search MITAB and Parquet | `single_search.py` | `download_single`; `POST /mitab`, `/parquet` |
| Complete species, progress, resume, cancel | `complete_species_search.py` | `start_species`, `get_species`, `wait_species`, `cancel_species`; `/species-ppi/jobs` and `/{job_id}[/cancel]` |
| Species MITAB and Parquet | `complete_species_search.py` | `download_species`; `POST /species-ppi/jobs/{job_id}/{mitab,parquet}` |
| Collection resolution, review, induced/expanded search | `collection_search.py` | `start_collection`, `get_collection`, `wait_collection`, `run_collection`; `/collection/jobs`, `/{job_id}`, `/{job_id}/run` |
| Collection rerun and cancel | `collection_search.py` | `rerun_collection`, `cancel_collection`; `POST /collection/jobs/{job_id}/{rerun,cancel}` |
| Network filters and statistics | `collection_followups.py` | `collection_analysis`; `GET /collection/jobs/{job_id}/analysis` |
| Graph JSON, GraphML, SIF, Cytoscape CX; node/edge CSV | `collection_search.py` | `export_network`, `export_collection_csv` (local exports from API data) |
| Unknown pairs from the full induced result | `collection_followups.py` | `unknown_pairs` (local enumeration before display filters) |
| Exact shared GO terms | `collection_followups.py` | `shared_go`; `GET /collection/jobs/{job_id}/shared-go?source=…&target=…` |
| Validated sequence and FASTA | `collection_followups.py` | `protein_sequence`; `GET /collection/jobs/{job_id}/sequence?accession=…` |
| Pair alignment, stage progress and retry | `collection_followups.py` | `start_alignment`, `get_alignment`, `wait_alignment`, `align_pair`; `POST /collection/jobs/{job_id}/alignments`, `GET /collection/jobs/{job_id}/alignments/{alignment_id}` |
| Embedding scores, explanations, runtime and TSV | `collection_embeddings.py` | `embedding_models`, `start_embedding`, `wait_embedding`, `get_embedding`; `GET /collection/embedding-models`, `POST /collection/jobs/{job_id}/embeddings`, `GET /collection/jobs/{job_id}/embeddings/{embedding_id}` |
| Protein BLAST, AlphaFold and Foldseek links | `collection_followups.py` | `write_protein_search_page` (local HTML launcher, no automatic searches) |

The web app renders network layout, appearance controls, interactive plots,
SVG/PNG snapshots and analysis PDF in the browser. These have no REST endpoints.
Use the web app for those rendered outputs; the Python examples export their
underlying graph, evidence, settings and statistics for analysis in other tools.
SIF contains topology only; JSON retains complete evidence, analysis metadata and
statistics. GraphML and CX retain protein metadata and evidence, and can be opened
in Cytoscape.

## Species, identifiers and databases

Use `search_species` to choose a taxonomy ID and inspect supported sources. Supply
a matching species name where required. Single and collection searches support
these exact source keys (availability varies by species):

`String`, `IntAct`, `BioGrid`, `Corum`, `HuRI`, `Predictomes`, `ComplexPortal`,
`Reactome`, `Signor`, `Hippie`, `HuMap`, `Mint`.

Complete-species support is narrower: `String`, `IntAct`, `BioGrid`, `Corum`,
`HuRI`, `Predictomes`, `ComplexPortal`, `HuMap`. Inspect `database_statuses` and
`available_databases`; a completed job can still have failed or unavailable sources.
Do not infer complete-species support from single-protein organism coverage alone.

Single searches accept explicit identifier types such as `UniProtKB`, `Gene_Name`,
`Ensembl`, and `GeneID`. Review gene matches first rather than relying on a default
mapping when multiple candidates exist:

```bash
.venv/bin/python python_api_example.py gene --gene TP53 --tax-id 9606
# After inspecting gene_candidates.json, explicitly select a returned accession:
.venv/bin/python python_api_example.py gene --gene TP53 --tax-id 9606 --accession P04637
```

## Collections and reviewable mappings

Collections accept **up to 20 distinct identifiers**, after trimming and merging
duplicate rows. This applies to Python iterables, pasted lists in the web app,
CSV/TSV/TXT files, and raw API requests. Files use UTF-8 (optional BOM), one ID per
line, without a header or extra columns. The parser rejects over-limit and
multi-column lists before submitting. The server independently enforces the limit.
Mixed collections use `auto`; an explicit type can disambiguate ID-like gene names.
Isoforms resolve to protein-entry accessions.

```bash
.venv/bin/python python_api_example.py collection --file proteins.csv \
  --input-type auto --mode induced --databases IntAct BioGrid
.venv/bin/python python_api_example.py collection --file proteins.tsv \
  --mode expanded --databases IntAct BioGrid
```

The example writes the job ID immediately, then saves `collection_resolution.json`.
Single-candidate IDs proceed automatically. Ambiguous IDs require explicit choices;
unresolved or skipped IDs remain isolated. If review is needed, the script exits
without starting interaction queries. Create a JSON choices file using original
input strings as keys, for example `{"TP53": "P04637", "skip_this_id": null}`, then:

```bash
.venv/bin/python python_api_example.py collection --job-id YOUR_JOB_ID --choices choices.json
.venv/bin/python python_api_example.py collection --job-id YOUR_JOB_ID --rerun
.venv/bin/python python_api_example.py collection --job-id YOUR_JOB_ID --cancel
```

`rerun_collection` preserves the reviewed inputs/mappings, species, sources and
network mode. Collection jobs live in one server process, expire after one hour
when inactive, and disappear on backend restart. Save exports while available.
There is a capacity limit of 12 retained collection jobs. Polling progress does
not imply every upstream database succeeded; inspect coverage warnings and
truncation before interpreting missing interactions.

For short programs, `collection_search(...)` combines resolution and analysis.
Ambiguity raises `KlinkPPIError` with the reviewable job in `error.job`:

```python
from klinkppi import KlinkPPIClient, KlinkPPIError

with KlinkPPIClient() as api:
    try:
        job = api.collection_search(
            ["TP53", "BRCA1"], species_name="Homo sapiens", tax_id="9606",
            databases=["IntAct", "BioGrid"], input_type="Gene_Name",
        )
    except KlinkPPIError as error:
        if error.job is not None:
            print(error.job["job_id"], error.job.get("resolution"))
        raise
```

## Filters, statistics and followups

Run followups against a saved completed collection while its server job is live:

```bash
.venv/bin/python python_api_example.py followups
# Inspect unknown_pairs.json, then explicitly choose a printed pair:
.venv/bin/python python_api_example.py followups --pair-index 0
```

The first command fetches network analysis and lists unknown pairs. Choosing a pair
fetches both protein sequences, exact shared GO terms, and a global alignment.
Each lookup handles failure independently; rerunning the command retries failed
lookups and reuses successful server sequence caches. GO/alignment comparisons
require a completed **induced** collection and a distinct resolved input pair with
no interaction evidence in the full result. Missing evidence, shared GO terms and
sequence similarity do not establish whether two proteins interact.

`collection_analysis` mirrors web filters: selected databases, `evidence_type`
(`all`, `direct`, `functional`, `predicted`), method substring, minimum distinct
publications, and a source-specific raw score cutoff. For example:

```python
filtered = api.collection_analysis(
    job["job_id"], databases=["IntAct", "BioGrid"], evidence_type="direct",
    method="two hybrid", min_publications=1,
    score_database="IntAct", min_score=0.6,
)
api.export_network(filtered, "filtered.graphml", "graphml")
```

The equivalent HTTP query is
`GET /collection/jobs/{job_id}/analysis?databases=IntAct&databases=BioGrid&evidence_type=direct&method=two%20hybrid&min_publications=1&score_database=IntAct&min_score=0.6`.
Omit `databases` for all searched sources; `databases=` selects none. The response
contains `nodes`, `edges`, `analysis` and `statistics`. A score cutoff removes
evidence only from that source; independently supported pairs remain. Scores stay
on their original scales. Isolated inputs remain visible; orphan first neighbors
are removed. Statistics include source overlap/Jaccard, components, degree/hubs,
mean local clustering, per-source score distributions and shared/source-only
interactors. Isolated nodes contribute zero clustering; empty-union Jaccard is null.

FASTA lookup checks the exact accession and collection taxonomy against UniProt,
uses the collection gene name in the header, and caches successful sequences for
up to one hour. Long FASTA sequences can be exported or used in BLAST; interactive
alignment is limited to 20,000 residues per sequence and 25 million position pairs.
Alignment results contain sequences, score, identity, gaps and scoring parameters.

Open the generated `{ACCESSION}_searches.html` locally and click **Search BLASTP ↗**.
The form POST prefills FASTA and a descriptive job title without URL length limits;
you choose settings and start the search at NCBI. The page includes selectable
FASTA and an AlphaFold link. Choose **Similar structures** on AlphaFold for
Foldseek; if no model is available, paste FASTA into <https://search.foldseek.com/>.
The scripts do not access your clipboard or launch searches automatically.

## Progress, cancellation and errors

Use `start_*`, `get_*`, `wait_*` and `cancel_*` to control jobs explicitly.
`species_search`, `collection_search` and `align_pair` are blocking convenience
methods. Wait methods accept `poll_interval`, `max_wait` (seconds; default 3600,
`None` for no polling deadline), and an `on_progress(job)` callback.
HTTP request timeout and polling deadline are separate; a request already in
flight can take up to the HTTP timeout. A polling timeout leaves the server job
running; `KlinkPPIError.job` holds the last known state for resuming or cancelling.
An alignment timeout carries an alignment task; retain the parent collection ID.

```bash
.venv/bin/python python_api_example.py complete-species --job-id YOUR_JOB_ID
.venv/bin/python python_api_example.py complete-species --job-id YOUR_JOB_ID --cancel
```

`KlinkPPIError.status_code` identifies HTTP errors; transport failures use `None`.
Inspect API validation errors (400/422), expired jobs (404), capacity errors (429),
and upstream lookup failures (502). POSTs are never automatically retried, since
a lost response may still have created a job. Resume a known job before creating
another. A failed alignment can be retried with `start_alignment`; there is no
alignment-cancel endpoint. Closing a client closes its owned HTTP session and does
not implicitly cancel server jobs.

## Local downloader and regression checks

The old in-process species downloader remains available separately:

```bash
.venv/bin/python api_examples/local_species_download.py
```

It requires backend dependencies and local datasets, writes one file per source,
and exports all columns. The HTTP examples above are the main web-compatible API.

Run offline checks (backend datasets/dependencies are required for app imports;
Node is used to compare API statistics with the existing frontend implementation):

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
npm --prefix frontend test
```

The API/client tests exercise real ASGI routing with synchronous upstream fixture
handlers run inline (production concurrency is not exercised), stream failure recovery, mapping review, validation, graph export and frontend statistics
parity. Live upstream services and complete production datasets are not exercised
by those offline checks.

## Embedding scores for unknown collection pairs

Run the standalone example using a completed induced collection created by
`collection_search.py`. List the unknown pairs first, then select one:

```bash
.venv/bin/python python_api_example.py embedding --list-models
.venv/bin/python python_api_example.py embedding
.venv/bin/python python_api_example.py embedding --pair-index 0 --models esm2-8m
# Multiple models are allowed in one API request:
.venv/bin/python python_api_example.py embedding --pair-index 0 --models esm2-8m esm2-35m esmc-300m
```

You can also run `.venv/bin/python api_examples/collection_embeddings.py --help`
or `.venv/bin/python -m api_examples.collection_embeddings --help`.
The default collection file is `api_example_outputs/collection_search.json`;
use `--result path/to/collection_search.json` or `--job-id YOUR_JOB_ID` to choose
another live collection. `KLINKPPI_OUTPUT_DIR` sets the output directory and the
default collection-file directory, as for the other examples.

**The API accepts one or multiple distinct supported models in `models`.**
The web UI allows one model at a time. Multiple API models run sequentially on the
server, and their scores are returned together. Large models or first-time downloads
may need a longer polling deadline; pass `--max-wait 7200` for two hours.

The example saves `{PAIR}_plm_scores.tsv` with exactly `metric` and `value` columns
and full-precision values, matching the web download. `{PAIR}_plm_scores.json`
contains the task, scores, explanations, total runtime, and per-model runtime.
The initial task is saved immediately; a polling failure also preserves the last
known task in JSON. No TSV is written for a failed computation. Without
`--pair-index`, the example only lists pairs and does not load any model.

The API supports all 12 models listed in
`embedding_FW/examples/test_two_seqs_mem.py`: `esm2-8m`, `esm2-35m`,
`esm2-150m`, `esm2-650m`, `esm1b-650m`, `esm1v-650m-1` through
`esm1v-650m-5`, `esmc-300m`, and `esmc-600m`. Other framework registry
models are not exposed by KlinkPPI. Run setup with Python 3.12+ to install
the bundled framework and both model backends.

Call `client.embedding_models()` for supported model IDs and metric descriptions.
For an unknown pair in a completed induced collection, call:

```python
task = client.embed_pair(
    job_id, source_accession, target_accession,
    models=["esm2-8m", "esmc-300m"],
)
print(task["runtime_seconds"])
print(task["result"]["scores"])
print(task["result"]["descriptions"])
print(task["result"]["model_runtime_seconds"])
```

For polling, use `start_embedding(...)` and `get_embedding(job_id, embedding_id)`.
HTTP routes are `GET /collection/embedding-models`,
`POST /collection/jobs/{job_id}/embeddings` (source, target, models), and
`GET /collection/jobs/{job_id}/embeddings/{embedding_id}`. Jobs return progress,
runtime and either explained scores or an error; partial scores are not returned.
Weights download on first use. Scores indicate similarity, not interaction
probability. Full sequences are required: ESM-2/1b/1v support up to 1,022 residues;
ESM-C up to 2,046. See the root README for setup, metrics and runtime semantics.
