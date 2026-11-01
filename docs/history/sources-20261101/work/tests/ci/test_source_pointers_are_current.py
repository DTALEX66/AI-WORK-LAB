"""Line pointers into fast-moving source must be re-derived mechanically, not re-measured by hand.

Measured over two days: four separate CI failures came from `path:LINE` citations pointing at a blank line or
at unrelated code after someone edited the file above them. Every repair was manual -- read the gate's message,
guess the new number, push, fail one line off -- which is why the same failure kept coming back under a new
number. This module pins the mechanical path instead:

* `scripts/ci/repoint_source_pointers.py` re-derives each pointer from the code it quotes (`--apply`), so a
  repair is one command rather than a guess;
* this gate runs it in check mode, so the next drift is a red line WITH the command that fixes it.

What it deliberately does NOT require: `UNRESOLVED` (a fragment quote whose target is genuinely ambiguous) and
`NARRATIVE` (a bare number in prose, which the pack's own matrix gate already tests for "not a blank line").
Failing on those would push editors to delete citations to make the gate green -- the opposite of the point.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "ci" / "repoint_source_pointers.py"
MATRIX = (ROOT / "docs" / "history" / "archive" / "ui-priority-20261009"
          / "UIV2-INTERFACE-BINDING-MATRIX.csv")
RUNS = ROOT / ".project-local" / "runs" / "pointer-plants"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: the tool declares a @dataclass, and dataclasses resolves a field's type through
    # sys.modules[cls.__module__], which is None for a module loaded only from a file path.
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


TOOL_MODULE = _load(TOOL)


class PointerDriftTests(unittest.TestCase):
    def test_no_quoted_pointer_has_drifted(self) -> None:
        proc = subprocess.run([sys.executable, str(TOOL)], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        out = proc.stdout + proc.stderr
        self.assertIn("REPOINT citations=", out, out)
        self.assertEqual(0, proc.returncode,
                         "a quoted pointer no longer lands on the code it quotes. Fix it mechanically, do not "
                         "re-measure by hand:\n"
                         f"  python scripts/ci/repoint_source_pointers.py --apply\n{out}")

    def test_the_tool_refuses_to_guess_an_unresolvable_quote(self) -> None:
        """A quote that is nowhere in the target must be reported, never silently re-pointed."""
        script = TOOL.read_text(encoding="utf-8")
        self.assertIn("UNRESOLVED", script)
        self.assertIn("nothing is guessed", script)

    def test_the_frozen_matrix_is_refused_rather_than_repaired(self) -> None:
        """The 2026-10-20 collision, made impossible: a pointer repair must never rewrite frozen bytes.

        `docs/history/archive/ui-priority-20261009/UIV2-INTERFACE-BINDING-MATRIX.csv` was this tool's default
        target while sitting inside an archive that `docs/history/archive/FROZEN-MANIFEST.json` and
        `docs/history/archive/MOVED-PATHS-20261019.json` both pin by hash. Repairing one line pointer there
        turned two integrity records red, so the tool now refuses the target outright.
        """
        proc = subprocess.run([sys.executable, str(TOOL), MATRIX.relative_to(ROOT).as_posix()],
                              cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("REPOINT_FROZEN_REFUSED", proc.stdout + proc.stderr)
        frozen = TOOL_MODULE.frozen_paths(ROOT)
        self.assertEqual([], sorted(p.relative_to(ROOT).as_posix()
                                    for p in TOOL_MODULE.live_pointer_surface(ROOT)
                                    if p.relative_to(ROOT).as_posix() in frozen))

    def test_a_drifted_pointer_on_the_live_surface_is_convicted(self) -> None:
        """The default population holds no code citation today, so the gate's teeth are proven by a plant.

        A green over an empty set proves nothing: this writes one live citation whose line has moved and
        requires check mode to fail on it rather than report a clean run.
        """
        RUNS.mkdir(parents=True, exist_ok=True)
        planted = RUNS / "planted-live-pointer.md"
        planted.write_text("See services/orchestration/run_quality_gate.py:1 "
                           "`RETIRED_ORDINARY_TESTS = {` for the retired list.\n",
                           encoding="utf-8", newline="\n")
        try:
            proc = subprocess.run([sys.executable, str(TOOL), str(planted)], cwd=ROOT,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
            self.assertIn("DRIFT services/orchestration/run_quality_gate.py:1", proc.stdout, proc.stdout)
        finally:
            planted.unlink()

    def test_the_live_population_is_enumerated_from_the_index(self) -> None:
        """No hand-listed default: a live document added next week is covered the day it lands."""
        surface = sorted(p.relative_to(ROOT).as_posix() for p in TOOL_MODULE.live_pointer_surface(ROOT))
        self.assertIn("docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md",
                      surface)
        self.assertEqual([], [p for p in surface if p.startswith("docs/history/")], surface[:4])
        self.assertIn(MATRIX.relative_to(ROOT).as_posix(), TOOL_MODULE.frozen_paths(ROOT))


if __name__ == "__main__":
    unittest.main(verbosity=2)
