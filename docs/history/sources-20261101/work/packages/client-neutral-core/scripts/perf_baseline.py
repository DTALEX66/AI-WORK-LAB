#!/usr/bin/env python
"""WLGM-230/§4.3 performance baseline for observer collectors.

Measures real latency of the non-interfering collectors against the task-pack
budgets (single-project git query < 2s, heartbeat path < 100ms, collector
timeout 2-5s). Produces P50/P95 and a PASS/PENDING verdict. This is the
performance-comparison evidence for WLGM-240 (no agent task-duration impact is
measurable here without an external canary; that stays PENDING).
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

WORK = Path(r"D:\All projects\WORK-LAB")
SCRIPTS = WORK / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from git_collector import collect_git_observation  # noqa: E402
from product_project import ProductProject, RepositoryIdentity  # noqa: E402
from project_identity_resolver import ApprovedProjectIndex, GitProbe, resolve_execution_path  # noqa: E402


def percentile(samples: list[float], p: float) -> float:
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, int(len(ordered) * p / 100))
    return ordered[index]


def measure(fn, rounds: int = 20) -> dict[str, float]:
    samples: list[float] = []
    cpu_before = time.process_time()
    for _ in range(rounds):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)  # ms
    cpu_ms_total = (time.process_time() - cpu_before) * 1000
    return {
        "p50_ms": round(percentile(samples, 50), 3),
        "p95_ms": round(percentile(samples, 95), 3),
        "max_ms": round(max(samples), 3),
        "cpu_ms_per_call": round(cpu_ms_total / rounds, 3),
        "samples": rounds,
    }


def process_memory() -> dict[str, object]:
    """Real resident-set figures for this process, stdlib only.

    ``time.process_time`` and these counters cover the interpreter process. The collectors shell out to
    ``git``, and a child's CPU time is NOT in ``process_time`` on Windows, so every figure here is a
    lower bound on the cost of a tick -- which is why the receipt also reports wall-clock p95 and says so.
    """
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class _Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong),
                        ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        counters = _Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # Without these declarations the pseudo-handle arrives as a C int and the call fails with
        # ERROR_INVALID_HANDLE (measured 2026-10-10: "K32GetProcessMemoryInfo error 6" -- an instrument
        # that reports its own broken signature as an unavailable metric, which is why the reason is
        # printed rather than defaulting to zero).
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Counters),
                                                      wintypes.DWORD]
        kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = kernel32.GetCurrentProcess()
        if not kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return {"available": False,
                    "reason": f"K32GetProcessMemoryInfo error {ctypes.get_last_error()}"}
        return {"available": True, "backend": "kernel32.K32GetProcessMemoryInfo",
                "workingSetKB": round(counters.WorkingSetSize / 1024, 1),
                "peakWorkingSetKB": round(counters.PeakWorkingSetSize / 1024, 1),
                "pagefileKB": round(counters.PagefileUsage / 1024, 1)}
    import resource

    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {"available": True, "backend": "resource.getrusage",
            "workingSetKB": round(usage.ru_maxrss / 1024, 1), "peakWorkingSetKB": round(usage.ru_maxrss / 1024, 1),
            "pagefileKB": None}


def main() -> int:
    report: dict[str, object] = {"schemaVersion": "worklab/perf-baseline/v1", "project": "work-lab"}

    git_stats = measure(lambda: collect_git_observation(WORK, include_dirty=True))
    report["git_collector_ms"] = git_stats

    project = ProductProject(project_id="work-lab")
    project.add_repository(RepositoryIdentity(repository_id="work-lab", remote_identity="github:DTALEX66/WORK-LAB"))
    index = ApprovedProjectIndex(projects=[project])
    probe = GitProbe()
    resolver_stats = measure(lambda: resolve_execution_path(str(WORK), index, git=probe), rounds=50)
    report["identity_resolver_ms"] = resolver_stats

    # Heartbeat path is a pure in-memory dict build (collector_scheduler emits
    # heartbeat events without IO); measure it directly.
    from execution_evidence import ExecutionEvidence  # noqa: E402

    heartbeat_stats = measure(
        lambda: ExecutionEvidence(
            event_id="hb", event_type="execution_heartbeat", occurred_at="2026-08-14T00:00:00Z",
        ).as_record(),
        rounds=200,
    )
    report["heartbeat_ms"] = heartbeat_stats

    # A real collector tick against the live repository: this is the load the task-pack budget is about,
    # and it is measured on the shipped code path (CanonicalStore + build_standard_collectors), not on a
    # stand-in. The store lives under the declared runtime root, so the measurement leaves nothing behind
    # the project boundary.
    from canonical_store import CanonicalStore
    from collectors import build_standard_collectors
    from durable_worker import make_worker
    from project_temp import runtime_dir

    runtime = runtime_dir("perf-baseline-worker")
    store = CanonicalStore(runtime / "canonical.sqlite")
    store.register_project("work-lab", str(WORK), display_name="WORK-LAB")
    worker = make_worker(store, project_id="work-lab", collectors=build_standard_collectors(WORK))
    memory_before = process_memory()
    tick_stats = measure(worker.run_once, rounds=5)
    memory_after = process_memory()
    store.close()
    report["collector_tick_ms"] = tick_stats
    report["memory"] = {
        "before": memory_before,
        "after": memory_after,
        "workingSetDeltaKB": (
            round(memory_after["workingSetKB"] - memory_before["workingSetKB"], 1)
            if memory_before.get("available") and memory_after.get("available") else None),
        "childProcessCPUIncluded": False,
        "cpuNote": "process_time counts this interpreter only; the collectors shell out to git, whose CPU "
                   "is in the wall-clock figure but not in cpu_ms_per_call",
    }

    budgets = {
        # §4.3: single-project git query < 2s.
        "git_collector_budget_2s": git_stats["p95_ms"] < 2000,
        # The task-pack target P95<=2s applies to a full collection tick, not only to one git query.
        "collector_tick_budget_2s": tick_stats["p95_ms"] < 2000,
        # §4.3: heartbeat send budget < 100ms (async, non-blocking).
        "heartbeat_budget_100ms": heartbeat_stats["p95_ms"] < 100,
        # Resolver is a LOW-FREQUENCY identity path (15-30s sampling), not the
        # heartbeat; budget covers several git subprocess spawns on Windows.
        "resolver_low_freq_budget_500ms": resolver_stats["p95_ms"] < 500,
    }
    report["budgets"] = budgets
    report["verdict"] = "PASS" if all(budgets.values()) else "FAIL"
    report["external_canary_perf_impact"] = "PENDING (requires WORKLAB_CANARY_PROJECT_ROOTS + agent task duration baseline)"

    report["subject"] = {
        "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=WORK, capture_output=True)
        .stdout.decode("utf-8", "replace").strip() or None,
        "platform": f"{os.name}/{sys.platform}",
        "python": sys.version.split()[0],
        "instrument": "packages/client-neutral-core/scripts/perf_baseline.py",
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\nPERF_BASELINE", report["verdict"])
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
