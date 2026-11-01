from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str) -> object:
    return importlib.import_module(name)


class ErrorLedgerSummaryTests(unittest.TestCase):
    def test_build_summary_groups_by_classification(self) -> None:
        module = load("error_ledger_summary")
        rows = [
            {"error_id": "ERR-A", "classification": "contract_drift", "phase": "verify",
             "root_cause": "schema changed", "fix": "regenerate", "regression_test": "test_x"},
            {"error_id": "ERR-B", "classification": "contract_drift", "phase": "verify",
             "root_cause": "digest stale", "fix": "regenerate", "regression_test": ""},
            {"error_id": "ERR-C", "classification": "feature_gap", "phase": "plan",
             "root_cause": "missing api", "fix": "implement", "regression_test": ""},
        ]
        summary = module.build_summary(rows)
        self.assertIn("contract_drift（2 条）", summary)
        self.assertIn("feature_gap（1 条）", summary)
        self.assertIn("ERR-A", summary)
        self.assertIn("regenerate", summary)


class SpecToTasksTests(unittest.TestCase):
    def test_parse_spec_extracts_tasks_and_dependencies(self) -> None:
        module = load("spec_to_tasks")
        spec_text = """# 任务包

## 1. 初始化

- 验收: 环境就绪

## 2. 构建

depends_on: 1

- 验收: 构建通过

## 3. 发布

depends_on: 2, 1
"""
        parsed = module.parse_spec(spec_text)
        tasks = parsed["tasks"]
        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0]["task_id"], "task-1")
        self.assertEqual(tasks[0]["title"], "初始化")
        self.assertNotIn("depends_on", tasks[0])
        self.assertEqual(tasks[1]["depends_on"], ["task-1"])
        self.assertEqual(tasks[2]["depends_on"], ["task-2", "task-1"])


if __name__ == "__main__":
    unittest.main()
