# SPDX-License-Identifier: MIT
"""Build a wheel for AI-WORK-LAB and install it into an isolated directory, offline.

Audit defect F06: the repository had no PEP 621 metadata, so

    python -m pip install --no-index --no-deps --no-build-isolation --target <dir> <ROOT>

answered "Directory ... is not installable" (exit 1). This script is the build half
of the fix; ``scripts/verify_isolated_install.py`` is the proof half.

Offline rules this script obeys, and records evidence for:

* every pip invocation carries ``--no-index`` (and ``--isolated``, so the machine's
  configured index URLs -- ``global.index-url`` / ``global.extra-index-url`` -- are
  not consulted at all). Nothing here edits pip config, and nothing writes to
  ``~/.pip``;
* no ``pip download``, no dependency resolution (``--no-deps``), no upgrade, and no
  write to any environment outside ``.project-local/build/<run>/``;
* the project ``.venv`` has no ``setuptools``, so the build step borrows a
  setuptools tree that already exists on this machine by putting it on
  ``PYTHONPATH`` for the BUILD ONLY. That is deliberate and bounded: pip is run with
  ``--no-build-isolation`` (otherwise it would try to fetch setuptools from the
  index) and with ``-B`` (so no ``__pycache__`` is written into the borrowed tree).
  The INSTALL step pops ``PYTHONPATH`` entirely.

Failure is reported as failure: a non-zero exit code from any step stops the run,
the step's stderr is kept verbatim in the JSON record, and the script exits 1. A
missing build backend is a real gap and is written up as ``BLOCKED`` with the
minimal path to close it -- never as "skipped" and never as exit 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = SOURCE_ROOT / ".project-local" / "build"

# Directories a wheel build actually needs, copied out of the checkout so the
# build never writes into the source tree (setuptools drops *.egg-info/ and build/
# next to the project it builds). `design-lab` is here because pyproject maps
# design_lab.resources.reconstruction onto design-lab/schemas/reconstruction, so
# those committed schemas are build input even though the directory is not a
# Python package and is never installed under that name.
#
# `config`, `vendor` and `research` joined that list in this run, each for a
# package-dir mapping the first build could not satisfy from the staged copy:
#   config      -> the WORK registries that domains/work/** resolves against the
#                  repository root (composition_root.py:65, orchestration/
#                  resources.py:31-32, snapshot_validator.py:74)
#   vendor      -> design_lab.resources.capability-library.vendor
#   research    -> ...capability-library.research.candidates
#                  (analysis/capability_library.py:27-30 plus its packaged branch at
#                  line 222; measured in this run as /api/capabilities answering 503
#                  from the install against 200 from the checkout)
STAGE_INCLUDES = ("backend", "domains", "packages", "migration", "design-lab", "apps",
                  "config", "vendor", "research")
STAGE_FILES = ("pyproject.toml",)
STAGE_PRUNE_DIRS = {"__pycache__", ".mimosa", "node_modules", ".pytest_cache", ".venv"}

# Setuptools trees that already exist on this machine. Searched in order; the
# first one that really contains setuptools/__init__.py wins. Nothing is
# downloaded and nothing is copied into these roots.
SETUPTOOLS_CANDIDATES = (
    Path(os.environ.get("AI_WORK_LAB_SETUPTOOLS_ROOT", ""))
    if os.environ.get("AI_WORK_LAB_SETUPTOOLS_ROOT") else None,
    Path(r"D:\All projects\OS External Configuration\ArcheAxis-Knowledge-OS-ci-venv"
         r"\Lib\site-packages"),
)

# Global pip switches. ``--isolated`` makes pip ignore this machine's configured
# index URLs, and every network-capable subcommand additionally gets an explicit
# ``--no-index`` -- the requirement is per-command, not per-environment.
PIP_GLOBAL = ["--disable-pip-version-check", "--isolated"]
PIP_OFFLINE = ["--no-index"]
# ``pip config list`` is recorded WITHOUT --isolated: --isolated suppresses exactly
# the configuration the record is supposed to show, so the first version of this
# script printed an empty string before and after and called that proof. Reading the
# config is offline and side-effect free; the switch only matters for commands that
# could resolve or download.
PIP_CONFIG_READ = ["--disable-pip-version-check"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def run(cmd: list[str], cwd: Path, env: dict[str, str], *, label: str,
        record: dict, echo_stdout: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True,
                          encoding="utf-8", errors="replace",
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    record["steps"].append({
        "label": label,
        "command": cmd,
        "cwd": str(cwd),
        "exit_code": proc.returncode,
        "env_pythonpath": env.get("PYTHONPATH"),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "start": now(),
    })
    stream = sys.stdout if proc.returncode == 0 else sys.stderr
    print(f"[{label}] exit={proc.returncode}", file=stream, flush=True)
    # echo_stdout=False is for steps whose output can contain a configured
    # credential (pip config list); the record is redacted separately.
    if proc.stdout and echo_stdout:
        print(proc.stdout.rstrip(), file=stream, flush=True)
    if proc.stderr:
        print(proc.stderr.rstrip(), file=stream, flush=True)
    return proc


def stage_source(run_dir: Path) -> tuple[Path, list[str]]:
    """Copy only what the wheel needs, so a build cannot write into the checkout."""
    src = run_dir / "src"
    if src.exists():
        shutil.rmtree(src)
    src.mkdir(parents=True)
    for name in STAGE_FILES:
        origin = SOURCE_ROOT / name
        if not origin.is_file():
            raise SystemExit(f"FATAL: {name} is missing from {SOURCE_ROOT}")
        shutil.copy2(origin, src / name)
    absent: list[str] = []
    for name in STAGE_INCLUDES:
        origin = SOURCE_ROOT / name
        if not origin.is_dir():
            # A directory a package-dir mapping points at is build input: skipping it
            # silently would produce a wheel that installs and then answers MISSING,
            # so the absence is returned and written into the record.
            absent.append(name)
            continue
        shutil.copytree(origin, src / name,
                        ignore=shutil.ignore_patterns(*sorted(STAGE_PRUNE_DIRS)))
    return src, absent


def interpreter_version(python: Path) -> str:
    proc = subprocess.run([str(python), "-B", "-c", "import sys;print(sys.version)"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.stdout.strip() or "UNKNOWN"


def find_setuptools_root(python: Path) -> tuple[Path | None, str]:
    probe = subprocess.run(
        [str(python), "-B", "-c", "import setuptools,sys;print(setuptools.__version__)"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if probe.returncode == 0:
        return None, f"importable without PYTHONPATH (setuptools {probe.stdout.strip()})"
    for candidate in SETUPTOOLS_CANDIDATES:
        if candidate and (candidate / "setuptools" / "__init__.py").is_file():
            return candidate, "not importable from the interpreter alone; borrowed tree used"
    return None, ("not importable and no local setuptools tree found in "
                  + ", ".join(str(c) for c in SETUPTOOLS_CANDIDATES if c))


def wheel_inventory(wheel: Path) -> dict:
    """What the wheel really carries, read out of the archive itself."""
    out: dict = {"name": wheel.name, "bytes": wheel.stat().st_size,
                 "sha256": sha256_file(wheel)}
    with zipfile.ZipFile(wheel) as archive:
        names = [n.replace("\\", "/") for n in archive.namelist()]
    packs: set[str] = set()
    resources = 0
    for name in names:
        if name.startswith("design_lab/resources/") and not name.endswith("/"):
            resources += 1
            # design_lab/resources/repo/design-lab/domain-packs/<pack>/...
            # len(parts) >= 7 keeps DOMAIN_PACK_SPEC_V2.md (a file, not a pack) out.
            parts = name.split("/")
            if len(parts) >= 7 and parts[3] == "design-lab" and parts[4] == "domain-packs":
                packs.add(parts[5])
    out["entries"] = len(names)
    out["design_lab_resource_files"] = resources
    out["domain_pack_directories"] = sorted(packs)
    out["domain_pack_directory_count"] = len(packs)
    out["has_domain_pack_manifests"] = sum(
        1 for name in names
        if name.startswith("design_lab/resources/repo/design-lab/domain-packs/")
        and name.endswith("/manifest.json"))
    out["has_assistance_plan_revision_schema"] = (
        "design_lab/resources/repo/design-lab/schemas/assistance-plan-revision-v1.schema.json"
        in names)
    out["has_reconstruction_ir_schema"] = (
        "design_lab/resources/reconstruction/reconstruction-ir.schema.json" in names)
    out["has_reconstruction_run_schema"] = (
        "design_lab/resources/reconstruction/reconstruction-run.schema.json" in names)
    out["has_orchestration_package"] = any(
        n.startswith("domains/work/orchestration/") for n in names)
    out["workbench_files"] = sorted(n for n in names
                                    if n.startswith("design_lab/resources/workbench/"))
    out["adobe_bridge_files"] = sorted(n for n in names
                                       if n.startswith("design_lab/resources/adobe/"))
    out["has_control_operation_contract"] = (
        "packages/contracts/schemas/workflow/control-operation.schema.json" in names)
    # Added in this run: the two asset groups the first build silently dropped. The
    # WORK registries are read at <install>/config/... by four call sites in
    # domains/work/**, and the capability-library files are the packaged branch of
    # analysis/capability_library.py:222. Counting them here is what makes a
    # regression visible in the build record instead of only in an HTTP 503.
    out["config_registry_files"] = sorted(n for n in names
                                          if n.startswith("config/") and n.endswith(".json"))
    out["config_registry_count"] = len(out["config_registry_files"])
    out["capability_library_files"] = sorted(
        n for n in names if n.startswith("design_lab/resources/capability-library/"))
    out["has_migration_mapping_csv"] = "migration/mapping.csv" in names
    out["has_state_sql"] = sum(1 for name in names
                               if name.startswith("design_lab/resources/state/")
                               and name.endswith(".sql"))
    out["top_level_dirs"] = sorted({n.split("/")[0] for n in names if n.split("/")[0]
                                    not in ("backend", "domains", "design_lab")})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-id", default=time.strftime("offline-%Y%m%dT%H%M%SZ"))
    parser.add_argument("--python", default=sys.executable,
                        help="interpreter that carries pip (the project .venv by default)")
    parser.add_argument("--setuptools-root", default=None,
                        help="directory containing a setuptools tree to borrow for the build")
    args = parser.parse_args(argv)

    python = Path(args.python).resolve()
    run_dir = BUILD_ROOT / args.run_id
    dist = run_dir / "dist"
    isolated = run_dir / "isolated"
    for path in (dist, isolated):
        path.mkdir(parents=True, exist_ok=True)

    record: dict = {
        "purpose": "offline wheel build + isolated install (audit F06)",
        "run_dir": str(run_dir),
        "source_root": str(SOURCE_ROOT),
        "status": "IN_PROGRESS",
        "os": {"system": platform.system(), "release": platform.release(),
               "machine": platform.machine(), "python_version": interpreter_version(python)},
        "interpreter": {"path": str(python),
                        "exists": python.is_file(),
                        "version": interpreter_version(python)},
        "steps": [],
        "artifacts": {},
        "gaps": [],
    }
    report_path = run_dir / "build-report.json"
    record["report_path"] = str(report_path)

    base_env = dict(os.environ)
    base_env.pop("PYTHONPATH", None)
    base_env["PYTHONNOUSERSITE"] = "1"
    base_env["PYTHONUTF8"] = "1"

    def write_report() -> None:
        report_path.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                               encoding="utf-8")

    if not python.is_file():
        record["status"] = "FAIL"
        record["gaps"].append(f"interpreter not found: {python}")
        write_report()
        print(f"FATAL: interpreter not found: {python}", file=sys.stderr)
        return 1

    # 1. Environment before anything runs. `global.index-url` / `extra-index-url` are
    #    read WITHOUT --isolated (see PIP_CONFIG_READ) so the record can show what the
    #    machine really is configured with, and only the setting NAMES are kept: a
    #    value can be an authenticated index URL, and this script must not copy a
    #    credential into a build artifact. Nothing here edits pip config, and nothing
    #    writes to ~/.pip.
    def redact(step_label: str) -> dict:
        step = next(s for s in record["steps"] if s["label"] == step_label)
        lines = [l for l in (step["stdout"] or "").splitlines() if l.strip()]
        names = sorted({line.split("=", 1)[0].strip() for line in lines if "=" in line})
        # The raw stdout never survives into the report: run() captured it verbatim,
        # and a configured index URL can carry a token.
        step["stdout"] = "<redacted: %d line(s), setting names only>" % len(lines)
        return {"setting_names": names, "lines": len(lines),
                "values_redacted": True, "exit_code": step["exit_code"]}

    run([str(python), "-B", "-m", "pip", *PIP_CONFIG_READ, "config", "list"],
        cwd=run_dir, env=base_env, label="pip-config-before", record=record,
        echo_stdout=False)
    record["pip_config_before"] = redact("pip-config-before")
    run([str(python), "-B", "-m", "pip", *PIP_GLOBAL, "--version"],
        cwd=run_dir, env=base_env, label="pip-version", record=record)

    # 2. Where does setuptools for the build backend come from?
    borrowed, note = find_setuptools_root(python)
    if args.setuptools_root:
        candidate = Path(args.setuptools_root).resolve()
        if (candidate / "setuptools" / "__init__.py").is_file():
            borrowed, note = candidate, "explicit --setuptools-root"
    record["build_backend"] = {"note": note,
                               "borrowed_setuptools_root": str(borrowed) if borrowed else None}
    print(f"[build-backend] {note}: {borrowed}", flush=True)

    build_env = dict(base_env)
    if borrowed is not None:
        build_env["PYTHONPATH"] = str(borrowed)

    if borrowed is None and "importable" not in note:
        record["status"] = "BLOCKED"
        record["gaps"].append(
            "no setuptools available offline: the project .venv has none and no local "
            "setuptools tree was found. Minimal fix: point --setuptools-root at a "
            "directory containing setuptools>=68 (pure-python, copyable), or add "
            "setuptools to a venv from a local wheel. Not fixed by reaching online here.")
        write_report()
        print("BLOCKED: no offline setuptools for the build backend", file=sys.stderr)
        return 1

    # 3. Stage, then build the wheel from the staged copy.
    src, absent_stage_includes = stage_source(run_dir)
    record["staged_source"] = {"path": str(src), "includes": list(STAGE_INCLUDES),
                               "absent_in_checkout": absent_stage_includes,
                               "pyproject_sha256": sha256_file(src / "pyproject.toml")}
    if absent_stage_includes:
        record["gaps"].append(
            "staged build input directory(ies) missing from the checkout: "
            + ", ".join(absent_stage_includes)
            + " -- any package-dir mapping onto them will ship nothing")

    wheel_step = run([str(python), "-B", "-m", "pip", *PIP_GLOBAL, "wheel",
                      *PIP_OFFLINE, "--no-deps", "--no-build-isolation", "--wheel-dir", str(dist),
                      str(src)],
                     cwd=src, env=build_env, label="pip-wheel", record=record)
    wheels = sorted(dist.glob("*.whl"))
    if wheel_step.returncode != 0 or not wheels:
        record["status"] = "FAIL"
        record["gaps"].append("pip wheel failed; stderr kept in steps[pip-wheel].stderr")
        write_report()
        print("FAIL: wheel build did not produce a wheel", file=sys.stderr)
        return 1
    wheel = wheels[0]
    record["artifacts"]["wheel"] = wheel_inventory(wheel)

    # 4. Install into the isolated directory. PYTHONPATH is dropped on purpose:
    #    the installed tree must not depend on the borrowed setuptools or on the
    #    source checkout being importable.
    install_env = dict(base_env)
    install_env.pop("PYTHONPATH", None)
    record["install_env_pythonpath"] = install_env.get("PYTHONPATH", "<absent>")
    # ``--upgrade`` is not a nicety here. Without it a second build into an existing
    # run directory installs NOTHING: pip answers "Target directory ... already
    # exists. Specify --upgrade to force replacement" for every top-level directory
    # and exits 0, leaving an install tree that is a mix of the old wheel and
    # whatever new files the rebuilt wheel added. Measured in this run: a rebuild
    # that added design_lab/resources/capability-library/** reported OK with
    # installed_files 1163 -> 1168 while the whole design_lab directory stayed at its
    # previous contents -- the proof would then have been made about a tree that no
    # wheel describes. --no-deps keeps it offline; the dist-info already present is
    # the same distribution, so nothing else is touched.
    install_step = run([str(python), "-B", "-m", "pip", *PIP_GLOBAL, "install",
                        *PIP_OFFLINE, "--no-deps", "--no-build-isolation", "--upgrade",
                        "--find-links", str(dist),
                        "--target", str(isolated), str(wheel)],
                       cwd=run_dir, env=install_env, label="pip-install-target",
                       record=record)
    if install_step.returncode != 0:
        record["status"] = "FAIL"
        record["gaps"].append("pip install --target failed; stderr kept in steps")
        write_report()
        print("FAIL: isolated install failed", file=sys.stderr)
        return 1
    if "already exists" in (install_step.stdout or "") + (install_step.stderr or ""):
        record["gaps"].append(
            "pip reported an 'already exists' target directory during the --upgrade "
            "install; the install tree may be a mix of two wheels. Treat this run's "
            "isolated directory as unproven (verify_isolated_install.py re-hashes every "
            "RECORD entry against the wheel and fails on a mismatch).")

    installed_files = [p for p in isolated.rglob("*") if p.is_file()]
    record["artifacts"]["isolated_install"] = {
        "path": str(isolated),
        "file_count": len(installed_files),
        "from_wheel": wheel.name,
        "from_wheel_sha256": record["artifacts"]["wheel"]["sha256"],
        "top_level": sorted({p.name for p in isolated.iterdir()}),
        "dist_info": sorted(p.name for p in isolated.glob("*.dist-info")),
    }
    # 5. Environment untouched afterwards.
    run([str(python), "-B", "-m", "pip", *PIP_CONFIG_READ, "config", "list"],
        cwd=run_dir, env=base_env, label="pip-config-after", record=record,
        echo_stdout=False)
    record["pip_config_after"] = redact("pip-config-after")
    record["pip_config_unchanged"] = (record["pip_config_before"]["setting_names"]
                                      == record["pip_config_after"]["setting_names"])

    record["status"] = "OK"
    record["finished"] = now()
    write_report()
    print(json.dumps({"status": "OK", "wheel": wheel.name,
                      "sha256": record["artifacts"]["wheel"]["sha256"],
                      "isolated": str(isolated),
                      "installed_files": record["artifacts"]["isolated_install"]["file_count"],
                      "config_registry_count": record["artifacts"]["wheel"]["config_registry_count"],
                      "capability_library_files": len(
                          record["artifacts"]["wheel"]["capability_library_files"]),
                      "run_id": args.run_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
