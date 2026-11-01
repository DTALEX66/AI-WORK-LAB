#!/usr/bin/env python3
"""Measure what the read-only stream costs: sidecar CPU and end-to-end data latency.

Why this exists (W06, plan line "测请求数、CPU 与数据延迟"):

The polling half of W06 is already asserted by tests -- "how many requests" is a
counting question. `CPU` and `end-to-end data latency` are not: they only exist while
a sidecar is actually serving a stream, so they cannot be asserted, they have to be
measured -- and a measurement nobody re-runs decays into a claim. This is the
re-runnable form.

Three things this probe refuses to do, each because it was measured to be wrong here:

1. **Report 0.0% CPU because the instrument is blind.** On this host, sampling a
   CHILD process with `GetProcessTimes` returns a stale value: a helper that
   self-reported 2.0 s of CPU was seen as 0.125 s and frozen (see `instrumentCheck`
   in the output). So before any window is timed, the probe runs a control: a helper
   burns a known amount of its own `process_time()` and the probe samples it the way
   it would sample a sidecar. If the external reading cannot see the known CPU, the
   external sampler is declared unusable and the probe co-hosts the sidecar in its
   own process instead (`time.process_time()`, verified accurate to 1.969 s of a
   2.0 s spin). A number that came from a blind instrument is worse than a gap.
2. **Call a paced number slow.** The canonical watcher polls every 0.25 s while the
   SSE handler wakes on `HEARTBEAT_SECONDS / 2` and pushes what accumulated. A change
   is *detected* in a quarter second and *delivered* on the next tick, so the latency
   below has the tick as its floor. Both constants are read from the source and
   reported next to the samples, so "paced" cannot be mistaken for "slow".
3. **Report a pass for a step that did not run.** CLI exit: 0 MEASURED, 1 FAILED,
   3 INCOMPLETE. A missing frame makes the run INCOMPLETE, never green.

What it does not measure: frontend render cost (the React polling regime needs a real
window; the request-count half is asserted by tests) and collector cost (the sidecar
is started with `--no-worker`, so the number is the stream, not the collectors). Both
are listed in `notMeasured` rather than left blank.

Usage:

    python scripts/audit/observer_stream_cost_probe.py
    python scripts/audit/observer_stream_cost_probe.py --events 12 --idle-seconds 60
    python scripts/audit/observer_stream_cost_probe.py --mode subprocess   # force, even if blind
"""

from __future__ import annotations

import argparse
import ctypes
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "work-lab/observer-stream-cost/v1"

# Repo root: this file is <root>/scripts/audit/<name>.py
ROOT = Path(__file__).resolve().parents[2]

MEASURED = "MEASURED"
INCOMPLETE = "INCOMPLETE"
FAILED = "FAILED"

CONTROL_SPIN_SECONDS = 0.8
CONTROL_TOLERANCE = 0.5  # an external reading that sees less than this share is blind


# --- pure helpers (unit-tested without starting anything) -------------------


def percentiles(samples: list[float]) -> dict[str, float]:
    """min / p50 / p95 / max, nearest-rank.

    Nearest-rank is the honest one at this sample size: an interpolated p95 would be
    a number no run ever produced.
    """
    if not samples:
        raise ValueError("no samples")
    ordered = sorted(samples)

    def pick(fraction: float) -> float:
        index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
        return ordered[index]

    return {"min": ordered[0], "p50": pick(0.5), "p95": pick(0.95), "max": ordered[-1]}


def read_heartbeat_seconds(source: Path) -> float | None:
    """Read HEARTBEAT_SECONDS from sse_hub.py without importing the service.

    Importing would drag the whole orchestration package (and its path setup) into an
    audit that needs one literal. A missing literal returns None, which the report
    shows as null rather than a guessed 15.0.
    """
    try:
        text = source.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^HEARTBEAT_SECONDS\s*=\s*([0-9.]+)\s*$", text, re.MULTILINE)
    return float(match.group(1)) if match else None


