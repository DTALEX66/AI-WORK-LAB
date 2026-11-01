#!/usr/bin/env python3
"""Tests for the reduced-motion floor gate — fed by synthetic censuses, so a plant is a data edit.

The gate's browser side walks every painted node and reports computed `transition`/`animation` durations; the
judgement lives in a pure function so each conviction can be proven here. The one thing these tests cannot
prove is the JS predicate itself, which is why the delivery receipt for this gate also carries a real CSS
mutation (the floor block removed from `apps/observer/frontend/src/skins/l10b-shell.css`, bundle rebuilt) and
the named FAILs it produced.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "audit" / "reduced_motion_floor_via_cdp.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("reduced_motion_floor_via_cdp", GATE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


def box(*, normal_transitions=5, normal_animations=1, reduce_transitions=0, reduce_animations=0,
        nodes=120, floor=30, normal_pinned_reduce=False, reduce_pinned_reduce=True,
        normal_scroll="auto", reduce_scroll="auto") -> dict:
    """One surface's reading: the shape the CDP probe returns, nothing else."""
    return {
        "normalPin": {"reduce": normal_pinned_reduce, "noPreference": not normal_pinned_reduce},
        "reducePin": {"reduce": reduce_pinned_reduce, "noPreference": not reduce_pinned_reduce},
        "normal": {"elements": nodes, "transitionCount": normal_transitions,
                   "animationCount": normal_animations, "scroll": normal_scroll,
                   "transitions": [{"node": f"button.n{i}", "prop": "all", "dur": "0.22s"}
                                   for i in range(min(normal_transitions, 3))],
                   "animations": [{"node": f"div.ambient", "name": "floatGlow", "dur": "12s"}
                                  for _ in range(min(normal_animations, 1))]},
        "reduce": {"elements": nodes, "transitionCount": reduce_transitions,
                   "animationCount": reduce_animations, "scroll": reduce_scroll,
                   "transitions": [{"node": "button.leaked", "prop": "all", "dur": "0.22s"}
                                   for _ in range(min(reduce_transitions, 3))],
                   "animations": [{"node": "div.leaked", "name": "floatGlow", "dur": "12s"}
                                  for _ in range(min(reduce_animations, 1))]},
        "minNodes": floor,
    }


def good() -> dict:
    return {"professional": box(normal_transitions=65, normal_animations=4, nodes=368),
            "strip-h01": box(normal_transitions=0, normal_animations=0, reduce_transitions=0,
                             nodes=95, floor=6),
            "panel-h01": box(normal_transitions=9, nodes=170, floor=12),
            "daily-home": box(normal_transitions=5, normal_animations=0, nodes=169, floor=30)}


def leak(into: dict, kind: str) -> None:
    """A plant that moves the same fields the browser would: the count and the examples travel together."""
    if kind == "transition":
        into["transitionCount"] = int(into.get("transitionCount") or 0) + 3
        into["transitions"] = [{"node": "button.leaked", "prop": "all", "dur": "0.22s"}]
    else:
        into["animationCount"] = int(into.get("animationCount") or 0) + 2
        into["animations"] = [{"node": "div.leaked", "name": "floatGlow", "dur": "12s"}]


def names(result: dict) -> set[str]:
    return {c["check"] for c in result["checks"] if not c["pass"]}


