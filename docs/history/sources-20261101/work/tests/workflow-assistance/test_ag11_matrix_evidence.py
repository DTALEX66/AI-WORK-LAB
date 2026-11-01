"""AG-11 gate: the published OCR/ASR matrix must stay a measurement, not become a badge.

`docs/audits/AG11_OCR_ASR_MATRIX_2026-10-07.json` carries nine cells produced by
`scripts/audit/ag11_ocr_asr_matrix.py` against a live vision server and the registered
faster-whisper weights. This gate re-derives every claim from the recorded numbers instead of
reading the status word, so a cell cannot quietly become decoration:

* an OCR cell's hit_rate must equal hits/probes it reports, and hits may not exceed probes;
* the ASR cell must restate the real-time factor it implies from its own seconds;
* a run with no ground truth may not carry a hit_rate or a character error rate at all;
* a skipped cell must say why, and a failed cell makes the gate red rather than invisible;
* the summary counts must equal the cells, and the declared cell set must be complete.

The checks run against a passed-in document, so the negative controls never touch the tracked
artifact.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "audits" / "AG11_OCR_ASR_MATRIX_2026-10-07.json"
TOOL = ROOT / "scripts" / "audit" / "ag11_ocr_asr_matrix.py"
DECLARED = ("ocr-mixed-zh-en-page", "ocr-scanned-degraded", "ocr-zh-prompt", "ocr-en-prompt",
            "ocr-pdf-page", "ocr-table", "ocr-page-order", "asr-fixture-zh-cer",
            "asr-vendor-wavs")
ALLOWED_STATUS = {"MEASURED", "MEASURED_NO_TRUTH", "NOT_RUN", "FAILED"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def violations(doc: dict) -> list[str]:
    found: list[str] = []
    cells = doc.get("cells") or []
    ids = [cell.get("id") for cell in cells]

    missing = [name for name in DECLARED if name not in ids]
    extra = [name for name in ids if name not in DECLARED]
    if missing:
        found.append(f"declared cells absent from the artifact: {missing}")
    if extra:
        found.append(f"cells not in the declared set: {extra}")
    if len(ids) != len(set(ids)):
        found.append("duplicate cell ids")

    for cell in cells:
        cell_id = cell.get("id")
        status = cell.get("status")
        if status not in ALLOWED_STATUS:
            found.append(f"{cell_id}: unknown status {status!r}")
        if status == "NOT_RUN" and not str(cell.get("reason") or "").strip():
            found.append(f"{cell_id}: NOT_RUN without a reason")
        if status == "FAILED":
            found.append(f"{cell_id}: FAILED cell ({str(cell.get('error'))[:80]!r})")
        if status == "MEASURED_NO_TRUTH":
            if cell.get("hit_rate") is not None or cell.get("character_error_rate") is not None:
                found.append(f"{cell_id}: a run without ground truth may not carry a score")
            if not str(cell.get("groundTruth") or "").strip():
                found.append(f"{cell_id}: no statement of what ground truth is absent")
        if status == "MEASURED" and str(cell_id).startswith("ocr-"):
            probes = cell.get("probes")
            hits = cell.get("hits")
            rate = cell.get("hit_rate")
            if not isinstance(probes, int) or probes <= 0:
                found.append(f"{cell_id}: MEASURED with no probe count")
                continue
            if not isinstance(hits, int) or hits > probes:
                found.append(f"{cell_id}: hits {hits!r} inconsistent with probes {probes!r}")
                continue
            if not isinstance(rate, (int, float)) or abs(rate - round(hits / probes, 3)) > 0.002:
                found.append(f"{cell_id}: hit_rate {rate!r} does not follow hits/probes")
            if not isinstance(cell.get("seconds"), (int, float)):
                found.append(f"{cell_id}: MEASURED without a measured duration")
        if cell_id == "asr-fixture-zh-cer" and status == "MEASURED":
            cer = cell.get("character_error_rate")
            if not isinstance(cer, (int, float)) or not 0.0 <= cer <= 1.0:
                found.append(f"{cell_id}: character_error_rate {cer!r} is not a rate")
            audio = cell.get("audio_seconds")
            took = cell.get("transcribe_seconds")
            rtf = cell.get("real_time_factor")
            if not (isinstance(audio, (int, float)) and audio > 0
                    and isinstance(took, (int, float))
                    and isinstance(rtf, (int, float))
                    and abs(rtf - round(took / audio, 2)) <= 0.02):
                found.append(f"{cell_id}: real_time_factor {rtf!r} does not follow "
                             f"transcribe_seconds {took!r} / audio_seconds {audio!r}")
            if not str(cell.get("transcript") or "").strip():
                found.append(f"{cell_id}: no transcript recorded")

    counts = doc.get("counts") or {}
    recomputed = {
        "declared": len(cells),
        "measured": sum(1 for c in cells if str(c.get("status")).startswith("MEASURED")),
        "not_run": sum(1 for c in cells if c.get("status") == "NOT_RUN"),
        "failed": sum(1 for c in cells if c.get("status") == "FAILED"),
    }
    if counts != recomputed:
        found.append(f"summary counts {counts} do not match the cells {recomputed}")

    identity = doc.get("fixtureIdentity") or {}
    for name, entry in identity.items():
        if not HEX64.match(str(entry.get("sha256") or "")):
            found.append(f"fixture {name}: sha256 is not 64 lowercase hex")
        if not isinstance(entry.get("bytes"), int) or entry["bytes"] <= 0:
            found.append(f"fixture {name}: no positive byte count")

    environment = doc.get("environment") or {}
    if TOOL.name not in str(doc.get("tool") or ""):
        found.append("the artifact does not name the tool that produced it")
    if environment.get("visionModel") not in (environment.get("servedModels") or []):
        found.append("the vision model used is not in the recorded served-model inventory")
    return found


class Ag11MatrixEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_the_producing_tool_is_tracked_and_declared(self) -> None:
        self.assertTrue(TOOL.is_file(), "the matrix tool must live in the repository")
        self.assertIn("ag11_ocr_asr_matrix.py", self.doc["tool"])

    def test_the_published_matrix_has_no_violations(self) -> None:
        self.assertEqual(violations(self.doc), [])

    def test_every_declared_cell_is_accounted_for(self) -> None:
        ids = [cell["id"] for cell in self.doc["cells"]]
        self.assertEqual(sorted(ids), sorted(DECLARED))

    def test_a_hit_rate_that_does_not_follow_its_counts_is_rejected(self) -> None:
        inflated = json.loads(json.dumps(self.doc))
        cell = next(c for c in inflated["cells"] if c["id"] == "ocr-table")
        cell["hits"] = 3
        self.assertIn("hit_rate", " ".join(violations(inflated)))

    def test_hits_greater_than_probes_is_rejected(self) -> None:
        broken = json.loads(json.dumps(self.doc))
        cell = next(c for c in broken["cells"] if c["id"] == "ocr-mixed-zh-en-page")
        cell["hits"] = cell["probes"] + 5
        self.assertIn("inconsistent with probes", " ".join(violations(broken)))

    def test_a_score_on_a_run_without_ground_truth_is_rejected(self) -> None:
        dressed = json.loads(json.dumps(self.doc))
        cell = next(c for c in dressed["cells"] if c["id"] == "asr-vendor-wavs")
        cell["hit_rate"] = 1.0
        self.assertIn("may not carry a score", " ".join(violations(dressed)))

    def test_a_missing_cell_is_rejected_rather_than_forgotten(self) -> None:
        shortened = json.loads(json.dumps(self.doc))
        shortened["cells"] = [c for c in shortened["cells"] if c["id"] != "ocr-pdf-page"]
        self.assertIn("declared cells absent", " ".join(violations(shortened)))

    def test_a_skip_must_carry_its_reason(self) -> None:
        silent = json.loads(json.dumps(self.doc))
        cell = next(c for c in silent["cells"] if c["id"] == "ocr-table")
        cell.pop("hit_rate", None)
        cell.pop("hits", None)
        cell["status"] = "NOT_RUN"
        stale = violations(silent)
        self.assertTrue(any("NOT_RUN without a reason" in row for row in stale), stale)

    def test_a_failed_cell_makes_the_gate_red(self) -> None:
        broken = json.loads(json.dumps(self.doc))
        cell = next(c for c in broken["cells"] if c["id"] == "ocr-pdf-page")
        cell["status"] = "FAILED"
        cell["error"] = "boom"
        stale = violations(broken)
        self.assertTrue(any("FAILED cell" in row for row in stale), stale)
        self.assertTrue(any("summary counts" in row for row in stale), stale)

    def test_a_real_time_factor_that_does_not_follow_its_seconds_is_rejected(self) -> None:
        broken = json.loads(json.dumps(self.doc))
        cell = next(c for c in broken["cells"] if c["id"] == "asr-fixture-zh-cer")
        cell["real_time_factor"] = 0.01
        self.assertIn("real_time_factor", " ".join(violations(broken)))


if __name__ == "__main__":
    unittest.main()
