"""Live documents may not cite paths that do not exist -- and historical documents must be left alone.

Measured 2026-10-18: 383 stale citations, but the split decided the fix. 376 live in historical/audit documents
where naming the September path is the POINT (rewriting them would falsify the record); 7 were in live prose and
three of those were load-bearing. So the gate's exclusions are as important as its findings, and both are pinned
here: a frozen root must NOT be reported, and a live citation MUST be.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "verify_live_doc_paths_resolve.py"
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import project_temp  # noqa: E402


def load_module():
    spec = importlib.util.spec_from_file_location("verify_live_doc_paths_resolve", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LiveDocPathTests(unittest.TestCase):
    def test_the_live_corpus_resolves(self) -> None:
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        out = proc.stdout + proc.stderr
        self.assertEqual(0, proc.returncode, out)
        self.assertIn("LIVE_DOC_PATHS_PASS", out)

    def _fixture(self, module, *, live_doc: str, frozen_doc: str | None = None,
                 exceptions: dict | None = None) -> Path:
        tmp = project_temp.fixture_dir(prefix="wl-live-docs-")
        (tmp / "docs/current").mkdir(parents=True, exist_ok=True)
        (tmp / ".project/governance").mkdir(parents=True, exist_ok=True)
        (tmp / "docs/current/live.md").write_text(live_doc, encoding="utf-8")
        if frozen_doc is not None:
            (tmp / "docs/history").mkdir(parents=True, exist_ok=True)
            (tmp / "docs/history/old.md").write_text(frozen_doc, encoding="utf-8")
        (tmp / ".project/governance/root-document-dispositions.json").write_text(
            json.dumps({"authority": []}), encoding="utf-8")
        (tmp / ".project/governance/live-doc-path-exceptions.json").write_text(
            json.dumps({"exceptions": exceptions or {}}), encoding="utf-8")
        for rel in ("docs/current/live.md", "docs/history/old.md"):
            if (tmp / rel).is_file():
                subprocess.run(["git", "add", rel], cwd=tmp, capture_output=True)
        module.ROOT = tmp
        module.DISPOSITIONS = tmp / ".project/governance/root-document-dispositions.json"
        module.EXCEPTIONS = tmp / ".project/governance/live-doc-path-exceptions.json"
        return tmp

    def test_a_live_citation_to_a_missing_path_is_reported(self) -> None:
        module = load_module()
        tmp = self._fixture(module, live_doc="see `scripts/does_not_exist.py` for details\n")
        try:
            problems, stale, _ = module.audit(tmp, ["docs/current/live.md", "docs/history/old.md"])
            self.assertTrue(any("does_not_exist.py" in p for p in problems), problems)
            self.assertEqual([], stale)
        finally:
            project_temp.force_release(tmp)

    def test_a_historical_citation_to_a_missing_path_is_not_reported(self) -> None:
        module = load_module()
        tmp = self._fixture(module, live_doc="ok\n", frozen_doc="see `scripts/gone_since_2026_09.py`\n")
        try:
            problems, _, _ = module.audit(tmp, ["docs/current/live.md", "docs/history/old.md"])
            self.assertEqual([], problems, "history must be allowed to name its own paths")
        finally:
            project_temp.force_release(tmp)

    def test_a_stale_exception_is_itself_a_finding(self) -> None:
        module = load_module()
        tmp = project_temp.fixture_dir(prefix="wl-live-docs-stale-")
        (tmp / "docs/current").mkdir(parents=True, exist_ok=True)
        (tmp / ".project/governance").mkdir(parents=True, exist_ok=True)
        (tmp / "docs/current/live.md").write_text("see `scripts/ci/real.py`\n", encoding="utf-8")
        (tmp / "scripts/ci").mkdir(parents=True, exist_ok=True)
        (tmp / "scripts/ci/real.py").write_text("# real\n", encoding="utf-8")
        for rel in ("docs/current/live.md", "scripts/ci/real.py"):
            subprocess.run(["git", "add", rel], cwd=tmp, capture_output=True)
        (tmp / ".project/governance/root-document-dispositions.json").write_text(
            json.dumps({"authority": []}), encoding="utf-8")
        (tmp / ".project/governance/live-doc-path-exceptions.json").write_text(
            json.dumps({"exceptions": {"scripts/ci/real.py": {"reason": "x", "since": "2026-01-01"}}}),
            encoding="utf-8")
        module.ROOT = tmp
        module.DISPOSITIONS = tmp / ".project/governance/root-document-dispositions.json"
        module.EXCEPTIONS = tmp / ".project/governance/live-doc-path-exceptions.json"
        try:
            _, stale, _ = module.audit(tmp, ["docs/current/live.md", "scripts/ci/real.py"])
            self.assertTrue(any("exists now" in s for s in stale), stale)
        finally:
            project_temp.force_release(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
