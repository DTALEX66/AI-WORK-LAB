# SPDX-License-Identifier: MIT
"""The 37 cache-only vendor roots must be accountable from the repository alone.

`vendor/sources.lock.json` says it holds 37 third-party trees whose bytes live only in
`.project-local/cache/vendor/` on one machine. Since 2026-10-09 each of them also carries a
committed manifest of per-file hashes, and `verify_vendor_manifests.py` re-derives the
aggregate digest from those rows to prove the manifest and the lock describe the same set of
bytes without the files being present.

These tests exist because a check nobody can make fail is not a check. Every finding the gate
emits is fed a planted defect, and the three cases that matter most are pinned directly: the
row-level recipe must reproduce `digest_dir` byte for byte (if it drifts, `--check` proves
nothing), regeneration must never invent a rights review, and an aggregate root's `origins`
list must account for every byte exactly once -- which is how `tool-control` was shown to hold
seven upstreams where the lock named four.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "design-lab" / "scripts" / "verify_vendor_manifests.py"
LOCK = ROOT / "vendor" / "sources.lock.json"

sys.path.insert(0, str(ROOT / "design-lab" / "scripts"))

import verify_vendor_manifests as v  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_cache(root: Path) -> None:
    """A tree whose bytes are identical on every platform.

    `newline="\n"` is deliberate: text mode would translate LF to CRLF on Windows, the
    fixture's hashes would then depend on the host, and the row-level expectations below
    would be asserting a platform behaviour rather than a record shape.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("# Vendor skill\n", encoding="utf-8", newline="\n")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8", newline="\n")
    nested = root / "references"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "guide.md").write_text("body text\n", encoding="utf-8", newline="\n")


def make_lock(cache_rel: str, rows: list[dict], *, files: int = 3,
              digest: str | None = None, presence: str = v.CACHE_ONLY) -> dict:
    return {
        "schemaVersion": "design-lab/vendor-sources/v1",
        "sources": [{
            "id": "demo-root",
            "presence": presence,
            "path": cache_rel,
            "canonicalUrl": "https://example.invalid/demo-root",
            "license": "MIT",
            "provenanceSource": "SOURCE.md",
            "observedAt": "2026-10-09",
            "files": files,
            "diskFiles": files,
            "contentDigest": digest if digest is not None
            else v.digest_from_rows(rows),
        }],
    }


def manifest_rows() -> list[dict]:
    """The rows `make_cache` produces, hashed independently of the gate under test."""
    return [
        {"path": "LICENSE", "bytes": 4, "sha256": sha(b"MIT\n")},
        {"path": "SKILL.md", "bytes": 15, "sha256": sha(b"# Vendor skill\n")},
        {"path": "references/guide.md", "bytes": 10, "sha256": sha(b"body text\n")},
    ]



class ConsistentState:
    """A repo-shaped tmp tree with a cache, a lock, and one manifest generated from both."""

    def __init__(self, ctx: tempfile.TemporaryDirectory) -> None:
        self.repo = Path(ctx.name) / "repo"
        self.cache = self.repo / ".project-local" / "cache" / "vendor" / "demo-root"
        self.manifests = self.repo / "vendor" / "manifests"
        (self.repo / "vendor").mkdir(parents=True, exist_ok=True)
        make_cache(self.cache)
        rows = v.walk_cache(self.cache)
        self.lock = make_lock(".project-local/cache/vendor/demo-root", rows)
        self.written, self.rows, self.missing, self.drift = v.write(
            self.lock, repo=self.repo, manifest_dir=self.manifests)

    def manifest(self) -> dict:
        return json.loads((self.manifests / "demo-root.json").read_text(encoding="utf-8"))

    def save(self, document: dict) -> None:
        (self.manifests / "demo-root.json").write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")

    def findings(self) -> list[str]:
        return v.check(self.lock, self.manifests).problems

    def result(self):
        return v.check(self.lock, self.manifests)

    def declare(self, origins: list[dict]) -> None:
        """Write a declaration, then let the generator compute the measured half.

        This is the production path, so the tests also prove `refresh_origins` will not let a
        declaration keep a stale number.
        """
        document = self.manifest()
        document["origins"] = origins
        self.save(document)
        v.write(self.lock, repo=self.repo, manifest_dir=self.manifests)

    def remeasure(self) -> None:
        """Re-run the presence audit over the current cache, the way the real script does.

        Without this a mutated cache is refused by the drift guard -- which is correct, and is
        exactly why a test that wants to exercise the writer has to move the lock too.
        """
        rows = v.walk_cache(self.cache)
        count, digest = v.digest_dir(self.cache)
        self.lock = make_lock(".project-local/cache/vendor/demo-root", rows,
                              files=count, digest=digest)


