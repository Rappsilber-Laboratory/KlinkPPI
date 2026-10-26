"""Shared settings. Importing examples performs no requests or file writes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from klinkppi import KlinkPPIClient  # noqa: E402

OUTPUT_DIR = Path(os.environ.get("KLINKPPI_OUTPUT_DIR", str(PROJECT_ROOT / "api_example_outputs")))


def client() -> KlinkPPIClient:
    # Backend origin, or your reverse proxy's full API prefix (e.g. https://host/api).
    return KlinkPPIClient(os.environ.get("KLINKPPI_API_URL", "http://127.0.0.1:8000"),
                         timeout=float(os.environ.get("KLINKPPI_HTTP_TIMEOUT", "60")))


def progress(job):
    """Called on each poll; production code can send this to a logger or UI."""
    print(f"{job.get('job_id', job.get('alignment_id', 'job'))}: {job['status']} — {job.get('progress', '')}")


def report_coverage(job):
    """Completed jobs can contain failed sources or truncated coverage: inspect both."""
    for warning in job.get("warnings", []):
        print(f"Coverage warning: {warning}")
    for database, state in job.get("database_statuses", {}).items():
        print(f"  {database}: {state['status']} — {state.get('message', state.get('error', ''))}")
