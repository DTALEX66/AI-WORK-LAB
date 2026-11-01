import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "packages/client-neutral-core/scripts" / "token_monitor.py"


def load_module():
    spec = importlib.util.spec_from_file_location("token_monitor", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TokenMonitorTests(unittest.TestCase):
    def test_parses_openai_usage_without_estimating(self):
        module = load_module()
        records = module.parse_log_line(
            json.dumps({"model": "kimi", "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}})
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].input_tokens, 12)
        self.assertEqual(records[0].output_tokens, 8)
        self.assertEqual(records[0].total_tokens, 20)
        self.assertEqual(records[0].model, "kimi")

    def test_computes_total_only_from_explicit_input_and_output(self):
        module = load_module()
        record = module.parse_log_line(json.dumps({"usage": {"input_tokens": "3", "output_tokens": 4}}))[0]
        self.assertEqual(record.total_tokens, 7)
        self.assertEqual(module.parse_log_line("ordinary prompt text"), [])

    def test_does_not_count_auth_or_arbitrary_token_fields(self):
        module = load_module()
        payload = {"api_key": "not-a-count", "token": "opaque", "message": "hello"}
        self.assertEqual(module.parse_usage_payload(payload), [])

    def test_tail_counts_append_once_and_handles_unknown_lines(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "agent.log"
            path.write_text(json.dumps({"model": "m", "usage": {"input_tokens": 5, "output_tokens": 2}}) + "\n", encoding="utf-8")
            monitor = module.UsageMonitor(path)
            self.assertEqual(monitor.poll(), 1)
            self.assertEqual(monitor.poll(), 0)
            with path.open("a", encoding="utf-8") as handle:
                handle.write("not-json\n")
            self.assertEqual(monitor.poll(), 0)
            self.assertEqual(monitor.totals.unrecognized_lines, 1)
            self.assertEqual(monitor.totals.total_tokens, 7)

    def test_self_test_contract(self):
        module = load_module()
        self.assertEqual(module.run_self_test(), 0)

    def test_tail_resets_after_truncation_and_counts_new_record(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "agent.log"
            path.write_text(json.dumps({"model": "m", "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}}) + "\n", encoding="utf-8")
            monitor = module.UsageMonitor(path)
            self.assertEqual(monitor.poll(), 1)
            path.write_text(json.dumps({"usage": {"total_tokens": 3}}) + "\n", encoding="utf-8")
            self.assertEqual(monitor.poll(), 1)
            self.assertEqual(monitor.totals.total_tokens, 10)


if __name__ == "__main__":
    unittest.main()
