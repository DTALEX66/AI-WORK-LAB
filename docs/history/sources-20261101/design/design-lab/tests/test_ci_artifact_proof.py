#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CLOUDAUDIT-H001: hermetic tests for the main-branch CI artifact proof gate.

Every test injects a fake ``fetch`` into
``design-lab/scripts/verify_ci_artifact_proof.py``, so no socket is ever
opened (one test even makes the fake raise the gate's own
``FetchUnavailable`` to model "no network").

Covered outcomes (the tri-state contract):
- PASS: run/SHA bound, both named artifacts downloaded, sha256 matches the
  API-reported digest -> exit 0, findings empty, proof record persisted
- BLOCKED: run not found / run/SHA mismatch / digest mismatch -> exit 2
- INCOMPLETE: no token, API unreachable, unindexed artifact (with and
  without the paced re-query) -> exit 3, never a silent PASS

The paced re-query is proven without sleeping: the test injects a fake
``sleep`` that records the call and flips the fake fetch from "unindexed"
to "indexed", proving the retry actually re-queries and that the final
status follows the second answer.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "design-lab" / "scripts" / "verify_ci_artifact_proof.py"

SLUG = "dtalex66/design-lab"
RUN_ID = "998877"
SHA = "a" * 40
OTHER_SHA = "b" * 40
TOKEN = "fake-ci-token"
ARTIFACT_S = "secret-history-report"
ARTIFACT_E2 = f"workbench-e2-{SHA}"

BYTES_S = b"secret-history-report-bytes-v1"
BYTES_E2 = b"browser-e2e-summary-and-screenshot"
DIGEST_S = hashlib.sha256(BYTES_S).hexdigest()
DIGEST_E2 = hashlib.sha256(BYTES_E2).hexdigest()
ARCHIVE_S = f"https://api.github.com/repos/{SLUG}/actions/artifacts/111/zip"
ARCHIVE_E2 = f"https://api.github.com/repos/{SLUG}/actions/artifacts/222/zip"


def load_gate():
    spec = importlib.util.spec_from_file_location("verify_ci_artifact_proof_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


gate = load_gate()


class FakeFetch:
    """Deterministic stand-in for the gate's single network entry point.

    Unknown URLs answer 404 (how GitHub reports "absent"); ``unavailable``
    URLs raise the gate's own ``FetchUnavailable`` to model no-network.
    """

    def __init__(self, routes=None, unavailable=()):
        self.routes = dict(routes or {})
        self.unavailable = set(unavailable)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, url, token=None, accept=gate.GITHUB_JSON):
        self.calls.append((url, accept))
        if url in self.unavailable:
            raise gate.FetchUnavailable("simulated network failure")
        if url not in self.routes:
            return gate.FetchResponse(404, b'{"message": "Not Found"}', {})
        status, body = self.routes[url]
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        return gate.FetchResponse(status, bytes(body), {})


def run_record(head_sha=SHA):
    return {"id": RUN_ID, "name": "Canonical Verify", "head_sha": head_sha}


def artifact_list(names_digests, archives=None):
    archives = archives or {}
    artifacts = [
        {
            "name": name,
            "digest": f"sha256:{digest}",
            "archive_download_url": archives.get(name, ""),
        }
        for name, digest in names_digests
    ]
    return {"artifacts": artifacts}


def green_routes():
    """A fully consistent main run: identity + both artifacts + downloads."""
    return {
        gate.runs_url(SLUG, RUN_ID): (200, run_record()),
        gate.run_artifacts_url(SLUG, RUN_ID): (
            200,
            artifact_list([(ARTIFACT_S, DIGEST_S), (ARTIFACT_E2, DIGEST_E2)],
                         {ARTIFACT_S: ARCHIVE_S, ARTIFACT_E2: ARCHIVE_E2}),
        ),
        ARCHIVE_S: (200, BYTES_S),
        ARCHIVE_E2: (200, BYTES_E2),
    }


CONTRACT_RE = re.compile(r"^CI_ARTIFACT_PROOF=(PASS|BLOCKED|INCOMPLETE) gate=ADVISORY checks=\d+ findings=\[.*\]$")


class GateBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def run_gate(self, fake, **overrides):
        params = dict(
            repo=SLUG,
            run_id=RUN_ID,
            sha=SHA,
            artifact_names=[ARTIFACT_S, ARTIFACT_E2],
            token=TOKEN,
            download_dir=str(self.tmp / "downloads"),
            proof_path=str(self.tmp / "proof" / "ci-artifact-proof.json"),
            fetch_fn=fake,
            retry_seconds=0.0,
            log=lambda _m: None,
        )
        params.update(overrides)
        return gate.run_proof(**params)


