"""Production entry point: the built web app at / and the API at /api.

    npm run build                       # builds frontend/dist
    cd backend && ../.venv/bin/python -m uvicorn app.server:application \
        --host 127.0.0.1 --port 8000 --workers 1 \
        --proxy-headers --forwarded-allow-ips=127.0.0.1

Run exactly one worker: background jobs execute inside the process (results
are persisted in SQLite, so restarts are safe). Terminate TLS on port 443 in
the university reverse proxy (see deploy/nginx-klinkppi.conf) and forward all
traffic to this process.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.main import app as api

DIST = Path(os.environ.get("KLINKPPI_FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "SAMEORIGIN",
    # Everything is self-hosted: no third-party scripts, fonts, trackers or cookies.
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; worker-src 'self' blob:; connect-src 'self'; font-src 'self'; "
        "form-action 'self' https://blast.ncbi.nlm.nih.gov; frame-ancestors 'self'"
    ),
}


class SPAStaticFiles(StaticFiles):
    """Serve index.html for client-side routes such as /results/<id> and /help."""

    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or "." in Path(path).name:
                raise
            response = FileResponse(DIST / "index.html")
        if path in {"", ".", "index.html"} or response.media_type == "text/html":
            response.headers["Cache-Control"] = "no-cache"
        return response


application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=api.router.lifespan_context)


@application.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


application.mount("/api", api)
if (DIST / "index.html").exists():
    application.mount("/", SPAStaticFiles(directory=DIST, html=True), name="frontend")
