"""One text predicate, three callers, and the table that proves they agree on a host they are not on.

`services/control/control_service.py` and `packages/client-neutral-core/scripts/evidence_range_reader.py`
both decide containment, and both were refuted by CI for consulting the host. The fix is a single module,
so the tests here are about IDENTITY (a shared vocabulary proves nothing -- a projection that imported a
token list and wrote its own scan once started serving `client.pfx`) and about verdicts on path SHAPES
this machine cannot produce natively.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "packages" / "client-neutral-core" / "scripts",
              ROOT / "services" / "control", ROOT / "services" / "orchestration",
              ROOT / "services" / "task-governance"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import control_service  # noqa: E402
import evidence_range_reader as reader  # noqa: E402
import path_text  # noqa: E402

HOST_FREE_MODULES = ["packages/client-neutral-core/scripts/path_text.py",
                     "services/control/control_service.py"]
BANNED_ATTRS = {"normcase", "normpath", "realpath", "abspath", "relpath"}


class OnePredicate(unittest.TestCase):
    def test_the_callers_hold_the_same_functions_the_module_exports(self) -> None:
        self.assertIs(path_text.normalise_path, control_service.normalise_path)
        self.assertIs(path_text.inside_root, control_service._inside_project)
        self.assertIs(path_text.relative_inside, control_service.relative_inside)
        self.assertIs(path_text.inside_root, reader.inside_root)
        self.assertIs(path_text.path_is_anchored, reader.path_is_anchored)

    def test_the_handle_projection_holds_the_same_predicate(self) -> None:
        import artifact_handle_projection as projection
        self.assertIs(path_text.inside_root, projection.inside_root)
        self.assertIs(path_text.relative_inside, projection.relative_inside)
        self.assertIs(path_text.normalise_path, projection.normalise_path)
        self.assertIs(path_text.path_is_anchored, projection.path_is_anchored)

    def test_the_reader_actually_decides_with_the_text_predicate(self) -> None:
        """A shared import is not proof of use: the refusal must name both lexical values."""
        result = reader.read_range(handle="D:/elsewhere/project/.project-local/runs/a.log",
                                   root=ROOT, offset=0, limit=10)
        self.assertEqual("REFUSED", result["status"], result)
        self.assertIn("OUT", result["reason_code"])
        self.assertIn("d:/elsewhere/project/.project-local/runs/a.log", result["reason"],
                      "the refusal did not print the normalised candidate, so a red elsewhere "
                      "would still not explain itself")


class VerdictsAcrossPathShapes(unittest.TestCase):
    CASES = [
        # (candidate, root, inside)
        ("D:/All projects/WORK-LAB/.project-local/runs/a.txt", "D:/All projects/WORK-LAB", True),
        ("d:/ALL PROJECTS/work-lab/.project-local/runs/a.txt", "D:/All projects/WORK-LAB", True),
        ("D:\\All projects\\WORK-LAB\\.project-local\\runs\\a.txt", "D:/All projects/WORK-LAB", True),
        # a sibling whose name starts with the root's name is NOT inside
        ("D:/All projects/WORK-LABX/a", "D:/All projects/WORK-LAB", False),
        # dot-segments may not climb above an anchored root
        ("D:/All projects/WORK-LAB/../../Windows/win.ini", "D:/All projects/WORK-LAB", False),
        ("/home/runner/work/WORK-LAB/.project-local/artifacts/a.json",
         "/home/runner/work/WORK-LAB", True),
        ("/etc/passwd", "/home/runner/work/WORK-LAB", False),
        # a POSIX-shaped path under a Windows root stays outside on any host: the text rule does not
        # invent a drive letter the way posixpath.join + resolve() would
        ("/home/runner/x", "D:/All projects/WORK-LAB", False),
    ]

    def test_inside_root_agrees_with_the_declared_verdict(self) -> None:
        for candidate, root, expected in self.CASES:
            with self.subTest(candidate=candidate, root=root):
                self.assertIs(expected, path_text.inside_root(candidate, root)[0])

    def test_relative_inside_keeps_the_declared_case(self) -> None:
        self.assertEqual("docs/history/archive/root-ui-records-20261019/UI_IMPLEMENTATION_REPORT.md",
                         path_text.relative_inside(
                             "D:/All projects/WORK-LAB/docs/history/archive/root-ui-records-20261019/"
                             "UI_IMPLEMENTATION_REPORT.md",
                             "D:/All projects/WORK-LAB"))
        self.assertEqual("Config.YAML",
                         path_text.relative_inside("/home/Runner/work/WORK-LAB/Config.YAML",
                                                   "/home/Runner/work/WORK-LAB"))
        self.assertIsNone(path_text.relative_inside("/home/runner/other/x", "/home/runner/work"))


class NoHostQueriesInThePredicate(unittest.TestCase):
    def test_no_os_path_attribute_access_in_the_rule_modules(self) -> None:
        for rel in HOST_FREE_MODULES:
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
            offenders = []
            for node in ast.walk(tree):
                if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
                        and isinstance(node.value.value, ast.Name)
                        and node.value.value.id == "os" and node.value.attr == "path"):
                    offenders.append((node.lineno, node.attr))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and node.func.attr in BANNED_ATTRS:
                    offenders.append((node.lineno, node.func.attr))
            self.assertEqual([], offenders, f"{rel} asks the host about paths: {offenders}")


if __name__ == "__main__":
    unittest.main()