class PassPathTest(GateBase):
    def test_full_readback_passes_with_three_checks(self):
        fake = FakeFetch(green_routes())
        code = self.run_gate(fake)
        self.assertEqual(code, 0)
        # identity (1) + two artifacts (2) = 3 checks, zero findings
        proof = json.loads((self.tmp / "proof" / "ci-artifact-proof.json").read_text(encoding="utf-8"))
        self.assertEqual(proof["status"], "PASS")
        self.assertEqual(proof["checks"], 3)
        self.assertEqual(proof["findings"], [])
        self.assertEqual(proof["runId"], RUN_ID)
        self.assertEqual(proof["subjectSha"], SHA)
        self.assertEqual(proof["facts"]["run_head_sha"], SHA)
        self.assertIn(f"sha256={DIGEST_S}", proof["facts"][f"artifact_{ARTIFACT_S}"])

    def test_downloads_persisted_next_to_proof(self):
        fake = FakeFetch(green_routes())
        self.run_gate(fake)
        self.assertEqual((self.tmp / "downloads" / f"{ARTIFACT_S}.zip").read_bytes(), BYTES_S)
        self.assertEqual((self.tmp / "downloads" / f"{ARTIFACT_E2}.zip").read_bytes(), BYTES_E2)

    def test_download_leg_carries_json_accept(self):
        # api.github.com's artifact archive route negotiates Accept and
        # answers 415 "Must accept 'application/json'" for octet-stream
        # (DL-CLOUDAUDIT-2026-09-25 H001). The bytes are a binary zip,
        # but the request must carry the JSON Accept the gateway requires.
        fake = FakeFetch(green_routes())
        self.run_gate(fake)
        accepts = {url: accept for url, accept in fake.calls}
        self.assertEqual(accepts[ARCHIVE_S], gate.GITHUB_JSON)
        self.assertEqual(accepts[ARCHIVE_E2], gate.GITHUB_JSON)

    def test_contract_line_shape(self):
        fake = FakeFetch(green_routes())
        lines = []
        self.run_gate(fake, log=lines.append)
        contract = [l for l in lines if l.startswith("CI_ARTIFACT_PROOF=")]
        self.assertEqual(len(contract), 1)
        self.assertRegex(contract[0], CONTRACT_RE)


class IdentityTest(GateBase):
    def test_run_sha_mismatch_is_blocked_and_skips_artifacts(self):
        routes = green_routes()
        routes[gate.runs_url(SLUG, RUN_ID)] = (200, run_record(head_sha=OTHER_SHA))
        fake = FakeFetch(routes)
        code = self.run_gate(fake)
        self.assertEqual(code, 2)
        # only the identity check ran: the artifact leg is skipped entirely on
        # a blocked identity (no artifact-list queries, no downloads)
        self.assertEqual(len([c for c in fake.calls if "/artifacts/" in c[0]]), 0)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0][0], gate.runs_url(SLUG, RUN_ID))
        self.assertEqual(fake.calls[0][1], gate.GITHUB_JSON)

    def test_run_not_found_is_blocked(self):
        routes = green_routes()
        del routes[gate.runs_url(SLUG, RUN_ID)]  # unknown URL -> 404
        code = self.run_gate(FakeFetch(routes))
        self.assertEqual(code, 2)

    def test_identity_query_failure_is_incomplete(self):
        routes = green_routes()
        routes[gate.runs_url(SLUG, RUN_ID)] = (500, b"boom")
        code = self.run_gate(FakeFetch(routes))
        self.assertEqual(code, 3)


class ArtifactTest(GateBase):
    def test_digest_mismatch_is_blocked(self):
        routes = green_routes()
        # tampered download: different bytes than the API-reported digest
        routes[ARCHIVE_S] = (200, b"tampered-bytes")
        code = self.run_gate(FakeFetch(routes))
        self.assertEqual(code, 2)
        proof = json.loads((self.tmp / "proof" / "ci-artifact-proof.json").read_text(encoding="utf-8"))
        self.assertTrue(any(f.startswith("ARTIFACT-SHA256-MISMATCH") for f in proof["findings"]))

    def test_missing_archive_url_is_blocked(self):
        routes = green_routes()
        routes[gate.run_artifacts_url(SLUG, RUN_ID)] = (
            200,
            artifact_list([(ARTIFACT_S, DIGEST_S), (ARTIFACT_E2, DIGEST_E2)]),  # no archive urls
        )
        code = self.run_gate(FakeFetch(routes))
        self.assertEqual(code, 2)

    def test_download_unavailable_is_incomplete(self):
        fake = FakeFetch(green_routes(), unavailable=[ARCHIVE_S])
        code = self.run_gate(fake)
        self.assertEqual(code, 3)

    def test_artifact_list_404_is_incomplete(self):
        routes = green_routes()
        del routes[gate.run_artifacts_url(SLUG, RUN_ID)]
        code = self.run_gate(FakeFetch(routes))
        self.assertEqual(code, 3)


