"""Gate: the evidence artifact handle list is a real projection, and never a content leak.

REQ-RANGE-20261007 stopped being a backend gap the moment ``/api/v1/evidence-range`` could read an exact
byte interval; it became a UI gap that stayed open because nothing in the snapshot told a browser which
handles exist. This gate pins the missing piece end to end:
``artifact_handle_projection`` -> ``snapshot_api.build_snapshot`` -> ``snapshot_validator``.

What it refuses, in the order the refusals matter:

* a credential-shaped name placed INSIDE an evidence root still gets no row (ERR-166: the project's own
  credentials live in the repository, so "inside the boundary" was never a reading licence) — and the
  token list and the surface list are the ones ``evidence_range_reader`` uses, so the projection cannot
  become the leak by proxy while the route stays shut;
* a file is never read for its bytes, and never read for a digest either: ``digest`` appears only when
  some project record already stated it, and ``digestRecorded: false`` says positively that none does;
* an unenumerated source yields NO key rather than an empty list, because "this project owns no evidence"
  is a different claim from "nobody looked";
* a capped enumeration says so, and a scope report that contradicts its own list is refused.

Discovered dynamically by ``run_quality_gate.py governance`` and the snapshot-schema-v3 gate.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import artifact_handle_projection as projection  # noqa: E402
import evidence_range_reader  # noqa: E402
import snapshot_api  # noqa: E402
import snapshot_validator  # noqa: E402
from project_temp import fixture_dir  # noqa: E402

GENERATED_AT = "2026-10-08T00:00:00Z"
ARTIFACTS = ".project-local/artifacts"
RUNS = ".project-local/runs"
SECRET_TEXT = "password=never-in-a-snapshot-token-value"


def make_root(prefix="artifact-handles-") -> Path:
    """A fixture repository that declares its own evidence surfaces.

    The boundary declaration is written because the projection names surfaces from that declaration rather
    than from a hardcoded opinion — so a fixture without it would legitimately fall back to the reader's
    default roots and name them "declared", and the assertions below would be testing the wrong layer.
    """
    root = fixture_dir(prefix=prefix)
    declaration = root / ".project" / "governance"
    declaration.mkdir(parents=True, exist_ok=True)
    (declaration / "project-data-boundary.json").write_text(
        json.dumps({"canonicalEvidenceRoot": ARTIFACTS, "taskArtifactsRoot": ARTIFACTS,
                    "runtimeRoot": RUNS,
                    "spillGovernance": {"ledger": {"path": f"{ARTIFACTS}/spill-ledger.jsonl"}}}),
        encoding="utf-8")
    return root


def write_evidence(root: Path, relative: str, text: str) -> Path:
    path = root / ARTIFACTS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def project(root: Path, **kwargs):
    kwargs.setdefault("with_digests", False)
    return projection.project_artifact_handles(root=root, generated_at=GENERATED_AT, **kwargs)


def snapshot_with(handles, summary=None, **extra):
    return snapshot_api.build_snapshot(revision=1, projects=[], generated_at=GENERATED_AT,
                                       artifact_handles=handles, artifact_handles_summary=summary,
                                       **extra)


def summary_for(handles, **over):
    """A summary that agrees with its own list — so a refusal test Convicts the row, not the bookkeeping."""
    summary = {
        "schemaVersion": projection.SUMMARY_SCHEMA_VERSION,
        "generatedAt": GENERATED_AT,
        "surfaces": [{"name": "canonical-evidence", "root": ARTIFACTS, "maxDepth": None,
                      "completeEnumeration": True, "filesObserved": len(handles)}],
        "surfaceState": [{"root": ARTIFACTS, "exists": True, "insideRepository": True}],
        "order": "modifiedAt-desc",
        "orderingKey": projection.ORDERING_KEY,
        "orderingRule": projection.ORDERING_RULE,
        "selection": {"policy": "digest-reserve-then-newest-per-surface", "orderingKey": projection.ORDERING_KEY,
                      "tieBrokenBy": "handle-asc", "cap": len(handles) or 1,
                      "capTrimmedTail": False, "candidatesAfterQuotas": len(handles),
                      "digestReserve": {"artifactsWithRecordedDigest": 0, "seats": 0, "filled": 0},
                      "perSurface": {}},
        "enumeratedCount": len(handles),
        "projectedCount": len(handles),
        "omittedCount": 0,
        "cap": len(handles) or 1,
        "truncated": False,
        "complete": True,
        "refused": {"sensitiveNames": 0, "reparseDirectories": 0, "notRegularFiles": 0,
                    "droppedOnVerification": {}, "unreadableEntries": 0,
                    "prunedRegenerableDirectories": 0},
        "enumerationScope": "declared-evidence-surfaces-only",
        "digestIndex": {"recordsScanned": 0, "recordsUnreadable": 0, "pairsIndexed": 0,
                        "rowsWithDigest": sum(1 for row in handles if row.get("digest")),
                        "rowsWithoutDigest": sum(1 for row in handles if not row.get("digest")),
                        "computedByHashing": False},
        "contentIncluded": False,
        "cost": {"elapsedMs": 1.0, "entriesScanned": len(handles)},
    }
    summary.update(over)
    return summary


class RealArtifactRowTests(unittest.TestCase):
    """(a) a real artifact under the canonical evidence root projects size and mtime — and no content."""

    def test_a_real_artifact_projects_an_identity_row(self) -> None:
        root = make_root()
        path = write_evidence(root, "gate-report.txt", SECRET_TEXT + "\nsecond line\n")
        result = project(root)
        row = next((item for item in result["handles"] if item["handle"].endswith("gate-report.txt")), None)
        self.assertIsNotNone(row, "a real artifact under an evidence root projected no row")
        self.assertEqual(row["sizeBytes"], path.stat().st_size)
        self.assertGreater(row["sizeBytes"], 0, "a real artifact projected a zero size")
        self.assertRegex(row["modifiedAt"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(row["surface"], "canonical-evidence")
        self.assertEqual(row["surfaceRoot"], ARTIFACTS)
        self.assertEqual(row["kind"], "report")
        self.assertTrue(Path(row["handle"]).is_absolute(), "a relative handle means a different file per cwd")

    def test_no_row_and_no_snapshot_carries_file_bytes(self) -> None:
        root = make_root()
        write_evidence(root, "gate-secret-body.txt", SECRET_TEXT)
        result = project(root)
        for row in result["handles"]:
            self.assertFalse(set(row) & set(projection.CONTENT_BEARING_KEYS),
                             f"row carried a content field: {sorted(row)}")
            self.assertNotIn(SECRET_TEXT, json.dumps(row, ensure_ascii=False))
        serialised = json.dumps(snapshot_with(result["handles"], result["summary"]), ensure_ascii=False)
        self.assertNotIn(SECRET_TEXT, serialised, "artifact content reached the snapshot")
        self.assertNotIn(SECRET_TEXT, json.dumps(result["summary"], ensure_ascii=False))

    def test_every_projected_handle_is_one_the_range_route_accepts(self) -> None:
        """The claim that makes the list usable: a projected handle is not refused by read_range."""
        root = make_root()
        write_evidence(root, "accept-me.log", "line one\nline two\n")
        handles = project(root)["handles"]
        self.assertTrue(handles)
        for row in handles:
            verdict = evidence_range_reader.read_range(handle=row["handle"], root=root, offset=0, limit=8,
                                                       evidence_roots=evidence_range_reader.declared_evidence_roots(root))
            # A 0-byte artifact is legitimately OUT_OF_RANGE (an empty interval, not a failed read);
            # anything the route REFUSES means the projection promised a handle the reader cannot take.
            self.assertIn(verdict["status"],
                          {evidence_range_reader.STATUS_OK, evidence_range_reader.STATUS_OUT_OF_RANGE},
                          f"route refused a projected handle: {row['handle']} ({verdict['reason_code']})")
            if verdict["status"] == evidence_range_reader.STATUS_OK:
                self.assertEqual(verdict["identity"]["sizeBytes"], row["sizeBytes"],
                                 "the size the projection reported is not the size the route read")

    def test_rows_outside_the_declared_surfaces_are_never_enumerated(self) -> None:
        root = make_root()
        write_evidence(root, "inside-surface.txt", "listed\n")
        (root / "docs" / "current").mkdir(parents=True, exist_ok=True)
        (root / "docs" / "current" / "not-evidence.md").write_text("source, not evidence", encoding="utf-8")
        handles = project(root)["handles"]
        self.assertTrue([row for row in handles if row["handle"].endswith("inside-surface.txt")],
                        "the evidence surface was not enumerated, so this refusal proved nothing")
        self.assertFalse([row for row in handles if "not-evidence" in row["handle"]],
                         "a repository file outside an evidence surface was projected")


class CredentialRefusalTests(unittest.TestCase):
    """(b) and (c) the refusal list, tested where it is tempting: inside an evidence root."""

    def test_credential_shaped_names_get_no_row_even_under_an_evidence_root(self) -> None:
        root = make_root()
        forbidden = [
            "restored/config.yaml", "keys/server.pem", "keys/server.key", "id_rsa",
            "task/.env", "task/.env.production", "my-token.json", "secret-notes.md",
            "credential-bundle.json", "browser/Cookies", "auth_store.json", "history.log",
            "session/export.jsonl", "db/canonical.sqlite", "db/state.db", "pw/passwords.txt",
            "p12/client.pfx", "p12/client.pkcs12",
        ]
        for relative in forbidden:
            write_evidence(root, relative, SECRET_TEXT)
        handles = project(root)["handles"]
        projected = [row["handle"] for row in handles]
        for relative in forbidden:
            name = relative.replace("/", os.sep)
            self.assertFalse(any(path.endswith(name) for path in projected),
                             f"credential-shaped row projected: {relative}")
        self.assertNotIn(SECRET_TEXT, json.dumps(handles, ensure_ascii=False))

    def test_a_sensitive_directory_prunes_its_whole_subtree(self) -> None:
        """The route's own test: the pre-install backup under an evidence root stays shut.

        ERR-166's real hit was exactly this shape — a restored ``hermes/config.yaml`` filed under
        ``.project-local/artifacts`` — so a projection that listed it would leak by proxy.
        """
        root = make_root()
        write_evidence(root, "pre-reinstall-archive/hermes/config.yaml", SECRET_TEXT)
        write_evidence(root, "pre-reinstall-archive/hermes/readme.md", "harmless sibling")
        handles = project(root)["handles"]
        self.assertFalse([row for row in handles if "config.yaml" in row["handle"]])

    def test_refusal_vocabulary_is_the_routes_own_decision(self) -> None:
        """One decision, not two opinions: the projection calls the reader's predicate.

        This used to assert that both modules shared the `SENSITIVE_NAME_TOKENS` *list*. That passed while
        the projection reimplemented the matching as a substring scan over the shared tokens, so when the
        reader's rule became word-boundary aware the projection silently started projecting `client.pfx`
        and `canonical.sqlite-wal`. Sharing a vocabulary proves nothing; sharing the decision does.
        """
        self.assertIs(projection.name_is_sensitive, evidence_range_reader.name_is_sensitive)
        self.assertEqual(projection.BOUNDARY_DECLARATION, evidence_range_reader.BOUNDARY_DECLARATION)
        for name in ("client.pfx", "canonical.sqlite-wal", "access_token.json", "passwords.txt"):
            with self.subTest(name=name):
                self.assertTrue(projection.name_is_sensitive(Path(name)), name)
        # and the over-refusal this change was meant to stop stays projectable
        for name in ("02_SCOPE_SUPERSESSION_MAP.md", "design-tokens.css"):
            with self.subTest(allowed=name):
                self.assertFalse(projection.name_is_sensitive(Path(name)), name)

    def test_existing_sqlite_is_never_projected(self) -> None:
        """(c) a real store file on the runtime surface, not a fixture — with a positive control.

        Without the sibling log this test would also pass if the runtime surface were skipped entirely,
        which is the classic way a refusal test convicts nothing.
        """
        root = make_root()
        runtime = root / RUNS / "workflow"
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "canonical.sqlite").write_bytes(b"SQLite format 3\x00" + bytes(4096))
        (runtime / "canonical.sqlite-wal").write_bytes(b"wal")
        (runtime / "session-archive.sqlite").write_bytes(b"SQLite format 3\x00")
        (runtime / "gate-run.log").write_text("a real runtime log line\n", encoding="utf-8")
        handles = project(root)["handles"]
        self.assertFalse([row for row in handles if ".sqlite" in row["handle"].lower()],
                         "a session/task database was projected as an evidence handle")
        self.assertTrue([row for row in handles if row["handle"].endswith("gate-run.log")],
                        "the runtime surface was not enumerated at all, so the refusal proved nothing")


class AbsentVersusEmptyTests(unittest.TestCase):
    """(d) no source means no key — an empty list is a claim about the project, not about the machine."""

    def test_no_declared_surface_yields_absent_not_empty(self) -> None:
        root = make_root()
        result = project(root)
        self.assertIsNone(result["handles"])
        self.assertIsNone(result["summary"])
        self.assertEqual(result["absentReason"], "no-declared-evidence-surface")
        snapshot = snapshot_api.build_snapshot(revision=1, projects=[], generated_at=GENERATED_AT,
                                               artifact_handles=result["handles"],
                                               artifact_handles_summary=result["summary"])
        self.assertNotIn("artifactHandles", snapshot)
        self.assertNotIn("artifactHandlesSummary", snapshot)
        self.assertTrue(snapshot_validator.validate_snapshot(snapshot)["valid"])

    def test_surface_that_exists_and_holds_nothing_projects_an_empty_list(self) -> None:
        root = make_root()
        (root / ARTIFACTS).mkdir(parents=True, exist_ok=True)
        result = project(root)
        self.assertEqual(result["handles"], [])
        self.assertIsNone(result["absentReason"])
        self.assertEqual(result["summary"]["enumeratedCount"], 0)

    def test_the_producer_can_stay_silent(self) -> None:
        snapshot = snapshot_api.build_snapshot(revision=1, projects=[], generated_at=GENERATED_AT)
        self.assertNotIn("artifactHandles", snapshot)
        self.assertNotIn("artifactHandlesSummary", snapshot)


class DigestProvenanceTests(unittest.TestCase):
    """(f) a digest appears only when a record states one — never hashed out of the file here."""

    def test_file_without_a_recorded_digest_says_so_instead_of_inventing_one(self) -> None:
        root = make_root()
        path = write_evidence(root, "uncited-artifact.txt", "no manifest mentions this file\n")
        result = project(root)
        row = next(item for item in result["handles"] if item["handle"].endswith("uncited-artifact.txt"))
        self.assertNotIn("digest", row, "a digest was invented for an artifact no record cites")
        self.assertFalse(row["digestRecorded"])
        self.assertEqual(row["sizeBytes"], path.stat().st_size)

    def test_recorded_digest_is_carried_with_its_provenance(self) -> None:
        root = make_root()
        artifact = write_evidence(root, "model-governance/fixtures/governance.pdf", "bytes of a pdf\n")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        manifest = root / ARTIFACTS / "model-governance/MANIFEST.json"
        manifest.write_text(json.dumps({"items": [{"path": "fixtures/governance.pdf", "sha256": digest}]}),
                            encoding="utf-8")
        result = projection.project_artifact_handles(root=root, generated_at=GENERATED_AT)
        row = next(item for item in result["handles"] if item["handle"].endswith("governance.pdf"))
        self.assertEqual(row["digest"], digest)
        self.assertTrue(row["digestRecorded"])
        self.assertIn("record:", row["digestSource"])
        self.assertTrue(row["digestSource"].endswith("MANIFEST.json"))

    def test_projection_never_reads_an_artifact_it_only_lists(self) -> None:
        """Cheap by contract: the range route refuses a whole-file digest, and so must the list behind it.

        The only files this projection may open are digest-BEARING RECORDS. An artifact it merely lists must
        never be opened at all — reading it to hash it would turn a listing into a full read of the evidence
        tree, which is the behaviour ERR-166's fix specifically refused to copy.
        """
        root = make_root()
        listed = write_evidence(root, "large/big.log", "x" * (2 * 1024 * 1024))
        opened: list[str] = []
        original = Path.read_text

        def spy(self, *args, **kwargs):
            opened.append(str(self))
            return original(self, *args, **kwargs)

        Path.read_text = spy
        try:
            result = projection.project_artifact_handles(root=root, generated_at=GENERATED_AT)
        finally:
            Path.read_text = original
        self.assertFalse([path for path in opened if Path(path).samefile(listed)],
                         "a listed artifact was opened by the projection")
        for path in opened:
            name = Path(path).name.lower()
            self.assertTrue(any(mark in name for mark in projection.DIGEST_RECORD_NAME_MARKS)
                            or name == "project-data-boundary.json"
                            or name == "config-ownership.json",
                            f"the projection read a non-record file: {name}")
        row = next(item for item in result["handles"] if item["handle"].endswith("big.log"))
        self.assertEqual(row["sizeBytes"], listed.stat().st_size)
        self.assertFalse(row["digestRecorded"])

    def test_spill_ledger_is_a_digest_source_and_still_an_evidence_row(self) -> None:
        """The ledger is read for what it states, and listed because the project owns it. Both, honestly."""
        root = make_root()
        ledger = root / ARTIFACTS / "spill-ledger.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        cited = write_evidence(root, "recovered/source-index.json", "{}\n")
        digest = hashlib.sha256(cited.read_bytes()).hexdigest()
        ledger.write_text(json.dumps({"at": GENERATED_AT, "actor": "gate", "action": "moved",
                                      "outOfRoot": False, "source": str(cited),
                                      "target": str(cited), "sha256": digest}) + "\n", encoding="utf-8")
        result = projection.project_artifact_handles(root=root, generated_at=GENERATED_AT)
        row = next(item for item in result["handles"] if item["handle"].endswith("source-index.json"))
        self.assertEqual(row.get("digest"), digest, "a spill-ledger digest was not carried")
        self.assertIn("spill-ledger.jsonl", row["digestSource"])
        self.assertTrue([item for item in result["handles"]
                         if item["handle"].endswith("spill-ledger.jsonl")],
                        "the ledger itself is project evidence and should be listed")


class ValidatorRuleTests(unittest.TestCase):
    """(e) the built snapshot validates — and each new rule refuses a specific lie."""

    def good(self):
        return {"handle": f"{ROOT}{os.sep}{ARTIFACTS}{os.sep}evidence.txt",
                "surface": "canonical-evidence",
                "surfaceRoot": ARTIFACTS, "kind": "report", "sizeBytes": 12,
                "modifiedAt": GENERATED_AT, "digestRecorded": False}

    def good_with_digest(self):
        return {"handle": f"{ROOT}{os.sep}{ARTIFACTS}{os.sep}cited.pdf", "surface": "canonical-evidence",
                "surfaceRoot": ARTIFACTS, "kind": "report", "sizeBytes": 4, "modifiedAt": GENERATED_AT,
                "digestRecorded": True, "digest": hashlib.sha256(b"pdf").hexdigest(),
                "digestSource": "record:.project-local/artifacts/MANIFEST.json"}

    def reject(self, rows, fragment, summary_over=None, drop=()):
        """`drop` removes a field the producer would have stated — an absent key is not an empty one."""
        summary = summary_for(rows, **(summary_over or {}))
        for key in drop:
            summary.pop(key, None)
        verdict = snapshot_validator.validate_snapshot(snapshot_with(rows, summary))
        self.assertFalse(verdict["valid"], f"accepted {rows}")
        self.assertTrue(any(fragment in error for error in verdict["errors"]),
                        f"errors={verdict['errors']} did not name {fragment!r}")
        return verdict

    def test_a_real_projection_validates(self) -> None:
        root = make_root()
        write_evidence(root, "gate-report.txt", "real row\n")
        result = project(root)
        verdict = snapshot_validator.validate_snapshot(
            snapshot_with(result["handles"], result["summary"]))
        self.assertTrue(verdict["valid"], verdict["errors"])
        self.assertIn("artifactHandles", snapshot_with(result["handles"], result["summary"]))

    def test_handle_is_required_absolute_and_unique(self) -> None:
        self.reject([dict(self.good(), handle="")], "handle required")
        self.reject([dict(self.good(), handle=".project-local/artifacts/x.txt")], "must be an absolute path")
        self.reject([self.good(), self.good()], "duplicates")

    def test_size_must_be_a_non_negative_int(self) -> None:
        self.reject([dict(self.good(), sizeBytes=-1)], "non-negative int")
        self.reject([dict(self.good(), sizeBytes="12")], "non-negative int")
        self.reject([dict(self.good(), sizeBytes=True)], "non-negative int")

    def test_surface_and_kind_must_be_vocabulary_words(self) -> None:
        self.reject([dict(self.good(), surface="downloads")], "surface must be one of")
        self.reject([dict(self.good(), kind="credential")], "kind must be one of")

    def test_modified_at_must_be_a_timestamp(self) -> None:
        self.reject([dict(self.good(), modifiedAt="yesterday")], "modifiedAt must be RFC3339")

    def test_digest_is_absent_or_hex_and_never_padded(self) -> None:
        self.reject([dict(self.good(), digest=None)], "absent, not null")
        self.reject([dict(self.good(), digest="fff")], "must be 64 hex characters")
        self.reject([dict(self.good(), digest="zz" * 32, digestRecorded=True)],
                    "must be 64 hex characters")
        self.reject([dict(self.good_with_digest(), digestRecorded=False)],
                    "while digestRecorded is not True")
        row = dict(self.good_with_digest())
        row.pop("digestSource")
        self.reject([row], "digestSource required")
        self.reject([dict(self.good(), digestRecorded=True)], "claims a recorded digest but carries none")
        self.reject([dict(self.good(), digestRecorded="yes")], "digestRecorded must be boolean")

    def test_a_row_never_carries_content(self) -> None:
        for key in sorted(projection.CONTENT_BEARING_KEYS)[:6]:
            self.reject([dict(self.good(), **{key: "bytes of the file"})], "carries content")

    def test_the_scope_report_must_agree_with_its_list(self) -> None:
        rows = [self.good()]
        verdict = snapshot_validator.validate_snapshot(
            snapshot_api.build_snapshot(revision=1, projects=[], generated_at=GENERATED_AT,
                                        artifact_handles=rows))
        self.assertFalse(verdict["valid"])
        self.assertTrue(any("requires artifactHandlesSummary" in error for error in verdict["errors"]))
        self.reject(rows, "projectedCount", summary_over={"projectedCount": 5})
        self.reject(rows, "cap must be a positive int", summary_over={"cap": 0})
        self.reject([self.good(), self.good()], "above its declared cap", summary_over={"cap": 1})
        self.reject(rows, "contradicts", summary_over={"truncated": True})
        self.reject(rows, "contentIncluded", summary_over={"contentIncluded": True})
        self.reject(rows, "computedByHashing",
                    summary_over={"digestIndex": {"rowsWithDigest": 0, "computedByHashing": True}})
        self.reject(rows, "surfaceState", summary_over={"surfaceState": None})
        self.reject(rows, "surfaces required", summary_over={"surfaces": []})
        self.reject(rows, "truncated must be boolean", summary_over={"truncated": "maybe"})
        self.reject(rows, "enumeratedCount", summary_over={"enumeratedCount": -3})
        self.reject(rows, "digestIndex required", summary_over={"digestIndex": "61 records"})

    def test_a_truncated_list_must_name_the_ordering_key_it_used(self) -> None:
        """A cap that keeps some rows and drops others owes the reader the key that decided it."""
        rows = [self.good(), self.good_with_digest()]
        # positive control: the identical payload WITH the stated key validates, so the refusals below
        # convict the missing key and not the fixture
        truncated = {"truncated": True, "enumeratedCount": 9, "projectedCount": 2, "cap": 2,
                     "omittedCount": 7, "complete": False,
                     "orderingKey": projection.ORDERING_KEY,
                     "selection": {"policy": "digest-reserve-then-newest-per-surface",
                                   "orderingKey": projection.ORDERING_KEY, "cap": 2}}
        self.assertTrue(snapshot_validator.validate_snapshot(
            snapshot_with(rows, summary_for(rows, **truncated)))["valid"])

        self.reject(rows, "orderingKey required when truncated", summary_over=truncated,
                    drop=("orderingKey",))
        self.reject(rows, "orderingKey required when truncated", summary_over={**truncated,
                                                                              "orderingKey": ""})
        self.reject(rows, "orderingKey required when truncated", summary_over={**truncated,
                                                                              "orderingKey": None})

        # an empty key is refused even when the list was not capped — a blank rule is not a rule
        self.reject([self.good()], "orderingKey must be a non-empty string",
                    summary_over={"orderingKey": "   "})

    def test_a_real_capped_projection_still_validates_after_the_disclosure_changed(self) -> None:
        root = make_root()
        for index in range(9):
            path = write_evidence(root, f"shape/evidence-{index:02d}.txt", f"row {index}\n")
            os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))
        result = project(root, max_handles=4)
        summary = result["summary"]
        self.assertTrue(summary["truncated"])
        verdict = snapshot_validator.validate_snapshot(snapshot_with(result["handles"], summary))
        self.assertTrue(verdict["valid"], verdict["errors"])
        self.assertEqual(summary["orderingKey"], projection.ORDERING_KEY)

    def test_a_summary_without_a_list_is_refused(self) -> None:
        """Hand-built producer path: the builder never splits the two, but another writer can."""
        snapshot = {"schemaVersion": snapshot_api.SNAPSHOT_SCHEMA_VERSION, "revision": 1,
                    "generatedAt": GENERATED_AT, "projects": [],
                    "artifactHandlesSummary": summary_for([])}
        verdict = snapshot_validator.validate_snapshot(snapshot)
        self.assertFalse(verdict["valid"])
        self.assertTrue(any("without artifactHandles" in error for error in verdict["errors"]))

    def test_the_builder_keeps_the_pair_together(self) -> None:
        """Asking for handles with no scope report still emits both, and the pair validates."""
        snapshot = snapshot_api.build_snapshot(revision=1, projects=[], generated_at=GENERATED_AT,
                                               artifact_handles=[self.good()])
        self.assertIn("artifactHandles", snapshot)
        self.assertNotIn("artifactHandlesSummary", snapshot)
        self.assertFalse(snapshot_validator.validate_snapshot(snapshot)["valid"],
                         "a list with no stated scope validated as if it were complete")


class CapDisclosureTests(unittest.TestCase):
    """An oversized enumeration is capped out loud, never trimmed in silence."""

    def test_cap_is_declared_and_the_tail_survives_as_a_counted_number(self) -> None:
        root = make_root()
        for index in range(12):
            write_evidence(root, f"many/evidence-{index:02d}.txt", f"row {index}\n")
        result = project(root, max_handles=5)
        self.assertEqual(len(result["handles"]), 5)
        summary = result["summary"]
        self.assertEqual(summary["projectedCount"], 5)
        self.assertEqual(summary["cap"], 5)
        self.assertGreaterEqual(summary["enumeratedCount"], 12)
        self.assertTrue(summary["truncated"])
        self.assertFalse(summary["complete"])
        self.assertTrue(snapshot_validator.validate_snapshot(
            snapshot_with(result["handles"], summary))["valid"])

    def test_cap_zero_refuses_to_project_a_lie_of_completeness(self) -> None:
        root = make_root()
        write_evidence(root, "one.txt", "row\n")
        result = project(root, max_handles=0)
        self.assertEqual(result["handles"], [])
        self.assertTrue(result["summary"]["truncated"])

    def test_digest_seats_are_not_trimmed_away_by_recency(self) -> None:
        """The reserve is applied before the cap: a cited artifact keeps a seat it can be clicked on."""
        root = make_root()
        old = write_evidence(root, "cited/package.pdf", "cited evidence\n")
        digest = hashlib.sha256(old.read_bytes()).hexdigest()
        (root / ARTIFACTS / "cited/MANIFEST.json").write_text(
            json.dumps({"items": [{"path": "package.pdf", "sha256": digest}]}), encoding="utf-8")
        for index in range(40):
            write_evidence(root, f"fresh/item-{index:02d}.txt", f"newer {index}\n")
        result = projection.project_artifact_handles(root=root, generated_at=GENERATED_AT, max_handles=6)
        rows = {row["handle"]: row for row in result["handles"]}
        self.assertTrue(any(row.get("digest") for row in result["handles"]),
                        "the cap trimmed every digested row out of the list")
        reserve = result["summary"]["selection"]["digestReserve"]
        self.assertGreaterEqual(reserve["filled"], 1)
        self.assertLessEqual(len(result["handles"]), 6)
        self.assertTrue(all(Path(handle).is_absolute() for handle in rows))


class DeterministicSelectionTests(unittest.TestCase):
    """The cap is a policy, so which rows survive it must not depend on the order the walk reached them.

    Measured on this machine: 4.1k artifacts enumerate against ``MAX_HANDLES`` of 200, so ranking IS the
    selection. If the surviving set were whatever the directory listing produced first, the Observer's
    evidence lane would show one set now and another after any other run wrote a file, and two readers of
    one snapshot revision would be shown different evidence. Each test below attacks that from one side.

    Every fixture here stamps whole-second modification times, so the second-resolution ``modifiedAt`` a
    reader sees cannot hide an inversion of the raw mtime the ranking actually used.
    """

    def stamp(self, path: Path, epoch: int) -> Path:
        os.utime(path, (epoch, epoch))
        return path

    def names(self, rows) -> list[str]:
        return [Path(row["handle"]).name for row in rows]

    def handles_of(self, result) -> list[str]:
        return [row["handle"] for row in result["handles"]]

    # (a) same filesystem state -> the same list, in the same order, byte for byte.
    def test_two_calls_over_the_same_state_project_identical_rows_in_identical_order(self) -> None:
        root = make_root()
        for index in range(12):
            path = write_evidence(root, f"stable/evidence-{index:02d}.txt", f"row {index}\n")
            # deliberately paired timestamps: a repeatability test whose fixture has no ties cannot see a
            # tie-break leak, because distinct mtimes re-sort to one order however the rows arrive
            self.stamp(path, 1_700_000_000 + index // 2)
        first = project(root, max_handles=5)
        second = project(root, max_handles=5)
        self.assertTrue(first["handles"], "nothing was projected, so the comparison proved nothing")
        self.assertEqual(self.handles_of(first), self.handles_of(second),
                         "two calls over an unchanged tree projected the same artifacts in another order")
        self.assertEqual(json.dumps(first["handles"], sort_keys=True, ensure_ascii=False),
                         json.dumps(second["handles"], sort_keys=True, ensure_ascii=False),
                         "the rows themselves are not byte-identical across calls")

    # (b) eviction follows the ranked key: a NEW arrival pushes out the OLDEST projected row, never the newest.
    def test_a_newer_artifact_evicts_the_oldest_projected_row_not_the_newest(self) -> None:
        root = make_root()
        base = 1_700_000_000
        for index, name in enumerate(("aa.txt", "bb.txt", "cc.txt", "dd.txt", "ee.txt", "ff.txt")):
            self.stamp(write_evidence(root, f"queue/{name}", f"row {index}\n"), base + index)
        before = project(root, max_handles=5)
        self.assertEqual(self.names(before["handles"]),
                         ["ff.txt", "ee.txt", "dd.txt", "cc.txt", "bb.txt"],
                         "the cap did not keep the 5 newest, newest-first")
        self.assertFalse([row for row in before["handles"] if row["handle"].endswith("aa.txt")],
                         "the oldest row survived a cap that still had newer candidates")

        # one strictly newer file now occupies the seat the OLDEST projected row held
        self.stamp(write_evidence(root, "queue/gg.txt", "newest\n"), base + 99)
        after = project(root, max_handles=5)
        self.assertEqual(self.names(after["handles"]),
                         ["gg.txt", "ff.txt", "ee.txt", "dd.txt", "cc.txt"],
                         "the arrival evicted something other than the oldest projected row (bb.txt)")
        self.assertTrue(any(row["handle"].endswith("gg.txt") for row in after["handles"]),
                        "the newest artifact was evicted by its own arrival")
        again = project(root, max_handles=5)
        self.assertEqual(self.handles_of(after), self.handles_of(again),
                         "the same tree evicted a different row on the second call")

    # (c) ties on mtime resolve by path, so a permuted directory listing cannot move the set.
    def test_mtime_ties_resolve_by_handle_and_survive_a_permuted_listing(self) -> None:
        root = make_root()
        same_moment = 1_700_000_000
        written_last_first = ["zeta.txt", "omega.txt", "middle.txt", "alpha.txt", "delta.txt", "bravo.txt"]
        for name in written_last_first:
            self.stamp(write_evidence(root, f"tied/{name}", "row\n"), same_moment)
        cap = 3
        result = project(root, max_handles=cap)
        # equal timestamps => the tie-break alone decides, and it decides by the handle string
        self.assertEqual(self.names(result["handles"]), sorted(written_last_first)[:cap],
                         "equal-mtime rows were not ordered by handle")

        original = projection._walk_all

        def permuted_walk(walk_root, surfaces):
            rows, per_surface, totals = original(walk_root, surfaces)
            random.Random(20261008).shuffle(rows)
            return rows, per_surface, totals

        projection._walk_all = permuted_walk
        try:
            shuffled = project(root, max_handles=cap)
        finally:
            projection._walk_all = original
        self.assertEqual(self.handles_of(shuffled), self.handles_of(result),
                         "a permuted directory listing changed the projected rows, so the selection is "
                         "still a function of walk order")
        self.assertEqual(json.dumps(shuffled["handles"], sort_keys=True, ensure_ascii=False),
                         json.dumps(result["handles"], sort_keys=True, ensure_ascii=False),
                         "a permuted directory listing changed the row bytes")

    # (d) the rule is written down, and what is written down is what was applied.
    def test_the_summary_states_the_ordering_key_that_was_actually_applied(self) -> None:
        root = make_root()
        base = 1_700_000_000
        self.stamp(write_evidence(root, "stated/new-01.txt", "row\n"), base + 30)
        self.stamp(write_evidence(root, "stated/new-02.txt", "row\n"), base + 29)
        # created in an order that CONTRADICTS the sorted order, so a projection that fell back on the
        # directory listing could not pass this test by accident
        for name in ("tie-c.txt", "tie-a.txt", "tie-b.txt"):
            self.stamp(write_evidence(root, f"stated/{name}", "row\n"), base)
        runtime = root / RUNS / "stated"
        runtime.mkdir(parents=True, exist_ok=True)
        for index in range(3):
            log = runtime / f"run-{index}.log"
            log.write_text("a real runtime log line\n", encoding="utf-8")
            self.stamp(log, base + 5)

        result = project(root, max_handles=4)
        summary = result["summary"]
        self.assertTrue(summary["truncated"], "this fixture did not exercise the truncation path")
        self.assertEqual(summary["orderingKey"], projection.ORDERING_KEY,
                         "the summary states an ordering key that is not the one the module ranks by")
        self.assertEqual(summary["selection"]["orderingKey"], projection.ORDERING_KEY)
        self.assertEqual(summary["order"], projection.ORDER_LABEL)
        self.assertIn("handle", summary["orderingRule"],
                      "the stated rule omits the tie-break, so a reader cannot reproduce the selection")

        # a disclosure the reader can act on: cap, projected, enumerated, omitted, truncated, agreeing
        self.assertEqual(summary["cap"], 4)
        self.assertEqual(summary["projectedCount"], len(result["handles"]))
        self.assertEqual(summary["enumeratedCount"], summary["projectedCount"] + summary["omittedCount"])
        self.assertGreater(summary["omittedCount"], 0, "a truncated list declared no omission")
        self.assertFalse(summary["complete"], "complete lost its existing false-on-truncation meaning")

        # the emitted rows really do satisfy the key that was stated
        self.assertEqual(self.names(result["handles"]),
                         ["new-01.txt", "new-02.txt", "tie-a.txt", "tie-b.txt"])
        for left, right in zip(result["handles"], result["handles"][1:]):
            self.assertGreaterEqual(left["modifiedAt"], right["modifiedAt"],
                                    f"rows are not newest-first: {left['handle']} before {right['handle']}")
            if left["modifiedAt"] == right["modifiedAt"]:
                self.assertLess(left["handle"], right["handle"],
                                f"equal timestamps were not tie-broken by handle: {left['handle']}, "
                                f"{right['handle']}")

        verdict = snapshot_validator.validate_snapshot(snapshot_with(result["handles"], summary))
        self.assertTrue(verdict["valid"], verdict["errors"])

    def test_the_projected_order_reproduces_from_the_fields_the_rows_disclose(self) -> None:
        """The key is auditable, not just declared: re-ranking the rows by their own `modifiedAt`+`handle`
        must return the emitted list exactly. A key ranked on precision the row does not show — the raw
        sub-second mtime — fails here, because a reader cannot re-derive the selection it claims."""
        root = make_root()
        base = 1_700_000_000
        for index in range(9):
            path = write_evidence(root, f"audit/evidence-{index:02d}.txt", "row\n")
            # three artifacts per second: the disclosed stamp ties, the sub-second mtime does not
            os.utime(path, (base + index / 3, base + index / 3))
        result = project(root, max_handles=5)
        self.assertEqual(len(result["handles"]), 5, "the cap did not bind, so re-ranking proved nothing")
        disclosed = sorted(result["handles"], key=lambda row: row["handle"])
        disclosed = sorted(disclosed, key=lambda row: row["modifiedAt"], reverse=True)
        self.assertEqual([row["handle"] for row in disclosed], self.handles_of(result),
                         "the projected list is not reproducible from the ordering it states")
        self.assertEqual(json.dumps(disclosed, sort_keys=True, ensure_ascii=False),
                         json.dumps(result["handles"], sort_keys=True, ensure_ascii=False))

        verdict = snapshot_validator.validate_snapshot(
            snapshot_with(result["handles"], result["summary"]))
        self.assertTrue(verdict["valid"], verdict["errors"])

    def test_one_ranking_function_answers_for_every_bound_taken(self) -> None:
        """``_rank`` is what ORDERING_KEY names; a bound ranked elsewhere is a second, unstated policy."""
        self.assertEqual(projection._rank(10, "b"), (-10, "b"))
        self.assertEqual(projection._rank_row({"mtimeSecond": 10, "handle": "b"}), projection._rank(10, "b"))
        rows = [{"mtimeSecond": 9, "handle": "z"}, {"mtimeSecond": 9, "handle": "a"},
                {"mtimeSecond": 11, "handle": "m"}]
        self.assertEqual([row["handle"] for row in sorted(rows, key=projection._rank_row)], ["m", "a", "z"])
        # the ranked term is the disclosed whole second, never the raw float the filesystem returned
        self.assertNotIn("mtime", projection._rank_row.__code__.co_names)


class CompositionRootShapeTests(unittest.TestCase):
    """The wiring the sidecar uses: a failure is a reported absence, never a crashed read path."""

    def test_load_artifact_handles_reports_absent_with_a_reason(self) -> None:
        root = make_root()
        handles, summary, reason = projection.load_artifact_handles(root, generated_at=GENERATED_AT)
        self.assertIsNone(handles)
        self.assertIsNone(summary)
        self.assertEqual(reason, "no-declared-evidence-surface")

    def test_an_undeclared_boundary_falls_back_to_the_readers_default_roots(self) -> None:
        """No declaration is a reason to narrow, not a reason to widen — the reader's rule, inherited."""
        root = fixture_dir(prefix="artifact-handles-no-declaration-")
        (root / ARTIFACTS).mkdir(parents=True, exist_ok=True)
        (root / "elsewhere").mkdir(parents=True, exist_ok=True)
        (root / "elsewhere" / "not-declared.txt").write_text("row\n", encoding="utf-8")
        surfaces, spill = projection.enumerate_surfaces(root)
        self.assertEqual(sorted(surface.relative for surface in surfaces),
                         sorted(evidence_range_reader.DEFAULT_EVIDENCE_ROOTS[:1]))
        self.assertTrue(all(surface.name in projection.KNOWN_SURFACES for surface in surfaces))
        self.assertIsNone(spill)
        handles = projection.project_artifact_handles(root=root, generated_at=GENERATED_AT)["handles"]
        self.assertFalse([row for row in handles if "not-declared" in row["handle"]])