class FloorClauseTests(unittest.TestCase):
    def test_a_shaped_reading_passes(self) -> None:
        result = gate.verdict(good())
        self.assertTrue(result["passed"], json.dumps([c for c in result["checks"] if not c["pass"]]))

    def test_a_transition_that_survives_the_preference_is_convicted_by_name(self) -> None:
        measured = good()
        leak(measured["daily-home"]["reduce"], "transition")
        result = gate.verdict(measured)
        self.assertFalse(result["passed"])
        self.assertEqual(names(result), {"reduced_motion_floor_holds[daily-home]"})
        detail = next(c["detail"] for c in result["checks"]
                      if c["check"] == "reduced_motion_floor_holds[daily-home]")
        self.assertIn("button.leaked", detail, "the conviction has to name what it saw, not just the count")

    def test_an_animation_that_survives_the_preference_is_also_convicted(self) -> None:
        measured = good()
        leak(measured["panel-h01"]["reduce"], "animation")
        self.assertEqual(names(gate.verdict(measured)), {"reduced_motion_floor_holds[panel-h01]"})

    def test_smooth_scrolling_under_the_preference_is_convicted(self) -> None:
        measured = good()
        measured["professional"]["reduce"]["scroll"] = "smooth"
        self.assertEqual(names(gate.verdict(measured)), {"reduced_motion_floor_holds[professional]"})

    def test_a_preference_that_was_not_actually_pinned_is_refused(self) -> None:
        measured = good()
        # The emulation call is a no-op on some paths; if the page still answers `reduce`, every `0` in this
        # reading is a statement about the environment rather than the stylesheet.
        measured["daily-home"]["reducePin"] = {"reduce": False, "noPreference": True}
        self.assertEqual(names(gate.verdict(measured)),
                         {"reduced_motion_preference_pinned[daily-home]"})

    def test_a_blank_root_is_not_allowed_to_pass_the_floor_for_the_wrong_reason(self) -> None:
        measured = good()
        measured["strip-h01"]["normal"]["elements"] = 4
        measured["strip-h01"]["reduce"]["elements"] = 4
        result = gate.verdict(measured)
        self.assertEqual(names(result), {"surface_was_painted_before_it_was_censused[strip-h01]"})
        # The floor clause itself stayed green: this is the pair that only exists because both branches
        # matter — a census of nothing satisfies "no motion" and proves nothing.
        self.assertIn("reduced_motion_floor_holds[strip-h01]",
                      [c["check"] for c in result["checks"] if c["pass"]])


class PopulationTests(unittest.TestCase):
    def test_nothing_measured_is_not_a_pass_by_omission(self) -> None:
        result = gate.verdict({})
        self.assertFalse(result["passed"])
        self.assertEqual(names(result), {"gate_measured_a_surface",
                                         "some_surface_moves_when_the_preference_is_off"},
                         "an empty population fails the population clause too, not only its own named check")

    def test_a_population_where_every_surface_is_motionless_guards_nothing(self) -> None:
        measured = {"strip-h01": box(normal_transitions=0, normal_animations=0, nodes=95, floor=6)}
        result = gate.verdict(measured)
        self.assertFalse(result["passed"])
        self.assertEqual(names(result), {"some_surface_moves_when_the_preference_is_off"})

    def test_a_motionless_surface_is_reported_instead_of_forgiven_or_convicted_alone(self) -> None:
        result = gate.verdict(good())
        self.assertIn("NO_MOTION_DECLARED_IN_EITHER_BRANCH", result["reported"]["strip-h01"])
        self.assertEqual(result["coverage"]["motionlessBothBranches"], ["strip-h01"])
        # The strip's own rows stay in the population the floor clause judges: the gap is a product
        # coverage fact (its hover is JS state, not a transition), not a reason to stop censusing it.
        self.assertIn("reduced_motion_floor_holds[strip-h01]", [c["check"] for c in result["checks"]])


class FakeCdp:
    """Drives the probe's own read path so the order of the two branches is a tested fact."""

    def __init__(self, *, always_reduce: bool = False) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.evaluations: list[str] = []
        self.always_reduce = always_reduce

    def send(self, method: str, params: dict | None = None) -> None:
        self.sent.append((method, params or {}))

    def evaluate(self, expr: str) -> str:
        self.evaluations.append(expr)
        if expr == gate.PIN_READBACK_JS:
            value = self.always_reduce
            return json.dumps({"reduce": value, "noPreference": not value})
        count = 0 if len([e for e in self.evaluations if e == gate.MOTION_CENSUS_JS]) > 1 else 7
        return json.dumps({"elements": 200, "transitionCount": count, "animationCount": 0,
                           "transitions": [], "animations": [], "scroll": "auto",
                           "pseudoScanned": 40, "measuredAt": 1.0})

    def pinned_values(self) -> list[str]:
        out = []
        for method, params in self.sent:
            if method == "Emulation.setEmulatedMedia":
                out.append(params["features"][0]["value"])
        return out


