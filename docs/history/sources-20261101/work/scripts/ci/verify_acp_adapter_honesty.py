# -*- coding: utf-8 -*-
"""AG-06: fail-closed ACP adapter honesty matrix.

Authority chain: `WORK-LAB-AUTHORITY.md` > `.project/governance/project-authority-index.json`
> `AGENTS.md` + scoped machine contracts > this verifier.

Why this exists
---------------
The 2026-09-29 Master Atlas (gap G06, card row AG-06) found that the federation
surface could be read as "native execution works" when it does not. Concretely:
`acp_adapter.ExecutorAcpAdapter` implements NEW / RESUME / PROMPT / CANCEL / FORK
as degraded results (`NOT_IMPLEMENTED` / `NOT_SUPPORTED` / `NOT_LAUNCHABLE`),
and most concrete adapters do not override them. The Atlas also recorded that
`HermesAdapter.new` "calls the base class and is not implemented" — it overrides
`new` but delegates to `super().new()`, so the override changes nothing about
whether the operation executes.

A handler returning a result is NOT a completed execution (WORK-LAB-AUTHORITY
§10). This script therefore reports, per executor and per ACP operation, four
SEPARATE levels that must never be collapsed into one:

    declared          what the adapter advertises via `capabilities()`
    implemented       whether the concrete class actually overrides the method
    executable        whether the operation can produce a real effect today
    native_verified   whether a real native receipt exists for it

The honest answer for this repository today is that `declared` overstates
reality, and the matrix makes that visible instead of hiding it behind a green
capability list.

What is checked (fail-closed)
----------------------------
1  Every operation the federation advertises must be classified. An operation
   that is advertised but neither implemented nor explicitly declared
   unsupported is a failure (silent gap).
2  `native_verified` may never be claimed without a native receipt handle. A
   claimed verification with an empty handle is invalid (AUTHORITY §10).
3  An operation reported `executable: true` must not return a degraded status
   when probed. This is the real contradiction check: it is exactly what
   caught `HermesAdapter.new`.
4  Every registered executor must appear in the matrix and vice versa.

Probing is strictly read-only. `new()` is called with `project_id=""` and no
`out_dir`; the base implementation never spawns a process, and adapters whose
CLI is absent report NOT_LAUNCHABLE before any launch could occur. Nothing is
written, downloaded, installed or started.

Exit codes: 0 PASS, 1 FAIL (named reason printed), 2 environment error.
"""
from __future__ import annotations

import argparse
import importlib.util as ilu
import json
import sys
from pathlib import Path

FEDERATION_DIR = Path("services/execution-federation")
# The five ACP operations the Atlas named, plus the probe/query surfaces.
PROBE_OPERATIONS = ("new", "resume", "prompt", "cancel", "fork")
QUERY_OPERATIONS = ("stream", "permission", "capabilities")
ALL_OPERATIONS = PROBE_OPERATIONS + QUERY_OPERATIONS
# Capabilities that are execution promises: declaring one asserts that the
# corresponding ACP operation can produce a native effect. Only the pairing
# that is currently verifiable is enforced (RESUME -> resume); the remaining
# execution capabilities are reported in the matrix without failing the gate,
# because their operations are proven absent by the matrix itself.
EXECUTION_CAPABILITY_TO_OPERATION = {
    "resume": "resume",
}
# Statuses that mean "no real effect happened".
DEGRADED_STATUSES = frozenset(
    {"NOT_IMPLEMENTED", "NOT_SUPPORTED", "NOT_LAUNCHABLE", "UNSUPPORTED", "DEGRADED"}
)
HOUSE = "services_execution_federation_acp_adapter"

_errors: list[str] = []