class SpillAndOwnershipSourceTests(unittest.TestCase):
    """The declared sources the enumeration is told to consult, against their real behaviour."""

    def test_config_ownership_is_read_as_a_record_and_never_as_an_artifact(self) -> None:
        root = make_root()
        ownership = root / "config" / "config-ownership.json"
        ownership.parent.mkdir(parents=True, exist_ok=True)
        cited = write_evidence(root, "owned/readback.json", "{}\n")
        digest = hashlib.sha256(cited.read_bytes()).hexdigest()
        ownership.write_text(json.dumps({"fields": [{"path": str(cited), "sha256": digest}]}),
                             encoding="utf-8")
        result = projection.project_artifact_handles(root=root, generated_at=GENERATED_AT)
        handles = result["handles"]
        self.assertFalse([row for row in handles if row["handle"].endswith("config-ownership.json")],
                         "a configuration file outside the evidence surfaces was projected")
        row = next(item for item in handles if item["handle"].endswith("readback.json"))
        self.assertEqual(row.get("digest"), digest,
                         "a digest stated by config-ownership.json was not carried to its artifact")



class HandleVerdictIsHostFree(unittest.TestCase):
    """`_verify` is pure string work now, so its verdict can be compared across path vocabularies.

    It used to call `path.relative_to(surface.absolute)` inside a try/except whose arm means
    "outside the declared surface". `relative_to` compares with the host's case rules, so a handle whose
    case disagreed with the surface raised ValueError and was reported as a boundary violation -- the same
    conflation of "I could not compare" with "this is outside" that CI punished twice in the control plane.
    Nothing here touches the filesystem: surfaces are constructed, not stat'd.
    """

    def verdict(self, root, surface_relative, handle):
        surfaces = [projection.Surface("runs", surface_relative, Path(root) / surface_relative, 4)]
        return projection._verify({"handle": handle, "surface": "runs"},
                              root=Path(root), surfaces=surfaces)[1]

    def test_the_same_handle_shape_gives_the_same_verdict_in_both_vocabularies(self) -> None:
        cases = [
            ("D:/proj", ".project-local/runs", "D:/proj/.project-local/runs/a.log", None),
            ("D:/proj", ".project-local/runs", r"D:\proj\.project-local\runs\a.log", None),
            ("D:/proj", ".project-local/runs", "d:/PROJ/.project-local/RUNS/a.log", None),
            ("/home/runner/proj", ".project-local/runs", "/home/runner/proj/.project-local/runs/a.log", None),
            ("/home/Runner/proj", ".project-local/runs", "/home/runner/PROJ/.project-local/runs/a.log", None),
            # a sibling whose name starts with the root name is not inside,
            ("D:/proj", ".project-local/runs", "D:/projX/.project-local/runs/a.log", "outside-declared-surface"),
            ("D:/proj", ".project-local/runs", "D:/other/.project-local/runs/a.log", "outside-declared-surface"),
            ("/home/runner/proj", ".project-local/runs", "/home/runner/projX/a.log", "outside-declared-surface"),
            # dot segments may not climb out,
            ("D:/proj", ".project-local/runs", "D:/proj/.project-local/runs/../../../Windows/x", "outside-declared-surface"),
            # an unanchored handle is refused in both vocabularies,
            ("D:/proj", ".project-local/runs", ".project-local/runs/a.log", "not-absolute"),
        ]
        for root, surface, handle, expected in cases:
            with self.subTest(root=root, handle=handle):
                self.assertEqual(expected, self.verdict(root, surface, handle))

    def test_a_credential_named_component_is_refused_whatever_the_surface(self) -> None:
        for root, surface in (("D:/proj", ".project-local/runs"),
                              ("/home/runner/proj", ".project-local/artifacts")):
            with self.subTest(root=root):
                self.assertEqual("sensitive-name",
                                 self.verdict(root, surface, f"{root}/{surface}/creds/token.bin"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