class UnindexedRetest(GateBase):
    def test_unindexed_artifact_stays_incomplete_without_retry(self):
        routes = green_routes()
        # the second artifact is not in the list yet
        routes[gate.run_artifacts_url(SLUG, RUN_ID)] = (
            200,
            artifact_list([(ARTIFACT_S, DIGEST_S)], {ARTIFACT_S: ARCHIVE_S}),
        )
        code = self.run_gate(FakeFetch(routes))
        self.assertEqual(code, 3)

    def test_paced_requery_recovers_when_indexing_catches_up(self):
        # The artifact listing lacks the E2 artifact (indexing lag) until the
        # paced sleep elapses; the re-query after the sleep sees it. The lag
        # flips off inside the injected sleep, so pass 1 reports E2
        # unindexed and the single re-query proves it.
        full = green_routes()
        full_list = full[gate.run_artifacts_url(SLUG, RUN_ID)]
        first_list = (200, artifact_list([(ARTIFACT_S, DIGEST_S)], {ARTIFACT_S: ARCHIVE_S}))

        state = {"lag_active": True}
        calls = {"list_queries": 0}
        slept: list[float] = []

        def routing(url, token=None, accept=gate.GITHUB_JSON):
            if url == gate.run_artifacts_url(SLUG, RUN_ID):
                calls["list_queries"] += 1
                status, body = first_list if state["lag_active"] else full_list
            elif url in full:
                status, body = full[url]
            else:
                return gate.FetchResponse(404, b'{"message": "Not Found"}', {})
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode("utf-8")
            return gate.FetchResponse(status, bytes(body), {})

        def paced_sleep(seconds: float) -> None:
            slept.append(seconds)
            state["lag_active"] = False

        code = self.run_gate(
            FakeFetch(green_routes()),
            fetch_fn=routing,
            retry_seconds=5.0,
            sleep=paced_sleep,
        )
        self.assertEqual(code, 0, "the paced re-query must turn the unindexed run into a PASS")
        self.assertEqual(slept, [5.0])
        self.assertEqual(
            calls["list_queries"], 3,
            "pass 1 lists twice (once per artifact) under lag; the re-query lists once",
        )


class NoTokenTest(GateBase):
    def test_missing_token_is_incomplete_and_never_passes(self):
        code = self.run_gate(FakeFetch(green_routes()), token=None)
        self.assertEqual(code, 3)

    def test_no_repo_is_incomplete(self):
        code = self.run_gate(FakeFetch(green_routes()), repo="")
        self.assertEqual(code, 3)

    def test_no_artifact_names_is_incomplete(self):
        code = self.run_gate(FakeFetch(green_routes()), artifact_names=[])
        self.assertEqual(code, 3)


class DefaultWiringTest(GateBase):
    def test_main_defaults_read_github_env_and_fail_closed_without_token(self):
        sha = "c" * 40
        env = {
            "GITHUB_REPOSITORY": SLUG,
            "GITHUB_RUN_ID": RUN_ID,
            "GITHUB_SHA": sha,
        }
        fake = FakeFetch()
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True):
            with redirect_stdout(out):
                code = gate.main(["--retry-seconds", "0"], fetch_fn=fake)
        self.assertEqual(code, 3)  # no GITHUB_TOKEN in the cleared env -> INCOMPLETE
        text = out.getvalue()
        # the default artifact set is derived from GITHUB_SHA
        self.assertIn(f"workbench-e2-{sha}", text)
        self.assertIn(ARTIFACT_S, text)
        matched = [l for l in text.splitlines() if re.match(CONTRACT_RE, l)]
        self.assertEqual(len(matched), 1)
        self.assertEqual(fake.calls, [], "no network may be attempted without a token")


if __name__ == "__main__":
    unittest.main()
