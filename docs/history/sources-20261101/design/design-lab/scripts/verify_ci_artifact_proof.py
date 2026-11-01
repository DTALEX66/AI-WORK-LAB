#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CLOUDAUDIT-H001: main-branch CI artifact proof gate (download readback).

FINAL TaskPack section H / H001:
  "main run #182 artifacts=0. 如要求 artifact proof，必须真实
   upload -> GitHub API query -> identity -> download/readback -> hash
   -> run/SHA binding."

State of the world this closes
------------------------------
The release layer already has the FULL real-readback chain, but only for tag
operations: ``release-gate.yml`` (tag-only, owner-gated, E5) drives
``design-lab/scripts/verify_release_preflight.py`` (identity -> CI run ->
download + sha256 -> release assets -> run/SHA binding).

What was missing is the *main-branch* side: the canonical verify run uploads
artifacts (``secret-history-report`` from the license-secret-gate;
``workbench-e2-<sha>`` from the browser-e2e job) but no step ever proved
those uploads actually reached GitHub, that the bytes come back identical,
and that they are bound to the exact run/SHA. H001 is that proof.

The four legs, against THIS run (``GITHUB_RUN_ID`` + ``GITHUB_SHA`` -- the
trusted default env vars every CI step receives, never attacker-controlled
event inputs)
--------------------------------------------------------------------------
1. identity : query ``/actions/runs/{run_id}``; the run's ``head_sha`` must
              equal the expected subject SHA (run/SHA binding). If the
              identity leg fails, the artifact leg is not attempted at all --
              proving bytes against the wrong run is a contradiction, not a
              proof.
2. query    : ``/actions/runs/{run_id}/artifacts`` must list the artifact by name.
3. download : fetch the artifact archive and recompute sha256.
4. hash     : the recomputed digest must equal the digest GitHub's API
              reported for that artifact (``digest: "sha256:<hex>"``).

