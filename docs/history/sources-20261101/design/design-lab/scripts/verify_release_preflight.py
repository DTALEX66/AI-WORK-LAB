#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CI-006 / Batch F-3: fail-closed release preflight with REAL API readback.

Why this exists
---------------
`release-gate.yml`'s former "API readback consistency check" step never called
the GitHub API: it compared `github.sha` with the attestation's
`subjectCommitSha`, i.e. two values produced by the same run. Audit report
P1-CI requires artifact proof to be *real* (upload -> query -> download ->
hash), and release discipline requires asset / identity / checksum / installer /
public readback before a tag may be called released.

Checks (every one fail-closed)
------------------------------
1. identity : tag -> commit SHA (`/git/ref/tags/{tag}`, annotated tags
              dereferenced once more through `/git/tags/{sha}`) must equal the
              target SHA.
2. CI       : the Canonical Verify run for that exact SHA must have concluded
              `success` (missing run / non-success conclusion is a finding).
3. artifact : the release-evidence artifact is located through the API, its
              archive is *downloaded* (`archive_download_url`) and the sha256 of
              the downloaded bytes must match an independently known digest (API
              `digest`, or `--expect-artifact-sha256`). The artifact is read from
              the run that uploaded it (`--run-id`, e.g. this release-gate run);
              without `--run-id` the CI run found in check 2 is used.
4. release  : when the tag has no release -> `RELEASE_NOT_PUBLISHED`; when it
              has one, the asset name set must match the expected patterns.
5. checksum : every published asset is downloaded and hashed against the local
              `artifacts.sha256`; an asset with no recorded digest cannot be
              verified and is therefore a finding, not a silent skip.

Output contract
---------------
    RELEASE_PREFLIGHT=<PASS|BLOCKED|INCOMPLETE> checks=N findings=[...]

- `PASS`       (exit 0): every check ran and matched. Never returned when a
                check could not run.
- `BLOCKED`    (exit 2): a check ran and contradicted the release claim.
- `INCOMPLETE` (exit 3): a check could not run (no token, no network,
                download unavailable, no expected digest, missing local
                checksum file). An unprovable release is never a `PASS`.

`checks` counts the checks that reached a verdict; a check whose prerequisite
already failed is not counted, because its prerequisite's own finding is the
stated reason.

Usage
-----
    python design-lab/scripts/verify_release_preflight.py --tag v1.2.3 \\
        --run-id "$GITHUB_RUN_ID" \\
        --expect-assets artifacts.sha256,attestation-*.json

The token is read from `GITHUB_TOKEN` (or `GH_TOKEN`); it is never accepted as
a command-line argument, so it cannot leak into a process listing.

