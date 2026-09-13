"""Serving the built interface from the API process.

In development the two run apart: Vite on 5173 proxies `/api` to uvicorn on
8000. A deployment has no proxy, so the API serves the built bundle itself and
the whole platform answers on one origin. That is not only convenience — the
interface calls `/api` as a relative path, so a single origin means there is
no CORS to configure and no build-time API URL to get wrong.

Nothing is mounted when `frontend/dist` is absent, which is the normal state of
a checkout that has never been built. The API then behaves exactly as it did
before this module existed, and `npm run dev` keeps serving the interface.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("gus")

# backend/app/static_site.py -> app -> backend -> repository root
REPO_ROOT = Path(__file__).resolve().parents[2]
DIST = REPO_ROOT / "frontend" / "dist"

# Paths that belong to the API and must never fall through to the interface.
# Without this the catch-all answers an unknown /api path with the HTML shell,
# and a client waiting for JSON reports a parse error instead of a 404.
API_PREFIXES = ("/api", "/docs", "/redoc", "/openapi.json")

# Vite writes every asset with a content hash in its name, so an asset URL
# never changes meaning and can be cached indefinitely. index.html carries no
# hash and names this deploy's assets, so a cached copy outlives the files it
# points at and the page comes up blank after a release.
ASSET_CACHE = "public, max-age=31536000, immutable"
SHELL_CACHE = "no-cache"


def mount_frontend(app: FastAPI, dist: Path | None = None) -> bool:
    """Serve the built interface alongside the API. True when it was found."""
    dist = (dist or DIST).resolve()
    index = dist / "index.html"
    if not index.is_file():
        log.info("No built interface at %s; serving the API only.", dist)
        return False

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", _CachedAssets(directory=assets), name="assets")

    # HEAD as well as GET. Plain Starlette answers HEAD on any GET route;
    # FastAPI does not, so every page replied 405 to the uptime monitors and
    # link unfurlers that ask for headers before they ask for a body.
    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def interface(request: Request, path: str) -> FileResponse:
        """A built file when the path names one, the shell when it does not.

        The shell is the answer for every route the interface owns — /queue,
        /companies/12 — because those exist only in the browser's router. A
        reload or a pasted link would otherwise 404 against the server.
        """
        if any(request.url.path.startswith(prefix) for prefix in API_PREFIXES):
            raise HTTPException(status_code=404, detail="Not found")

        file = _within(dist, path)
        if file is not None:
            return FileResponse(file, headers={"Cache-Control": ASSET_CACHE})
        return FileResponse(index, headers={"Cache-Control": SHELL_CACHE})

    log.info("Serving the interface from %s", dist)
    return True


def _within(dist: Path, path: str) -> Path | None:
    """The file `path` names inside `dist`, or None.

    None covers every case the shell should answer instead: a route of the
    interface, a missing file, and a path that climbs out of the directory.
    `..` is resolved before the check rather than searched for, so an encoded
    or unusual spelling of it cannot walk the filesystem either.
    """
    if not path or path.endswith("/"):
        return None
    try:
        candidate = (dist / path).resolve()
    except (OSError, ValueError):
        return None
    if candidate == dist or dist not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


class _CachedAssets(StaticFiles):
    """StaticFiles that marks hashed assets cacheable."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers.setdefault("Cache-Control", ASSET_CACHE)
        return response
