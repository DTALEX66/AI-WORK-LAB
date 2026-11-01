# SPDX-License-Identifier: MIT
"""GA-1: fail-closed regression tests for scripts/verify_path_refs.py.

Covers CROSSWALK 2026-09-24 items G-A (path-reference drift) and G-C
(machine install policy) plus G-B self-enforcement (drift guard stays
wired into CI). Every guard must FAIL CLOSED when weakened.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def load_gate():
    path = SCRIPTS / "verify_path_refs.py"
    spec = importlib.util.spec_from_file_location("verify_path_refs", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POLICY = {
    "schemaVersion": "design-lab/path-ref-policy/v1",
    "policyId": "TEST-POLICY",
    "approvedIn": "unit test",
    "note": "test",
    "allowAutoInstall": False,
    "officialReleaseOnly": True,
    "eDriveProtected": True,
    "externalRootDrive": "D:",
    "sharedInputs": {"model-library": "D:/All projects/Model library"},
    "externalAssetsRoots": {"model-library": "D:\\All projects\\Model library"},
    "allowlist_missing": [],
}


def build_fixture(tmp: Path, agents_refs=("AUTHORITY.md",), extra: dict | None = None) -> Path:
    """Materialise the minimal authority surface the gate inspects."""
    (tmp / ".project/governance").mkdir(parents=True, exist_ok=True)
    (tmp / "design-lab/scripts").mkdir(parents=True, exist_ok=True)
    (tmp / "design-lab/config").mkdir(parents=True, exist_ok=True)
    (tmp / ".github/workflows").mkdir(parents=True, exist_ok=True)

    (tmp / "AUTHORITY.md").write_text(
        "DL-AUTHORITY-2026-09-18-R2\nsee `AGENTS.md` and `docs/x.json`.\n",
        encoding="utf-8",
    )
    (tmp / "AGENTS.md").write_text("see `AUTHORITY.md`.\n", encoding="utf-8")
    (tmp / "docs").mkdir(exist_ok=True)
    (tmp / "docs/x.json").write_text("{}", encoding="utf-8")
    (tmp / ".project/paths.json").write_text(
        json.dumps({"schemaVersion": "v1", "shared_inputs": POLICY["sharedInputs"]}),
        encoding="utf-8",
    )
    (tmp / "design-lab/config/external-assets-index.json").write_text(
        json.dumps({"shared_roots": POLICY["externalAssetsRoots"]}), encoding="utf-8"
    )
    policy = dict(POLICY)
    policy.update(extra or {})
    (tmp / ".project/governance/path-ref-policy.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )
    (tmp / "design-lab/scripts/verify_project_drift.py").write_text("# guard\n", encoding="utf-8")
    (tmp / ".github/workflows/canonical-verify.yml").write_text(
        "jobs:\n  python-gate:\n    steps:\n"
        "      - name: Language/product drift guard (DL-GOV-130)\n"
        "        run: python design-lab/scripts/verify_project_drift.py\n",
        encoding="utf-8",
    )
    return tmp


class PathRefGateTests(unittest.TestCase):
    def setUp(self):
        self.g = load_gate()
        self._tmpdir = None

    def _run(self, repo: Path) -> list[dict]:
        return self.g.checks_all(repo)

    def test_fixture_all_pass(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            results = self._run(repo)
            failed = [r for r in results if r["result"] != "PASS"]
            self.assertEqual(failed, [], msg=f"unexpected FAILs: {failed}")

    def test_missing_reference_fails_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            (repo / "AGENTS.md").write_text("see `docs/ghost.json`.\n", encoding="utf-8")
            results = self._run(repo)
            by = {r["check"]: r for r in results}
            self.assertEqual(by["path-refs-resolve"]["result"], "FAIL")

    def test_unallowlisted_missing_ref_fails_but_allowlisted_passes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            (repo / "AGENTS.md").write_text(
                "see `docs/ghost.json` (allowlisted below).\n", encoding="utf-8"
            )
            p = repo / ".project/governance/path-ref-policy.json"
            policy = json.loads(p.read_text(encoding="utf-8"))
            policy["allowlist_missing"] = [
                {"ref": "docs/ghost.json", "reason": "generated at build", "approvedIn": "unit test"}
            ]
            p.write_text(json.dumps(policy), encoding="utf-8")
            by = {r["check"]: r for r in self._run(repo)}
            self.assertEqual(by["path-refs-resolve"]["result"], "PASS")
            self.assertEqual(by["allowlist-reviewed"]["result"], "PASS")

    def test_allowlist_entry_without_reason_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            p = repo / ".project/governance/path-ref-policy.json"
            policy = json.loads(p.read_text(encoding="utf-8"))
            policy["allowlist_missing"] = [{"ref": "docs/ghost.json"}]  # no reason/approvedIn
            p.write_text(json.dumps(policy), encoding="utf-8")
            by = {r["check"]: r for r in self._run(repo)}
            self.assertEqual(by["allowlist-reviewed"]["result"], "FAIL")

    def test_project_alias_resolves_to_dot_project(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            text = (repo / "AGENTS.md").read_text(encoding="utf-8")
            (repo / "AGENTS.md").write_text(
                text + "index at `project/governance/authority-index.json`.\n", encoding="utf-8"
            )
            (repo / ".project/governance/authority-index.json").write_text("{}", encoding="utf-8")
            by = {r["check"]: r for r in self._run(repo)}
            self.assertEqual(by["path-refs-resolve"]["result"], "PASS")

    def test_e_drive_root_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            p = repo / ".project/governance/path-ref-policy.json"
            policy = json.loads(p.read_text(encoding="utf-8"))
            policy["sharedInputs"]["model-library"] = "E:/BaiduSyncdisk/Obsidian知识库"
            p.write_text(json.dumps(policy), encoding="utf-8")
            # keep paths.json consistent so the run reaches the e-drive check
            (repo / ".project/paths.json").write_text(
                json.dumps({"schemaVersion": "v1", "shared_inputs": policy["sharedInputs"]}),
                encoding="utf-8",
            )
            by = {r["check"]: r for r in self._run(repo)}
            self.assertEqual(by["e-drive-protected"]["result"], "FAIL")

    def test_auto_install_true_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            p = repo / ".project/governance/path-ref-policy.json"
            policy = json.loads(p.read_text(encoding="utf-8"))
            policy["allowAutoInstall"] = True
            p.write_text(json.dumps(policy), encoding="utf-8")
            by = {r["check"]: r for r in self._run(repo)}
            self.assertEqual(by["auto-install-deny"]["result"], "FAIL")

    def test_missing_policy_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            (repo / ".project/governance/path-ref-policy.json").unlink()
            by = {r["check"]: r for r in self._run(repo)}
            self.assertEqual(by["policy-exists"]["result"], "FAIL")

    def test_policy_schema_mismatch_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            p = repo / ".project/governance/path-ref-policy.json"
            policy = json.loads(p.read_text(encoding="utf-8"))
            policy["schemaVersion"] = "design-lab/path-ref-policy/v2"
            p.write_text(json.dumps(policy), encoding="utf-8")
            by = {r["check"]: r for r in self._run(repo)}
            self.assertEqual(by["policy-schema"]["result"], "FAIL")

    def test_unwired_drift_guard_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            (repo / ".github/workflows/canonical-verify.yml").write_text("jobs: {}\n", encoding="utf-8")
            by = {r["check"]: r for r in self._run(repo)}
            self.assertEqual(by["dl-gov-130-ci-wired"]["result"], "FAIL")

    def test_code_fences_excluded_from_refs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            repo = build_fixture(Path(d))
            (repo / "AGENTS.md").write_text(
                "run it:\n```\npython docs/not-in-any-code-path.json --check\n```\n",
                encoding="utf-8",
            )
            by = {r["check"]: r for r in self._run(repo)}
            self.assertEqual(by["path-refs-resolve"]["result"], "PASS")

    def test_live_repo_gate_passes(self):
        """The committed tree itself must satisfy the gate (smoke)."""
        rc = self.g.main(REPO) if hasattr(self.g, "main") else None
        # main() prints and returns int; assert PASS state without touching stdout policy
        self.assertEqual(rc, 0, msg="live repo must pass scripts/verify_path_refs.py")


if __name__ == "__main__":
    unittest.main()
