"""Read the version metadata of the managed client binaries WITHOUT launching them.

`executor_live_probe.py` asks each entry point for its version by running it. That is right for a CLI
(codex, gh) and wrong for an Electron desktop binary: `Hermes.exe --version` never answers, so the live
probe records PROBE_TIMEOUT and the registry row keeps `UNVERIFIED` indefinitely. A Windows executable also
carries its version inside the file, and reading that resource starts no process - which is what this tool
does, and the only acceptable way to close those rows on a machine whose owner asked not to be disturbed by
launched windows.

Verdicts:
  LIVE_VERSION_FROM_FILE_METADATA   the file exists and FileVersion/ProductVersion came from its version
                                    resource; `launched` is recorded false because no process was started.
  ENTRY_MISSING_ON_DISK             a path was resolved but is gone now.
  FILE_EXISTS_WITHOUT_VERSION_RESOURCE
                                    the binary is there and carries neither FileVersion nor
                                    ProductVersion, so no version may be reported for it.
  ENTRY_IS_WRAPPER_USE_LIVE_PROBE   argv[0] is a .cmd/.bat or a bare command name; a wrapper has no
                                    version resource, so its version belongs to the live probe.
  INSTALLED_VERSION_FROM_UNINSTALL_KEY
                                    the declared entry did not resolve but HKCU/HKLM says the tool is
                                    installed; the uninstall DisplayVersion plus, when InstallLocation
                                    names a directory, the version resource of the largest exe inside it.
  NOT_RESOLVED_AND_NOT_IN_UNINSTALL_REGISTRY
                                    no entry point and no install key - reported as absent, not as unknown.
  ENTRY_NOT_RESOLVED                the declared entry point did not resolve; a registry lookup is then
                                    run so the reason is either "installed elsewhere" or "not installed",
                                    never a silent version.
Registry lookup is read-only: HKCU and HKLM uninstall keys matched by DisplayName.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "executor_live_probe.py"
DEFAULT_OUT = ROOT / "docs" / "audits" / "TOOL_VERSION_METADATA_PROBE_2026-10-07.json"

spec = importlib.util.spec_from_file_location("executor_live_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)  # type: ignore[attr-defined]

POWERSHELL = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]

VERSION_PS = """
$p = $env:WL_TARGET
if (Test-Path -LiteralPath $p) {
  $vi = (Get-Item -LiteralPath $p).VersionInfo
  Write-Output ("FOUND|" + $vi.FileVersion + "|" + $vi.ProductVersion)
} else { Write-Output "MISSING" }
"""

UNINSTALL_PS = """
$names = $env:WL_NAMES.Split(';')
$roots = @('HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall',
           'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall',
           'HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall')
