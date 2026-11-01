"""Gate: every licence value in the source ledger must trace to a fetched-evidence entry.

`scripts/ci/verify_source_ledger.py` checks the ledger's shape; it cannot know whether
"Apache-2.0" was read from somewhere or typed from memory. This gate closes that gap for the rows
touched by the 2026-10-07 readback: each external row's value must match an entry in
`docs/audits/LICENCE_READBACK_2026-10-07.json` that names the URL fetched and quotes the document,
and a row left UNKNOWN must say why. CI cannot re-fetch these URLs, so the durable property is the
agreement between the two tracked records — plus the negative controls below, which prove the
agreement check is not a formality.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / ".project/governance" / "source-ledger.json"
AUDIT = ROOT / "docs" / "audits" / "LICENCE_READBACK_2026-10-07.json"
SELF_HOSTS = ("github.com/DTALEX66/WORK-LAB",)
METHODS = {"gh-api-detection", "license-file", "docs-page"}
HEX64 = re.compile(r"[0-9a-f]{64}")


def violations(rows: list[dict], audit: dict) -> list[str]:
    by_id = {r["id"]: r for r in rows}
    entries = {e["id"]: e for e in audit["rows"]}
    out = []
    for rid, row in by_id.items():
        if any(h in (row.get("canonicalUrl") or "") for h in SELF_HOSTS):
            if rid not in audit["unlicensedSelfRows"]["ids"]:
                out.append(f"{rid}: self-owned row missing from unlicensedSelfRows")
            continue
        spdx = str(row.get("spdx", "")).upper()
        entry = entries.get(rid)
        if spdx == "UNKNOWN":
            if entry is None:
                out.append(f"{rid}: UNKNOWN with no readback entry explaining it")
            elif entry.get("valueWritten") is not None:
                out.append(f"{rid}: ledger says UNKNOWN but the audit wrote {entry['valueWritten']}")
            elif not (entry.get("caveat") or "").strip():
                out.append(f"{rid}: UNKNOWN kept without a stated reason")
            continue
        if entry is None:
            out.append(f"{rid}: claims {spdx} with no evidence entry")
            continue
        if entry.get("valueWritten") != row.get("spdx"):
            out.append(f"{rid}: ledger {row.get('spdx')} != audit valueWritten "
                       f"{entry.get('valueWritten')!r}")
        if entry.get("method") not in METHODS:
            out.append(f"{rid}: evidence method {entry.get('method')!r} is not one of "
                       f"{sorted(METHODS)}")
        if not (entry.get("quote") or "").strip():
            out.append(f"{rid}: evidence entry carries no verbatim quote")
        if not (entry.get("url") or "").startswith(("https://", "http://")):
            out.append(f"{rid}: evidence entry has no fetched URL")
        if row.get("licenseFileHash") and entry["method"] == "gh-api-detection":
            out.append(f"{rid}: detection-only evidence cannot back a licenseFileHash")
        # A licence value must be bound to the bytes it was read from, and both tracked records must
        # name the same digest — otherwise "I read the file" is itself an unevidenced claim.
        if not row.get("licenseFileHash"):
            out.append(f"{rid}: claims {spdx} but names no licence-file hash")
        elif not HEX64.fullmatch(str(row["licenseFileHash"])):
            out.append(f"{rid}: licenseFileHash is not 64 lowercase hex characters")
        if entry.get("method") == "license-file":
            if str(entry.get("licenseFileSha256") or "") != str(row.get("licenseFileHash") or ""):
                out.append(f"{rid}: audit licenseFileSha256 {entry.get('licenseFileSha256')!r} != "
                           f"ledger licenseFileHash {row.get('licenseFileHash')!r}")
            if not (entry.get("licenseFileName") or ""):
                out.append(f"{rid}: file-based evidence names no file")
            if not isinstance(entry.get("licenseFileBytes"), int) or entry["licenseFileBytes"] <= 0:
                out.append(f"{rid}: file-based evidence states no positive byte count")
    for rid in entries:
        if rid not in by_id:
            out.append(f"audit entry {rid!r} matches no ledger row")
    counts = audit["counts"]
    written = sum(1 for e in audit["rows"] if e.get("valueWritten"))
    if counts["valuesWritten"] != written:
        out.append(f"counts.valuesWritten={counts['valuesWritten']} but {written} entries wrote a value")
    return out


class SourceLedgerLicenceEvidenceGate(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = json.loads(LEDGER.read_text(encoding="utf-8"))["entries"]
        self.audit = json.loads(AUDIT.read_text(encoding="utf-8"))

    def test_the_shipped_records_agree(self) -> None:
        self.assertEqual(violations(self.rows, self.audit), [])

    def test_the_readback_really_moved_the_ledger(self) -> None:
        external = [r for r in self.rows
                    if not any(h in (r.get("canonicalUrl") or "") for h in SELF_HOSTS)]
        named = [r["id"] for r in external if str(r["spdx"]).upper() != "UNKNOWN"]
        self.assertEqual(len(named), self.audit["counts"]["valuesWritten"],
                         "the ledger does not carry as many named licences as the readback wrote")
        self.assertIn("mcp-inspector", [r["id"] for r in external
                                        if str(r["spdx"]).upper() == "UNKNOWN"],
                      "the relicensing row must still be UNKNOWN")

    def test_every_named_licence_row_mentions_its_readback_in_the_note(self) -> None:
        for row in self.rows:
            if str(row["spdx"]).upper() == "UNKNOWN":
                continue
            self.assertIn("readback", row["integrationNote"],
                          f"{row['id']} has a licence value but no readback sentence in its note")

    # ---------------- negative controls
    def _audit_with(self, entry):
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        audit["rows"] = [e for e in audit["rows"] if e["id"] != "trivy"]
        if entry is not None:
            audit["rows"].append(entry)
        audit["counts"]["valuesWritten"] = sum(1 for e in audit["rows"] if e.get("valueWritten"))
        return audit

    def test_a_value_with_no_evidence_entry_is_refused(self) -> None:
        rows = [dict(r) for r in self.rows if r["id"] != "trivy"]
        rows.append({"id": "trivy", "canonicalUrl": "https://aquasecurity.github.io/trivy/",
                     "spdx": "Apache-2.0", "license": "Apache-2.0", "integrationNote": "x"})
        self.assertIn("trivy: claims APACHE-2.0 with no evidence entry",
                      violations(rows, self._audit_with(None)))

    def test_a_value_disagreeing_with_its_evidence_is_refused(self) -> None:
        rows = [dict(r, **({"spdx": "MIT"} if r["id"] == "trivy" else {})) for r in self.rows]
        bad = next(e for e in self.audit["rows"] if e["id"] == "trivy") | {"valueWritten": "GPL-3.0"}
        found = violations(rows, self._audit_with(bad))
        self.assertTrue(any("trivy" in v and "!=" in v for v in found), found)

    def test_an_evidence_entry_without_a_quote_is_refused(self) -> None:
        rows = [dict(r) for r in self.rows]
        bad = next(e for e in self.audit["rows"] if e["id"] == "trivy") | {"quote": ""}
        self.assertIn("trivy: evidence entry carries no verbatim quote",
                      violations(rows, self._audit_with(bad)))

    def test_an_unknown_kept_without_a_reason_is_refused(self) -> None:
        rows = [dict(r, **({"spdx": "UNKNOWN"} if r["id"] == "trivy" else {})) for r in self.rows]
        audit = self._audit_with(next(e for e in self.audit["rows"] if e["id"] == "trivy")
                                 | {"valueWritten": None, "caveat": ""})
        self.assertIn("trivy: UNKNOWN kept without a stated reason", violations(rows, audit))

    def test_an_audit_entry_for_a_row_that_does_not_exist_is_refused(self) -> None:
        audit = self._audit_with(next(e for e in self.audit["rows"] if e["id"] == "trivy")
                                 | {"id": "ghost-tool"})
        self.assertIn("audit entry 'ghost-tool' matches no ledger row",
                      violations(self.rows, audit))

    def test_a_detection_only_backing_cannot_claim_a_file_hash(self) -> None:
        rows = [dict(r, **({"licenseFileHash": "a" * 64} if r["id"] == "opa" else {}))
                for r in self.rows]
        self.assertTrue(any("opa" in v and "licenseFileHash" in v
                            for v in violations(rows, self.audit)))

    def test_a_hash_that_disagrees_with_the_audit_is_refused(self) -> None:
        rows = [dict(r, **({"licenseFileHash": "f" * 64} if r["id"] == "opa" else {}))
                for r in self.rows]
        found = violations(rows, self.audit)
        self.assertTrue(any("opa" in v and "licenseFileSha256" in v for v in found), found)

    def test_a_licence_value_without_a_file_hash_is_refused(self) -> None:
        rows = [dict(r, **({"licenseFileHash": None} if r["id"] == "cosign" else {}))
                for r in self.rows]
        self.assertIn("cosign: claims APACHE-2.0 but names no licence-file hash",
                      violations(rows, self.audit))

    def test_a_file_hash_that_is_not_a_digest_is_refused(self) -> None:
        rows = [dict(r, **({"licenseFileHash": "c71d23"} if r["id"] == "trivy" else {}))
                for r in self.rows]
        self.assertIn("trivy: licenseFileHash is not 64 lowercase hex characters",
                      violations(rows, self.audit))

    def test_file_evidence_without_a_name_or_byte_count_is_refused(self) -> None:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        e = next(x for x in audit["rows"] if x["id"] == "trivy")
        e.pop("licenseFileName")
        e["licenseFileBytes"] = 0
        self.assertTrue(any("trivy" in v and "no positive byte count" in v
                            for v in violations(self.rows, audit)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