All network access goes through `fetch()`, which is injectable, so the unit
tests exercise every branch with a fake fetch and never open a socket.
"""
from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent.parent
API_ROOT = "https://api.github.com"
DEFAULT_WORKFLOW = "Canonical Verify"
DEFAULT_CHECKSUMS = "artifacts.sha256"
GITHUB_JSON = "application/vnd.github+json"
OCTET_STREAM = "application/octet-stream"
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

STATUS_EXIT_CODES = {"PASS": 0, "BLOCKED": 2, "INCOMPLETE": 3}


class FetchUnavailable(Exception):
    """The request could not be performed at all (no network, DNS, TLS, timeout).

    Distinct from an HTTP error status: a status is an answer, this is the
    absence of one, and the preflight turns it into `INCOMPLETE`.
    """


@dataclasses.dataclass(frozen=True)
class FetchResponse:
    """A completed HTTP exchange (any status code)."""

    status: int
    body: bytes
    headers: Mapping[str, str]

    def json(self):
        return json.loads(self.body.decode("utf-8"))


class _SameHostAuthRedirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects without resending the token to another host.

    Artifact and asset downloads answer with a 302 to a signed object-storage
    URL on a different host. urllib copies the request headers onto the
    redirected request, which would leak the API token to that third party, so
    the Authorization header is dropped whenever the host changes.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            if urllib.parse.urlsplit(new.full_url).netloc != urllib.parse.urlsplit(req.full_url).netloc:
                new.remove_header("Authorization")
        return new


def fetch(
    url: str,
    token: str | None = None,
    accept: str = GITHUB_JSON,
    timeout: float = 30.0,
) -> FetchResponse:
    """Single network entry point (stdlib only).

    Returns a `FetchResponse` for any HTTP status; raises `FetchUnavailable`
    when no exchange happened. Tests inject a fake with this signature.
    """
    headers = {
        "Accept": accept,
        "User-Agent": "design-lab-release-preflight/1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    opener = urllib.request.build_opener(_SameHostAuthRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return FetchResponse(response.status, response.read(), dict(response.headers))
    except urllib.error.HTTPError as exc:  # `answers` with a status, not a failure
        try:
            body = exc.read()
        except OSError:
            body = b""
        return FetchResponse(exc.code, body or b"", dict(exc.headers or {}))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise FetchUnavailable(f"{type(exc).__name__}: {exc}") from exc


Fetcher = Callable[..., FetchResponse]


# --------------------------------------------------------------------------
# URL builders (shared with the tests so URL shapes cannot drift)
# --------------------------------------------------------------------------
def tag_ref_url(repo: str, tag: str) -> str:
    return f"{API_ROOT}/repos/{repo}/git/ref/tags/{urllib.parse.quote(tag, safe='')}"


def tag_object_url(repo: str, sha: str) -> str:
    return f"{API_ROOT}/repos/{repo}/git/tags/{sha}"


def runs_url(repo: str, sha: str) -> str:
    return f"{API_ROOT}/repos/{repo}/actions/runs?head_sha={sha}&per_page=100"


def run_artifacts_url(repo: str, run_id: object) -> str:
    return f"{API_ROOT}/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"


def release_url(repo: str, tag: str) -> str:
    return f"{API_ROOT}/repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe='')}"


# --------------------------------------------------------------------------
# local helpers
# --------------------------------------------------------------------------
def git(*args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def repo_from_remote_url(url: str) -> str:
    """`owner/name` from an ssh/https GitHub remote; "" when unrecognisable."""
    remote = (url or "").strip()
    if not remote:
        return ""
    if remote.startswith("git@") and ":" in remote:
        path = remote.split(":", 1)[1]
    elif "://" in remote:
        parsed = urllib.parse.urlsplit(remote)
        if parsed.netloc not in {"github.com", "www.github.com"}:
            return ""
        path = parsed.path.lstrip("/")
    else:
        return ""
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [part for part in path.split("/") if part]
    if len(parts) != 2:
        return ""
    return f"{parts[0]}/{parts[1]}"


def load_checksums(path: Path) -> dict[str, str] | None:
    """`sha256sum` output -> {basename: digest}; None when unreadable."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    recorded: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts[0].lower(), parts[1].strip()
        if not SHA256_HEX.match(digest):
            continue
        if name.startswith("*"):  # sha256sum binary marker
            name = name[1:]
        recorded[Path(name).name] = digest
    return recorded