class ProbeOrderTests(unittest.TestCase):
    def test_the_normal_branch_is_censused_before_the_reduced_one(self) -> None:
        cdp = FakeCdp()
        reading = gate.measure_surface(cdp)
        self.assertEqual(cdp.pinned_values(), ["no-preference", "reduce"])
        self.assertEqual(reading["normal"]["transitionCount"], 7,
                         "the first census is the one that still has motion")
        self.assertEqual(reading["reduce"]["transitionCount"], 0)

    def test_a_page_that_answers_reduce_whatever_was_pinned_is_convicted_not_credited(self) -> None:
        cdp = FakeCdp(always_reduce=True)
        reading = gate.measure_surface(cdp)
        result = gate.verdict({"professional": dict(reading, minNodes=30)})
        self.assertFalse(result["passed"])
        self.assertIn("reduced_motion_preference_pinned[professional]", names(result))


class SurfaceDeclarationTests(unittest.TestCase):
    class Strip:
        MOUNT_SELECTOR = gate.hud.MOUNT_SELECTOR
        SURFACES = [{"name": n, "kind": "strip" if n.startswith("strip") else
                     ("panel" if n.startswith("panel") else "daily"),
                     "query": f"q-{n}", "size": (150, 480)} for n in gate.SHELL_SURFACES]

    def test_surfaces_come_from_the_strip_gate_not_a_second_copy(self) -> None:
        specs = gate.surfaces(self.Strip, ["professional", "strip-h01"])
        self.assertEqual([s["label"] for s in specs], ["professional", "strip-h01"])
        self.assertEqual(specs[1]["query"], "q-strip-h01",
                         "the query is the strip gate's declaration, not a literal copied here")

    def test_a_renamed_surface_is_refused_instead_of_quietly_dropped(self) -> None:
        class Renamed(SurfaceDeclarationTests.Strip):
            SURFACES = [s for s in SurfaceDeclarationTests.Strip.SURFACES if s["name"] != "daily-governance"]

        with self.assertRaises(RuntimeError) as ctx:
            gate.surfaces(Renamed, ["professional"])
        self.assertIn("SURFACE_MISSING", str(ctx.exception))

    def test_an_unknown_name_is_refused_before_anything_is_read(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            gate.surfaces(self.Strip, ["strip-h9"])
        self.assertIn("UNKNOWN_SURFACE", str(ctx.exception))

    def test_the_density_floors_are_the_legibility_gates_numbers_not_a_second_pin(self) -> None:
        specs = {s["label"]: s for s in gate.surfaces(self.Strip, list(gate.SHELL_SURFACES))}
        leg = gate.legibility
        self.assertEqual(specs["strip-h01"]["minNodes"], leg.MIN_STRIP_NODES)
        self.assertEqual(specs["panel-h01"]["minNodes"], leg.MIN_SHELL_NODES)
        self.assertEqual(gate.PROFESSIONAL["minNodes"], leg.MIN_NODES)


class RefusalTests(unittest.TestCase):
    """`scripts/ci/verify_ci_check_reachability.py` needs a local route for every CDP instrument: what is
    tested here is the refusal, because a gate that cannot say NOT_RUN is a gate that will lie."""

    def setUp(self) -> None:
        # `tests/workflow-assistance/test_temp_fixture_stays_inside_the_boundary.py` convicts a bare
        # `mkdtemp()`: an invented root outside the project boundary leaks unless someone remembers to
        # delete it, so the fixture goes under `.project-local/runs/tmp` and is removed here.
        self.tmp_root = ROOT / ".project-local" / "runs" / "tmp"
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.roots: list[str] = []

    def tearDown(self) -> None:
        for path in self.roots:
            shutil.rmtree(path, ignore_errors=True)

    def empty_root(self) -> Path:
        created = tempfile.mkdtemp(prefix="reduced-motion-refusal-", dir=str(self.tmp_root))
        self.roots.append(created)
        return Path(created)

    def test_a_bad_surface_name_refuses_before_the_dist_is_even_looked_up(self) -> None:
        proc = subprocess.run([sys.executable, str(GATE), "--root", str(self.empty_root()),
                               "--surface", "strip-h9"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("UNKNOWN_SURFACE", proc.stdout)
        self.assertNotIn("DIST_ABSENT", proc.stdout,
                         "a typo is a typo regardless of what this machine built; rc 2 must not be rc 3")

    def test_a_missing_bundle_refuses_by_name_as_not_run(self) -> None:
        proc = subprocess.run([sys.executable, str(GATE), "--root", str(self.empty_root())],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn("DIST_ABSENT", proc.stdout)


if __name__ == "__main__":
    unittest.main()
