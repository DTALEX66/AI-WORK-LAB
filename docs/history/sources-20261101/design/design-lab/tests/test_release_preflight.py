# SPDX-License-Identifier: MIT
"""Batch F-3: fail-closed release-preflight tests.

Every test injects a fake `fetch` into
`design-lab/scripts/verify_release_preflight.py`, so no socket is ever opened
(one test even makes `urllib.request.build_opener` explode to prove it).

Covered failure modes:
- tag SHA match / mismatch, annotated-tag dereference, missing tag
- CI conclusion non-success / run missing -> BLOCKED
- artifact sha256 mismatch -> BLOCKED; artifact download unavailable -> INCOMPLETE
- tag exists but release not published -> RELEASE_NOT_PUBLISHED (never PASS)
- asset set mismatch, unrecorded checksum, checksum mismatch
- no token / unreachable API -> INCOMPLETE (never PASS)
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import inspect
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "design-lab" / "scripts" / "verify_release_preflight.py"

SHA = "b" * 40
OTHER_SHA = "c" * 40
TAG_OBJECT_SHA = "d" * 40
TAG = "v9.9.9"
SLUG = "dtalex66/design-lab"
RUN_ID = 4242
ARTIFACT_NAME = f"dl-release-evidence-{SHA}"
ARTIFACT_URL = f"https://api.github.com/repos/{SLUG}/actions/artifacts/777/zip"
ARTIFACT_BYTES = b"PK\x03\x04fake-release-evidence-archive"
ARTIFACT_DIGEST = hashlib.sha256(ARTIFACT_BYTES).hexdigest()
ASSET_NAME = "artifacts.sha256"
ASSET_URL = f"https://api.github.com/repos/{SLUG}/releases/assets/888"
ASSET_BYTES = b"attestation payload"
ASSET_DIGEST = hashlib.sha256(ASSET_BYTES).hexdigest()

CONTRACT_RE = re.compile(
    r"^RELEASE_PREFLIGHT=(PASS|BLOCKED|INCOMPLETE) checks=\d+ findings=\[.*\]$"
)


def load_module():
    spec = importlib.util.spec_from_file_location("verify_release_preflight_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Register before execution: the module declares dataclasses and uses
    # `from __future__ import annotations`, and dataclasses resolve those string
    # annotations through sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


preflight = load_module()


class FakeFetch:
    """Deterministic stand-in for the module's single network entry point.

    Unknown URLs answer 404 (which is how GitHub reports "absent"), listed
    URLs answer their canned status/body, and `unavailable` URLs raise the
    module's `FetchUnavailable` to model "no network".
    """

    def __init__(self, routes=None, unavailable=()):
        self.routes = dict(routes or {})
        self.unavailable = set(unavailable)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, url, token=None, accept=preflight.GITHUB_JSON):
        self.calls.append((url, accept))
        if url in self.unavailable:
            raise preflight.FetchUnavailable("simulated network failure")
        if url not in self.routes:
            return preflight.FetchResponse(404, b'{"message":"Not Found"}', {})
        status, body = self.routes[url]
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        return preflight.FetchResponse(status, bytes(body), {})


def run_record(name=preflight.DEFAULT_WORKFLOW, conclusion="success", run_id=RUN_ID):
    return {"id": run_id, "name": name, "conclusion": conclusion, "head_sha": SHA}


def artifact_record(name=ARTIFACT_NAME, digest=f"sha256:{ARTIFACT_DIGEST}"):
    record = {"name": name, "archive_download_url": ARTIFACT_URL, "size_in_bytes": len(ARTIFACT_BYTES)}
    if digest is not None:
        record["digest"] = digest
    return record


def asset_record(name=ASSET_NAME, url=ASSET_URL):
    return {"name": name, "url": url, "size": len(ASSET_BYTES)}


def green_routes(**overrides):
    """A fully consistent release: identity, CI, artifact, release, checksums."""
    routes = {
        preflight.tag_ref_url(SLUG, TAG): (200, {"object": {"type": "commit", "sha": SHA}}),
        preflight.runs_url(SLUG, SHA): (200, {"workflow_runs": [run_record()]}),
        preflight.run_artifacts_url(SLUG, RUN_ID): (200, {"artifacts": [artifact_record()]}),
        ARTIFACT_URL: (200, ARTIFACT_BYTES),
        preflight.release_url(SLUG, TAG): (200, {"tag_name": TAG, "assets": [asset_record()]}),
        ASSET_URL: (200, ASSET_BYTES),
    }
    routes.update(overrides)
    return routes


class PreflightTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.checksums = self.tmp / "artifacts.sha256"
        self.write_checksums({ASSET_NAME: ASSET_DIGEST})

    def write_checksums(self, entries: dict[str, str]) -> None:
        lines = [f"{digest}  .project-local/task-runtime/evidence/{name}" for name, digest in entries.items()]
        self.checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run_preflight_with(self, fake, **overrides):
        params = dict(
            tag=TAG,
            sha=SHA,
            repo=SLUG,
            token="fake-token",
            expect_assets=[ASSET_NAME],
            local_checksums=self.checksums,
            fetch_fn=fake,
        )
        params.update(overrides)
        return preflight.run_preflight(**params)

    def main_with(self, fake, argv_extra=()):
        argv = [
            "--tag", TAG,
            "--sha", SHA,
            "--repo", SLUG,
            "--expect-assets", ASSET_NAME,
            "--local-checksums", str(self.checksums),
            *argv_extra,
        ]
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}, clear=False):
            with contextlib.redirect_stdout(out):
                code = preflight.main(argv, fetch_fn=fake)
        return code, out.getvalue()


class TagIdentityTest(PreflightTestCase):
    def test_matching_tag_sha_passes_with_five_checks(self):
        result = self.run_preflight_with(FakeFetch(green_routes()))
        self.assertEqual(result.status, "PASS", result.findings)
        self.assertEqual(result.checks, 5)
        self.assertEqual(result.findings, [])

    def test_lightweight_tag_sha_mismatch_is_blocked(self):
        routes = green_routes(**{
            preflight.tag_ref_url(SLUG, TAG): (200, {"object": {"type": "commit", "sha": OTHER_SHA}}),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("TAG-SHA-MISMATCH") for f in result.findings), result.findings)

    def test_annotated_tag_is_dereferenced(self):
        routes = green_routes(**{
            preflight.tag_ref_url(SLUG, TAG): (200, {"object": {"type": "tag", "sha": TAG_OBJECT_SHA}}),
            preflight.tag_object_url(SLUG, TAG_OBJECT_SHA): (
                200,
                {"object": {"type": "commit", "sha": SHA}, "tag": TAG},
            ),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "PASS", result.findings)
        self.assertEqual(result.facts["tag_sha"], SHA)

    def test_annotated_tag_dereferencing_to_another_commit_is_blocked(self):
        routes = green_routes(**{
            preflight.tag_ref_url(SLUG, TAG): (200, {"object": {"type": "tag", "sha": TAG_OBJECT_SHA}}),
            preflight.tag_object_url(SLUG, TAG_OBJECT_SHA): (200, {"object": {"type": "commit", "sha": OTHER_SHA}}),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("TAG-SHA-MISMATCH") for f in result.findings), result.findings)

    def test_missing_tag_is_blocked_not_incomplete(self):
        routes = green_routes()
        del routes[preflight.tag_ref_url(SLUG, TAG)]  # -> 404 from FakeFetch
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("TAG-NOT-FOUND") for f in result.findings), result.findings)

    def test_tag_ref_server_error_is_incomplete(self):
        routes = green_routes(**{preflight.tag_ref_url(SLUG, TAG): (500, b"boom")})
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(any(f.startswith("TAG-REF-QUERY-FAILED") for f in result.findings), result.findings)

    def test_tag_ref_unreachable_is_incomplete(self):
        fake = FakeFetch(green_routes(), unavailable={preflight.tag_ref_url(SLUG, TAG)})
        result = self.run_preflight_with(fake)
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(any(f.startswith("API-UNREACHABLE") for f in result.findings), result.findings)


class CiConclusionTest(PreflightTestCase):
    def test_non_success_conclusion_is_blocked(self):
        routes = green_routes(**{
            preflight.runs_url(SLUG, SHA): (200, {"workflow_runs": [run_record(conclusion="failure")]}),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("CI-NOT-SUCCESS") for f in result.findings), result.findings)

    def test_missing_canonical_verify_run_is_blocked(self):
        routes = green_routes(**{
            preflight.runs_url(SLUG, SHA): (200, {"workflow_runs": [run_record(name="Some Other Workflow")]}),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("CI-RUN-MISSING") for f in result.findings), result.findings)

    def test_empty_run_list_is_blocked(self):
        routes = green_routes(**{preflight.runs_url(SLUG, SHA): (200, {"workflow_runs": []})})
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("CI-RUN-MISSING") for f in result.findings), result.findings)

    def test_successful_run_wins_over_earlier_failure(self):
        routes = green_routes(**{
            preflight.runs_url(SLUG, SHA): (
                200,
                {
                    "workflow_runs": [
                        run_record(conclusion="failure", run_id=1),
                        run_record(conclusion="success", run_id=RUN_ID),
                    ]
                },
            ),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "PASS", result.findings)
        self.assertEqual(result.facts["ci_run_id"], RUN_ID)

    def test_ci_query_unreachable_is_incomplete(self):
        fake = FakeFetch(green_routes(), unavailable={preflight.runs_url(SLUG, SHA)})
        result = self.run_preflight_with(fake)
        self.assertEqual(result.status, "INCOMPLETE")


class ArtifactReadbackTest(PreflightTestCase):
    def test_artifact_shipped_with_sha_mismatch_is_blocked(self):
        result = self.run_preflight_with(
            FakeFetch(green_routes()), expect_artifact_sha256="e" * 64
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("ARTIFACT-SHA256-MISMATCH") for f in result.findings), result.findings)

    def test_artifact_missing_from_run_is_blocked(self):
        routes = green_routes(**{
            preflight.run_artifacts_url(SLUG, RUN_ID): (200, {"artifacts": [artifact_record(name="something-else")]}),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("ARTIFACT-MISSING") for f in result.findings), result.findings)

    def test_artifact_download_unreachable_is_incomplete(self):
        fake = FakeFetch(green_routes(), unavailable={ARTIFACT_URL})
        result = self.run_preflight_with(fake)
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(any(f.startswith("API-UNREACHABLE") for f in result.findings), result.findings)

    def test_artifact_download_http_error_is_incomplete(self):
        routes = green_routes(**{ARTIFACT_URL: (502, b"")})
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(any(f.startswith("ARTIFACT-DOWNLOAD-UNAVAILABLE") for f in result.findings), result.findings)

    def test_api_digest_is_the_reference_when_no_expectation_is_passed(self):
        result = self.run_preflight_with(FakeFetch(green_routes()), expect_artifact_sha256="")
        self.assertEqual(result.status, "PASS", result.findings)
        self.assertEqual(result.facts["artifact_sha256"], ARTIFACT_DIGEST)

    def test_no_digest_available_is_incomplete(self):
        routes = green_routes(**{
            preflight.run_artifacts_url(SLUG, RUN_ID): (200, {"artifacts": [artifact_record(digest=None)]}),
        })
        result = self.run_preflight_with(FakeFetch(routes), expect_artifact_sha256="")
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(any(f.startswith("ARTIFACT-DIGEST-UNSPECIFIED") for f in result.findings), result.findings)

    def test_downloaded_bytes_are_hashed_and_persisted(self):
        download_dir = self.tmp / "downloads"
        result = self.run_preflight_with(FakeFetch(green_routes()), download_dir=str(download_dir))
        self.assertEqual(result.status, "PASS", result.findings)
        saved = download_dir / f"{ARTIFACT_NAME}.zip"
        self.assertTrue(saved.exists(), "downloaded artifact not persisted")
        self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(), ARTIFACT_DIGEST)
        self.assertEqual(result.facts["artifact_bytes"], len(ARTIFACT_BYTES))

    def test_archive_is_requested_as_json_accept(self):
        # The api.github.com artifact archive route negotiates Accept and
        # answers 415 for octet-stream (DL-CLOUDAUDIT-2026-09-25 H001):
        # the download leg must carry the JSON Accept even though the
        # bytes it retrieves are a binary zip.
        fake = FakeFetch(green_routes())
        self.run_preflight_with(fake)
        accepts = {url: accept for url, accept in fake.calls}
        self.assertEqual(accepts[ARTIFACT_URL], preflight.GITHUB_JSON)

    def test_explicit_run_id_is_read_back_even_when_ci_is_blocked(self):
        routes = green_routes(**{
            preflight.runs_url(SLUG, SHA): (200, {"workflow_runs": [run_record(conclusion="failure")]}),
        })
        result = self.run_preflight_with(FakeFetch(routes), run_id=str(RUN_ID))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("CI-NOT-SUCCESS") for f in result.findings), result.findings)
        self.assertEqual(result.facts["artifact_sha256"], ARTIFACT_DIGEST)

    def test_explicit_run_id_without_the_artifact_is_blocked(self):
        routes = green_routes(**{
            preflight.run_artifacts_url(SLUG, RUN_ID): (200, {"artifacts": []}),
        })
        result = self.run_preflight_with(FakeFetch(routes), run_id=str(RUN_ID))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("ARTIFACT-MISSING") for f in result.findings), result.findings)

    def test_artifact_check_is_not_counted_when_no_run_is_known(self):
        routes = green_routes(**{
            preflight.runs_url(SLUG, SHA): (200, {"workflow_runs": [run_record(name="Other")]}),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.checks, 4)


class ReleaseAssetTest(PreflightTestCase):
    def test_unpublished_release_is_reported_and_never_passes(self):
        routes = green_routes()
        del routes[preflight.release_url(SLUG, TAG)]  # tag exists, release does not
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("RELEASE_NOT_PUBLISHED") for f in result.findings), result.findings)

    def test_expected_asset_missing_is_blocked(self):
        routes = green_routes(**{
            preflight.release_url(SLUG, TAG): (200, {"assets": [asset_record(name="other.bin", url=ASSET_URL)]}),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("RELEASE-ASSET-MISSING") for f in result.findings), result.findings)

    def test_unexpected_asset_is_blocked(self):
        routes = green_routes(**{
            preflight.release_url(SLUG, TAG): (
                200,
                {"assets": [asset_record(), asset_record(name="surprise.bin")]},
            ),
        })
        result = self.run_preflight_with(FakeFetch(routes))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("RELEASE-ASSET-UNEXPECTED") for f in result.findings), result.findings)

    def test_glob_expectation_matches_timestamped_attestation(self):
        asset = "attestation-20260920T000000Z.json"
        attestation_bytes = b"attestation json"
        self.write_checksums({asset: hashlib.sha256(attestation_bytes).hexdigest()})
        routes = green_routes(**{
            preflight.release_url(SLUG, TAG): (200, {"assets": [asset_record(name=asset)]}),
            ASSET_URL: (200, attestation_bytes),
        })
        result = self.run_preflight_with(
            FakeFetch(routes), expect_assets=["attestation-*.json"]
        )
        self.assertEqual(result.status, "PASS", result.findings)

    def test_unspecified_asset_expectation_is_incomplete(self):
        result = self.run_preflight_with(FakeFetch(green_routes()), expect_assets=[])
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(
            any(f.startswith("RELEASE-ASSETS-EXPECTATION-UNSPECIFIED") for f in result.findings),
            result.findings,
        )

    def test_release_query_unreachable_is_incomplete(self):
        fake = FakeFetch(green_routes(), unavailable={preflight.release_url(SLUG, TAG)})
        result = self.run_preflight_with(fake)
        self.assertEqual(result.status, "INCOMPLETE")


class ChecksumTest(PreflightTestCase):
    def test_asset_checksum_mismatch_is_blocked(self):
        self.write_checksums({ASSET_NAME: "f" * 64})
        result = self.run_preflight_with(FakeFetch(green_routes()))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("ASSET-SHA256-MISMATCH") for f in result.findings), result.findings)

    def test_asset_download_unreachable_is_incomplete(self):
        fake = FakeFetch(green_routes(), unavailable={ASSET_URL})
        result = self.run_preflight_with(fake)
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(any(f.startswith("API-UNREACHABLE") for f in result.findings), result.findings)

    def test_unrecorded_asset_cannot_be_silently_accepted(self):
        self.write_checksums({"some-other-file.json": "a" * 64})
        result = self.run_preflight_with(FakeFetch(green_routes()))
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(f.startswith("ASSET-CHECKSUM-UNRECORDED") for f in result.findings), result.findings)

    def test_missing_local_checksum_file_is_incomplete(self):
        result = self.run_preflight_with(
            FakeFetch(green_routes()), local_checksums=self.tmp / "absent.sha256"
        )
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(any(f.startswith("LOCAL-CHECKSUMS-MISSING") for f in result.findings), result.findings)

    def test_asset_bytes_are_hashed_from_the_download(self):
        fake = FakeFetch(green_routes())
        result = self.run_preflight_with(fake)
        self.assertEqual(result.status, "PASS", result.findings)
        self.assertEqual(
            result.facts[f"asset_sha256_{ASSET_NAME}"],
            f"OK bytes={len(ASSET_BYTES)} sha256={ASSET_DIGEST}",
        )


class FailClosedContractTest(PreflightTestCase):
    def test_no_token_is_incomplete_and_never_pass(self):
        result = self.run_preflight_with(FakeFetch(green_routes()), token=None)
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertNotEqual(result.status, "PASS")
        self.assertEqual(result.checks, 0)
        self.assertTrue(any(f.startswith("NO-GITHUB-TOKEN") for f in result.findings), result.findings)

    def test_no_token_opens_no_connection(self):
        fake = FakeFetch(green_routes())
        self.run_preflight_with(fake, token=None)
        self.assertEqual(fake.calls, [], "preflight hit the network without a token")

    def test_main_without_token_env_exits_nonzero_with_incomplete(self):
        argv = [
            "--tag", TAG, "--sha", SHA, "--repo", SLUG,
            "--expect-assets", ASSET_NAME,
            "--local-checksums", str(self.checksums),
        ]
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False):
            with contextlib.redirect_stdout(out):
                code = preflight.main(argv, fetch_fn=FakeFetch(green_routes()))
        self.assertNotEqual(code, 0)
        self.assertIn("RELEASE_PREFLIGHT=INCOMPLETE", out.getvalue())
        self.assertNotIn("RELEASE_PREFLIGHT=PASS", out.getvalue())

    def test_contract_line_format(self):
        for status in ("PASS", "BLOCKED", "INCOMPLETE"):
            line = preflight.PreflightResult(status=status, checks=5, findings=["A-B c=d"]).contract_line()
            self.assertRegex(line, CONTRACT_RE)

    def test_contract_line_reports_findings_as_json_list(self):
        result = self.run_preflight_with(FakeFetch(green_routes()), expect_assets=["missing.bin"])
        self.assertEqual(json.loads(result.contract_line().split("findings=", 1)[1]), result.findings)
        self.assertIn("RELEASE_PREFLIGHT=BLOCKED", result.contract_line())

    def test_exit_codes_pass_blocked_incomplete(self):
        code, output = self.main_with(FakeFetch(green_routes()))
        self.assertEqual(code, 0, output)
        self.assertIn("RELEASE_PREFLIGHT=PASS", output)

        routes = green_routes(**{
            preflight.tag_ref_url(SLUG, TAG): (200, {"object": {"type": "commit", "sha": OTHER_SHA}}),
        })
        code, output = self.main_with(FakeFetch(routes))
        self.assertEqual(code, 2, output)
        self.assertIn("RELEASE_PREFLIGHT=BLOCKED", output)

        code, output = self.main_with(FakeFetch(green_routes(), unavailable={preflight.runs_url(SLUG, SHA)}))
        self.assertEqual(code, 3, output)
        self.assertIn("RELEASE_PREFLIGHT=INCOMPLETE", output)

    def test_network_goes_through_one_injectable_function(self):
        signature = inspect.signature(preflight.run_preflight)
        self.assertIs(signature.parameters["fetch_fn"].default, preflight.fetch)
        self.assertIn("token", inspect.signature(preflight.fetch).parameters)

    def test_full_pass_never_touches_urllib(self):
        fake = FakeFetch(green_routes())
        with mock.patch("urllib.request.build_opener", side_effect=AssertionError("real network use")):
            result = self.run_preflight_with(fake)
        self.assertEqual(result.status, "PASS", result.findings)
        self.assertTrue(fake.calls, "the fake fetch was never used")


class HelperTest(unittest.TestCase):
    def test_repo_from_remote_url(self):
        self.assertEqual(preflight.repo_from_remote_url("git@github.com:DTALEX66/DESIGN-LAB.git"), "DTALEX66/DESIGN-LAB")
        self.assertEqual(preflight.repo_from_remote_url("https://github.com/DTALEX66/DESIGN-LAB.git"), "DTALEX66/DESIGN-LAB")
        self.assertEqual(preflight.repo_from_remote_url("https://github.com/DTALEX66/DESIGN-LAB"), "DTALEX66/DESIGN-LAB")
        self.assertEqual(preflight.repo_from_remote_url("https://gitlab.com/other/repo.git"), "")
        self.assertEqual(preflight.repo_from_remote_url(""), "")

    def test_load_checksums_parses_sha256sum_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifacts.sha256"
            path.write_text(
                "# comment\n"
                f"{'a' * 64}  .project-local/task-runtime/evidence/attestation-1.json\n"
                f"{'b' * 64} *design-lab/config/sbom-v42.spdx.json\n"
                "not-a-line\n"
                f"{'z' * 64}  bad-digest.json\n",
                encoding="utf-8",
            )
            recorded = preflight.load_checksums(path)
            self.assertEqual(
                recorded,
                {
                    "attestation-1.json": "a" * 64,
                    "sbom-v42.spdx.json": "b" * 64,
                },
            )

    def test_load_checksums_returns_none_for_missing_file(self):
        self.assertIsNone(preflight.load_checksums(Path("does-not-exist.sha256")))

    def test_parse_asset_expectations(self):
        self.assertEqual(preflight.parse_asset_expectations("a,b , c"), ["a", "b", "c"])
        self.assertEqual(preflight.parse_asset_expectations(None), [])
        self.assertEqual(preflight.parse_asset_expectations("  "), [])

    def test_script_is_stdlib_only(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for banned in ("import requests", "import urllib3", "import httpx"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
