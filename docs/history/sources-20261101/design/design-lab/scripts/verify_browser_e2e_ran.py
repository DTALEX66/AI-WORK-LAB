#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Enforce the no-skip policy for the Workbench browser E2E on CI.

`test_workbench_design_layer_e2e.py` and `test_workbench_overflow_gate.py` are
PROBE-driven: when the toolchain (node + a resolvable `playwright` + a matching
Chromium) is present they drive the real browser against the live loopback
service; when it is absent they HONESTLY SKIP. On a clean GitHub runner nothing
is pre-installed, so a naive run would skip and be silently treated as a pass.

This gate makes that impossible in the dedicated `workbench-browser-e2e` CI
job: the job installs the pinned `playwright` (workspace dependency) and its
matching Chromium first, and this script REQUIRES every browser test to actually
RUN and PASS — a skip or failure in ANY module exits non-zero, turning the CI
job red.

Deterministic and stdlib-only (drives the existing unittest shell in-process).
"""
from __future__ import annotations

import importlib
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Every browser gate rides the same required CI job. `test_workbench_overflow_gate`
# is the rendered-geometry gate (nothing clipped / unreachable / sub-11px); it was
# falsified against the pre-fix checkout before being wired in, so it can go red.
# `test_workbench_theme_geometry_gate` joined on 2026-10-11: it measures the nav rail's painted width
# per palette. The register is a tuple, not a glob, so an unlisted browser suite would skip forever
# without a finding -- and this comment said "Both" while three modules were already listed.
TEST_MODULES = (
    "test_workbench_design_layer_e2e",
    "test_workbench_overflow_gate",
    "test_workbench_contrast_gate",
    "test_workbench_theme_geometry_gate",
    # Joined 2026-10-11 after the DOT audit found both theme buttons were no-ops in a real
    # browser. The geometry gate sets the <html> attributes itself and so cannot see that:
    # only a gate that clicks can. An unlisted browser suite skips forever without a finding,
    # which is exactly how this defect stayed out of every green rollup.
    "test_workbench_theme_affordance_gate",
    # The quantitative audit (26 scopes at the two CI widths, measuring overflow, contrast,
    # keyboard reachability, targets, names, degraded wording and console noise) was a
    # manual command until 2026-10-08. On 2026-10-18 it reported three live violations the
    # entire required context was green over, including a palette row landing on a page
    # whose title named something else.
    "test_workbench_ui_audit_gate",
    # Joined 2026-10-22 (B5): the motion gate reads SRC-T07-MOTION-COMPOSITED out of Chromium's own
    # CSSOM and computed styles over every nav route, and it is the proof behind the first CONSUMED
    # landing in packages/capabilities/selected-sources.json. A CONSUMED claim whose measuring gate
    # could skip silently would be a record kept alive by nobody looking, so it belongs on this list.
    "test_workbench_motion_gate",
    # Joined 2026-10-25 (full-scope audit): this suite existed, passed locally in 2.455s, and
    # was named by no workflow step and no entry above -- so every CI roll-up was green over a
    # preflight block->fix->re-check chain that the cloud never once executed. Its own module
    # comment says an unlisted browser suite skips forever without a finding; this entry is
    # that finding. Registration was safe because line ~87 below exports E2E_NODE_MODULES for
    # every module here; the module's own browser probe was the thing that needed fixing first
    # -- it globbed `$HOME/AppData/Local/ms-playwright/chromium*/chrome-win*/chrome.exe`, a
    # Windows-only shape, so on Linux it silently declined to name a browser. It now asks the
    # same shared cross-platform question the other seven gates ask, so the receipt says which
    # Chromium actually answered.
    "test_workbench_preflight_handoff_e2e",
)


def main() -> int:
    # The shell test's `E2E_NODE_MODULES` must name the directory that CONTAINS
    # node_modules/. In this workspace the pinned `playwright` dependency is
    # installed per-package, so that directory is apps/workbench (it resolves
    # `apps/workbench/node_modules/playwright`). The matching Chromium is
    # provisioned by the CI job's `playwright install`.
    os.environ.setdefault("E2E_NODE_MODULES", str(ROOT / "apps" / "workbench"))

    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "design-lab" / "tests"))

    loader = unittest.TestLoader()
    ran = skipped = failed = 0
    skip_reasons = []
    for name in TEST_MODULES:
        module = importlib.import_module(name)
        result = unittest.TextTestRunner(verbosity=2).run(
            loader.loadTestsFromModule(module))
        module_tests = result.testsRun
        module_skips = len(result.skipped)
        module_fails = len(result.failures) + len(result.errors)
        print(f"BROWSER_E2E[{name}] ran={module_tests} skipped={module_skips} "
              f"failed={module_fails}")
        if module_tests == 0:
            print(f"BROWSER_E2E_NO_TESTS: nothing was discovered in {name}; fail-closed.")
            return 1
        ran += module_tests
        skipped += module_skips
        failed += module_fails
        skip_reasons.extend((test, reason) for test, reason in result.skipped)

    print(f"BROWSER_E2E ran={ran} skipped={skipped} failed={failed}")
    if skipped:
        for test, reason in skip_reasons:
            print(f"BROWSER_E2E_NO_SKIP_VIOLATION: skipped {test} -> {reason}")
        print("The no-skip policy requires the toolchain to be present and every "
              "browser gate to run. Install the pinned playwright + Chromium and re-run.")
        return 1
    if failed:
        print("BROWSER_E2E FAILED: see the traceback above.")
        return 1
    print("BROWSER_E2E: PASS (ran, no-skip, no-skip policy satisfied)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
