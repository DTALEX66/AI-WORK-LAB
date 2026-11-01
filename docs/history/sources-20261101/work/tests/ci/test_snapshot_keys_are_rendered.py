"""The Observer must not leave a declared snapshot fact unrendered.

Real measurement behind this gate: with 22 keys pinned by the frontend contract, two of them
(`artifactHandles`, `artifactHandlesSummary`) had zero consumers in the interface source while the live
v3 snapshot carried 200 projected handle rows. Nothing failed, because nothing looked.

The population grew to 24 on 2026-10-23, when CL-07 wired the issue-centre sections into the project
monitoring lane and added `issues` and `issuesSummary` to that same array. The count is asserted only to
make an intentional contract change visible here; the render coverage itself is asserted separately.

The synthetic cases exist so the gate cannot be quietly disabled: a key named only in a comment, or only
in a type/contract declaration, still has to count as unrendered.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "verify_snapshot_keys_rendered", ROOT / "scripts/ci/verify_snapshot_keys_rendered.py")
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)

SRC = MODULE.SRC_REL
CONTRACT = MODULE.CONTRACT_REL


def build_tree(root: Path, keys: list[str], consumers: dict[str, list[tuple[str, str]]]) -> Path:
    src = root / SRC
    src.mkdir(parents=True, exist_ok=True)
    array = ", ".join(f"'{key}'" for key in keys)
    (root / CONTRACT).parent.mkdir(parents=True, exist_ok=True)
    (root / CONTRACT).write_text(
        f"export const PINNED_REFINEMENT_PATHS = [{array}] as const\n", encoding="utf-8")
    (src / "types.ts").write_text(
        "\n".join(f"export type T = {{ {key}: unknown }}" for key in keys) + "\n", encoding="utf-8")
    for key, files in consumers.items():
        for name, body in files:
            (src / name).parent.mkdir(parents=True, exist_ok=True)
            (src / name).write_text(body, encoding="utf-8")
    return src


class SnapshotKeyCoverageTests(unittest.TestCase):
    def test_the_shipped_interface_consumes_every_pinned_snapshot_key(self) -> None:
        result = MODULE.analyze(ROOT)
        self.assertEqual(24, len(result["keys"]),
                         "the contract pinned a different number of keys than this gate was written for; "
                         "re-read the source rather than editing the expectation")
        self.assertEqual([], result["unrendered"],
                         "declared snapshot facts that no interface code reads never reach a reader")

    def test_an_orphan_key_is_named_not_absorbed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_tree(Path(tmp), ["readKey", "orphanKey"],
                       {"readKey": [("views/A.tsx", "const v = snap?.readKey\n")]})
            result = MODULE.analyze(Path(tmp))
        self.assertEqual(["orphanKey"], result["unrendered"])

    def test_a_key_named_only_in_a_comment_is_still_unrendered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_tree(Path(tmp), ["commentedKey"],
                       {"commentedKey": [("views/B.tsx", "// we show commentedKey here\nexport const x = 1\n")]})
            result = MODULE.analyze(Path(tmp))
        self.assertEqual(["commentedKey"], result["unrendered"])

    def test_a_key_named_only_in_the_type_declaration_is_still_unrendered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_tree(Path(tmp), ["typedOnly"], {})
            result = MODULE.analyze(Path(tmp))
        self.assertEqual(["typedOnly"], result["unrendered"])

    def test_destructured_and_bracket_forms_count_as_consumption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_tree(Path(tmp), ["destKey", "bracketKey"],
                       {"destKey": [("views/C.tsx", "const { destKey } = snap\n")],
                        "bracketKey": [("views/D.tsx", "const value = snap['bracketKey']\n")]})
            result = MODULE.analyze(Path(tmp))
        self.assertEqual([], result["unrendered"])

    def test_the_pinned_list_is_read_from_the_contract_not_copied_here(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                build_tree(Path(tmp), [], {})
                MODULE.analyze(Path(tmp))


if __name__ == "__main__":
    unittest.main()
