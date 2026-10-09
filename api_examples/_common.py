from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from klinkppi import KlinkPPIClient  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "api_example_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def client() -> KlinkPPIClient:
    return KlinkPPIClient(os.environ.get("KLINKPPI_API_URL", "http://127.0.0.1:8000"))
