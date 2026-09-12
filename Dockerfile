# GUS-DEDEKTIV as one container: the API serves the built interface, so the
# whole platform answers on a single origin with no CORS and no build-time API
# URL to get wrong.
#
# Build and run it the same way Render will:
#   docker build -t gus-dedektiv .
#   docker run --rm -p 8000:8000 -e PORT=8000 gus-dedektiv

# --------------------------------------------------------------------------- #
# The interface
# --------------------------------------------------------------------------- #
FROM node:20-slim AS web

WORKDIR /build
# The lockfile alone first, so a source edit does not reinstall the world.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# --------------------------------------------------------------------------- #
# The service
# --------------------------------------------------------------------------- #
FROM python:3.12-slim AS runtime

# LightGBM links against OpenMP, which the slim image does not carry. Without
# it the model engine cannot load and the service quietly falls back to the
# rule engine.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# The layout matches the repository, because the panel is resolved relative to
# the repository root and the API looks for the interface at frontend/dist.
COPY backend/ backend/
COPY ml/data/output/csv/ ml/data/output/csv/
COPY --from=web /build/dist/ frontend/dist/

WORKDIR /app/backend

# Seeded here rather than at boot. Building the database means importing the
# panel and scoring 600 companies across 14 periods, which is half a minute of
# CPU; doing that on the first request would make every deploy look broken for
# as long as it took. A boot now opens a database that is already there.
RUN python -m app.database.gus_import --reset

# The service writes decisions, so it owns its directory: SQLite needs to
# create a journal beside the database, not only write the file.
RUN useradd --create-home --uid 10001 gus && chown -R gus:gus /app
USER gus

EXPOSE 8000

# For `docker run`. Render uses healthCheckPath from render.yaml instead.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health',timeout=4).status==200 else 1)"

# One worker on purpose. The active scoring policy is process state, loaded at
# startup and replaced by PUT /api/scoring/policy; a second worker would keep
# its own copy and serve the old thresholds until it restarted.
#
# Deliberately without --proxy-headers. Behind a platform proxy it would take
# the client address from X-Forwarded-For, and with the wildcard trust such a
# deployment needs, uvicorn reads the leftmost entry of that header — which the
# caller writes. The assistant's rate limit is keyed on that address and every
# call it allows is a paid one, so a spoofable address means a spoofable
# ceiling on someone else's bill. Without the flag every anonymous viewer
# shares one allowance: lower, and not something a caller can talk its way out
# of. ASSISTANT_REQUESTS_PER_MINUTE sizes it.
#
# exec, so uvicorn is PID 1 and stops on the signal Render sends it.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