Boundary, stated honestly (never silently widened):
    step 4 compares two API-produced facts (the uploaded bytes' digest vs.
    GitHub's own digest of those same bytes) -- a download round-trip /
    availability proof on the main branch. It is NOT independent asset
    identity: the independent ``artifacts.sha256`` asset-set + checksum
    binding stays in the release layer (``release-gate.yml`` /
    ``verify_release_preflight.py``), where published release assets are
    checked against locally-known digests. H001 proves the upload -> readback
    leg on main; it does not re-implement the release leg.

Indexing lag, and why the gate paces a re-query
-----------------------------------------------
H001 runs as its own job *after* the two uploader jobs, i.e. seconds after
their ``upload-artifact``. GitHub's ``/artifacts`` list API indexes uploads
asynchronously, so a just-uploaded artifact is frequently not yet listed.
That lag is a real, recurring property of this exact timing (unlike the
tag-time release preflight, whose artifacts pre-exist the check). So the
gate paces ONE re-query of the still-incomplete artifacts after
``--retry-seconds`` (default 20s): the common lag resolves to PASS within a
single run instead of forcing a manual re-dispatch. A genuinely BLOCKED
artifact (a digest mismatch / missing download URL) is terminal and is never
re-queried.

Output contract
---------------
    CI_ARTIFACT_PROOF=<PASS|BLOCKED|INCOMPLETE> checks=N findings=[...]

- ``PASS``       (exit 0): run identity bound, every named artifact found in
             the run's artifact list (after at most one paced re-query),
             downloaded, and its recomputed sha256 matched the API-reported
             digest.
- ``BLOCKED``    (exit 2): a check ran and contradicted the claim (run not
             found / run/SHA mismatch / named artifact has no download URL /
             digest mismatch). BLOCKED is terminal -- the re-query is skipped.
- ``INCOMPLETE`` (exit 3): a check could not run (no token, API unreachable,
             not-JSON answer, or an artifact still not indexed even after the
             re-query). An unindexed artifact is NEVER a PASS.

Usage (from the non-required ``ci-artifact-proof`` job in canonical-verify):
    python design-lab/scripts/verify_ci_artifact_proof.py
        # defaults: GITHUB_REPOSITORY / GITHUB_RUN_ID / GITHUB_SHA,
        # artifacts "secret-history-report,workbench-e2-${GITHUB_SHA}"

All network access goes through ``verify_release_preflight.fetch`` (the
release layer's single injectable stdlib entry point) so the download
redirection policy (drop the token across hosts) is inherited, not
re-implemented. Unit tests inject a fake fetch and a fake sleep and never
open a socket or actually wait.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, Mapping, Sequence

_OK = "ok"
_INCOMPLETE = "incomplete"
_BLOCKED = "blocked"


def _load_preflight():
    """Sibling-load ``verify_release_preflight``.

    ``design-lab/scripts`` is not a Python package (no ``__init__.py``; the
    gate runs as top-level ``python design-lab/scripts/<name>.py``), so a
    relative import would fail both in CI and when a test loads this module
    via ``spec_from_file_location``. The sibling's stdlib network primitives
    are the release layer's single injectable network entry point -- reused
    here so the cross-host token-dropping redirect policy is inherited, not
    re-implemented. The module carries an ``if __name__ == "__main__"``
    guard, so executing it on import has no side effects.
    """
    import importlib.util
    import sys as _sys

    # A sibling load is idempotent: if the preflight module is already
    # registered under its canonical name, reuse it (one class identity for
    # FetchUnavailable in this process keeps the except-clauses exact).
    cached = _sys.modules.get("verify_release_preflight")
    if cached is not None and hasattr(cached, "fetch"):
        return cached

    path = Path(__file__).resolve().parent / "verify_release_preflight.py"
    spec = importlib.util.spec_from_file_location("verify_release_preflight", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load verify_release_preflight from {path}")
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: Python 3.11's dataclasses resolves the string
    # annotations of @dataclass(frozen=True) through sys.modules[cls.__module__],
    # and exec_module of a module that is not yet in sys.modules crashes with
    # AttributeError there. (Same registration the preflight's own test
    # loader performs; see test_release_preflight.load_module.)
    _sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        _sys.modules.pop(spec.name, None)
        raise
    return module


_preflight = _load_preflight()

# Re-exported so a test's fake fetch raises the *same* class the catchers
# use (class identity matters for ``except FetchUnavailable``).
fetch = _preflight.fetch
FetchResponse = _preflight.FetchResponse
FetchUnavailable = _preflight.FetchUnavailable
GITHUB_JSON = _preflight.GITHUB_JSON
# ---------------------------------------------------------------------------
# Download-leg Accept fix (DL-CLOUDAUDIT-2026-09-25 H001 / Prompt G):
# the api.github.com artifact archive endpoint (archive_download_url) is an
# API route that negotiates Accept -- it answers 415 "Must accept
# 'application/json'" for octet-stream. The zip body is what comes back
# either way, but the request must carry the JSON Accept the gateway
# requires. Verified live: octet-stream -> 415; GITHUB_JSON -> 200 + zip.
# The octet-stream constant was re-exported here only for the download leg;
# the release-asset leg keeps its own constant in verify_release_preflight.
# ---------------------------------------------------------------------------
api_digest = _preflight.api_digest
run_artifacts_url = _preflight.run_artifacts_url

STATUS_EXIT_CODES = {"PASS": 0, "BLOCKED": 2, "INCOMPLETE": 3}

Fetcher = Callable[..., FetchResponse]


def runs_url(repo: str, run_id: object) -> str:
    return f"https://api.github.com/repos/{repo}/actions/runs/{run_id}"


class Report:
    """Findings, check count and API facts for the contract line.

    ``findings`` are appended only at the *commit* step (from the final leg
    outcomes), so the sticky ``blocked_seen`` / ``incomplete_seen`` flags
    stay in exact lockstep with them -- there is no mid-flight record that a
    re-query could desync.
    """

    def __init__(self) -> None:
        self.findings: list[str] = []
        self.checks = 0
        self.facts: dict[str, object] = {}
        self.blocked_seen = False
        self.incomplete_seen = False

    def commit(self, outcome: str, finding: str | None) -> None:
        if outcome == _BLOCKED:
            self.blocked_seen = True
            self.findings.append(finding)
        elif outcome == _INCOMPLETE:
            self.incomplete_seen = True
            self.findings.append(finding)

    def status(self) -> str:
        if self.blocked_seen:
            return "BLOCKED"
        if self.incomplete_seen:
            return "INCOMPLETE"
        return "PASS"

    def contract_line(self) -> str:
        # gate=ADVISORY marks this lane as observability-only (Prompt G #5/#6):
        # it is never part of the required-green signal, so a red lane must
        # never be readable as "main is red". The release layer's own
        # artifact proof stays fail-closed independently of this marking.
        return (
            f"CI_ARTIFACT_PROOF={self.status()} gate=ADVISORY checks={self.checks} "
            f"findings={json.dumps(self.findings, ensure_ascii=False)}"
        )


def _get(fetch_fn: Fetcher, url: str, token: str | None, note: str) -> FetchResponse | None:
    """fetch() with the one 'no answer' outcome the whole gate is built on.

    Returns None (and records nothing) when the exchange could not happen;
    the caller turns that into an INCOMPLETE finding.
    """
    try:
        return fetch_fn(url, token=token)
    except FetchUnavailable:
        return None


def check_run_identity(
    repo: str, run_id: str, expected_sha: str, rep: Report, fetch_fn: Fetcher, token: str | None
) -> tuple[str, str]:
    """1. the run exists and its head SHA equals the subject SHA (run/SHA binding).

    Returns ``(outcome, finding)`` where outcome is ok/blocked/incomplete.
    Records the observed ``run_head_sha`` fact when the answer is readable.
    """
    rep.checks += 1
    url = runs_url(repo, run_id)
    response = _get(fetch_fn, url, token, f"run identity {run_id}")
    if response is None:
        return _INCOMPLETE, f"API-UNREACHABLE run identity {run_id}"
    if response.status == 404:
        return _BLOCKED, f"RUN-NOT-FOUND run_id={run_id} (no such Actions run)"
    if response.status != 200:
        return _INCOMPLETE, f"RUN-QUERY-FAILED run_id={run_id} status={response.status}"
    try:
        data = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _INCOMPLETE, f"RUN-RESPONSE-NOT-JSON run_id={run_id}"
    if not isinstance(data, dict):
        return _INCOMPLETE, f"RUN-RESPONSE-NOT-AN-OBJECT run_id={run_id}"
    head_sha = str(data.get("head_sha") or "").lower()
    rep.facts["run_head_sha"] = head_sha
    if not head_sha:
        return _INCOMPLETE, f"RUN-SHA-ABSENT run_id={run_id} (API returned no head_sha)"
    if head_sha != expected_sha.lower():
        return _BLOCKED, (
            f"RUN-SHA-MISMATCH run_id={run_id} head_sha={head_sha} expected_sha={expected_sha}"
        )
    rep.facts["run_identity"] = f"OK run={run_id} sha={expected_sha}"
    return _OK, ""


def check_artifact(
    repo: str,
    run_id: str,
    artifact_name: str,
    rep: Report,
    fetch_fn: Fetcher,
    token: str | None,
    download_dir: str | None,
) -> tuple[str, str]:
    """2-4. find the named artifact in the run, download it, verify sha256.

    Returns ``(outcome, finding)``. On success it records the ``artifact_*``
    digest fact (and persists the archive when ``download_dir`` is set);
    ``not in the list yet`` (indexing lag) is ``incomplete`` -- never ``ok``
    and never ``blocked``.
    """
    rep.checks += 1
    url = run_artifacts_url(repo, run_id)
    response = _get(fetch_fn, url, token, f"artifact list {run_id}")
    if response is None:
        return _INCOMPLETE, f"API-UNREACHABLE artifact list {run_id}"
    if response.status == 404:
        return _INCOMPLETE, f"ARTIFACT-LIST-UNINDEXED run_id={run_id} (upload not visible to the API yet)"
    if response.status != 200:
        return _INCOMPLETE, f"ARTIFACT-QUERY-FAILED run_id={run_id} status={response.status}"
    try:
        data = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _INCOMPLETE, f"ARTIFACT-LIST-NOT-JSON run_id={run_id}"
    if not isinstance(data, dict):
        return _INCOMPLETE, f"ARTIFACT-LIST-NOT-AN-OBJECT run_id={run_id}"
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        return _INCOMPLETE, f"ARTIFACT-LIST-MALFORMED run_id={run_id}"
    matching = [
        art for art in artifacts if isinstance(art, dict) and art.get("name") == artifact_name
    ]
    if not matching:
        available = sorted(str(art.get("name")) for art in artifacts if isinstance(art, dict))
        return _INCOMPLETE, (
            f"ARTIFACT-UNINDEXED name={artifact_name} run_id={run_id} "
            f"(not in the run's artifact list yet; indexed={available})"
        )
    expected = api_digest(matching[0])
    if not expected:
        return _INCOMPLETE, f"ARTIFACT-DIGEST-ABSENT name={artifact_name} run_id={run_id}"
    archive_url = str(matching[0].get("archive_download_url") or "")
    if not archive_url:
        return _BLOCKED, f"ARTIFACT-NO-ARCHIVE-URL name={artifact_name} run_id={run_id}"
    download = _get_download(fetch_fn, archive_url, token)
    if download is None:
        return _INCOMPLETE, f"ARTIFACT-DOWNLOAD-UNAVAILABLE name={artifact_name}"
    if download.status != 200:
        return _INCOMPLETE, (
            f"ARTIFACT-DOWNLOAD-FAILED name={artifact_name} run_id={run_id} status={download.status}"
        )
    actual = hashlib.sha256(download.body).hexdigest()
    rep.facts[f"artifact_{artifact_name}"] = (
        f"OK bytes={len(download.body)} sha256={actual} api_sha256={expected}"
    )
    if actual != expected:
        return _BLOCKED, (
            f"ARTIFACT-SHA256-MISMATCH name={artifact_name} actual={actual} expected={expected}"
        )
    if download_dir:
        destination = Path(download_dir) / f"{artifact_name}.zip"
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(download.body)
        except OSError as exc:
            # Persisting the local copy is a convenience, not part of the
            # proof: the bytes were downloaded and their digest verified, so
            # a write failure is a noted, non-terminal concern.
            rep.facts[f"artifact_persist_{artifact_name}"] = f"FAILED path={destination}: {exc}"
        else:
            rep.facts[f"artifact_path_{artifact_name}"] = str(destination)
    return _OK, ""


def _get_download(fetch_fn: Fetcher, url: str, token: str | None) -> FetchResponse | None:
    try:
        # The api.github.com artifact archive route negotiates Accept and
        # answers 415 for octet-stream; the zip body is unchanged, so the
        # JSON Accept is required even though the bytes are binary.
        return fetch_fn(url, token=token, accept=GITHUB_JSON)
    except FetchUnavailable:
        return None


def write_proof(
    proof_path: str,
    *,
    repo: str,
    run_id: str,
    sha: str,
    status: str,
    checks: int,
    findings: Sequence[str],
    facts: Mapping[str, object],
    artifact_names: Sequence[str],
) -> str:
    """Persist the run/SHA-bound proof record (gitignored runtime dir)."""
    document = {
        "schemaVersion": "design-lab/ci-artifact-proof/v1",
        "gate": "ADVISORY",
        "audit": "DL-CLOUDAUDIT-H001 (FINAL TaskPack section H: main-run artifact proof)",
        "repo": repo,
        "runId": str(run_id),
        "subjectSha": sha,
        "artifacts": [str(n) for n in artifact_names],
        "status": status,
        "checks": checks,
        "findings": [str(f) for f in findings],
        "facts": {str(k): str(v) for k, v in sorted(facts.items())},
    }
    path = Path(proof_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)


def run_proof(
    *,
    repo: str,
    run_id: str,
    sha: str,
    artifact_names: Sequence[str],
    token: str | None = None,
    download_dir: str | None = None,
    proof_path: str | None = None,
    fetch_fn: Fetcher = fetch,
    retry_seconds: float = 20.0,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] | None = None,
) -> int:
    """Run the four legs; return the exit code.

    A single paced re-query of the still-incomplete artifact legs turns the
    common Actions-indexing lag into a PASS within one run. ``sleep`` is
    injectable so the test proves the pacing without actually waiting.
    """
    say = log or (lambda _m: None)
    rep = Report()

    say(f"CI_ARTIFACT_PROOF_REPO={repo or '(unresolved)'}")
    say(f"CI_ARTIFACT_PROOF_RUN={run_id or '(unresolved)'}")
    say(f"CI_ARTIFACT_PROOF_SHA={sha or '(unresolved)'}")
    say(f"CI_ARTIFACT_PROOF_ARTIFACTS={','.join(artifact_names)}")

    # input resolution: the readback is impossible without these, so each is
    # an INCOMPLETE (never a PASS), not a crash.
    for label in (
        "REPO-UNRESOLVED (pass --repo or set GITHUB_REPOSITORY)" if not repo else None,
        "RUN-UNRESOLVED (pass --run-id or set GITHUB_RUN_ID)" if not run_id else None,
        "SHA-UNRESOLVED (pass --sha or set GITHUB_SHA)" if not sha else None,
        "NO-GITHUB-TOKEN (token unset: the API readback is impossible, so this is never PASS)"
        if not token
        else None,
        "NO-ARTIFACTS-NAMED (pass --artifacts so something can be proven)" if not artifact_names else None,
    ):
        if label:
            rep.commit(_INCOMPLETE, label)
            _finish(rep, say)
            return STATUS_EXIT_CODES[rep.status()]

    # 1. identity (run/SHA binding) -- the artifact leg is only meaningful
    # against a correctly-identified run.
    identity_outcome, identity_finding = check_run_identity(
        repo, str(run_id), sha, rep, fetch_fn, token
    )
    if identity_outcome != _OK:
        rep.commit(identity_outcome, identity_finding)
        _finish(rep, say)
        return STATUS_EXIT_CODES[rep.status()]

    # 2-4. each named artifact; one paced re-query for the still-incomplete.
    outcomes: dict[str, tuple[str, str]] = {}
    for name in artifact_names:
        outcome, finding = check_artifact(repo, str(run_id), name, rep, fetch_fn, token, download_dir)
        outcomes[name] = (outcome, finding)
    requery = [n for n in artifact_names if outcomes[n][0] == _INCOMPLETE]
    if requery and retry_seconds > 0 and not rep.blocked_seen:
        say(
            f"CI_ARTIFACT_PROOF_REQUERY paces re-query after {retry_seconds:.0f}s "
            f"for {sorted(requery)}"
        )
        sleep(retry_seconds)
        for name in requery:
            outcome, finding = check_artifact(
                repo, str(run_id), name, rep, fetch_fn, token, download_dir
            )
            outcomes[name] = (outcome, finding)
    # commit the terminal per-artifact findings (once, from the final outcome).
    for name in artifact_names:
        outcome, finding = outcomes[name]
        if outcome != _OK:
            rep.commit(outcome, finding)

    for name, fact in sorted(rep.facts.items()):
        if name.startswith("artifact_") and not name.startswith("artifact_path_"):
            say(f"CI_ARTIFACT_PROOF_{name.upper()}={fact}")
    _finish(rep, say)
    status = rep.status()
    if proof_path:
        path = write_proof(
            proof_path,
            repo=repo,
            run_id=str(run_id),
            sha=sha,
            status=status,
            checks=rep.checks,
            findings=rep.findings,
            facts=rep.facts,
            artifact_names=artifact_names,
        )
        say(f"CI_ARTIFACT_PROOF_RECORD={path}")
    return STATUS_EXIT_CODES[status]


def _finish(rep: Report, say: Callable[[str], None]) -> None:
    for finding in rep.findings:
        say(f"CI_ARTIFACT_PROOF_FINDING {finding}")
    say(rep.contract_line())


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Main-branch CI artifact proof (real GitHub API readback, H001)."
    )
    parser.add_argument("--repo", default=_env("GITHUB_REPOSITORY"), help="owner/name (default: GITHUB_REPOSITORY)")
    parser.add_argument("--run-id", default=_env("GITHUB_RUN_ID"), help="Actions run id (default: GITHUB_RUN_ID)")
    parser.add_argument("--sha", default=_env("GITHUB_SHA"), help="subject SHA (default: GITHUB_SHA)")
    parser.add_argument(
        "--artifacts",
        default="",
        help="comma-separated artifact names to read back (default: this run's two uploaders)",
    )
    parser.add_argument(
        "--retry-seconds",
        type=float,
        default=20.0,
        help="pace a single re-query when an artifact is not yet indexed (0 disables)",
    )
    parser.add_argument(
        "--download-dir",
        default=".project-local/task-artifacts/ci-artifact-proof",
        help="directory to persist the downloaded archives into (gitignored)",
    )
    parser.add_argument(
        "--proof",
        default=".project-local/task-artifacts/ci-artifact-proof/ci-artifact-proof.json",
        help="path of the persisted run/SHA-bound proof record (gitignored)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    fetch_fn: Fetcher = fetch,
    log: Callable[[str], None] | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    names = [n.strip() for n in (args.artifacts or "").split(",") if n.strip()]
    if not names:
        sha = args.sha or _env("GITHUB_SHA")
        names = ["secret-history-report"]
        if sha:
            names.append(f"workbench-e2-{sha}")
    say = log or print
    return run_proof(
        repo=args.repo or "",
        run_id=args.run_id or "",
        sha=args.sha or "",
        artifact_names=names,
        token=token or None,
        download_dir=args.download_dir or None,
        proof_path=args.proof or None,
        fetch_fn=fetch_fn,
        retry_seconds=args.retry_seconds,
        log=say,
    )


if __name__ == "__main__":
    sys.exit(main())
