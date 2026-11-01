#!/usr/bin/env python
"""U17.7/27 — Global Agent Policy coverage freshness verifier.

Fail-closed, read-only check that the *derived* policy-coverage surfaces are
fresh with respect to their *sources*. Run in the integration gate and locally
before any execution task. It never mutates state.

Single source of truth, by design (taskpack U17.7 / U17.20 / U17.27):

    config/global-agent-policy.yaml          (the WHAT — semantic core)
    integrations/executors/<sw>/<sw>-policy-extension.yaml   (native knobs)
            ->
    config/adapter-registry.json#entries[].policy_projection.capability_states
    config/loss-reports/<sw>-policy-loss-report.json
            ->
    config/capability-matrix.json#global_agent_policy_coverage   (derived view)

Hand-editing a generated artifact (a loss report, the capability-matrix coverage
block, or a golden) without the source policy / extension moving is a
fail-closed drift, NOT a legitimate change. Checks (each failure aborts with a
non-zero exit and a named reason):

- every persisted loss report is schema-valid and non-deceptive
  (no capability in two buckets, no capability missing);
- for each loss-report-carrying adapter, the registry's
  ``capability_states`` exactly equal the loss report's buckets
  (registry is the source of truth; the loss report is its projection);
- the capability-matrix ``global_agent_policy_coverage.coverage`` block is
  byte-identical to the coverage derived from the registry (matrix is a
  read-only view, never a second source);
- a golden renderer output that has been hand-edited while the policy source
  is unchanged is detected by comparing the freshly rendered golden to the
  committed golden (renderer determinism).

Exit codes: 0 PASS, 1 FAIL (named reason printed), 2 environment error.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

MATRIX = "config/capability-matrix.json"
REGISTRY = "config/adapter-registry.json"
LOSS_REPORTS_DIR = "config/loss-reports"
LOSS_REPORT_SCHEMA = "packages/contracts/schemas/workflow/policy-projection-loss-report.schema.json"
POLICY = "config/global-agent-policy.yaml"

_LOSS_BUCKETS = ("native_enforced", "native_guidance", "workflow_guard", "observe_only", "unsupported")


def _fail(reason: str, detail: str = "") -> int:
    suffix = f" {detail}" if detail else ""
    print(f"POLICY_COVERAGE_FAIL {reason}{suffix}", file=sys.stderr)
    return 1


def _load(name: str, rel: Path):
    spec = importlib.util.spec_from_file_location(name, rel)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {rel}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _loss_buckets_to_states(report: dict) -> dict:
    states: dict[str, str] = {}
    for bucket in _LOSS_BUCKETS:
        for cap in report.get(bucket, []):
            states[cap] = bucket.upper().replace("NATIVE_ENFORCED", "NATIVE_ENFORCED")
    return states


def verify_coverage(root: Path) -> int:
    pp = _load("wa_pp", root / "services" / "policy" / "policy_projection.py")

    # --- loss-report schema ---
    import jsonschema

    schema = json.loads((root / LOSS_REPORT_SCHEMA).read_text(encoding="utf-8"))
    loss_dir = root / LOSS_REPORTS_DIR
    if not loss_dir.is_dir():
        return _fail("LOSS_REPORT_DIR_MISSING", str(loss_dir))
    loss_reports: dict[str, dict] = {}
    for path in sorted(loss_dir.glob("*-policy-loss-report.json")):
        adapter = path.name[: -len("-policy-loss-report.json")]
        report = json.loads(path.read_text(encoding="utf-8"))
        try:
            jsonschema.Draft202012Validator(schema).validate(report)
        except jsonschema.ValidationError as exc:
            return _fail("LOSS_REPORT_SCHEMA_INVALID", f"{adapter}: {exc.message}")
        # non-deceptive: every capability in exactly one bucket
        seen: set[str] = set()
        for bucket in _LOSS_BUCKETS:
            for cap in report.get(bucket, []):
                if cap in seen:
                    return _fail("LOSS_REPORT_DOUBLE_CLASSIFIED", f"{adapter}: {cap}")
                seen.add(cap)
        missing = set(pp.POLICY_CAPABILITIES) - seen
        if missing:
            return _fail("LOSS_REPORT_CAPABILITY_MISSING", f"{adapter}: {sorted(missing)}")
        loss_reports[adapter] = report

    # --- registry capability_states == loss report buckets ---
    registry = json.loads((root / REGISTRY).read_text(encoding="utf-8"))
    reg_by_id = {e["id"]: e for e in registry["entries"]}
    for adapter, report in loss_reports.items():
        entry = reg_by_id.get(adapter)
        if entry is None:
            return _fail("ADAPTER_MISSING_IN_REGISTRY", adapter)
        reg_states = entry.get("policy_projection", {}).get("capability_states", {})
        expected = _loss_buckets_to_states(report)
        diff = {c: (reg_states.get(c), expected.get(c)) for c in pp.POLICY_CAPABILITIES if reg_states.get(c) != expected.get(c)}
        if diff:
            return _fail("REGISTRY_LOSS_REPORT_MISMATCH", f"{adapter}: {diff}")
        if entry.get("policy_projection", {}).get("capability_coverage_complete") is not True:
            return _fail("REGISTRY_COVERAGE_INCOMPLETE", f"{adapter} carries a loss report but capability_coverage_complete is not true")

    # --- capability-matrix derived block is byte-identical to the registry ---
    matrix = json.loads((root / MATRIX).read_text(encoding="utf-8"))
    block = matrix.get("global_agent_policy_coverage")
    if not isinstance(block, dict):
        return _fail("MATRIX_COVERAGE_BLOCK_MISSING", MATRIX)
    software = block.get("software", [])
    caps = block.get("policy_capabilities", [])
    coverage = block.get("coverage", {})
    if not software or not caps or not coverage:
        return _fail("MATRIX_COVERAGE_BLOCK_EMPTY", MATRIX)
    for cap in caps:
        row = coverage.get(cap)
        if not isinstance(row, dict):
            return _fail("MATRIX_COVERAGE_ROW_MISSING", f"capability {cap}")
        for sw in software:
            expected_state = reg_by_id.get(sw, {}).get("policy_projection", {}).get("capability_states", {}).get(cap, "UNSUPPORTED")
            if row.get(sw) != expected_state:
                return _fail(
                    "MATRIX_COVERAGE_NOT_DERIVED",
                    f"{cap}/{sw} = {row.get(sw)!r} but registry says {expected_state!r} — the matrix is a read-only view; regenerate it, do not hand-edit",
                )

    # --- golden freshness: the committed golden equals the freshly rendered golden ---
    for renderer_rel in (
        "integrations/executors/codex/codex_policy_renderer.py",
        "integrations/executors/hermes/hermes_policy_renderer.py",
    ):
        renderer = _load("wa_renderer_" + Path(renderer_rel).stem, root / renderer_rel)
        result = renderer.build_renderer(root).project()  # fail-closed: validates the policy
        golden_key = "global-guidance.md" if "codex" in renderer_rel else "config/SOUL.md"
        committed = (root / golden_key if "hermes" in renderer_rel else root / "integrations" / "executors" / "codex" / "global-guidance.md")
        rendered = result["assets"][golden_key]
        if committed.read_text(encoding="utf-8") != rendered:
            return _fail(
                "GOLDEN_STALE",
                f"{committed} differs from the freshly rendered golden; either the policy/extension changed (re-run the renderer) or the golden was hand-edited — commit the renderer output, never the edit",
            )

    print(
        "POLICY_COVERAGE_PASS "
        f"loss_reports={sorted(loss_reports)} matrix_software={len(software)} capabilities={len(caps)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_REPO, help="repository root to verify")
    args = parser.parse_args()
    return verify_coverage(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
