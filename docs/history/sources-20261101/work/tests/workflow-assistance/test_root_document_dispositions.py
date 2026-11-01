"""Mandatory gate: every tracked root Markdown file must declare a checked disposition.

A root document that reads like an assignment is opened before the authority chain, so the
control is not "someone wrote it down in the census" but "the machine refuses a root file that
nobody has classified, and refuses a historical file whose banner has gone stale or whose body
was quietly rewritten."

The negative controls below are what make that a check rather than a count: each one feeds the
real predicate a synthetic document and requires a named red.
"""

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/verify_root_document_dispositions.py"
REGISTRY = ROOT / ".project/governance/root-document-dispositions.json"
AUTHORITY_INDEX = ROOT / ".project/governance/project-authority-index.json"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_root_document_dispositions", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()
BANNER = (MODULE.BEGIN_MARK + "\n> body points to "
          + json.loads(AUTHORITY_INDEX.read_text(encoding="utf-8"))["currentTaskpack"]
          + "\n" + MODULE.END_MARK + "\n")


class RootDocumentDispositionTests(unittest.TestCase):
    def run_verifier(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=ROOT,
            text=True, encoding="utf-8", errors="replace", capture_output=True)

    def historical_entry(self):
        return {"disposition": "historical-non-normative", "reason": "dated record"}

    def test_the_shipped_repository_passes(self):
        result = self.run_verifier()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("ROOT_DISPOSITIONS_PASS", result.stdout)
        rows = json.loads(REGISTRY.read_text(encoding="utf-8"))["documents"]
        summary = next(line for line in result.stdout.splitlines() if "root_md=" in line)
        count = lambda word: sum(1 for row in rows if row["disposition"] == word)  # noqa: E731
        expected = "authority={} convention={} historical={}".format(
            count("authority"), count("convention-current"), count("historical-non-normative"))
        self.assertIn(expected, summary)
        self.assertIn(f"root_md={len(MODULE.tracked_root_markdown(ROOT))}", summary)
        self.assertEqual(len(rows), len(MODULE.tracked_root_markdown(ROOT)),
                         "the registry and the tracked root must be the same set of files")

    def test_a_root_document_nobody_classified_is_red(self):
        findings = MODULE.check_document("NEW-HANDOFF.md", None, "x", "x", "tp.md")
        self.assertEqual(["UNCLASSIFIED_ROOT_DOCUMENT NEW-HANDOFF.md: tracked at the root and in "
                          "no disposition registry"], findings)

    def test_an_unknown_disposition_word_is_red(self):
        findings = MODULE.check_document("X.md", {"disposition": "maybe", "reason": "r"},
                                         "body", "body", "tp.md")
        self.assertTrue(any(f.startswith("BAD_DISPOSITION X.md") for f in findings), findings)

    def test_a_classification_without_a_reason_is_red(self):
        findings = MODULE.check_document("X.md", {"disposition": "historical-non-normative",
                                                 "reason": "  "}, "body", "body", "tp.md")
        self.assertTrue(any("MISSING_REASON X.md" in f for f in findings), findings)

    def test_a_historical_file_with_no_banner_is_red(self):
        findings = MODULE.check_document("X.md", self.historical_entry(),
                                         "# Title\n\nlive instructions here\n",
                                         "# Title\n\nlive instructions here\n", "tp.md")
        self.assertTrue(any(f.startswith("UNLABELLED_HISTORICAL X.md") for f in findings), findings)

    def test_a_banner_naming_a_superseded_taskpack_is_red(self):
        stale = ("# Title\n" + MODULE.BEGIN_MARK + "\n> see "
                 "taskpacks/history/WORK-LAB-OLD.md\n" + MODULE.END_MARK + "\n\nbody\n")
        findings = MODULE.check_document("X.md", self.historical_entry(), stale,
                                         "# Title\n\nbody\n", "taskpacks/current/NEW.md")
        self.assertTrue(any(f.startswith("STALE_POINTER X.md") for f in findings), findings)

    def test_editing_the_body_of_a_historical_record_is_red(self):
        original = "# Title\n\noriginal bytes\n"
        edited = "# Title\n" + BANNER + "\nchanged bytes\n"
        findings = MODULE.check_document("X.md", self.historical_entry(), edited, original,
                                         json.loads(AUTHORITY_INDEX.read_text(encoding="utf-8"))["currentTaskpack"])
        self.assertTrue(any(f.startswith("BODY_REWRITTEN X.md") for f in findings), findings)
        self.assertNotIn("UNLABELLED_HISTORICAL", "".join(findings))

    def test_the_body_identity_control_reproduces_the_committed_bytes(self):
        original = "# Title\n\noriginal bytes\n"
        bannered = "# Title\n" + BANNER + "\noriginal bytes\n"
        taskpack = json.loads(AUTHORITY_INDEX.read_text(encoding="utf-8"))["currentTaskpack"]
        findings = MODULE.check_document("X.md", self.historical_entry(), bannered, original, taskpack)
        self.assertEqual([], findings, f"a banner-only change must be clean: {findings}")

    def test_a_line_ending_difference_is_not_a_body_rewrite(self):
        """The repository normalizes on check-in, so CRLF on disk is the same text as LF in the object.

        Measured the other way round: at `0db79f9f` the guard convicted all six historical root documents the
        moment they were committed, because the comparison was byte-exact and the checkout is CRLF. A check that
        fires on every file it inspects is not protecting those files, it is training the reader to ignore it --
        so the terminator is normalized while a changed WORD still has to be caught (the case above).
        """
        original = "# Title\r\n\r\noriginal bytes\r\n"
        bannered = "# Title\r\n" + BANNER.replace("\n", "\r\n") + "\r\noriginal bytes\r\n"
        taskpack = json.loads(AUTHORITY_INDEX.read_text(encoding="utf-8"))["currentTaskpack"]
        self.assertEqual([], MODULE.check_document("X.md", self.historical_entry(), bannered,
                                                  original.replace("\r\n", "\n"), taskpack))
        # and the same document with one word changed is still convicted, terminator normalization and all
        rewritten = bannered.replace("original bytes", "quietly edited")
        findings = MODULE.check_document("X.md", self.historical_entry(), rewritten,
                                         original.replace("\r\n", "\n"), taskpack)
        self.assertTrue(any(f.startswith("BODY_REWRITTEN X.md") for f in findings), findings)

    def test_a_committed_banner_is_not_read_as_a_rewritten_body(self):
        """Once the labelling round is committed, BOTH sides carry the banner.

        The first version of the comparison stripped only the disk text, so the day the banners landed in a
        commit every historical document was convicted of rewriting itself. This is the state after that
        commit, and the honest scope statement: the guard compares against the committed bytes, so a rewrite
        already inside history is out of its reach -- it catches an uncommitted edit to a file that is
        declared immutable outside its banner.
        """
        taskpack = json.loads(AUTHORITY_INDEX.read_text(encoding="utf-8"))["currentTaskpack"]
        committed = "# Title\n" + BANNER + "\noriginal bytes\n"
        untouched = committed
        findings = MODULE.check_document("X.md", self.historical_entry(), untouched, committed, taskpack)
        self.assertEqual([], findings, f"a committed banner must not convict its own file: {findings}")
        edited = "# Title\n" + BANNER + "\noriginal bytes, quietly changed\n"
        findings = MODULE.check_document("X.md", self.historical_entry(), edited, committed, taskpack)
        self.assertTrue(any(f.startswith("BODY_REWRITTEN X.md") for f in findings), findings)

    def test_an_authority_document_cannot_claim_a_historical_banner(self):
        entry = {"disposition": "authority", "reason": "named by the index"}
        text = "# Title\n" + BANNER + "\nrules\n"
        findings = MODULE.check_document("AGENTS.md", entry, text, text, "tp.md")
        self.assertTrue(any(f.startswith("CONTRADICTION AGENTS.md") for f in findings), findings)

    def test_the_authority_population_is_derived_not_copied(self):
        index = json.loads(AUTHORITY_INDEX.read_text(encoding="utf-8"))
        derived = MODULE.authority_named_root_documents(index)
        self.assertIn("AGENTS.md", derived)
        self.assertIn("WORK-LAB-AUTHORITY.md", derived)
        self.assertNotIn("NOTICE.md", derived,
                         "a provenance notice must never be read as an authority document")
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        declared = {row["path"] for row in registry["documents"]
                    if row["disposition"] == "authority"}
        self.assertEqual(derived, declared)
        tampered = {"topHumanAuthority": "SOMETHING-ELSE.md",
                    "auditBootstrap": [], "sourcePrecedence": []}
        self.assertEqual({"SOMETHING-ELSE.md"},
                         MODULE.authority_named_root_documents(tampered))

    def test_every_banner_carries_the_marker_within_its_first_twelve_lines(self):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for row in registry["documents"]:
            if row["disposition"] != "historical-non-normative":
                continue
            text = (ROOT / row["path"]).read_text(encoding="utf-8")
            head = "".join(text.splitlines(keepends=True)[:12])
            self.assertIn(MODULE.MARKER, head, row["path"])
            self.assertIn(json.loads(AUTHORITY_INDEX.read_text(encoding="utf-8"))["currentTaskpack"],
                          text[:4000], row["path"])

    def test_no_convention_or_authority_document_is_mislabelled_as_history(self):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for row in registry["documents"]:
            if row["disposition"] == "historical-non-normative":
                continue
            text = (ROOT / row["path"]).read_text(encoding="utf-8")
            self.assertNotIn(MODULE.BEGIN_MARK, text, row["path"])

    def test_the_registry_covers_the_tracked_root_exactly(self):
        population = set(MODULE.tracked_root_markdown(ROOT))
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        declared = {row["path"] for row in registry["documents"]}
        self.assertEqual(population, declared,
                         "a root document must be classified, or its row removed with the file")
        self.assertTrue(MODULE.authority_named_root_documents(
            json.loads(AUTHORITY_INDEX.read_text(encoding="utf-8"))) <= population)

    def test_the_verifier_names_its_own_blindness_instead_of_passing(self):
        """No git means no population, so the verdict must be a named non-pass."""
        import contextlib
        import io

        original = MODULE.tracked_root_markdown
        buffer = io.StringIO()
        try:
            def raise_missing(root):
                raise RuntimeError("git: not found")
            MODULE.tracked_root_markdown = raise_missing
            with contextlib.redirect_stdout(buffer):
                code = MODULE.main()
        finally:
            MODULE.tracked_root_markdown = original
        self.assertEqual(2, code, buffer.getvalue())
        self.assertIn("ROOT_DISPOSITIONS_NO_GIT", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