def read_poll_seconds(source: Path) -> float | None:
    """The canonical watcher's default interval, read from the signature."""
    try:
        text = source.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"def start_live_updates\(self, interval_seconds: float = ([0-9.]+)\)", text)
    return float(match.group(1)) if match else None


def decide_mode(check: dict[str, Any], requested: str) -> str:
    """`auto` uses the process boundary only while the external sampler can see CPU."""
    if requested != "auto":
        return requested
    return "subprocess" if check.get("externalSamplerUsable") else "inprocess"


def process_cpu_seconds(pid: int) -> float | None:
    """Cumulative CPU seconds of another process, without psutil."""
    if os.name == "nt":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            created = ctypes.c_ulonglong()
            exited = ctypes.c_ulonglong()
            kernel = ctypes.c_ulonglong()
            user = ctypes.c_ulonglong()
            ok = ctypes.windll.kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            )
            if not ok:
                return None
            return (kernel.value + user.value) / 1e7  # 100 ns units
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        ticks = os.sysconf("SC_CLK_TCK")
        return (int(fields[13]) + int(fields[14])) / ticks
    except (OSError, IndexError, ValueError):
        return None


def wait_for_port(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.25)
            if probe.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.05)
    return False


# --- the instrument check ---------------------------------------------------

_CONTROL_SOURCE = (
    "import time\n"
    "t = time.process_time()\n"
    f"while time.process_time() - t < {CONTROL_SPIN_SECONDS}: pass\n"
    "print(round(time.process_time() - t, 4), flush=True)\n"
    "time.sleep(5)\n"
)


def check_external_sampler() -> dict[str, Any]:
    """Can `process_cpu_seconds(pid)` see CPU that a child demonstrably burned?

    This is the whole reason the probe has two modes. Measured 2026-10-18 on the
    authoring host: the helper self-reported 2.0 s while the external reading sat at
    0.125 s -- a sampler that would have reported every window as "0.0%, free".
    """
    started = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, "-c", _CONTROL_SOURCE],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        # Declared, not inherited: on a cp936 host a child that prints non-ASCII kills the reader thread
        # and the stream comes back None (ERR-211), which here would read as "the sampler saw nothing"
        # and silently downgrade every CPU window to a fabricated 0.0%.
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        before = process_cpu_seconds(process.pid)
        # Let the child finish its spin, then read the same process again.
        time.sleep(CONTROL_SPIN_SECONDS + 0.4)
        after = process_cpu_seconds(process.pid)
        output = process.stdout.readline().strip() if process.stdout else ""
        try:
            self_reported = float(output)
        except ValueError:
            self_reported = None
    finally:
        process.kill()
        process.wait(timeout=5)

    observed = None if before is None or after is None else after - before
    usable = bool(
        self_reported
        and observed is not None
        and observed >= self_reported * CONTROL_TOLERANCE
    )
    return {
        "control": "child spins on time.process_time(), parent samples externally",
        "childSelfReportedSeconds": self_reported,
        "externalObservedSeconds": None if observed is None else round(observed, 4),
        "tolerance": CONTROL_TOLERANCE,
        "externalSamplerUsable": usable,
        "reason": None if usable else (
            "the external reading is smaller than half of what the child measured for itself; "
            "per-process CPU accounting is stale here, so windows timed that way would read 0.0%"
        ),
        "seconds": round(time.monotonic() - started, 3),
    }


# --- the SSE consumer -------------------------------------------------------