foreach ($root in $roots) {
  Get-ChildItem $root -ErrorAction SilentlyContinue | ForEach-Object {
    $v = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
    if ($v.DisplayName) {
      foreach ($n in $names) {
        if ($v.DisplayName -like "*$n*") {
          Write-Output ("REG|" + $v.DisplayName + "|" + $v.DisplayVersion + "|" +
                        $v.InstallLocation + "|" + $root)
        }
      }
    }
  }
}
"""


def ps(command: str, env: dict[str, str]) -> str:
    full = dict(os.environ)
    full.update(env)
    r = subprocess.run(POWERSHELL + [command], capture_output=True, text=True, timeout=90,
                       encoding="utf-8", errors="replace", env=full)
    return r.stdout


def install_stamp_for(binary: str) -> dict | None:
    """The install stamp the tool itself trusts, found by walking up from its binary.

    Hermes' CLI resolves its own identity in exactly this order (hermes_cli/version_info.py: stamp
    first, live git second, unknown third), so reading the file is not a proxy for running the CLI —
    it is the same authority, reached without launching. That matters here because `hermes.exe` carries
    no Windows version resource and `hermes.exe --version` times out at 25s in the live probe, which
    left the declared version aging twice without anyone being able to check it.
    """
    p = Path(binary)
    if not p.is_absolute():
        return None
    for parent in list(p.parents)[:4]:
        for candidate in (parent / "install-stamp.json",
                          parent / "hermes-agent" / "install-stamp.json"):
            if candidate.is_file():
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    return None
                if data.get("displayVersion"):
                    return {"stampPath": str(candidate),
                            "displayVersion": data.get("displayVersion"),
                            "baseVersion": data.get("baseVersion"),
                            "distance": data.get("distance"),
                            "commit": data.get("commit"),
                            "builtAt": data.get("builtAt"),
                            "dirty": data.get("dirty"),
                            "updateMechanism": data.get("updateMechanism")}
    return None


def version_of(path: str) -> dict:
    for line in ps(VERSION_PS, {"WL_TARGET": path}).splitlines():
        if line.startswith("FOUND|"):
            _, file_version, product_version = line.split("|", 2)
            file_version = file_version.strip() or None
            product_version = product_version.strip() or None
            # A binary can exist and carry no version resource at all (hermes' bundled CLI launcher does
            # not). Naming that "LIVE_VERSION..." would be a version claim with no version behind it.
            if not file_version and not product_version:
                stamp = install_stamp_for(path)
                if stamp:
                    return {"path": path, "launched": False,
                            "verdict": "LIVE_VERSION_FROM_INSTALL_STAMP", **stamp}
                return {"path": path, "launched": False,
                        "verdict": "FILE_EXISTS_WITHOUT_VERSION_RESOURCE"}
            return {"path": path, "fileVersion": file_version, "productVersion": product_version,
                    "launched": False, "verdict": "LIVE_VERSION_FROM_FILE_METADATA"}
    return {"path": path, "launched": False, "verdict": "ENTRY_MISSING_ON_DISK"}


def registry_lookup(names: list[str]) -> list[dict]:
    rows = []
    for line in ps(UNINSTALL_PS, {"WL_NAMES": ";".join(names)}).splitlines():
        if line.startswith("REG|"):
            _, display, version, location, root = line.split("|", 4)
            rows.append({"displayName": display, "displayVersion": version or None,
                         "installLocation": location or None, "hive": root})
    return rows


def exe_under(location: str, hint: str) -> dict:
    """The largest exe directly inside an install location, with its version resource read.

    `InstallLocation` from the uninstall key is the only pointer the registry offers for a tool whose
    desktop shortcut is missing; taking the largest executable is a heuristic, so the path is published
    next to the number and the verdict never inherits the DisplayVersion silently.
    """
    base = Path(location.strip().strip('"'))
    if not base.is_dir():
        return {"verdict": "INSTALL_LOCATION_NOT_A_DIRECTORY", "installLocation": location}
    exes = sorted((p for p in base.glob("*.exe") if p.is_file()),
                  key=lambda p: p.stat().st_size, reverse=True)
    if not exes:
        return {"verdict": "NO_EXE_DIRECTLY_IN_INSTALL_LOCATION", "installLocation": location}
    chosen = next((p for p in exes if hint.split()[0].lower() in p.name.lower()), exes[0])
    row = version_of(str(chosen))
    row["installLocation"] = location
    row["exeCandidates"] = [p.name for p in exes[:5]]
    return row


# Only used when the declared entry point does not resolve, to separate "installed elsewhere"
# from "not installed on this machine".
FALLBACK_NAMES = {"hermes": ["Hermes"], "codex": ["Codex"], "github": ["GitHub CLI"],
                  "deepseek-harness": ["DeepSeek Harness"], "openhuman": ["OpenHuman", "Open Human"],
                  "open-design": ["Open Design", "OpenDesign"], "cc-switch": ["CC Switch", "cc-switch"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    results: dict[str, dict] = {}
    for key, resolver in probe.RESOLVERS.items():
        argv = resolver()
        if not argv:
            found = registry_lookup(FALLBACK_NAMES.get(key, [key]))
            if not found:
                results[key] = {"verdict": "NOT_RESOLVED_AND_NOT_IN_UNINSTALL_REGISTRY", "registry": []}
                continue
            row = {"verdict": "INSTALLED_VERSION_FROM_UNINSTALL_KEY", "registry": found}
            for entry in found:
                location = entry.get("installLocation")
                if location:
                    row["binary"] = exe_under(location, entry["displayName"])
                    break
            results[key] = row
            continue
        head = argv[0]
        if Path(head).suffix.lower() in {".cmd", ".bat"} or ("\\" not in head and "/" not in head):
            # A wrapper or a bare command name has no version resource of its own; the version of this
            # chain comes from the live probe, which runs it. Saying so is the honest verdict here.
            results[key] = {"verdict": "ENTRY_IS_WRAPPER_USE_LIVE_PROBE", "argvDeclared": argv,
                            "launched": False}
            continue
        resolved = str(Path(head)) if Path(head).is_absolute() else shutil.which(head)
        row = version_of(resolved or head)
        row["argvDeclared"] = argv
        results[key] = row

    Path(args.out).write_text(json.dumps(
        {"schemaVersion": "work-lab/tool-version-metadata-probe/v1",
         "tool": "scripts/audit/tool_version_metadata_probe.py",
         "method": "FileVersion/ProductVersion from the binary version resource, then the tool's own "
                   "install stamp when the binary carries no resource, then HKCU/HKLM uninstall "
                   "keys when the declared entry does not resolve",
         "launchedAnyProcessForVersion": False,
         "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for key, row in results.items():
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        detail = row.get("fileVersion") \
            or row.get("displayVersion") \
            or (row.get("binary") or {}).get("fileVersion") \
            or (row.get("registry") or [{}])[0].get("displayVersion") \
            or row.get("verdict")
        print(f"{key:18s} {row['verdict']:42s} {detail}")
    print("probe ->", args.out)
    print(json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
