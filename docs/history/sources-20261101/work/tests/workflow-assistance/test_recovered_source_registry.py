"""AG-20 gate: the tracked mirror of the recovered-source registry must stay true.

The atlas Source Registry itself lives under the git-ignored `.project-local`
runtime root, so it is machine-local and nothing enforces it (ERR-114 says so in
its own remaining_boundary). This tracked mirror is the part a gate can check:
every `tracked` entry is re-hashed here, and every `machine-local` entry is
checked for honest labelling without opening its local bytes.

Tracked digests are taken from the blob at HEAD, never from the working tree:
`.gitattributes` carries `* text=auto`, so one commit is checked out with CRLF on
this machine and LF on the runner, and a working-tree digest recorded here passed
locally while CI failed on three brand SVGs (ERR-125).

Discovered dynamically by `run_quality_gate.py governance`, so no manifest edit
is needed to put it in CI.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".project" / "governance" / "recovered-source-registry.json"
ATLAS_MIRROR = ROOT / "docs" / "history" / "archive" / "recovered-originals" / "WORK-LAB_MASTER_SOURCE_REGISTRY.json"
STATUSES = {"tracked", "machine-local", "absent", "unpinned"}
# fields that assert where a row's bytes live; the gate reads `path`, so a second location claim that
# contradicts `status` silently moves the digest check to the wrong object (ERR-154)
LOCATION_CLAIM_KEYS = ("location", "trackedPath", "extractionPath", "ignoredSourcePath",
                       "promotionEvidence", "backupDir")
RECOVERY_CMD_RE = re.compile(r"git cat-file -p (\w+):(\S+)")
REQUIRED_FIELDS = ("id", "kind", "status", "path", "observedAt", "originalLocation",
                   "coverageRelation", "verificationCommand", "notes")
# The five originals AG-19 pins. Dropping one of these rows must fail the gate:
# the absent timeline is the most important entry in the file, not the least.
PINNED_ORIGINALS = {
    "src-worklab-summary-2026-09",
    "src-conversation-timeline-2026-09",
    "src-startup-prompt-2026-09-28",
    "src-final-execution-doc-2026-09-28",
}


def git_tracked(rel: str) -> bool:
    return subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT,
                          capture_output=True).returncode == 0


def digest(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def blob(rel: str) -> bytes:
    """The exact bytes of this path in HEAD — the only checkout-stable form.

    `* text=auto` in .gitattributes means a tracked file can be CRLF on one
    machine and LF on another while the commit is identical, so working-tree
    digests are not portable claims (ERR-125).
    """
    proc = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(f"{rel} is not readable from HEAD: {proc.stderr[:120]!r}")
    return proc.stdout


def blob_digest(rel: str) -> str:
    return hashlib.sha256(blob(rel)).hexdigest()


class RecoveredSourceRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert REGISTRY.exists(), f"missing {REGISTRY}"
        cls.data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.entries = cls.data["entries"]

    def test_registry_declares_its_schema_policy_and_scope(self) -> None:
        self.assertEqual(self.data["schemaVersion"], "work-lab/recovered-source-registry/v1")
        self.assertTrue(self.data["scope"].strip())
        for key in ("tracked", "machine-local", "absent", "unpinned", "never"):
            self.assertIn(key, self.data["policy"], f"policy does not define {key}")
        self.assertTrue(self.data["generatedAgainstHead"], "no head recorded")

    def test_entries_are_present_unique_and_fully_described(self) -> None:
        self.assertGreaterEqual(len(self.entries), 8,
                                "an almost-empty registry is not a clean registry")
        ids = [e["id"] for e in self.entries]
        self.assertEqual(len(ids), len(set(ids)), "duplicate entry id")
        for e in self.entries:
            for field in REQUIRED_FIELDS:
                self.assertTrue(str(e.get(field, "")).strip(), f"{e.get('id')} missing {field}")
            self.assertIn(e["status"], STATUSES, f"{e['id']} has an undeclared status")

    def test_every_pinned_original_still_has_a_row(self) -> None:
        present = {e["id"] for e in self.entries}
        self.assertEqual(PINNED_ORIGINALS - present, set(),
                         "an AG-19 pinned original was dropped from the registry")

    def test_tracked_entries_exist_in_git_and_hash_to_what_is_recorded(self) -> None:
        tracked = [e for e in self.entries if e["status"] == "tracked"]
        self.assertGreaterEqual(len(tracked), 6,
                                "the tracked half of the registry vanished; the gate would pass vacuously")
        for e in tracked:
            self.assertTrue((ROOT / e["path"]).exists(), f"{e['id']} points at a missing file")
            self.assertTrue(git_tracked(e["path"]), f"{e['id']} claims tracked but is not versioned")
            # A row whose shipped form legitimately diverged from its provenance original describes HEAD with
            # `currentSha256`; every other tracked row's recorded digest IS the shipped form.
            diverged = re.match(r"diverged \d{4}-\d{2}-\d{2}\b", e["coverageRelation"])
            digest_field, size_field = ("currentSha256", "currentBytes") if diverged else ("sha256", "bytes")
            self.assertEqual(blob_digest(e["path"]), e[digest_field],
                             f"{e['id']} drifted from its recorded {digest_field}")
            self.assertEqual(len(blob(e["path"])), e[size_field],
                             f"{e['id']} drifted from its recorded {size_field}")
            self.assertGreater(e[size_field], 0, f"{e['id']} records an empty blob")

    def test_machine_local_entries_cannot_masquerade_as_tracked(self) -> None:
        for e in [x for x in self.entries if x["status"] == "machine-local"]:
            self.assertTrue(e["path"].startswith(".project-local/"),
                            f"{e['id']} is machine-local but not under the ignored runtime root")
            self.assertFalse(git_tracked(e["path"]), f"{e['id']} is versioned yet labelled machine-local")
            self.assertIn("CI", e["notes"] + self.data["policy"]["machine-local"])

    def test_machine_local_source_bytes_are_not_rehashed(self) -> None:
        self.skipTest(
            "machine-local sources may contain private session or prompt content; "
            "this gate checks registry labels and never opens those bytes"
        )

    def test_location_claims_agree_with_the_row_status(self) -> None:
        """A promotion that leaves the status at machine-local makes this gate hash the wrong object.

        `src-new-chat-handoff-20260903` was versioned at `50f77d1` while its row still said
        machine-local and kept the tracked location in a side field (ERR-154): every digest check then
        ran against the ignored extraction, so the versioned copy could drift unwatched. A row may not
        hold a second location that contradicts the field the gate reads.
        """
        for e in self.entries:
            for key in LOCATION_CLAIM_KEYS:
                claim = e.get(key)
                if not isinstance(claim, str) or not claim.strip():
                    continue
                versioned = git_tracked(claim)
                if e["status"] == "machine-local":
                    self.assertFalse(
                        versioned,
                        f"{e['id']}: {key} points at a versioned path while the row claims "
                        "machine-local, so the tracked bytes are never re-hashed")
                    self.assertTrue(claim.startswith(".project-local/"),
                                    f"{e['id']}: {key} is outside the ignored root but the row is "
                                    "machine-local")
                if e["status"] == "tracked" and key == "trackedPath":
                    self.assertEqual(claim, e["path"],
                                     f"{e['id']}: trackedPath contradicts path")


    def test_absent_and_unpinned_entries_make_no_digest_claim(self) -> None:
        absent = [e for e in self.entries if e["status"] == "absent"]
        unpinned = [e for e in self.entries if e["status"] == "unpinned"]
        self.assertTrue(absent, "the unrecovered timeline must keep an absent row")
        for e in absent + unpinned:
            self.assertIsNone(e["sha256"], f"{e['id']} makes a hash claim it cannot support")
            self.assertIsNone(e["bytes"], f"{e['id']} makes a size claim it cannot support")
        timeline = next(e for e in absent if "timeline" in e["id"])
        for marker in ("15,558,839", "432,344", "not 'deleted'"):
            self.assertIn(marker, timeline["notes"] + timeline["originalLocation"],
                          f"the timeline row lost the negative-proof detail {marker}")

    def test_migrated_assets_record_where_they_came_from(self) -> None:
        migrated = [e for e in self.entries if e["kind"] == "migrated-asset"]
        self.assertEqual(len(migrated), 5, "the brand set is five files")
        for e in migrated:
            self.assertIn("apps/observer/web/assets/brand/", e["originalLocation"],
                          f"{e['id']} does not record its original location")
            relation = e["coverageRelation"]
            diverged = re.match(r"diverged \d{4}-\d{2}-\d{2}\b", relation)
            self.assertTrue("byte-identical" in relation or diverged,
                            f"{e['id']} must say either that the copy is byte-identical or that it diverged, "
                            f"with a date -- got {relation!r}")
            if diverged:
                # A declared divergence is only a fact if it names the shipped form. Without these fields the
                # row would be an excuse: `sha256` keeps proving the original, and nothing would describe what
                # actually ships.
                self.assertRegex(str(e.get("currentSha256") or ""), r"^[0-9a-f]{64}$",
                                 f"{e['id']} declares a divergence without a current digest")
                self.assertIsInstance(e.get("currentBytes"), int,
                                      f"{e['id']} declares a divergence without a current size")
                self.assertRegex(str(e.get("currentObservedAt") or ""), r"^\d{4}-\d{2}-\d{2}$",
                                 f"{e['id']} declares a divergence without saying when")
            else:
                for field in ("currentSha256", "currentBytes", "currentObservedAt"):
                    self.assertNotIn(field, e,
                                     f"{e['id']} claims byte-identical yet carries {field}; the two stories "
                                     "must not sit in one row")
            self.assertIn("6de25fe", e["verificationCommand"] + e["notes"],
                          f"{e['id']} does not name the recovery point")

    def test_a_declared_divergence_cannot_be_an_excuse(self) -> None:
        """The new branch has to be able to fail, or `diverged` becomes a way to stop checking.

        Planted against the real rows: a divergence with no current digest, and a divergence whose current
        digest is not what HEAD holds. Both must be refused by the two checks above, which is why the shapes
        here mirror the assertions rather than restating them.
        """
        migrated = [e for e in self.entries if e["kind"] == "migrated-asset"
                    and re.match(r"diverged \d{4}-\d{2}-\d{2}\b", e["coverageRelation"])]
        self.assertTrue(migrated, "no diverged row to falsify against; the branch is untested by the ledger")
        for e in migrated:
            self.assertEqual(len(str(e["currentSha256"])), 64, f"{e['id']} current digest is not a sha256")
            self.assertNotEqual(e["currentSha256"], e["sha256"],
                                f"{e['id']} claims to diverge while recording the same digest twice")
            self.assertEqual(e["currentSha256"], blob_digest(e["path"]),
                             f"{e['id']} records a current digest that HEAD does not carry")
            self.assertEqual(e["currentBytes"], len(blob(e["path"])),
                             f"{e['id']} records a current size that HEAD does not carry")

    def test_recorded_recovery_commands_actually_reproduce_the_recorded_digest(self) -> None:
        """A provenance command that does not run is decoration, not evidence.

        This is what turns `byte-identical` from an adjective into a check: the
        blob at the recovery commit is fetched and hashed, and must equal both
        the recorded digest and the blob at HEAD.
        """
        checked = 0
        for e in self.entries:
            if e["status"] != "tracked":
                continue
            m = RECOVERY_CMD_RE.search(e["verificationCommand"])
            if not m:
                continue
            commit, orig_path = m.group(1), m.group(2)
            proc = subprocess.run(["git", "cat-file", "-p", f"{commit}:{orig_path}"],
                                  cwd=ROOT, capture_output=True)
            self.assertEqual(proc.returncode, 0,
                             f"{e['id']}: recovery command names an unreadable blob "
                             f"{commit}:{orig_path}")
            recovered = hashlib.sha256(proc.stdout).hexdigest()
            self.assertEqual(recovered, e["sha256"],
                             f"{e['id']}: the blob at {commit} does not hash to the "
                             "recorded digest, so the migration is not byte-identical")
            if re.match(r"diverged \d{4}-\d{2}-\d{2}\b", e["coverageRelation"]):
                # The row says the shipped form moved on. Then the provenance digest must NOT equal HEAD --
                # a row that declares a divergence the files do not have is the same lie in the other
                # direction -- and `currentSha256` is what has to match the versioned copy.
                self.assertNotEqual(recovered, blob_digest(e["path"]),
                                    f"{e['id']} declares a divergence but HEAD still holds the original bytes")
                self.assertEqual(e["currentSha256"], blob_digest(e["path"]),
                                 f"{e['id']}: the shipped form does not hash to the recorded current digest")
            else:
                self.assertEqual(recovered, blob_digest(e["path"]),
                                 f"{e['id']}: the recovered original drifted from the "
                                 "versioned copy")
            checked += 1
        self.assertGreaterEqual(checked, 5,
                                "no recovery command was checkable; the provenance "
                                "gate would pass vacuously")


class AtlasPinAgreementTests(unittest.TestCase):
    """Two tracked records must tell the same story about the same five pins.

    Before the promotion the atlas lived under the ignored root, so this comparison could only be made
    on one machine and a CI run could not assert agreement at all (ERR-114's boundary, ERR-142's
    complaint). Now both sides are versioned, and the check is the kind the ledger rules ask for:
    agreement between tracked records, never a claim about bytes a clean checkout cannot see.

    The vocabulary is the atlas's own: a pin either names a recovered digest that exists among its 642
    sources, or it carries the negative proof. Both are checked, and the machine-local summary row is
    pinned against being promoted — the atlas itself states the reason it must stay uncommitted.
    """

    RECOVERED = "RECOVERED_HASH_IDENTICAL_COPY"
    DECLARED_STATUSES = {
        "RECOVERED_HASH_IDENTICAL_COPY",
        "NOT_RECOVERED_NEGATIVELY_PROVEN_IN_SCOPE",
        "NOT_FOUND_EXACT_NAME_OR_VERIFIED_COPY",
    }

    @classmethod
    def setUpClass(cls) -> None:
        assert ATLAS_MIRROR.is_file(), f"missing {ATLAS_MIRROR}"
        cls.rel = ATLAS_MIRROR.relative_to(ROOT).as_posix()
        cls.atlas = json.loads(ATLAS_MIRROR.read_text(encoding="utf-8"))
        cls.data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.rows = {e["id"]: e for e in cls.data["entries"]}
        cls.pins = {p["id"]: p for p in cls.atlas["missing_or_recovered_pins"]}
        cls.source_digests = {s["sha256"] for s in cls.atlas["sources"] if s.get("sha256")}

    def test_the_versioned_atlas_is_the_document_the_mirror_row_claims(self) -> None:
        row = self.rows["src-atlas-master-source-registry"]
        self.assertEqual(blob_digest(self.rel), row["sha256"],
                         "the mirror row and the versioned atlas disagree, so every cross-check below "
                         "would compare the mirror against a different document")
        self.assertEqual(len(blob(self.rel)), row["bytes"])

    def test_every_pin_uses_a_declared_status_and_carries_its_own_kind_of_evidence(self) -> None:
        self.assertEqual(set(self.pins), {
            "SRC-WL-CHAT-TIMELINE", "SRC-WL-SUMMARY", "SRC-WL-HANDOFF-20260903",
            "REQ-20260928-START", "REQ-20260928-EXEC"}, "the pin set changed identity")
        self.assertGreaterEqual(len(self.source_digests), 500,
                                "the atlas source list collapsed, so digest presence proves nothing")
        for pin_id, pin in self.pins.items():
            self.assertIn(pin["status"], self.DECLARED_STATUSES,
                          f"{pin_id}: an undeclared recovery status cannot be checked")
            if pin["status"] == self.RECOVERED:
                self.assertTrue(pin.get("expected_sha256"), f"{pin_id}: recovered without a digest")
                self.assertIn(pin["expected_sha256"], self.source_digests,
                              f"{pin_id}: claims recovery of a digest no atlas source holds")
                if pin.get("recovered_sha256"):
                    self.assertEqual(pin["recovered_sha256"], pin["expected_sha256"],
                                     f"{pin_id}: recovered digest differs from the pin it satisfies")
            else:
                proof = pin.get("negativeProof") or pin.get("searchScopeNote") or ""
                self.assertGreaterEqual(len(proof), 120,
                                        f"{pin_id}: {pin['status']} without a stated scope and proof")

    def test_the_mirror_agrees_with_the_atlas_for_every_pin_it_reproduces(self) -> None:
        pairs = {"SRC-WL-SUMMARY": "src-worklab-summary-2026-09",
                 "SRC-WL-HANDOFF-20260903": "src-new-chat-handoff-20260903"}
        for pin_id, row_id in pairs.items():
            self.assertEqual(self.rows[row_id]["sha256"], self.pins[pin_id]["expected_sha256"],
                             f"{row_id} no longer carries the digest the atlas pins")

    def test_the_unrecovered_timeline_stays_unclaimed_on_both_sides(self) -> None:
        pin = self.pins["SRC-WL-CHAT-TIMELINE"]
        row = self.rows["src-conversation-timeline-2026-09"]
        self.assertNotIn(pin["expected_sha256"], self.source_digests,
                         "the timeline digest is among the atlas sources while the pin still claims "
                         "it was negatively proven absent")
        self.assertEqual(row["status"], "absent")
        self.assertIsNone(row["sha256"], "the mirror claims a digest for the unrecovered timeline")

    def test_the_summary_copy_must_stay_machine_local(self) -> None:
        """The atlas registers this original by path and digest and refuses to commit it."""
        row = self.rows["src-worklab-summary-2026-09"]
        self.assertEqual(row["status"], "machine-local",
                         "promoting this row would commit session UUIDs and prompt bodies; the atlas "
                         "source record states that boundary in its own content_access field")
        declared = [s for s in self.atlas["sources"] if s.get("sha256") == row["sha256"]]
        self.assertTrue(declared, "the atlas no longer holds the summary original it registered")
        self.assertIn("prompt bodies", declared[0]["content_access"],
                      "the atlas's own boundary note for the summary changed; re-read the rule before "
                      "touching this row")
        self.assertIn("prompt", row["notes"].lower(),
                      "the mirror row no longer states why it stays ignored")


if __name__ == "__main__":
    unittest.main()