class StreamReader:
    """Read SSE frames off a loopback connection and timestamp each revision."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._lock = threading.Lock()
        self._arrivals: dict[int, float] = {}
        self._closed = threading.Event()
        self._error: str | None = None
        self._thread: threading.Thread | None = None

    def start(self, timeout: float = 10.0) -> None:
        self._thread = threading.Thread(target=self._run, name="sse-reader", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not self._arrivals and self._error is None:
            time.sleep(0.02)

    def _run(self) -> None:
        connection = http.client.HTTPConnection(self._host, self._port, timeout=60)
        try:
            connection.request("GET", "/api/v1/events", headers={"Accept": "text/event-stream"})
            response = connection.getresponse()
            if response.status != 200:
                self._error = f"events_status_{response.status}"
                return
            memo: dict[str, Any] = {}
            while not self._closed.is_set():
                raw = response.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if not line:
                    if "id" in memo:  # blank line terminates a frame
                        self._record(memo.get("id"))
                    memo = {}
                    continue
                field, _, value = line.partition(":")
                memo[field] = value.strip()
        except Exception as exc:  # a socket closed at shutdown is not a failure
            if not self._closed.is_set():
                self._error = f"{type(exc).__name__}: {exc}"
        finally:
            connection.close()

    def _record(self, raw_id: Any) -> None:
        try:
            revision = int(str(raw_id))
        except (TypeError, ValueError):
            return
        with self._lock:
            self._arrivals.setdefault(revision, time.monotonic())

    def revision_baseline(self) -> int:
        with self._lock:
            return max(self._arrivals, default=0)

    def wait_after(self, revision: int, timeout: float) -> tuple[int, float] | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                newer = sorted(r for r in self._arrivals if r > revision)
                if newer:
                    return newer[0], self._arrivals[newer[0]]
            if self._error:
                return None
            time.sleep(0.01)
        return None

    def stop(self) -> None:
        self._closed.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    @property
    def error(self) -> str | None:
        return self._error


# --- launching the sidecar --------------------------------------------------


class Sidecar:
    """Either a separate process (canonical) or co-hosted in this one (fallback)."""

    def __init__(self, runtime_root: Path, mode: str) -> None:
        self.runtime_root = runtime_root
        self.mode = mode
        self.port: int | None = None
        self.process: subprocess.Popen[str] | None = None
        self._server: Any = None
        self._thread: threading.Thread | None = None
        self._sidecar: Any = None

    def start(self, timeout: float) -> None:
        if self.mode == "subprocess":
            self._start_subprocess(timeout)
        else:
            self._start_inprocess()
        if self.port is None or not wait_for_port("127.0.0.1", self.port, timeout=10.0):
            raise RuntimeError("sidecar_port_not_reachable")

    def _start_subprocess(self, timeout: float) -> None:
        command = [
            sys.executable,
            str(ROOT / "services" / "orchestration" / "sidecar.py"),
            "--project-root", str(ROOT),
            "--runtime-root", str(self.runtime_root),
            "--host", "127.0.0.1",
            "--port", "0",
            "--no-worker",
        ]
        self.process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
        )
        assert self.process.stdout is not None
        ready = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.process.stdout.readline()
            if not line:
                break
            ready += line
            if "WORKFLOW_SIDECAR_READY" in line:
                break
        match = re.search(r"WORKFLOW_SIDECAR_READY url=http://[^:]+:(\d+)", ready)
        if not match:
            raise RuntimeError("sidecar_not_ready: " + ready.strip()[:400])
        self.port = int(match.group(1))

    def _start_inprocess(self) -> None:
        orchestration = ROOT / "services" / "orchestration"
        if str(orchestration) not in sys.path:
            sys.path.insert(0, str(orchestration))
        # `sidecar` first: its module prelude is what puts the other module roots on
        # sys.path. Importing `composition_root` first fails on canonical_store -- the
        # same ordering trap that made the documented CLI un-runnable (fixed 2026-10-18).
        from sidecar import WorkflowSidecar, create_server  # noqa: PLC0415
        from composition_root import build_v3_snapshot  # noqa: F401,PLC0415 - imported to prove the roots resolve

        self._sidecar = WorkflowSidecar(ROOT, self.runtime_root)
        self._server = create_server(self._sidecar, "127.0.0.1", 0, live_updates=True)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, name="sidecar-serve", daemon=True)
        self._thread.start()

    def cpu_seconds(self) -> float | None:
        if self.mode == "subprocess":
            assert self.process is not None
            return process_cpu_seconds(self.process.pid)
        return time.process_time()

    def describe(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "port": self.port,
            "pid": self.process.pid if self.process else os.getpid(),
            "liveUpdates": True,
            "worker": "disabled",
            "cpuSource": "GetProcessTimes on the child" if self.mode == "subprocess" else "time.process_time() in a shared process",
        }

    def stop(self) -> None:
        if self.mode == "subprocess":
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            if self.process is not None and self.process.stdout is not None:
                self.process.stdout.close()
            return
        try:
            if self._server is not None:
                self._server.shutdown()
                self._server.server_close()
        except Exception:
            pass
        try:
            if self._sidecar is not None:
                self._sidecar.stop_worker()
                self._sidecar.close()
        except Exception:
            pass


# --- windows ----------------------------------------------------------------


def cpu_window(cpu: Callable[[], float | None], seconds: float) -> dict[str, Any]:
    """CPU percent of one core over a wall window."""
    before = cpu()
    started = time.monotonic()
    time.sleep(seconds)
    after = cpu()
    elapsed = time.monotonic() - started
    if before is None or after is None:
        return {"seconds": round(elapsed, 3), "percentOfOneCore": None, "reason": "cpu_time_unavailable"}
    return {
        "seconds": round(elapsed, 3),
        "cpuSeconds": round(after - before, 4),
        "percentOfOneCore": round((after - before) / elapsed * 100.0, 2),
    }


# --- the probe --------------------------------------------------------------


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    report: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": sys.platform,
        "parameters": {
            "events": args.events,
            "idleSeconds": args.idle_seconds,
            "streamIdleSeconds": args.stream_idle_seconds,
            "gapSeconds": args.gap_seconds,
            "mode": args.mode,
        },
        "steps": [],
        "notMeasured": [
            "frontend render cost (needs a real window; W06's request-count half is asserted by tests)",
            "collector cost (started with --no-worker: the number is the stream, not the collectors)",
        ],
        "verdict": INCOMPLETE,
    }

    def step(name: str, verdict: str, detail: Any = None) -> None:
        report["steps"].append({"step": name, "verdict": verdict, "detail": detail})

    heartbeat = read_heartbeat_seconds(ROOT / "services" / "orchestration" / "sse_hub.py")
    poll = read_poll_seconds(ROOT / "services" / "orchestration" / "sidecar.py")
    report["decomposition"] = {
        "canonicalWatcherPollSeconds": poll,
        "ssePushTickSeconds": (heartbeat / 2.0) if heartbeat else None,
        "heartbeatSeconds": heartbeat,
        "note": (
            "a write is DETECTED within one watcher poll and DELIVERED on the next push tick; "
            "the latency below is detection+delivery, and the tick is the floor, not a regression"
        ),
    }

    check = check_external_sampler()
    report["instrumentCheck"] = check
    mode = decide_mode(check, args.mode)
    report["effectiveMode"] = mode
    step("instrument_check", INCOMPLETE if not check["externalSamplerUsable"] else MEASURED, check)

    runtime_root = Path(
        args.runtime_root or tempfile.mkdtemp(prefix="stream-cost-", dir=_temp_parent())
    ).resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)

    sidecar: Sidecar | None = None
    reader: StreamReader | None = None
    store = None
    try:
        sidecar = Sidecar(runtime_root, mode)
        try:
            sidecar.start(args.startup_timeout)
        except Exception as error:
            step("start_sidecar", FAILED, {"error": str(error)})
            report["verdict"] = FAILED
            return report, 1
        report["sidecar"] = sidecar.describe()
        report["cpuAttribution"] = (
            "process CPU of the child sidecar only"
            if mode == "subprocess"
            else (
                "process CPU shared with this probe: the idle window has no probe threads running, "
                "so it is the cleanest sidecar figure; the stream window adds the probe's reader thread "
                "and the one-off first snapshot the server renders; the write window adds the probe's "
                "own canonical writes (the writer's cost, not the sidecar's)"
            )
        )
        step("start_sidecar", MEASURED, report["sidecar"])

        # Window 1: nobody consuming. The watcher still polls canonical.
        report["cpuIdle"] = cpu_window(sidecar.cpu_seconds, args.idle_seconds)
        step("cpu_idle_no_consumer", MEASURED if report["cpuIdle"].get("percentOfOneCore") is not None else INCOMPLETE)

        # Window 2: a consumer attached, nothing changing.
        reader = StreamReader("127.0.0.1", sidecar.port)
        reader.start(timeout=10.0)
        if reader.error:
            step("open_stream", FAILED, {"error": reader.error})
            report["verdict"] = FAILED
            return report, 1
        baseline = reader.revision_baseline()
        report["stream"] = {"baselineRevision": baseline, "framesBeforeWrites": baseline}
        step("open_stream", MEASURED, {"baselineRevision": baseline})
        report["cpuStreamIdle"] = cpu_window(sidecar.cpu_seconds, args.stream_idle_seconds)
        step("cpu_stream_idle", MEASURED if report["cpuStreamIdle"].get("percentOfOneCore") is not None else INCOMPLETE)

        # Window 3: writes that a consumer can see. The store is a SECOND connection
        # on purpose -- the latency includes the crossing from writer to sidecar.
        sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
        from canonical_store import CanonicalStore  # noqa: PLC0415 - path is set one line up

        store = CanonicalStore(runtime_root / "canonical.sqlite")
        samples: list[float] = []
        missing: list[int] = []
        cpu_before = sidecar.cpu_seconds()
        wall_before = time.monotonic()
        previous = reader.revision_baseline()
        for index in range(args.events):
            marker = f"stream-cost-{os.getpid()}-{index}-{time.time_ns()}"
            store.append_telemetry({
                "event_id": marker,
                "project_id": "work-lab",
                "producer": "observer-stream-cost-probe",
                "kind": "probe_marker",
                "payload": {"marker": marker},
            })
            committed = time.monotonic()
            observed = reader.wait_after(previous, timeout=args.event_timeout)
            if observed is None:
                missing.append(index)
            else:
                revision, arrived = observed
                samples.append(arrived - committed)
                previous = revision
            if index + 1 < args.events:
                time.sleep(args.gap_seconds)
        wall_after = time.monotonic()
        cpu_after = sidecar.cpu_seconds()

        report["events"] = {"requested": args.events, "observed": len(samples), "missing": missing}
        report["latencySeconds"] = (
            {**percentiles(samples), "samples": [round(value, 4) for value in samples]}
            if samples else None
        )
        if cpu_before is not None and cpu_after is not None and wall_after > wall_before:
            report["cpuUnderWrites"] = {
                "seconds": round(wall_after - wall_before, 3),
                "cpuSeconds": round(cpu_after - cpu_before, 4),
                "percentOfOneCore": round((cpu_after - cpu_before) / (wall_after - wall_before) * 100.0, 2),
                "writesPerSecond": round(args.events / (wall_after - wall_before), 3),
            }
        else:
            report["cpuUnderWrites"] = {"percentOfOneCore": None, "reason": "cpu_time_unavailable"}

        cpu_reported = all(
            (report.get(key) or {}).get("percentOfOneCore") is not None
            for key in ("cpuIdle", "cpuStreamIdle", "cpuUnderWrites")
        )
        if missing:
            step("deliver_writes", INCOMPLETE, {"missingEventIndexes": missing})
            report["verdict"] = INCOMPLETE
            return report, 3
        if not cpu_reported:
            step("deliver_writes", MEASURED, report["latencySeconds"])
            step("cpu_windows", INCOMPLETE, {"reason": "no CPU figure was measurable"})
            report["verdict"] = INCOMPLETE
            return report, 3
        step("deliver_writes", MEASURED, report["latencySeconds"])
        step("cpu_windows", MEASURED)
        report["verdict"] = MEASURED
        return report, 0
    finally:
        if reader is not None:
            reader.stop()
        if store is not None:
            try:
                store.close()
            except Exception:
                pass
        if sidecar is not None:
            sidecar.stop()
        if args.keep_runtime:
            report["runtimeRoot"] = str(runtime_root)
        else:
            shutil.rmtree(runtime_root, ignore_errors=True)


def _temp_parent() -> str:
    """Temp roots stay inside the project (AGENTS.md data boundary)."""
    candidate = ROOT / ".project-local" / "runs" / "tmp"
    return str(candidate) if candidate.is_dir() else tempfile.gettempdir()


def summarise(report: dict[str, Any]) -> str:
    lines = [f"OBSERVER_STREAM_COST_{report['verdict']}"]
    check = report.get("instrumentCheck") or {}
    if not check.get("externalSamplerUsable"):
        lines.append(
            f"  instrument: external sampler BLIND "
            f"(child said {check.get('childSelfReportedSeconds')}s, external saw "
            f"{check.get('externalObservedSeconds')}s) -> mode={report.get('effectiveMode')}"
        )
    decomposition = report.get("decomposition") or {}
    if decomposition.get("ssePushTickSeconds") is not None:
        lines.append(
            f"  pacing poll={decomposition.get('canonicalWatcherPollSeconds')}s "
            f"push_tick={decomposition.get('ssePushTickSeconds')}s (latency floor is the tick)"
        )
    for label, key in (
        ("idle (no consumer)", "cpuIdle"),
        ("stream idle       ", "cpuStreamIdle"),
        ("under writes      ", "cpuUnderWrites"),
    ):
        window = report.get(key) or {}
        percent = window.get("percentOfOneCore")
        if percent is None:
            lines.append(f"  cpu {label} NOT_MEASURED ({window.get('reason', 'unknown')})")
        else:
            lines.append(f"  cpu {label} {percent}% of one core over {window.get('seconds')}s")
    latency = report.get("latencySeconds")
    events = report.get("events") or {}
    if latency:
        lines.append(
            f"  latency n={events.get('observed')} min={latency['min']:.3f}s "
            f"p50={latency['p50']:.3f}s p95={latency['p95']:.3f}s max={latency['max']:.3f}s"
        )
    if events.get("missing"):
        lines.append(f"  MISSING events={events['missing']}")
    for item in report.get("notMeasured") or []:
        lines.append(f"  NOT MEASURED: {item}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("auto", "inprocess", "subprocess"), default="auto",
                        help="auto: use a separate process only while the external CPU sampler is trustworthy")
    parser.add_argument("--runtime-root", type=Path, default=None,
                        help="reuse an explicit runtime root instead of a temp one")
    parser.add_argument("--json-out", type=Path,
                        default=ROOT / ".project-local" / "artifacts" / "observer-stream-cost.json")
    parser.add_argument("--events", type=int, default=10)
    parser.add_argument("--idle-seconds", type=float, default=45.0)
    parser.add_argument("--stream-idle-seconds", type=float, default=30.0)
    parser.add_argument("--gap-seconds", type=float, default=1.0)
    parser.add_argument("--event-timeout", type=float, default=30.0)
    parser.add_argument("--startup-timeout", type=float, default=45.0)
    parser.add_argument("--keep-runtime", action="store_true")
    args = parser.parse_args(argv)

    report, exit_code = run(args)
    print(summarise(report))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OBSERVER_STREAM_COST_RECORD={args.json_out}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
