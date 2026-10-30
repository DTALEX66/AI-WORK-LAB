# SPDX-License-Identifier: MIT
"""V24: compat ``GET /api/health`` must not depend on a build product.

Found by running the suite inside a fresh clone: the route read the built workbench
bundle, the bundle does not exist in a checkout that never built it, the read raised
``FileNotFoundError``, and the kernel's dispatch folded that into
``503 PROJECT_STORE_UNAVAILABLE``. An operator reading that code goes looking at the
database, while the true fact was "nobody has run the UI build here".
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
for _entry in (str(TARGET_ROOT), str(TARGET_ROOT / "domains" / "design")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from design_lab import workbench  # noqa: E402

#: The exact answer the route must give when the bundle is absent, so the test cannot
#: pass by accepting any 2xx.
UNBUILT = {"status": "OK", "scope": "project-metadata", "bundleSha256": None,
           "bundleOrigin": "not-built"}


def _health_body(server, monkeypatch) -> dict:
    def refuse_bundle():
        raise FileNotFoundError(2, "the workbench bundle was never built")

    monkeypatch.setattr(workbench, "served_bundle_sha256", refuse_bundle)
    status, body = server.client.get("/api/health")
    assert status == 200, (status, body)
    return body


def test_health_names_the_missing_bundle_instead_of_blaming_the_store(server, monkeypatch):
    body = _health_body(server, monkeypatch)
    for key, expected in UNBUILT.items():
        assert body[key] == expected, (key, body.get(key), expected)
    assert "PROJECT_STORE_UNAVAILABLE" not in str(body), body
    assert body.get("version"), "health stopped reporting which build it is serving"


def test_the_absence_is_reported_not_silently_omitted(server, monkeypatch):
    """A route that dropped the fields would also read as "fine"; the keys must stay."""
    body = _health_body(server, monkeypatch)
    assert "bundleSha256" in body and "bundleOrigin" in body, sorted(body)
    assert body["bundleOrigin"] == "not-built"


def test_a_served_bundle_is_still_reported_by_origin(server):
    """The falsifier in the other direction: when a bundle IS served, the same route must
    not report the absence. Without this, an implementation that always answered
    ``not-built`` would pass the two tests above."""
    status, body = server.client.get("/api/health")
    assert status == 200, (status, body)
    origin = body.get("bundleOrigin")
    assert origin != "not-built" or not (TARGET_ROOT / "apps" / "workbench" / "dist").exists(), (
        "the route claimed no bundle while a built bundle directory exists")
    if origin != "not-built":
        assert isinstance(body.get("bundleSha256"), str) and len(body["bundleSha256"]) >= 16, body
