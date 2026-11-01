"""W06 (2026-10-18): the stream-cost probe, and the two ways a measurement lies about itself.

The recorded failure this guards against is not a crash. It is a number that looks like
work: a per-process CPU sampler that reads a spinning child as 0.0% (measured here: the
child reported 0.8125 s of its own `process_time()` while `GetProcessTimes` showed
0.0938 s and froze) would have published every window as "free". So the assertions are:

1. the instrument check has to catch a blind sampler and switch modes rather than emit 0.0%;
2. a frame that never arrived has to be INCOMPLETE, never a pass;
3. the pacing constants are read from the source, so "paced at 7.5 s" cannot be reported as
   "slow at 7.5 s" -- and cannot silently drift from the code it describes.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "observer_stream_cost_probe.py"
SIDECAR = ROOT / "services" / "orchestration" / "sidecar.py"
SSE_HUB = ROOT / "services" / "orchestration" / "sse_hub.py"


def load_module():
    spec = importlib.util.spec_from_file_location("observer_stream_cost_probe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_probe(*args: str, timeout: float = 180.0) -> tuple[int, dict, str]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.json"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--json-out", str(out), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(ROOT),
        )
        report = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
        return completed.returncode, report, completed.stdout + completed.stderr


class PercentileTests(unittest.TestCase):
    def test_percentiles_are_nearest_rank_not_interpolated(self) -> None:
        module = load_module()
        stats = module.percentiles([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(1.0, stats["min"])
        self.assertEqual(4.0, stats["max"])
        # nearest-rank: every value is one the run actually produced
        for key in ("min", "p50", "p95", "max"):
            self.assertIn(stats[key], [1.0, 2.0, 3.0, 4.0])

    def test_no_samples_is_an_error_not_a_zero(self) -> None:
        module = load_module()
        with self.assertRaises(ValueError):
            module.percentiles([])


class PacingTests(unittest.TestCase):
    def test_the_pacing_constants_come_from_the_source(self) -> None:
        module = load_module()
        self.assertEqual(15.0, module.read_heartbeat_seconds(SSE_HUB))
        self.assertEqual(0.25, module.read_poll_seconds(SIDECAR))

    def test_a_missing_literal_is_null_not_a_guess(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "sse_hub.py"
            empty.write_text("# no constant here\n", encoding="utf-8")
            self.assertIsNone(module.read_heartbeat_seconds(empty))
            self.assertIsNone(module.read_poll_seconds(empty))


class ModeDecisionTests(unittest.TestCase):
    def test_a_blind_sampler_falls_back_to_a_shared_process(self) -> None:
        module = load_module()
        self.assertEqual("inprocess", module.decide_mode({"externalSamplerUsable": False}, "auto"))

    def test_a_trustworthy_sampler_keeps_the_process_boundary(self) -> None:
        module = load_module()
        self.assertEqual("subprocess", module.decide_mode({"externalSamplerUsable": True}, "auto"))

    def test_an_explicit_mode_is_not_overridden(self) -> None:
        module = load_module()
        self.assertEqual("subprocess", module.decide_mode({"externalSamplerUsable": False}, "subprocess"))


class EndToEndTests(unittest.TestCase):
    def test_a_measured_run_reports_cpu_and_latency(self) -> None:
        """The number the plan asks for exists and is not a placeholder."""
        code, report, output = run_probe(
            "--mode", "inprocess", "--events", "2",
            "--idle-seconds", "0.3", "--stream-idle-seconds", "0.3", "--gap-seconds", "0",
        )
        self.assertEqual(0, code, output)
        self.assertEqual("MEASURED", report.get("verdict"), output)
        self.assertEqual(2, report["events"]["observed"], output)
        self.assertEqual([], report["events"]["missing"])
        self.assertIsNotNone(report["latencySeconds"])
        self.assertGreaterEqual(report["latencySeconds"]["min"], 0.0)
        for key in ("cpuIdle", "cpuStreamIdle", "cpuUnderWrites"):
            self.assertIsNotNone(report[key]["percentOfOneCore"], f"{key} had no figure: {output}")
        # the pacing is reported next to the samples, so a tick cannot be read as a regression
        self.assertEqual(7.5, report["decomposition"]["ssePushTickSeconds"])

    def test_a_frame_that_never_arrives_is_incomplete_not_green(self) -> None:
        """The failure mode this whole repo keeps paying for: a check that did not run exiting 0."""
        code, report, output = run_probe(
            "--mode", "inprocess", "--events", "1",
            "--idle-seconds", "0.2", "--stream-idle-seconds", "0.2", "--event-timeout", "0.001",
        )
        self.assertEqual(3, code, output)
        self.assertEqual("INCOMPLETE", report.get("verdict"), output)
        self.assertEqual([0], report["events"]["missing"], output)


if __name__ == "__main__":
    unittest.main()
