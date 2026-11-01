#!/usr/bin/env python
"""Re-measure every WUI render artifact against the bundle that exists right now, then seal.

Why this is a tracked script and not something typed at a prompt: the evidence set for the Observer UI is
seven instruments' worth of receipts, and a rebuild silently invalidates all of them (found 2026-10-10,
ERR-234). "Re-measure everything" has to be one reproducible command that the next agent can run at a new
commit, with the same boundary rules, or it will be done partially and quoted as if it were whole.

Rules this script obeys:
  * it reports each step's own exit code and never rewrites a red into a pass; the SSE falsification step
    EXPECTS exit 1 -- that is its control running, not a failure -- and any other exit there is a failure;
  * the display-scaling step used to end red on this machine: the shipped HUD (440x780, not resizable)
    needed 880x1560 physical at 200% DPI against a measured work area of 2560x1392. That owner decision was
    settled on 2026-10-13 by shrinking the declared panel to 440x680 (1360 physical at 200%), so the step is
    now expected to PASS; if it goes red again, that is a new finding, not the known limit;
  * a step that cannot run (no browser) is reported as NOT_RUN with its exit code, not swallowed;
  * everything stays inside the repository: the store the capture reads is a fresh one under
    `.project-local/runs/`, and the receipts land in `.project-local/artifacts/wui-20261009/`.

usage: python scripts/audit/reseal_wui_evidence.py [--only STEP]
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
ARTIFACTS = ROOT / ".project-local" / "artifacts" / "wui-20261009"
LOGS = ROOT / ".project-local" / "runs" / "wui-20261009"

MODULE_PYTHONPATH = ";".join([
    str(ROOT / "services" / "authority"), str(ROOT / "services" / "orchestration"),
    str(ROOT / "services" / "policy"), str(ROOT / "services" / "receipts"),
    str(ROOT / "packages" / "client-neutral-core" / "scripts"),
    str(ROOT / "packages" / "client-neutral-core" / "bin"),
])


def base_env() -> dict[str, str]:
    """The parent's own environment plus the module roots, not a rebuilt one.

    A hand-written env loses PATH, TEMP and SYSTEMROOT, and a Chrome or git lookup that fails for that
    reason reports itself as "browser not found" -- a fake zero about the product.
    """
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{MODULE_PYTHONPATH}{os.pathsep}{existing}" if existing else MODULE_PYTHONPATH
    env["PYTHONIOENCODING"] = "utf-8"
    return env

# (name, argv, expected exit). An expected exit of 1 means the step is a control that must fire.
STEPS = [
    ("slice-capture", None, 0),
    ("geometry", ["scripts/audit/topbar_geometry_via_cdp.py",
                  "--json-out", str(ARTIFACTS / "geometry-freshbundle.json")], 0),
    ("legibility-all-views", ["scripts/audit/text_legibility_via_cdp.py", "--all-views",
                             "--json-out", str(ARTIFACTS / "legibility-allviews-fresh.json")], 0),
    # The static preview collapses every lane to the offline panel, so it measures shell typography only.
    # This step is the one that reaches each lane's own surface -- and the pills.
    ("legibility-live-views", ["scripts/audit/text_legibility_via_cdp.py", "--all-views", "--live-backend",
                               "--json-out", str(ARTIFACTS / "legibility-live-views.json")], 0),
    ("legibility-dpi-widths", ["scripts/audit/text_legibility_via_cdp.py", "--all-views",
                               "--sizes", "2048,1706",
                               "--json-out", str(ARTIFACTS / "legibility-dpi-widths.json")], 0),
    ("legibility-1440", ["scripts/audit/text_legibility_via_cdp.py", "--all-views",
                         "--sizes", "1440",
                         "--json-out", str(ARTIFACTS / "legibility-1440.json")], 0),
    ("display-scaling", ["scripts/audit/display_scaling_via_cdp.py"], 0),
    ("sse-revision", ["scripts/audit/sse_revision_via_cdp.py"], 0),
    ("sse-falsification", ["scripts/audit/sse_revision_via_cdp.py", "--revisions", "7,9,10",
                           "--json-out", str(ARTIFACTS / "sse-revision-falsify.json")], 1),
    # The seal is told which set to seal instead of inheriting a default: the receipt directory is a
    # location this script owns, while the seal's identity comes from the bytes and the commit it just
    # measured (see seal_wui_evidence.py).
    ("seal", ["scripts/audit/seal_wui_evidence.py", "--write",
              "--artifacts-dir", str(ARTIFACTS)], 0),
]


def run(name: str, argv: list[str], expect: int, env_extra: dict[str, str] | None = None) -> dict:
    log = LOGS / f"reseal-{name}.log"
    LOGS.mkdir(parents=True, exist_ok=True)
    env = base_env()
    env.update(env_extra or {})
    started = time.time()
    result = subprocess.run([PY, *argv], cwd=ROOT, capture_output=True, env=env, check=False)
    text = (result.stdout + result.stderr).decode("utf-8", "replace")
    log.write_text(f"$ {' '.join(argv)}\nexit={result.returncode} seconds={time.time() - started:.1f}\n\n{text}",
                   encoding="utf-8", errors="replace")
    outcome = "PASS" if result.returncode == expect else ("CONTROL_STAYED_GREEN" if expect == 1 else "RED")
    tail = [line for line in text.splitlines() if line.strip()][-1:] or ["<no output>"]
    print(f"STEP {name} exit={result.returncode} expect={expect} {outcome} :: {tail[0][:150]}", flush=True)
    return {"step": name, "exit": result.returncode, "expectedExit": expect,
            "outcome": outcome, "log": str(log), "seconds": round(time.time() - started, 1)}


def start_sidecar() -> tuple[subprocess.Popen, str, dict]:
    """Boot the read-only sidecar on an ephemeral port with a fresh canonical store, worker off."""
    store = ROOT / ".project-local" / "runs" / f"wui-slice-store-{time.strftime('%Y%m%d%H%M%S')}"
    env = base_env()
    proc = subprocess.Popen(
        [PY, "services/orchestration/sidecar.py", "--project-root", str(ROOT),
         "--runtime-root", str(store), "--port", "0", "--no-worker"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    assert proc.stdout is not None
    deadline = time.time() + 40
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        text = line.decode("utf-8", "replace").strip()
        if "WORKFLOW_SIDECAR_READY" in text:
            url = text.split("url=", 1)[1].split()[0]
            return proc, url, {"store": str(store), "readyLine": text}
        if "Traceback" in text:
            break
    remainder = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
    proc.kill()
    raise SystemExit(f"RESEAL_NOT_RUN sidecar did not become ready:\n{remainder[:800]}")


def main() -> int:
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    sidecar: subprocess.Popen | None = None
    url = ""
    try:
        for name, argv, expect in STEPS:
            if only and name != only:
                continue
            if name == "slice-capture":
                sidecar, url, facts = start_sidecar()
                print(f"SIDECAR {facts['readyLine']} store={facts['store']}", flush=True)
                results.append(run(name, ["scripts/audit/wui_slice_capture.py", url], expect))
                continue
            if argv is None:
                continue
            results.append(run(name, argv, expect))
    finally:
        if sidecar is not None:
            sidecar.kill()
            sidecar.wait(timeout=10)
            print("SIDECAR_STOPPED", flush=True)

    bad = [r for r in results if r["outcome"] != "PASS"]
    print(f"RESEAL_ALL steps={len(results)} red={len(bad)} "
          f"details={[r['step'] + ':' + r['outcome'] for r in bad]}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