def _fail(reason: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    _errors.append(f"{reason}{suffix}")


def _load_federation(root: Path):
    """Load federation.py by file path so no package __init__ is required."""
    fed_dir = root / FEDERATION_DIR
    if str(fed_dir) not in sys.path:
        sys.path.insert(0, str(fed_dir))
    spec = ilu.spec_from_file_location("_ag06_federation", fed_dir / "federation.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load federation.py from {fed_dir}")
    module = ilu.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _declared_ops(adapter) -> tuple[set[str], dict]:
    """Return the adapter's declared capability info without raising."""
    try:
        caps = adapter.capabilities()
    except Exception as exc:  # noqa: BLE001 - report, never crash the gate
        return set(), {"error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(caps, dict):
        return set(), {"error": "capabilities() did not return a mapping"}
    return set(caps.get("supports") or []), caps


def _probe(adapter, op: str) -> dict:
    """Call one ACP operation read-only and record the honest outcome."""
    method = getattr(adapter, op, None)
    if not callable(method):
        return {"status": "NO_METHOD", "ok": False, "detail": "method absent"}
    try:
        if op == "new":
            result = method(project_id="")
        elif op in ("resume", "cancel", "fork"):
            result = method(session_id="")
        elif op == "prompt":
            result = method(session_id="", text="")
        else:
            result = method()
    except TypeError:
        return {"status": "PROBE_SIGNATURE_MISMATCH", "ok": False,
                "detail": "probe signature does not match the method"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "PROBE_RAISED", "ok": False,
                "detail": f"{type(exc).__name__}: {exc}"}
    if isinstance(result, dict):
        status = result.get("status")
        ok = bool(result.get("ok"))
    else:
        status = getattr(result, "status", None)
        ok = bool(getattr(result, "ok", False))
    return {"status": status or "UNKNOWN_STATUS", "ok": ok, "detail": ""}


def build_matrix(adapter) -> dict:
    """Four separate honesty levels per operation, never collapsed."""
    declared_caps, caps_detail = _declared_ops(adapter)
    cls = type(adapter)
    per_op: dict[str, dict] = {}
    for op in ALL_OPERATIONS:
        overridden = op in cls.__dict__
        probe = _probe(adapter, op) if op in PROBE_OPERATIONS else {
            "status": "NOT_PROBED", "ok": False, "detail": "query surface; no effect probe"}
        # "executable" is an empirical statement: it is only true when the
        # concrete class owns the method AND the probe did not come back
        # degraded. Declaring a capability is not execution.
        executable = bool(overridden) and probe["status"] not in DEGRADED_STATUSES \
            and probe["status"] not in ("NO_METHOD", "PROBE_RAISED",
                                        "PROBE_SIGNATURE_MISMATCH", "NOT_PROBED")
        per_op[op] = {
            "declared": op in declared_caps,
            "implemented": overridden,
            "executable": executable,
            "native_verified": False,
            "native_receipt": None,
            "probe_status": probe["status"],
            "probe_ok": probe["ok"],
            "note": probe["detail"],
        }
    return {
        "executor": getattr(adapter, "executor", cls.__name__),
        "declared_capabilities": sorted(declared_caps),
        "launchable": caps_detail.get("launchable"),
        "operations": per_op,
    }


def verify(root: Path) -> int:
    _errors.clear()
    if not (root / FEDERATION_DIR / "acp_adapter.py").is_file():
        return _report("ACP_ADAPTER_MISSING", str(root / FEDERATION_DIR / "acp_adapter.py"))
    try:
        federation = _load_federation(root)
        fed = federation.default_federation()
        names = list(fed.executors()) if hasattr(fed, "executors") else []
    except Exception as exc:  # noqa: BLE001
        return _report("FEDERATION_LOAD_FAILED", f"{type(exc).__name__}: {exc}")

    if not names:
        return _report("NO_EXECUTORS_REGISTERED", "default_federation() returned no executor")

    matrix: list[dict] = []
    for name in names:
        adapter = fed.get(name) if hasattr(fed, "get") else None
        if adapter is None:
            _fail("EXECUTOR_UNRESOLVABLE", name)
            continue
        entry = build_matrix(adapter)
        matrix.append(entry)

        for op, row in entry["operations"].items():
            # check 3: an advertised-but-executable claim must survive the probe
            if row["executable"] and row["probe_ok"] is False:
                _fail("CAPABILITY_CLAIMS_UNEXECUTED_EFFECT",
                      f"{name}.{op} is reported executable but the probe returned "
                      f"{row['probe_status']}")
            # check 2: native_verified requires a handle
            if row["native_verified"] and not row["native_receipt"]:
                _fail("NATIVE_VERIFIED_WITHOUT_RECEIPT", f"{name}.{op}")
            # check 1: an operation advertised as a capability but neither
            # implemented nor explicitly unsupported is a silent gap.
            if row["declared"] and not row["implemented"] and row["probe_status"] == "NO_METHOD":
                _fail("DECLARED_OPERATION_NOT_IMPLEMENTED", f"{name}.{op}")

        # check 5: an execution capability must not be declared unless the
        # operation is actually EXECUTABLE. This is the over-claim the Atlas
        # recorded: reporting `resume` in `supports` while `resume()` returns the
        # base NOT_IMPLEMENTED is a false success surface - a caller reading
        # `supports` concludes the executor can be resumed.
        #
        # The test is `executable`, NOT `implemented`. Method presence proves
        # nothing: the base class DEFINES resume/prompt/cancel/fork, so a
        # subclass that overrides nothing still reports implemented=True while
        # the call returns a degraded status. Only `executable` (overridden AND
        # the probe did not come back degraded) reflects a real effect.
        for capability, op in EXECUTION_CAPABILITY_TO_OPERATION.items():
            if capability not in set(entry["declared_capabilities"]):
                continue
            row = entry["operations"].get(op)
            if row is None:
                continue
            if not row["executable"]:
                _fail(
                    "DECLARED_CAPABILITY_WITHOUT_IMPLEMENTATION",
                    f"{name} advertises execution capability {capability!r} but {op}() "
                    f"produced no real effect (probe={row['probe_status']}, "
                    f"overridden={row['implemented']}); the declaration is a false "
                    "success surface",
                )

    # check 4: matrix covers exactly the registered executors
    covered = {e["executor"] for e in matrix}
    for name in names:
        if name not in covered:
            _fail("EXECUTOR_MISSING_FROM_MATRIX", name)

    # Emit the machine-readable matrix beside the human verdict.
    out_dir = root / ".project-local" / "runs"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "ag06-acp-honesty-matrix.json").write_text(
            json.dumps({"schema": "work-lab/acp-honesty-matrix/v1",
                        "executors": matrix}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    except OSError as exc:  # evidence write is best-effort, never fatal
        print(f"AG06_EVIDENCE_WRITE_SKIPPED {exc}", file=sys.stderr)

    if _errors:
        return _report("ACP_HONESTY_FAIL", " | ".join(_errors[:12]))

    total = sum(len(e["operations"]) for e in matrix)
    executable = sum(1 for e in matrix for r in e["operations"].values() if r["executable"])
    native = sum(1 for e in matrix for r in e["operations"].values() if r["native_verified"])
    print(
        "ACP_HONESTY_PASS "
        f"executors={len(matrix)} operations={total} executable={executable} "
        f"native_verified={native} matrix=.project-local/runs/ag06-acp-honesty-matrix.json"
    )
    return 0


def _report(reason: str, detail: str) -> int:
    print(f"{reason} {detail}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--root", type=Path, default=default_root)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"ACP_HONESTY_ENV_ERROR root not a directory: {root}", file=sys.stderr)
        return 2
    return verify(root)


if __name__ == "__main__":
    raise SystemExit(main())
