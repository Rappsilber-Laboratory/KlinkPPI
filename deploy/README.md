# Deploying KlinkPPI

Users only need a web browser: nothing is installed or preprocessed on their side.
The operator prepares the server once.

1. Install dependencies and build the web app (repository root):

   ```bash
   npm install          # creates .venv, installs Python + frontend packages
   npm run build        # writes frontend/dist
   ```

2. Prepare all server-side data and the tutorial example result:

   ```bash
   .venv/bin/python scripts/prepare_server.py --models
   .venv/bin/python scripts/prepare_server.py --check   # every line must be OK
   ```

3. Run the production server (one worker; jobs run in-process and are persisted in
   `Data/jobs/klinkppi_jobs.sqlite3`, so restarts keep every result):

   ```bash
   npm run serve        # or install deploy/klinkppi.service
   ```

4. Put `deploy/nginx-klinkppi.conf` (or the equivalent Apache config) in front for HTTPS
   on port 443. Monitor `https://<host>/api/health?details=true`.

## Configuration (environment variables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `KLINKPPI_RESULT_RETENTION_DAYS` | `14` | Days a result stays at its bookmarkable link |
| `KLINKPPI_JOB_DB` | `Data/jobs/klinkppi_jobs.sqlite3` | Job database |
| `KLINKPPI_PUBLIC_API_URL` | request URL | API URL written into the downloadable template script |
| `KLINKPPI_MAX_ACTIVE_COLLECTION_JOBS` | `8` | Collection analyses resolving/running at once |
| `KLINKPPI_MAX_ACTIVE_COLLECTION_JOBS_PER_CLIENT` | `3` | Running analyses per client address |
| `KLINKPPI_COLLECTION_WORKERS` | `2` | Parallel collection analyses (others wait in the queue) |
| `KLINKPPI_EMBEDDING_MODELS` | all 12 | Comma-separated allowlist (e.g. smaller models on CPU-only hosts) |
| `KLINKPPI_EMBEDDING_WORKERS` | `1` | Concurrent model inferences (keep 1 per GPU) |
| `KLINKPPI_MAX_QUEUED_EMBEDDINGS` | `16` | Queued + running embedding comparisons |
| `KLINKPPI_MAX_QUEUED_EMBEDDINGS_PER_CLIENT` | `2` | Per client address |
| `KLINKPPI_MAX_MODELS_PER_EMBEDDING` | `3` | Models per comparison request |
| `KLINKPPI_MAX_ACTIVE_ALIGNMENTS` | `64` | Queued + running pairwise alignments |
| `KLINKPPI_RATE_LIMITS` | `on` | `off` disables per-client rate limits |
| `KLINKPPI_RATE_LIMIT_SCALE` | `1` | Multiplies every rate limit |
| `KLINKPPI_BUILD_EXAMPLE` | `1` | Build the tutorial example on startup when missing |
| `KLINKPPI_ALLOWED_ORIGINS` | – | Extra CORS origins (not needed when served from one host) |

Client addresses are used only in memory for fair-use limits; they are never written
to the job database. Disable or anonymise proxy access logs for the same reason.
