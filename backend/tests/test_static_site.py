"""Serving the built interface from the API process.

This is the deployment's shape: one origin, the API under /api and the
interface everywhere else. The cases below are the ones that decide whether a
deployed build works at all — a reloaded deep link, an unknown API path, and a
request that tries to read the server's own files.

A built interface is not assumed. The tests below build a small `dist` of their
own, so they check the serving rules rather than whatever `npm run build` last
produced, and they pass in a checkout that has never been built.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static_site import mount_frontend

SHELL = '<!doctype html><html><body><div id="root"></div></body></html>'


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    directory = tmp_path_factory.mktemp("dist")
    (directory / "index.html").write_text(SHELL, encoding="utf-8")
    (directory / "assets").mkdir()
    (directory / "assets" / "index-abc123.js").write_text("export default 1;\n", encoding="utf-8")
    (directory / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    # The file a traversal would be reaching for, one level above the build.
    (directory.parent / "secret.txt").write_text("not for the public", encoding="utf-8")
    return directory


@pytest.fixture(scope="module")
def site(dist):
    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    assert mount_frontend(app, dist) is True
    with TestClient(app) as test_client:
        yield test_client


def test_nothing_is_mounted_without_a_build(tmp_path):
    """A checkout that has never been built still serves its API."""
    app = FastAPI()
    assert mount_frontend(app, tmp_path / "never-built") is False


def test_root_serves_the_shell(site):
    response = site.get("/")
    assert response.status_code == 200
    assert '<div id="root">' in response.text


@pytest.mark.parametrize(
    "path",
    ["/queue", "/impact", "/companies/12", "/companies/12/history", "/audit-trail"],
)
def test_interface_routes_survive_a_reload(site, path):
    """Routes that exist only in the browser's router are served the shell.

    Without this a reload, or a pasted link, 404s against the server.
    """
    response = site.get(path)
    assert response.status_code == 200
    assert '<div id="root">' in response.text


def test_built_files_are_served(site):
    response = site.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert "export default 1;" in response.text

    assert site.get("/favicon.ico").status_code == 200


def test_hashed_assets_are_cacheable_and_the_shell_is_not(site):
    """A cached shell outlives the assets it names, and the page comes up blank."""
    assert "immutable" in site.get("/assets/index-abc123.js").headers["cache-control"]
    assert site.get("/").headers["cache-control"] == "no-cache"


def test_unknown_api_paths_do_not_fall_through_to_the_interface(site):
    """A client waiting for JSON must not be handed the HTML shell."""
    response = site.get("/api/no-such-endpoint")
    assert response.status_code == 404
    assert "<div" not in response.text


def test_the_api_still_answers(site):
    assert site.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "path",
    [
        "/../secret.txt",
        "/../../secret.txt",
        "/%2e%2e/secret.txt",
        "/assets/../../secret.txt",
        "/....//secret.txt",
    ],
)
def test_traversal_cannot_read_outside_the_build(site, path):
    """Whatever the spelling, nothing above `dist` is readable."""
    response = site.get(path)
    assert "not for the public" not in response.text
    # The shell or a 404 are both fine; serving the file is not.
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert '<div id="root">' in response.text