def parse_asset_expectations(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclasses.dataclass
class PreflightResult:
    status: str
    checks: int
    findings: list[str]
    facts: dict[str, object] = dataclasses.field(default_factory=dict)

    def contract_line(self) -> str:
        return (
            f"RELEASE_PREFLIGHT={self.status} checks={self.checks} "
            f"findings={json.dumps(self.findings, ensure_ascii=False)}"
        )


class _Report:
    """Accumulates findings, the check count and the API facts to print."""

    def __init__(self) -> None:
        self.findings: list[str] = []
        self.checks = 0
        self.facts: dict[str, object] = {}
        self.blocked_seen = False
        self.incomplete_seen = False

    def blocked(self, finding: str) -> None:
        self.blocked_seen = True
        self.findings.append(finding)

    def incomplete(self, finding: str) -> None:
        self.incomplete_seen = True
        self.findings.append(finding)

    def status(self) -> str:
        if self.incomplete_seen:
            return "INCOMPLETE"
        if self.blocked_seen:
            return "BLOCKED"
        return "PASS"


def api_request(
    fetch_fn: Fetcher,
    token: str | None,
    url: str,
    rep: _Report,
    what: str,
    accept: str = GITHUB_JSON,
) -> FetchResponse | None:
    """Perform one request; unreachable endpoints become INCOMPLETE findings."""
    try:
        return fetch_fn(url, token=token, accept=accept)
    except FetchUnavailable as exc:
        rep.incomplete(f"API-UNREACHABLE {what}: {exc}")
        return None


def api_json(response: FetchResponse, rep: _Report, what: str) -> dict | None:
    try:
        data = response.json()
    except (UnicodeDecodeError, ValueError) as exc:
        rep.incomplete(f"API-RESPONSE-NOT-JSON {what}: {exc}")
        return None
    if not isinstance(data, dict):
        rep.incomplete(f"API-RESPONSE-NOT-OBJECT {what}")
        return None
    return data


def api_digest(artifact: Mapping[str, object]) -> str:
    """sha256 from an artifact record's `digest` ("sha256:<hex>"), else ""."""
    digest = str(artifact.get("digest") or "").strip().lower()
    if digest.startswith("sha256:"):
        digest = digest.split(":", 1)[1]
    return digest if SHA256_HEX.match(digest) else ""


# --------------------------------------------------------------------------
# the five checks
# --------------------------------------------------------------------------
def check_identity(
    repo: str, tag: str, sha: str, rep: _Report, fetch_fn: Fetcher, token: str | None
) -> None:
    """a. tag -> commit SHA identity (annotated tags dereferenced)."""
    rep.checks += 1
    response = api_request(fetch_fn, token, tag_ref_url(repo, tag), rep, f"tag ref {tag}")
    if response is None:
        return
    if response.status == 404:
        rep.blocked(f"TAG-NOT-FOUND tag={tag} (remote has no such tag)")
        return
    if response.status != 200:
        rep.incomplete(f"TAG-REF-QUERY-FAILED tag={tag} status={response.status}")
        return
    data = api_json(response, rep, f"tag ref {tag}")
    if data is None:
        return
    target = data.get("object")
    if not isinstance(target, dict) or not target.get("sha"):
        rep.blocked(f"TAG-REF-MALFORMED tag={tag}")
        return
    resolved = str(target["sha"])
    if target.get("type") == "tag":  # annotated tag: one more dereference
        rep.facts["tag_object_sha"] = resolved
        annotated = api_request(
            fetch_fn, token, tag_object_url(repo, resolved), rep, f"annotated tag {tag}"
        )
        if annotated is None:
            return
        if annotated.status != 200:
            rep.incomplete(f"ANNOTATED-TAG-QUERY-FAILED tag={tag} status={annotated.status}")
            return
        tag_data = api_json(annotated, rep, f"annotated tag {tag}")
        if tag_data is None:
            return
        inner = tag_data.get("object")
        if not isinstance(inner, dict) or not inner.get("sha"):
            rep.blocked(f"ANNOTATED-TAG-MALFORMED tag={tag} object={resolved}")
            return
        resolved = str(inner["sha"])
    rep.facts["tag_sha"] = resolved
    if resolved != sha:
        rep.blocked(f"TAG-SHA-MISMATCH tag={tag} tag_sha={resolved} expected_sha={sha}")
    else:
        rep.facts["identity"] = f"OK tag={tag} sha={sha}"


def check_ci(
    repo: str, sha: str, workflow: str, rep: _Report, fetch_fn: Fetcher, token: str | None
) -> dict | None:
    """b. the named workflow's run for this exact SHA concluded `success`."""
    rep.checks += 1
    response = api_request(fetch_fn, token, runs_url(repo, sha), rep, f"actions runs head_sha={sha}")
    if response is None:
        return None
    if response.status != 200:
        rep.incomplete(f"CI-QUERY-FAILED head_sha={sha} status={response.status}")
        return None
    data = api_json(response, rep, f"actions runs head_sha={sha}")
    if data is None:
        return None
    runs = data.get("workflow_runs")
    if not isinstance(runs, list):
        rep.incomplete("CI-QUERY-MALFORMED (workflow_runs is not a list)")
        return None
    matching = [run for run in runs if isinstance(run, dict) and run.get("name") == workflow]
    if not matching:
        rep.blocked(f"CI-RUN-MISSING workflow={workflow} head_sha={sha}")
        return None
    successful = [run for run in matching if run.get("conclusion") == "success"]
    if not successful:
        conclusions = sorted({str(run.get("conclusion")) for run in matching})
        rep.blocked(f"CI-NOT-SUCCESS workflow={workflow} conclusions={conclusions} head_sha={sha}")
        return None
    best = max(successful, key=lambda run: int(run.get("id") or 0))
    rep.facts["ci_run_id"] = best.get("id")
    rep.facts["ci_conclusion"] = best.get("conclusion")
    return best


def check_artifact(
    repo: str,
    run_id: object,
    artifact_name: str,
    expect_digest: str,
    rep: _Report,
    fetch_fn: Fetcher,
    token: str | None,
    download_dir: str | None,
) -> None:
    """c. find the run's artifact, download it, verify sha256 of the bytes."""
    if not run_id:
        return
    rep.checks += 1
    response = api_request(
        fetch_fn, token, run_artifacts_url(repo, run_id), rep, f"artifacts of run {run_id}"
    )
    if response is None:
        return
    if response.status != 200:
        rep.incomplete(f"ARTIFACT-QUERY-FAILED run={run_id} status={response.status}")
        return
    data = api_json(response, rep, f"artifacts of run {run_id}")
    if data is None:
        return
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        rep.incomplete(f"ARTIFACT-QUERY-MALFORMED run={run_id}")
        return
    matching = [
        art for art in artifacts if isinstance(art, dict) and art.get("name") == artifact_name
    ]
    if not matching:
        available = sorted(str(art.get("name")) for art in artifacts if isinstance(art, dict))
        rep.blocked(
            f"ARTIFACT-MISSING name={artifact_name} run={run_id} present={available}"
        )
        return
    artifact = matching[0]
    expected = (expect_digest or "").strip().lower()
    if expected.startswith("sha256:"):
        expected = expected.split(":", 1)[1]
    if not SHA256_HEX.match(expected):
        expected = api_digest(artifact)
    if not expected:
        rep.incomplete(
            f"ARTIFACT-DIGEST-UNSPECIFIED name={artifact_name} "
            "(API returned no digest and --expect-artifact-sha256 was not given)"
        )
        return
    archive_url = str(artifact.get("archive_download_url") or "")
    if not archive_url:
        rep.blocked(f"ARTIFACT-NO-ARCHIVE-URL name={artifact_name}")
        return
    # The api.github.com artifact archive route negotiates Accept and
    # answers 415 for octet-stream; the zip body is unchanged, so the JSON
    # Accept is required even though the bytes are binary.
    download = api_request(
        fetch_fn, token, archive_url, rep, f"artifact archive {artifact_name}", accept=GITHUB_JSON
    )
    if download is None:
        return
    if download.status != 200:
        rep.incomplete(
            f"ARTIFACT-DOWNLOAD-UNAVAILABLE name={artifact_name} status={download.status}"
        )
        return
    actual = hashlib.sha256(download.body).hexdigest()
    rep.facts["artifact_name"] = artifact_name
    rep.facts["artifact_bytes"] = len(download.body)
    rep.facts["artifact_sha256"] = actual
    if actual != expected:
        rep.blocked(
            f"ARTIFACT-SHA256-MISMATCH name={artifact_name} actual={actual} expected={expected}"
        )
        return
    rep.facts["artifact_digest"] = f"OK download_bytes={len(download.body)} sha256={actual}"
    if download_dir:
        destination = Path(download_dir) / f"{artifact_name}.zip"
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(download.body)
        except OSError as exc:
            rep.incomplete(f"ARTIFACT-PERSIST-FAILED path={destination}: {exc}")
        else:
            rep.facts["artifact_path"] = str(destination)
    return


def check_release(
    repo: str,
    tag: str,
    expected_patterns: Sequence[str],
    rep: _Report,
    fetch_fn: Fetcher,
    token: str | None,
) -> list[dict] | None:
    """d. release assets: published and matching the expected name set."""
    rep.checks += 1
    response = api_request(fetch_fn, token, release_url(repo, tag), rep, f"release {tag}")
    if response is None:
        return None
    if response.status == 404:
        rep.blocked(
            f"RELEASE_NOT_PUBLISHED tag={tag} "
            "(the tag exists but has no GitHub release to read back)"
        )
        return None
    if response.status != 200:
        rep.incomplete(f"RELEASE-QUERY-FAILED tag={tag} status={response.status}")
        return None
    data = api_json(response, rep, f"release {tag}")
    if data is None:
        return None
    assets = data.get("assets")
    if not isinstance(assets, list):
        rep.blocked(f"RELEASE-ASSETS-MALFORMED tag={tag}")
        return None
    named = [asset for asset in assets if isinstance(asset, dict)]
    names = [str(asset.get("name") or "") for asset in named]
    rep.facts["release_assets"] = names
    if not expected_patterns:
        rep.incomplete(
            "RELEASE-ASSETS-EXPECTATION-UNSPECIFIED (pass --expect-assets "
            "so the published asset set can be verified)"
        )
        return named
    for pattern in expected_patterns:
        if not any(fnmatch.fnmatch(name, pattern) for name in names):
            rep.blocked(f"RELEASE-ASSET-MISSING pattern={pattern} published={names}")
    for name in names:
        if not any(fnmatch.fnmatch(name, pattern) for pattern in expected_patterns):
            rep.blocked(f"RELEASE-ASSET-UNEXPECTED name={name}")
    return named


def check_checksums(
    assets: list[dict] | None,
    checksums_path: Path,
    rep: _Report,
    fetch_fn: Fetcher,
    token: str | None,
) -> None:
    """e. hash every published asset and compare with the local artifacts.sha256."""
    rep.checks += 1
    if assets is None:
        return
    recorded = load_checksums(checksums_path)
    if recorded is None:
        rep.incomplete(f"LOCAL-CHECKSUMS-MISSING path={checksums_path}")
        return
    for asset in assets:
        name = str(asset.get("name") or "")
        expected = recorded.get(name)
        asset_url = str(asset.get("url") or "")
        if not asset_url:
            rep.blocked(f"ASSET-NO-API-URL name={name}")
            continue
        if expected is None:
            rep.blocked(
                f"ASSET-CHECKSUM-UNRECORDED name={name} "
                f"(no digest for this asset in {checksums_path.name}; cannot be verified)"
            )
            continue
        download = api_request(
            fetch_fn, token, asset_url, rep, f"release asset {name}", accept=OCTET_STREAM
        )
        if download is None:
            continue
        if download.status != 200:
            rep.incomplete(f"ASSET-DOWNLOAD-UNAVAILABLE name={name} status={download.status}")
            continue
        actual = hashlib.sha256(download.body).hexdigest()
        if actual != expected:
            rep.blocked(
                f"ASSET-SHA256-MISMATCH name={name} actual={actual} expected={expected}"
            )
        else:
            rep.facts[f"asset_sha256_{name}"] = f"OK bytes={len(download.body)} sha256={actual}"


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------
def _finish(rep: _Report, say: Callable[[str], None]) -> PreflightResult:
    for key in sorted(rep.facts):
        say(f"RELEASE_PREFLIGHT_{key.upper()}={rep.facts[key]}")
    return PreflightResult(
        status=rep.status(),
        checks=rep.checks,
        findings=list(rep.findings),
        facts=dict(rep.facts),
    )


def run_preflight(
    *,
    tag: str,
    sha: str = "",
    repo: str = "",
    token: str | None = None,
    workflow: str = DEFAULT_WORKFLOW,
    artifact_name: str = "",
    run_id: str = "",
    expect_artifact_sha256: str = "",
    expect_assets: Sequence[str] = (),
    local_checksums: str | Path = DEFAULT_CHECKSUMS,
    download_dir: str | None = None,
    fetch_fn: Fetcher = fetch,
    log: Callable[[str], None] | None = None,
) -> PreflightResult:
    """Run every check and return the fail-closed verdict."""
    say = log or (lambda _message: None)
    rep = _Report()

    resolved_sha = sha or git("rev-parse", "HEAD")
    resolved_repo = repo or repo_from_remote_url(git("remote", "get-url", "origin"))
    resolved_artifact = artifact_name or (
        f"dl-release-evidence-{resolved_sha}" if resolved_sha else "dl-release-evidence"
    )

    say(f"RELEASE_PREFLIGHT_TAG={tag}")
    say(f"RELEASE_PREFLIGHT_SHA={resolved_sha or '(unresolved)'}")
    say(f"RELEASE_PREFLIGHT_REPO={resolved_repo or '(unresolved)'}")
    say(f"RELEASE_PREFLIGHT_ARTIFACT={resolved_artifact}")

    if not resolved_sha:
        rep.incomplete("SHA-UNRESOLVED (pass --sha; git rev-parse HEAD failed)")
        return _finish(rep, say)
    if not resolved_repo:
        rep.incomplete("REPO-UNRESOLVED (pass --repo owner/name; git remote get-url origin failed)")
        return _finish(rep, say)
    if not token:
        rep.incomplete(
            "NO-GITHUB-TOKEN (token unset: API readback is impossible, so this is never PASS)"
        )
        return _finish(rep, say)

    check_identity(resolved_repo, tag, resolved_sha, rep, fetch_fn, token)
    run = check_ci(resolved_repo, resolved_sha, workflow, rep, fetch_fn, token)
    # The artifact lives in the run that actually uploaded it; --run-id names it
    # explicitly (e.g. the release-gate run), otherwise the CI run is used.
    resolved_run_id = run_id or (str(run.get("id")) if isinstance(run, dict) and run.get("id") else "")
    check_artifact(
        resolved_repo,
        resolved_run_id,
        resolved_artifact,
        expect_artifact_sha256,
        rep,
        fetch_fn,
        token,
        download_dir,
    )
    assets = check_release(resolved_repo, tag, list(expect_assets), rep, fetch_fn, token)
    check_checksums(assets, Path(local_checksums), rep, fetch_fn, token)
    return _finish(rep, say)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed release preflight (real GitHub API readback)."
    )
    parser.add_argument("--tag", required=True, help="release tag to qualify")
    parser.add_argument("--sha", default="", help="expected commit SHA (default: git HEAD)")
    parser.add_argument("--repo", default="", help="owner/name (default: from git remote origin)")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="CI workflow name to require")
    parser.add_argument(
        "--artifact-name",
        default="",
        help="expected artifact name (default: dl-release-evidence-<sha>)",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="run whose artifact list is read back (default: the CI run for --sha)",
    )
    parser.add_argument(
        "--expect-artifact-sha256",
        default="",
        help="independently known sha256 of the artifact archive (else the API digest is used)",
    )
    parser.add_argument(
        "--expect-assets",
        default="",
        help="comma-separated release asset names/globs that must be published",
    )
    parser.add_argument(
        "--local-checksums",
        default=DEFAULT_CHECKSUMS,
        help=f"sha256sum output to compare published assets against (default: {DEFAULT_CHECKSUMS})",
    )
    parser.add_argument(
        "--download-dir",
        default="",
        help="optional directory to persist the downloaded artifact archive into",
    )
    return parser


def main(argv: Sequence[str] | None = None, fetch_fn: Fetcher = fetch) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    result = run_preflight(
        tag=args.tag,
        sha=args.sha,
        repo=args.repo,
        token=token,
        workflow=args.workflow,
        artifact_name=args.artifact_name,
        run_id=args.run_id,
        expect_artifact_sha256=args.expect_artifact_sha256,
        expect_assets=parse_asset_expectations(args.expect_assets),
        local_checksums=args.local_checksums,
        download_dir=args.download_dir or None,
        fetch_fn=fetch_fn,
        log=print,
    )
    for finding in result.findings:
        print(f"RELEASE_PREFLIGHT_FINDING {finding}")
    print(result.contract_line())
    return STATUS_EXIT_CODES[result.status]


if __name__ == "__main__":
    sys.exit(main())
