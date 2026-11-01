from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / "taskpacks" / "history" / "WORK-LAB-STAGE-3-TASK-GRAPH.json"
BASELINE = ROOT / ".project/governance" / "generated" / "STAGE3_BASELINE.json"
DIGEST = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")


class Stage3BaselineTests(unittest.TestCase):
    def test_task_graph_is_complete_acyclic_and_dependency_closed(self) -> None:
        graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        tasks = graph["tasks"]
        by_id = {task["id"]: task for task in tasks}

        self.assertEqual(graph["taskpackId"], "WORK-LAB-FINAL-MASTER-CONTROL-PLANE")
        self.assertEqual(len(tasks), 28)
        self.assertEqual(len(by_id), len(tasks))
        self.assertEqual(by_id["WL3-000"]["dependsOn"], [])
        self.assertEqual(set(by_id["WL3-820"]["dependsOn"]), {"WL3-800", "WL3-810"})

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                self.fail(f"dependency cycle at {task_id}")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in by_id[task_id]["dependsOn"]:
                self.assertIn(dependency, by_id)
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in by_id:
            visit(task_id)
        self.assertEqual(visited, set(by_id))

    def test_baseline_preserves_incoming_tree_and_has_no_unknown_dirty_paths(self) -> None:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        git = baseline["git"]
        classification = baseline["dirtyClassification"]

        self.assertEqual(git["head"], git["remoteMain"])
        self.assertEqual(git["headTree"], git["realIndexTree"])
        self.assertTrue(DIGEST.fullmatch(git["incomingCandidateTree"]))
        self.assertTrue(DIGEST.fullmatch(git["incomingCandidateSourceDigest"]))
        self.assertEqual(len(classification["PREDECESSOR_OUTPUT"]), 5)
        self.assertEqual(classification["UNKNOWN"], [])
        self.assertEqual(classification["FORBIDDEN_OR_SENSITIVE"], [])
        self.assertEqual(baseline["writer"]["state"], "UNIQUE")


if __name__ == "__main__":
    unittest.main()
