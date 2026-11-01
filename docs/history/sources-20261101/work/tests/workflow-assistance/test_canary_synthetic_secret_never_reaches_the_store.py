"""Mandatory gate: a synthetic secret must not survive ingest into canonical state.

WUI-18's canary clause says the canary uses *synthetic* secrets -- nothing real is planted, and nothing
planted may be stored. The store has always refused a field NAMED like a credential
(``{"api_key": ...}``), so this gate aims at the shape it could not see: a provider token carried as a
VALUE under an ordinary field. Measured 2026-10-10, ``collect_usage_files`` turns a foreign ``usage.jsonl``
line into a canonical record with whatever ``provider``/``model``/``note`` strings it found, so a key hiding
in one of those fields used to be written to ``canonical.sqlite`` and then projected to the Observer.

The negative controls are the point: each planted shape has to be refused, and the two shapes a real
repository is full of -- a 64-hex error fingerprint and a 40-hex commit SHA -- have to keep passing. A guard
that refused those would have broken the worker loop, which is how it was found (an existing
``test_durable_worker`` case convicted it on the first run).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from artifact_flow_policy import SHAPE_SELF_IDENTIFYING, secret_shape_classes
from canonical_store import CanonicalStore, validate_record
from collectors import collect_usage_files
import project_temp

# Synthetic shapes only. None of these is a live credential; they exist to be caught.
PLANTED = {
    "sk-provider-key": "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4",
    "aws-style-access-key": "AKIA" + "ABCDEFGHIJKLMNOP",
    "github-server-token": "ghs_" + "0123456789abcdefghij",
    "bearer-header": "Bearer " + "abcdefghijklmnop",
    "raw-base64-blob": "Q" * 64 + "=",
}
BENIGN = {
    "error_fingerprint": "a" * 64,
    "commit_sha": "1234567890abcdef1234567890abcdef12345678",
    "stable_id": "usage-" + "0123456789abcdef0123456789abcdef",
    "note_prose": "the goal mentions a bearer token rotation, but carries no key",
}

# Synthetic markers for the prose variant of the same defect (P2, 2026-10-26): an anchored value screen
# only convicts a field that is *nothing but* a key, so these embedded shapes used to reach
# ``canonical.sqlite`` and be projected to the Observer.
MARK_GHP = "ghp_" + "A1b2C3d4E5f6G7h8I9j0"
MARK_PAT = "github_pat_" + "11A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
MARK_SK = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5"
MARK_BEARER = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdef"
# field -> (marker, prose that carries it). Never interpolate a marker into an assertion message: the
# refusal under test must not echo the value, and neither may the evidence for it.
PLANTED_IN_PROSE = {
    "note": (MARK_GHP, "rotated " + MARK_GHP + " on tuesday after the incident"),
    "provider": (MARK_PAT, "github " + MARK_PAT + " reused by the repo bot"),
    "source_ref": (MARK_SK, ".hermes/task-artifacts/usage.jsonl?line=42&fallback=" + MARK_SK),
    "goal": (MARK_BEARER, "paste " + MARK_BEARER + " into the header"),
}

# False-positive control set: ordinary repository text. Each entry was a credential-shaped blob under at
# least one plausible reading, and every one of them must keep passing -- an over-broad value screen that
# starts refusing SHAs, digests, paths, model names or prose is the regression this batch convicts.
BENIGN_PROSE = (
    "1234567890abcdef1234567890abcdef12345678",                       # git commit SHA (40 hex)
    "9f8e7d6c5b4a39281706f5e4d3c2b1a0" * 2,                            # SHA-256 content digest (64 hex)
    r"C:\Users\DEV\AppData\Local\Programs\DeepSeek Harness\DeepSeek Harness.exe",
    "the README documents the Bearer-style token refresh flow; no token is stored in this note",
    "gpt-4o-2024-08-06",
    "https://api.github.com/repos/DTALEX66/WORK-LAB/commits?sha=1234567890abcdef",
    "docs/current/authority-convergence-20261019/ROADMAP.md",
    "checkpoint written before the retry loop, see usage.jsonl line 42",
    "task-ledger-9e93e51224215f8f3d5a4ed720ce7a86",   # a real collector event_id, measured 2026-10-26
    "Bearer tokens are rotated weekly and never written to the store",
)
BENIGN_FIELDS = ("note", "provider", "source_ref")


class SyntheticSecretCanaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = project_temp.fixture_dir(prefix="canary-ingest-")

    def tearDown(self) -> None:
        project_temp.force_release(self.root)

    def record(self, field: str, value: str) -> dict:
        return {
            "project_id": "work-lab",
            "provider": "github" if field != "provider" else value,
            "model": value if field == "model" else "gpt-test",
            "observed_at": "2026-10-10T00:00:00Z",
            "quality": "EXACT_SOURCE",
            "source_ref": ".hermes/task-artifacts/usage.jsonl",
            "sample_id": "usage-abc",
            "input_tokens": 5,
            "note": value if field == "note" else "",
        }

    def test_a_planted_key_is_refused_wherever_it_is_hidden(self) -> None:
        refused: list[str] = []
        for shape, value in PLANTED.items():
            for field in ("provider", "model", "note"):
                finding = None
                try:
                    validate_record(self.record(field, value), allow_usage_tokens=True)
                except ValueError as exc:
                    finding = str(exc)
                self.assertIsNotNone(finding, f"{shape} in {field} was accepted by validate_record")
                self.assertIn("sensitive value(s) at", finding, f"{shape} in {field}")
                self.assertIn(field, finding, f"{shape} in {field} was not named by path")
                refused.append(f"{shape}/{field}")
        self.assertEqual(15, len(refused), "every planted shape must be caught in every allowed field")

    def test_a_planted_key_in_a_nested_list_is_refused_too(self) -> None:
        record = self.record("provider", "github")
        record["tags"] = ["routine", PLANTED["aws-style-access-key"]]
        with self.assertRaises(ValueError) as refused:
            validate_record(record, allow_usage_tokens=True)
        self.assertIn("tags[1]", str(refused.exception))

    def test_a_planted_key_buried_in_prose_is_refused(self) -> None:
        """A key inside a sentence or behind a provider label is still a key (P2, 2026-10-26).

        The whole-string screen accepted ``provider="github ghp_..."`` and
        ``note="rotated ghp_... on tuesday"``, so the store wrote both to ``canonical.sqlite``. Each
        persisted string field is refused on its own here, named by field, and the refusal must not
        carry the value -- an echoed match would move the credential into the log, the exception text
        and this test's own artifact.
        """
        refused: list[str] = []
        for field, (marker, prose) in PLANTED_IN_PROSE.items():
            record = self.record("provider", "github")
            record[field] = prose
            finding = None
            try:
                validate_record(record, allow_usage_tokens=True)
            except ValueError as exc:
                finding = str(exc)
            self.assertIsNotNone(finding, f"a key buried in {field} was accepted by validate_record")
            self.assertIn("sensitive value(s) at", finding, f"{field}: wrong refusal family")
            self.assertIn(field, finding, f"{field} was not named by path")
            self.assertNotIn(marker, finding, f"the refusal echoed the planted value from {field}")
            refused.append(field)
        self.assertEqual(4, len(refused), "note, provider, source_ref and goal must each refuse on their own")

    def test_the_benign_prose_batch_is_never_a_credential(self) -> None:
        """Counted false-positive control: 10 ordinary strings x 3 persisted string fields, all accepted.

        Widening the family patterns to a substring search is only correct because the ambiguous 64+
        base64 alternative stayed whole-string anchored -- unanchored it would convict these digests,
        paths and sentences. The count is asserted so a future regex that starts blocking prose fails
        here instead of in the worker loop. The last two rows are the measured 2026-10-26 collisions:
        an event_id whose "task-" hides the run "sk-", and a sentence that names the Bearer scheme
        without carrying a token.
        """
        accepted = 0
        for value in BENIGN_PROSE:
            for field in BENIGN_FIELDS:
                record = self.record("provider", "openai")
                record[field] = value
                validate_record(record, allow_usage_tokens=True)  # must not raise
                accepted += 1
        self.assertEqual(len(BENIGN_PROSE) * len(BENIGN_FIELDS), accepted,
                         "every benign string must survive validation in every screened field")
        self.assertEqual(30, accepted)

    def test_the_word_opener_excludes_letters_and_digits_only(self) -> None:
        """The ``(?<![A-Za-z0-9])`` opener is a boundary, not the whole-string anchor come back again.

        It exists for one measured collision (``task-ledger-...`` hides the run ``sk-``). Widen it to
        cover ``_``, ``=``, ``:`` or ``/`` and every glued form below stops being caught, which is how
        a key pasted into a path, a query string or an identifier reaches the store.
        """
        run = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5"
        for glued in ("", "x ", "key=", "token_", "?fallback=", "/path/", "1:"):
            classes = secret_shape_classes({"note": glued + "sk-" + run})
            self.assertEqual({"note": SHAPE_SELF_IDENTIFYING}, classes,
                             f"a key glued to {glued!r} was not caught")
        for word in ("task-ledger-" + "0" * 32, "ask-" + run, "flask-" + run):
            self.assertEqual({}, secret_shape_classes({"note": word}),
                             f"an English word that merely contains the prefix was convicted: {word[:12]}")

    def test_digests_and_prose_are_not_credentials(self) -> None:
        record = self.record("provider", "openai")
        record.update({"error_fingerprint": BENIGN["error_fingerprint"],
                       "head_sha": BENIGN["commit_sha"],
                       "event_id": BENIGN["stable_id"],
                       "note": BENIGN["note_prose"]})
        validate_record(record, allow_usage_tokens=True)  # must not raise

    def test_the_canary_never_reaches_the_canonical_store_through_the_collector(self) -> None:
        artifacts = self.root / ".hermes" / "task-artifacts"
        artifacts.mkdir(parents=True)
        poisoned = {"provider": PLANTED["sk-provider-key"], "model": "gpt-test", "input_tokens": 7}
        honest = {"provider": "openai", "model": "gpt-test", "input_tokens": 3}
        (artifacts / "usage.jsonl").write_text(
            "\n".join(json.dumps(row) for row in (poisoned, honest)) + "\n", encoding="utf-8")

        store = CanonicalStore(self.root / "canonical.sqlite")
        try:
            store.register_project("work-lab", str(self.root), display_name="canary")
            collected = collect_usage_files(store, "work-lab", artifacts)
            self.assertEqual(2, len(collected.records),
                             "the collector should see both lines; the refusal belongs at ingest")
            stored = 0
            refusals = 0
            for row in collected.records:
                try:
                    store.record_usage_sample(row)
                    stored += 1
                except ValueError:
                    refusals += 1
            self.assertEqual(1, refusals, f"the planted key was not refused: {refusals}")
            self.assertEqual(1, stored, "an honest line must not be collateral damage")
            rows = store.list_usage_samples()
            self.assertEqual(1, len(rows), "only the honest sample should be readable back")
            self.assertEqual("openai", rows[0]["provider"])
            self.assertNotIn(PLANTED["sk-provider-key"], json.dumps(rows, ensure_ascii=False),
                             "the readback still carries the planted key")
            self.assertNotIn(PLANTED["sk-provider-key"], json.dumps(store.projection(), ensure_ascii=False,
                                                                    default=str),
                             "the canonical projection still carries the planted key")
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