def demo_origins() -> list[dict]:
    """`make_cache` holds two upstreams: a nested script tree and two files at the root."""
    return [
        {"id": "guide-upstream", "subtree": "references", "upstream": "acme/guide",
         "upstreamUrl": "https://example.invalid/acme/guide", "licenseAsRecorded": "MIT",
         "declaredScriptCount": 1, "declaredCountText": "1 guide", "evidenceFile": "README.md",
         "reviewedBy": None, "rightsDecision": None},
        {"id": "root-upstream", "files": ["LICENSE", "SKILL.md"], "upstream": "acme/skill",
         "upstreamUrl": None, "urlAbsentReason": "the tree names owner/repo with no URL",
         "licenseAsRecorded": "Apache-2.0", "declaredScriptCount": 1,
         "declaredCountText": "1 skill + licence", "evidenceFile": "README.md",
         "reviewedBy": None, "rightsDecision": None},
    ]


class VendorManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx_stack: list[tempfile.TemporaryDirectory] = []

    def state(self) -> ConsistentState:
        ctx = tempfile.TemporaryDirectory()
        self._ctx_stack.append(ctx)
        return ConsistentState(ctx)

    def tearDown(self) -> None:
        for ctx in self._ctx_stack:
            ctx.cleanup()
        self._ctx_stack.clear()

    # ---- the recipe the whole gate rests on ----

    def test_rows_reproduce_digest_dir_byte_for_byte(self) -> None:
        """`--check` has no files, so the row recipe must be the *same* hash as the walk.

        If these two ever disagree, every clean-clone PASS is a statement about the manifest
        rather than about the bytes the lock attests.
        """
        state = self.state()
        rows = v.walk_cache(state.cache)
        count, digest = v.digest_dir(state.cache)
        self.assertEqual(count, len(rows))
        self.assertEqual(v.digest_from_rows(rows), digest)
        # Order must not matter: the recipe sorts by path itself.
        self.assertEqual(v.digest_from_rows(list(reversed(rows))), digest)

    def test_the_recipe_is_sensitive_to_path_as_well_as_content(self) -> None:
        state = self.state()
        rows = v.walk_cache(state.cache)
        base = v.digest_from_rows(rows)
        renamed = [dict(r, path=r["path"].upper()) for r in rows]
        self.assertNotEqual(v.digest_from_rows(renamed), base,
                            "upper-casing every path must move the digest, or the path is "
                            "not in the hash and any file can be swapped silently")

    # ---- generation ----

    def test_a_consistent_cache_writes_exactly_one_manifest(self) -> None:
        state = self.state()
        self.assertEqual((state.written, state.rows, state.missing, state.drift),
                         (1, 3, [], []))
        self.assertEqual(state.manifest()["files"], manifest_rows(),
                         "the committed record must list exactly the files the tree holds")
        self.assertFalse(state.findings(), "a faithful manifest must not be convicted")

    def test_generation_never_invents_a_rights_review(self) -> None:
        document = self.state().manifest()
        for field in v.OWNER_FIELDS:
            self.assertIsNone(document[field],
                              f"{field} is the owner's to fill; an agent signing it here is "
                              "the exact forgery the task pack forbids")

    def test_regeneration_preserves_a_ruling_a_human_recorded(self) -> None:
        state = self.state()
        document = state.manifest()
        document["reviewedBy"] = "DTALEX66"
        document["reviewedAt"] = "2026-10-09"
        document["rightsDecision"] = "reference-only"
        state.save(document)
        self.assertEqual(v.write(state.lock, repo=state.repo,
                                 manifest_dir=state.manifests)[0], 1)
        again = state.manifest()
        self.assertEqual(again["reviewedBy"], "DTALEX66")
        self.assertEqual(again["rightsDecision"], "reference-only")

    def test_writing_twice_changes_no_bytes(self) -> None:
        """Regeneration must be a fixed point, or every run dirties the tracked record."""
        state = self.state()
        first = (state.manifests / "demo-root.json").read_bytes()
        self.assertEqual(v.write(state.lock, repo=state.repo,
                                 manifest_dir=state.manifests)[0], 1)
        self.assertEqual((state.manifests / "demo-root.json").read_bytes(), first)

    def test_the_writer_emits_lf_so_the_committed_bytes_are_the_checked_out_bytes(self) -> None:
        """.gitattributes declares `*.json text eol=lf`, but this writer runs on Windows.

        Text-mode defaults would put CRLF in the working copy; git then stores LF while the
        file on disk is not the file any clone has, which is the shape of the digest bug this
        repository has already paid for once.
        """
        state = self.state()
        raw = (state.manifests / "demo-root.json").read_bytes()
        self.assertNotIn(b"\r\n", raw)
        self.assertIn(b"\n", raw)

    def test_an_empty_cache_root_is_refused_not_attested(self) -> None:
        state = self.state()
        for path in sorted(state.cache.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
        written, rows, _missing, drift = v.write(state.lock, repo=state.repo,
                                                 manifest_dir=state.manifests)
        self.assertEqual((written, rows), (0, 0))
        self.assertTrue(drift, "an empty directory must never be recorded as verified content")

    def test_a_cache_that_moved_since_the_audit_is_refused(self) -> None:
        state = self.state()
        before = (state.manifests / "demo-root.json").read_text(encoding="utf-8")
        (state.cache / "extra.md").write_text("new\n", encoding="utf-8", newline="\n")
        written, _rows, _missing, drift = v.write(state.lock, repo=state.repo,
                                                  manifest_dir=state.manifests)
        self.assertEqual(written, 0)
        self.assertTrue(any("the cache moved after the presence audit" in d for d in drift),
                        f"drift was reported as {drift}")
        self.assertEqual((state.manifests / "demo-root.json").read_text(encoding="utf-8"),
                         before,
                         "a refused write must leave the committed record alone rather than "
                         "rewriting it to describe new bytes under the old identity")

    def test_a_file_count_that_disagrees_with_the_lock_is_refused(self) -> None:
        state = self.state()
        rows = v.walk_cache(state.cache)
        tampered = make_lock(".project-local/cache/vendor/demo-root", rows, files=99)
        written, _rows, _missing, drift = v.write(tampered, repo=state.repo,
                                                 manifest_dir=state.manifests)
        self.assertEqual(written, 0)
        self.assertTrue(any("presence audit counted" in d for d in drift))

    def test_a_missing_cache_is_reported_separately_from_drift(self) -> None:
        """The machine without the cache must not look like a machine with corrupt bytes."""
        state = self.state()
        shutil.rmtree(state.cache)
        written, _rows, missing, drift = v.write(state.lock, repo=state.repo,
                                                 manifest_dir=state.manifests)
        self.assertEqual((written, missing, drift), (0, ["demo-root"], []))

    # ---- each finding is fed its own lie ----

    def test_missing_manifest_is_convicted(self) -> None:
        state = self.state()
        (state.manifests / "demo-root.json").unlink()
        self.assertTrue(any(p.startswith("MANIFEST_MISSING demo-root")
                            for p in state.findings()))

    def test_empty_row_list_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["files"] = []
        state.save(document)
        self.assertTrue(any(p.startswith("MANIFEST_EMPTY") for p in state.findings()))

    def test_a_tampered_row_hash_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        target = next(r for r in document["files"] if r["path"] == "LICENSE")
        target["sha256"] = sha(b"NOT MIT\n")
        state.save(document)
        findings = state.findings()
        self.assertTrue(any("MANIFEST-DIGEST" in f for f in findings),
                        f"changing a file's hash did not move the verdict: {findings}")

    def test_a_lock_digest_that_no_longer_matches_the_rows_is_convicted(self) -> None:
        state = self.state()
        lock = json.loads(json.dumps(state.lock))
        lock["sources"][0]["contentDigest"] = sha(b"different bytes")
        findings = v.check(lock, state.manifests)[0]
        self.assertTrue(any(f.startswith("LOCK-MANIFEST-DIGEST") for f in findings))

    def test_a_stale_file_count_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["fileCount"] = document["fileCount"] + 1
        state.save(document)
        self.assertTrue(any("MANIFEST-COUNT" in f for f in state.findings()))

    def test_a_stale_byte_total_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["totalBytes"] = document["totalBytes"] + 1
        state.save(document)
        self.assertTrue(any("MANIFEST-BYTES" in f for f in state.findings()))

    def test_a_manifest_disagreeing_with_the_presence_audit_is_convicted(self) -> None:
        state = self.state()
        lock = json.loads(json.dumps(state.lock))
        lock["sources"][0]["files"] = 4
        lock["sources"][0]["contentDigest"] = state.manifest()["contentDigest"]
        document = state.manifest()
        document["lockFiles"] = 3
        state.save(document)
        findings = v.check(lock, state.manifests)[0]
        self.assertTrue(any("LOCK-MANIFEST-FILES" in f for f in findings))

    def test_a_duplicated_path_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["files"].append(dict(document["files"][0]))
        document["fileCount"] = len(document["files"])
        document["totalBytes"] = sum(r["bytes"] for r in document["files"])
        state.save(document)
        self.assertTrue(any("MANIFEST-DUPLICATE-PATH" in f for f in state.findings()))

    def test_a_truncated_hash_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["files"][0]["sha256"] = document["files"][0]["sha256"][:40]
        state.save(document)
        self.assertTrue(any("MANIFEST-ROW-SHAPE" in f for f in state.findings()))

    def test_a_negative_byte_size_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["files"][0]["bytes"] = -1
        document["totalBytes"] = sum(r["bytes"] for r in document["files"])
        state.save(document)
        self.assertTrue(any("MANIFEST-ROW-SHAPE" in f for f in state.findings()))

    def test_an_orphan_manifest_is_convicted(self) -> None:
        state = self.state()
        source = state.manifests / "demo-root.json"
        (state.manifests / "gone-root.json").write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8")
        findings = state.findings()
        self.assertTrue(any("MANIFEST-ORPHAN gone-root.json" in f for f in findings),
                        "a manifest for a root the lock does not list as cache-only would "
                        "be read as current evidence")
        # The copy is otherwise faithful, so the orphan is the only thing wrong with it.
        self.assertEqual(sum("MANIFEST-ORPHAN" in f for f in findings), 1)

    def test_a_manifest_left_behind_when_a_root_moves_class_is_convicted(self) -> None:
        """A tree absorbed in-repo stops needing a manifest, and must not keep one.

        Without this the two halves of the vendor record could drift apart: the lock would
        say IN_REPO while `vendor/manifests/` still published evidence for it.
        """
        state = self.state()
        lock = json.loads(json.dumps(state.lock))
        lock["sources"][0]["presence"] = "IN_REPO"
        findings = v.check(lock, state.manifests)[0]
        self.assertEqual([f.split(" --")[0] for f in findings],
                         ["MANIFEST-ORPHAN demo-root.json"])

    def test_a_foreign_schema_version_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["schemaVersion"] = "design-lab/vendor-manifest/v0"
        state.save(document)
        self.assertTrue(any("MANIFEST-SCHEMA" in f for f in state.findings()))

    def test_a_manifest_named_for_one_root_holding_another_id_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["id"] = "other-root"
        state.save(document)
        self.assertTrue(any("MANIFEST-ID" in f for f in state.findings()))

    def test_unreadable_json_is_convicted_rather_than_missing(self) -> None:
        state = self.state()
        (state.manifests / "demo-root.json").write_text("{not json", encoding="utf-8")
        findings = state.findings()
        self.assertTrue(any(f.startswith("MANIFEST-UNREADABLE") for f in findings))
        self.assertFalse(any(f.startswith("MANIFEST_MISSING") for f in findings),
                         "a corrupt file must not be reported as an absent one")

    # ---- scope of the gate ----

    def test_roots_that_are_not_cache_only_need_no_manifest(self) -> None:
        """IN_REPO ships its bytes and ABSENT_FROM_GIT has nothing to list.

        Without this the gate would demand a manifest for a tree that is either already in
        the repository or deleted, i.e. it would convict the wrong presence class.
        """
        state = self.state()
        rows = v.walk_cache(state.cache)
        (state.manifests / "demo-root.json").unlink()
        for presence in ("IN_REPO", "ABSENT_FROM_GIT"):
            lock = make_lock(".project-local/cache/vendor/demo-root", rows,
                             presence=presence)
            result = v.check(lock, state.manifests)
            self.assertEqual(result.problems, [], presence)
            self.assertEqual((result.pending, result.rows), ([], 0), presence)

    def test_pending_review_is_counted_and_not_failed(self) -> None:
        state = self.state()
        result = v.check(state.lock, state.manifests)
        self.assertEqual(result.problems, [])
        self.assertEqual(result.pending, ["demo-root"])
        self.assertEqual((result.rows, result.license_files_absent), (3, 0))
        # A root nobody has split declares nothing, and must not be convicted for it.
        self.assertEqual((result.origins, result.origins_unreviewed), (0, 0))

    def test_a_signed_root_leaves_the_pending_list(self) -> None:
        state = self.state()
        document = state.manifest()
        document["reviewedBy"] = "DTALEX66"
        state.save(document)
        self.assertEqual(v.check(state.lock, state.manifests).pending, [])

    def test_a_tree_without_a_licence_file_is_counted_for_the_reviewer(self) -> None:
        state = self.state()
        document = state.manifest()
        document["licenseFilesPresent"] = []
        state.save(document)
        self.assertEqual(v.check(state.lock, state.manifests).license_files_absent, 1)

    # ---- shipped state and registration ----

    def test_the_committed_manifests_pass_the_gate_on_repository_state_alone(self) -> None:
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERIFY_VENDOR_MANIFESTS=OK", r.stdout)

    def test_the_verdict_line_is_last_because_the_aggregate_reads_from_the_end(self) -> None:
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
        last = [line for line in r.stdout.splitlines() if line][-1]
        self.assertTrue(last.startswith("VERIFY_VENDOR_MANIFESTS="), last)

    def test_the_gate_covers_every_cache_only_row_in_the_shipped_lock(self) -> None:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        sources = v.sources_with_presence(lock)
        # Pinned, not derived: this number is the whole claim of "no third-party tree is
        # invisible to a reviewer", and it moves only when a root's presence really changes.
        self.assertEqual(len(sources), 37,
                         f"the lock now records {len(sources)} cache-only roots; if a root "
                         "moved class, say so here rather than editing the number blind")
        for source in sources:
            self.assertTrue((ROOT / "vendor" / "manifests" / (source["id"] + ".json")).is_file(),
                            f"{source['id']} has no committed manifest")

    def test_owner_fields_are_blank_across_the_whole_shipped_set(self) -> None:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        signed = [s["id"] for s in v.sources_with_presence(lock)
                  if json.loads((ROOT / "vendor" / "manifests" /
                                 (s["id"] + ".json")).read_text(encoding="utf-8")
                                 ).get("reviewedBy")]
        self.assertEqual(signed, [], "an agent must not have signed a rights decision")

    def test_the_gate_is_registered_in_the_aggregate(self) -> None:
        scripts = (ROOT / "design-lab" / "scripts" / "verify_design_lab.py").read_text(
            encoding="utf-8")
        self.assertIn("verify_vendor_manifests.py", scripts,
                      "a gate nobody invokes is documentation")


class VendorOriginTests(unittest.TestCase):
    """An aggregate vendor root must answer for each of its upstreams, byte by byte."""

    def setUp(self) -> None:
        self._ctx_stack: list[tempfile.TemporaryDirectory] = []

    def state(self, declared: list[dict] | None = None) -> ConsistentState:
        ctx = tempfile.TemporaryDirectory()
        self._ctx_stack.append(ctx)
        state = ConsistentState(ctx)
        state.declare(declared if declared is not None else demo_origins())
        return state

    def tearDown(self) -> None:
        for ctx in self._ctx_stack:
            ctx.cleanup()
        self._ctx_stack.clear()

    def origin(self, state: ConsistentState, key: str) -> dict:
        return next(o for o in state.manifest()["origins"] if o["id"] == key)

    def test_a_faithful_declaration_validates(self) -> None:
        state = self.state()
        self.assertEqual(state.findings(), [])
        result = state.result()
        self.assertEqual((result.origins, result.origins_unreviewed), (2, 2))

    def test_the_generator_computes_the_measured_half(self) -> None:
        """Nothing about the bytes is typed by the person naming the upstreams."""
        state = self.state()
        guide = self.origin(state, "guide-upstream")
        rows = v.walk_cache(state.cache)
        self.assertEqual(guide["measuredFiles"], 1)
        self.assertEqual(guide["measuredBytes"], 10)
        self.assertEqual(guide["contentDigest"],
                         v.digest_rows([r for r in rows if r["path"].startswith("references/")]))
        root = self.origin(state, "root-upstream")
        self.assertEqual(root["licenseFilesPresent"], ["LICENSE"])
        self.assertEqual(root["measuredFiles"], 2)

    def test_a_file_without_an_owner_is_convicted(self) -> None:
        state = self.state()
        (state.cache / "stray.md").write_text("orphan\n", encoding="utf-8", newline="\n")
        state.remeasure()
        state.declare(demo_origins())
        findings = state.findings()
        self.assertTrue(any("ORIGINS-UNASSIGNED-ROW stray.md" in f for f in findings),
                        f"an unattributed byte was accepted: {findings}")

    def test_an_origin_that_is_not_in_the_bytes_is_convicted(self) -> None:
        declared = demo_origins() + [
            {"id": "ghost", "subtree": "scripts/absent", "upstream": "acme/ghost",
             "upstreamUrl": "https://example.invalid/acme/ghost", "licenseAsRecorded": "MIT",
             "declaredScriptCount": 3, "declaredCountText": "3 scripts", "evidenceFile": "R"}]
        state = self.state(declared)
        self.assertTrue(any("ORIGINS-EMPTY-ORIGIN ghost" in f for f in state.findings()),
                        "a named upstream whose files are not in the bundle would otherwise "
                        "read as held content")

    def test_a_tampered_origin_count_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["origins"][0]["measuredFiles"] = 99
        state.save(document)
        self.assertTrue(any("ORIGINS-MEASUREDFILES" in f for f in state.findings()))

    def test_a_tampered_origin_digest_is_convicted(self) -> None:
        state = self.state()
        document = state.manifest()
        document["origins"][0]["contentDigest"] = sha(b"not the group")
        state.save(document)
        self.assertTrue(any("ORIGINS-CONTENTDIGEST" in f for f in state.findings()))

    def test_two_file_lists_claiming_the_same_row_is_convicted(self) -> None:
        doubled = [
            {"id": "a", "files": ["references/guide.md", "LICENSE"], "upstream": "acme/a",
             "upstreamUrl": "https://example.invalid/a", "licenseAsRecorded": "MIT",
             "declaredScriptCount": 2, "declaredCountText": "2", "evidenceFile": "R"},
            {"id": "b", "files": ["references/guide.md", "SKILL.md"], "upstream": "acme/b",
             "upstreamUrl": "https://example.invalid/b", "licenseAsRecorded": "MIT",
             "declaredScriptCount": 2, "declaredCountText": "2", "evidenceFile": "R"},
        ]
        state = self.state(doubled)
        findings = state.findings()
        self.assertTrue(any("ORIGINS-UNASSIGNED-ROW references/guide.md" in f and "matches 2" in f
                            for f in findings), findings)

    def test_nested_subtree_prefixes_are_convicted(self) -> None:
        nested = demo_origins() + [
            {"id": "deeper", "subtree": "references/sub", "upstream": "acme/deeper",
             "upstreamUrl": "https://example.invalid/d", "licenseAsRecorded": "MIT",
             "declaredScriptCount": 1, "declaredCountText": "1", "evidenceFile": "R"}]
        state = self.state(nested)
        self.assertTrue(any("ORIGINS-NESTED" in f for f in state.findings()),
                        "with one subtree inside another, a row has two owners and neither "
                        "count can be trusted")

    def test_a_claim_of_more_scripts_than_the_bytes_is_convicted(self) -> None:
        over = [demo_origins()[0], dict(demo_origins()[1], declaredScriptCount=77)]
        state = self.state(over)
        self.assertTrue(any("ORIGINS-DECLARED-COUNT-UNMATCHED" in f
                            for f in state.findings()),
                        "the record would claim 77 scripts where 2 files exist")

    def test_a_licence_file_extra_does_not_convict_a_script_count(self) -> None:
        """One-sided on purpose: `references` holds 1 file and the record claims 1 script."""
        state = self.state([dict(o, declaredScriptCount=1) for o in demo_origins()])
        self.assertFalse([f for f in state.findings() if "DECLARED-COUNT" in f])

    def test_an_unexplained_missing_url_is_convicted(self) -> None:
        blank = [dict(demo_origins()[0], upstreamUrl=None), demo_origins()[1]]
        state = self.state(blank)
        self.assertTrue(any("ORIGINS-URL-UNEXPLAINED guide-upstream" in f
                            for f in state.findings()),
                        "a null URL must say why, or the next reader will 'helpfully' invent one")

    def test_a_non_https_url_is_convicted(self) -> None:
        dodgy = [dict(demo_origins()[0], upstreamUrl="github.com/acme/guide"),
                 demo_origins()[1]]
        state = self.state(dodgy)
        self.assertTrue(any("ORIGINS-URL-SHAPE" in f for f in state.findings()))

    def test_a_nameless_origin_is_convicted(self) -> None:
        nameless = [dict(demo_origins()[0], upstream="  "), demo_origins()[1]]
        state = self.state(nameless)
        self.assertTrue(any("ORIGINS-NO-UPSTREAM" in f for f in state.findings()))

    def test_an_empty_origin_list_is_convicted(self) -> None:
        state = self.state([])
        self.assertTrue(any("ORIGINS-UNENUMERATED" in f for f in state.findings()),
                        "declaring an aggregate and enumerating nothing is the exact lie "
                        "this check exists for")

    def test_a_count_of_none_needs_the_trees_own_wording(self) -> None:
        vague = [dict(demo_origins()[0], declaredScriptCount=None, declaredCountText=""),
                 demo_origins()[1]]
        state = self.state(vague)
        self.assertTrue(any("ORIGINS-DECLARED-COUNT-MISSING" in f for f in state.findings()))

    def test_regeneration_keeps_the_declaration_and_updates_the_numbers(self) -> None:
        state = self.state()
        (state.cache / "references" / "second.md").write_text("more\n", encoding="utf-8",
                                                              newline="\n")
        state.remeasure()
        state.declare(demo_origins())
        guide = self.origin(state, "guide-upstream")
        self.assertEqual(guide["measuredFiles"], 2)
        self.assertEqual(guide["upstream"], "acme/guide")
        self.assertEqual(state.findings(), [])

    def test_a_vanished_subtree_is_left_convictable_not_dropped(self) -> None:
        state = self.state()
        (state.cache / "references" / "guide.md").unlink()
        state.remeasure()
        state.declare(demo_origins())
        guide = self.origin(state, "guide-upstream")
        self.assertIsNone(guide["contentDigest"],
                          "an empty origin must not carry the hash of nothing")
        self.assertTrue(any("ORIGINS-EMPTY-ORIGIN guide-upstream" in f
                            for f in state.findings()))

    def test_a_human_origin_review_is_removed_from_the_pending_count(self) -> None:
        state = self.state()
        document = state.manifest()
        document["origins"][0]["reviewedBy"] = "DTALEX66"
        state.save(document)
        result = state.result()
        self.assertEqual((result.origins, result.origins_unreviewed), (2, 1))
        self.assertEqual(result.problems, [], "a signed origin is not a finding")

    def test_the_shipped_tool_control_aggregate_is_attributed_completely(self) -> None:
        path = ROOT / "vendor" / "manifests" / "tool-control.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        origins = manifest["origins"]
        # Pinned with the reason: the tree's own READMEs name seven upstreams plus our two
        # provenance tables. A number here moves only when the bundle itself changes.
        self.assertEqual(len(origins), 8)
        self.assertEqual(sum(o["measuredFiles"] for o in origins), manifest["fileCount"])
        self.assertEqual(sum(o["measuredBytes"] for o in origins), manifest["totalBytes"])
        licensed = [o["id"] for o in origins if o["licenseFilesPresent"]]
        self.assertEqual(licensed, ["creold-photoshop-scripts", "creold-illustrator-scripts"],
                         "six of the eight origins have no licence file in the bundle; if that "
                         "ever reads differently, check the tree before the claim")
        self.assertEqual([o["id"] for o in origins if o["reviewedBy"]], [],
                         "an agent must not have signed a per-origin rights decision")
        self.assertIn("未核实", json.dumps(origins, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
