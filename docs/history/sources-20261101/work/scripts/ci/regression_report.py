"""NX-710 size/performance/boundary regression report.

Measures the current tree and representative local gates without network,
provider calls, or generated artifacts. A missing historical baseline is
reported honestly rather than fabricated.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from statistics import median
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / "packages" / "client-neutral-core" / "scripts"
OBS = ROOT / "apps" / "observer" / "scripts"
import sys
sys.path.insert(0, str(WF))
sys.path.insert(0, str(OBS))

from design_contract import DesignContractChecker  # noqa: E402
from memory_contamination import run_all_negative_controls  # noqa: E402
from offline_pilot import run_pilots  # noqa: E402
from usage_rollup import rollup  # noqa: E402


FIXTURE_EVENTS = [
    {"schemaVersion": "work-lab/observer-event/v2", "usage": {
        "provider": "fixture", "model": "deepseek-v4-flash", "inputTokens": 100,
        "outputTokens": 50, "taskDigest": "a", "observedAt": "2026-08-08T00:00:00Z",
    }},
    {"schemaVersion": "work-lab/observer-event/v2", "usage": {
        "provider": "fixture", "model": "gpt-5.6-terra", "inputTokens": 10,
        "outputTokens": 5, "taskDigest": "b", "observedAt": "2026-08-08T00:00:01Z",
    }},
]


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return ordered[index]


def benchmark(fn: Callable[[], Any], repeats: int = 25) -> dict[str, float]:
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "p50Ms": round(median(samples), 3),
        "p95Ms": round(percentile(samples, 0.95), 3),
        "maxMs": round(max(samples), 3),
        "samples": repeats,
    }


def tracked_tree_stats() -> dict[str, Any]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, text=False, capture_output=True, check=True,
    )
    paths = [Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]
    files = []
    total_bytes = 0
    for path in paths:
        full = ROOT / path
        if full.is_file():
            size = full.stat().st_size
            files.append({"path": path.as_posix(), "bytes": size})
            total_bytes += size
    return {"trackedFiles": len(files), "trackedBytes": total_bytes,
            "pythonFiles": sum(p["path"].endswith(".py") for p in files),
            "nodeModulesTracked": any("node_modules/" in p["path"] for p in files)}


def git_baseline() -> dict[str, str | None]:
    def rev(ref: str) -> str | None:
        result = subprocess.run(["git", "rev-parse", ref], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
        return result.stdout.strip() if result.returncode == 0 else None
    return {"previousCommit": rev("HEAD~1"), "currentCommit": rev("HEAD"),
            "baselineStatus": "COMPARABLE_TO_PARENT_COMMIT" if rev("HEAD~1") else "NOT_AVAILABLE"}


def run_report() -> dict[str, Any]:
    pilot = run_pilots()
    contamination = run_all_negative_controls()
    contract_brief = "# colors\ncolors: #0f172a\n# methods\nmethod: critique\n"
    contract = DesignContractChecker().evaluate(contract_brief)
    aggregate = rollup(FIXTURE_EVENTS + FIXTURE_EVENTS[:1])

    performance = {
        "usageRollup": benchmark(lambda: rollup(FIXTURE_EVENTS + FIXTURE_EVENTS[:1])),
        "designContract": benchmark(lambda: DesignContractChecker().evaluate(contract_brief)),
        "offlinePilot": benchmark(run_pilots),
    }
    return {
        "schemaVersion": "work-lab/regression-report/v1",
        "mode": "LOCAL_OFFLINE_READ_ONLY",
        "baseline": git_baseline(),
        "tree": tracked_tree_stats(),
        "performance": performance,
        "quality": {
            "tokenDedupCount": aggregate["totals"]["count"],
            "tokenDedupExpected": len(FIXTURE_EVENTS),
            "unknownModelCostStatus": rollup([{
                "schemaVersion": "work-lab/observer-event/v2",
                "usage": {"model": "unknown-fixture", "inputTokens": 1, "outputTokens": 1,
                          "observedAt": "2026-08-08T00:00:00Z"},
            }])["byModel"]["unknown-fixture"]["costStatus"],
            "designReadbackLossless": contract["readback"]["lossless"],
            "contaminationControls": len(contamination),
            "observerMutationSurface": pilot["pilots"][1]["mutationSurface"],
        },
        "boundaries": {
            "network": False, "credentials": False, "externalWrites": False,
            "nodeModulesTracked": tracked_tree_stats()["nodeModulesTracked"],
        },
    }
