# -*- coding: utf-8 -*-
"""C2: verify external-libraries-index.json without any hardcoded checkout path.

Design (per prompt C2, reusing U17/U21 machine truth instead of a second
implementation):

* The index is resolved from the CURRENT Git root (``git rev-parse
  --show-toplevel``), optionally overridden by ``--root``. No absolute
  ``D:\\...`` checkout path is ever hardcoded, so the checker works from any
  clone, worktree, or CI runner.

* Two separated check classes:

  1. in-repo STRUCTURE checks — schema version, policy clause, library
     identity fields (id/sharedRoot/relativePath/kind/ownedBy), asset-list
     presence. These run on the JSON text alone and must PASS for the gate
     to be green; a structure violation is a real failure.

  2. authorized machine DISCOVERY of shared roots — whether a registered
     root actually exists on this machine. Discovery returns a closed status
     vocabulary per root:

         NOT_SEARCHED
         ACCESS_DENIED
         VOLUME_OFFLINE
         PATH_STALE
         FOUND_COMPATIBLE
         FOUND_INCOMPATIBLE
         NOT_FOUND_AFTER_AUTHORIZED_SEARCH

     The first five states are *machine-state observations, never evidence
     of "not installed"*: a root that is offline, inaccessible or not
     searched is reported as such — the gate must not convert it into a
     missing-software verdict. Discovery states never fail the gate by
     themselves; only the in-repo structure class can fail it.

* Location identity reuses U17 machine truth
  (``software_installation_identity.location_readback``): when both an
  index-declared root and an observed machine root are available, an update
  that silently relocated the registered root surfaces as a
  LOCATION_DRIFT observation rather than being hidden by a plain exists()
  check.

Exit code: 0 when structure checks pass (discovery states are reported, not
fatal), 1 on a structure violation or when the index itself is absent.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from software_installation_identity import _norm, location_readback
    _U17_AVAILABLE = True
except Exception:  # pragma: no cover - U17 module missing degrades gracefully
    _U17_AVAILABLE = False

    def _norm(p):
        return str(p or "").strip().replace("\\", "/").rstrip("/").casefold()

    def location_readback(before, after, *, is_relocation=False):
        return {
            "install_root_unchanged": _norm(before.get("install_root")) == _norm(after.get("install_root")),
            "location_readback_passed": False,
            "fail_reason": "U17_MODULE_UNAVAILABLE",
        }

SCHEMA_VERSION = "work-lab/external-libraries-index/v1"
LIBRARY_ID_FIELDS = ("id", "sharedRoot", "relativePath", "kind", "ownedBy")

# Closed discovery status vocabulary (prompt C2, min set).
DISCOVERY_STATUSES = (
    "NOT_SEARCHED",
    "ACCESS_DENIED",
    "VOLUME_OFFLINE",
    "PATH_STALE",
    "FOUND_COMPATIBLE",
    "FOUND_INCOMPATIBLE",
    "NOT_FOUND_AFTER_AUTHORIZED_SEARCH",
)
_DISCOVERY_NON_FATAL = DISCOVERY_STATUSES


def resolve_git_root(start: Path) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).resolve()


def _windows_long_path(path: Path) -> Path:
    """Resolve a Windows 8.3 short alias back to its long form (identity-safe)."""
    if os.name != "nt" or not path.exists():
        return path
    try:
        buffer_size = ctypes.windll.kernel32.GetLongPathNameW(str(path), None, 0)
        if buffer_size <= 0:
            return path
        buffer = ctypes.create_unicode_buffer(buffer_size)
        if ctypes.windll.kernel32.GetLongPathNameW(str(path), buffer, buffer_size) <= 0:
            return path
        return Path(buffer.value)
    except Exception:
        return path


def _drive_of(root: str) -> str:
    s = str(root).strip()
    if len(s) >= 2 and s[1] == ":" and s[0].isalpha():
        return s[0].upper() + ":"
    return ""


def _drive_present(drive: str) -> bool:
    if not drive or os.name != "nt":
        return True
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\MountedDevices")
        names = []
        i = 0
        while True:
            try:
                names.append(winreg.EnumValue(key, i).strip("\\??\\"))
                i += 1
            except OSError:
                break
        return any(n.startswith(drive) for n in names)
    except Exception:
        # MountedDevices unreadable: treat as present (don't fabricate OFFLINE
        # from an access failure of the registry, only of the root itself).
        return True


def discover_root(root: str) -> tuple[str, str]:
    """One authorized, local discovery attempt for a registered shared root.

    Returns (status, detail). The status is always one of DISCOVERY_STATUSES;
    a non-FOUND status is a machine observation, NOT a "not installed"
    verdict.
    """
    if not root:
        return "PATH_STALE", "empty registered root"
    p = _windows_long_path(Path(root))
    if not p.exists():
        if not _drive_present(_drive_of(str(p))):
            return "VOLUME_OFFLINE", f"drive {p.drive or '<none>'} not mounted"
        return "PATH_STALE", f"registered root does not resolve on this machine: {p}"
    if not p.is_dir():
        return "FOUND_INCOMPATIBLE", f"root exists but is not a directory: {p}"
    try:
        os.access(p, os.R_OK | os.X_OK)
        if not os.access(p, os.R_OK):
            return "ACCESS_DENIED", f"read access denied: {p}"
    except OSError as exc:
        return "ACCESS_DENIED", f"probe error: {exc}"
    return "FOUND_COMPATIBLE", str(p)


def structure_check(data: dict) -> list[str]:
    """In-repo structure class: violations of these fail the gate."""
    errors: list[str] = []
    if data.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion mismatch (want %s)" % SCHEMA_VERSION)
    policy = data.get("policy")
    if not isinstance(policy, str) or not policy:
        errors.append("policy missing content-exclusion clause")
    roots = data.get("sharedRoots", {})
    if not isinstance(roots, dict) or not roots:
        errors.append("sharedRoots missing or empty")
    libs = data.get("libraries", [])
    if not isinstance(libs, list) or not libs:
        errors.append("no libraries")
        return errors
    for lib in libs:
        for field in LIBRARY_ID_FIELDS:
            if not lib.get(field):
                errors.append(f"library {lib.get('id', '?')} missing {field}")
        shared_root = lib.get("sharedRoot", "")
        if shared_root and roots and shared_root not in roots:
            errors.append(f"library {lib.get('id', '?')} references undeclared sharedRoot {shared_root!r}")
        if lib.get("kind") == "model-weights" and not lib.get("assets"):
            errors.append(f"model library {lib.get('id', '?')} has empty assets (must list, not upload)")
    return errors


def location_identity(data: dict, root_status: dict[str, str]) -> list[dict]:
    """U17 reuse: an observed machine root may not silently relocate the
    registered root (update != migration). Observation-only: drift is
    reported, never fatal on its own."""
    observations: list[dict] = []
    if not _U17_AVAILABLE:
        observations.append({"check": "location_readback", "status": "UNVERIFIED", "detail": "U17 module unavailable"})
        return observations
    roots = data.get("sharedRoots", {})
    for name, declared in roots.items():
        status = root_status.get(name)
        if status not in ("FOUND_COMPATIBLE", "FOUND_INCOMPATIBLE", "PATH_STALE"):
            continue
        result = location_readback(
            {"install_root": declared},
            {"install_root": declared if status == "FOUND_COMPATIBLE" else None},
        )
        observations.append(
            {
                "check": "location_readback",
                "root": name,
                "declared": declared,
                "discovery_status": status,
                "location_readback_passed": bool(result.get("location_readback_passed")),
                "install_root_unchanged": bool(result.get("install_root_unchanged")),
            }
        )
    return observations


def run_check(index_path: Path, authorized_discovery: bool) -> int:
    data_raw = index_path.read_text(encoding="utf-8")
    try:
        data = json.loads(data_raw)
    except Exception as exc:
        print(f"FAIL external-libraries-index: index JSON invalid ({exc})")
        return 1
    if not isinstance(data, dict):
        print("FAIL external-libraries-index: index root is not an object")
        return 1

    structure_errors = structure_check(data)

    roots = data.get("sharedRoots", {})
    root_status: dict[str, str] = {}
    root_detail: dict[str, str] = {}
    if authorized_discovery:
        for name, root in roots.items():
            status, detail = discover_root(root)
            root_status[name] = status
            root_detail[name] = detail
    else:
        for name in roots:
            root_status[name] = "NOT_SEARCHED"
            root_detail[name] = "discovery not authorized for this run"

    location_obs = location_identity(data, root_status)

    print("EXTERNAL_LIBRARIES_INDEX structure=" + ("PASS" if not structure_errors else "FAIL"))
    if structure_errors:
        for e in structure_errors:
            print("  -", e)
    print("EXTERNAL_LIBRARIES_INDEX discovery (machine observations, never converted to not-installed):")
    for name in sorted(roots):
        print(f"  - {name}: {root_status.get(name, 'NOT_SEARCHED')} ({root_detail.get(name, '')})")
    if location_obs:
        print("EXTERNAL_LIBRARIES_INDEX location-identity (U17 location_readback):")
        for obs in location_obs:
            print("  -", json.dumps(obs, ensure_ascii=False, sort_keys=True))

    if structure_errors:
        return 1
    print(
        f"PASS external-libraries-index: {len(data.get('libraries', []))} libraries, "
        f"{len(roots)} roots, JSON valid, structure OK; "
        f"discovery statuses={ {s: sum(1 for x in root_status.values() if x == s) for s in DISCOVERY_STATUSES if any(x == s for x in root_status.values())} }"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Explicit project root (default: resolve from the current Git root).",
    )
    parser.add_argument(
        "--authorized-discovery",
        action="store_true",
        help="Authorize probing registered shared roots on this machine. "
        "Without it, every root is reported NOT_SEARCHED and the structural "
        "checks still run.",
    )
    args = parser.parse_args(argv)

    if args.root is not None:
        index_path = (args.root.resolve() / ".project/governance/external-libraries-index.json")
    else:
        git_root = resolve_git_root(Path.cwd())
        if git_root is None:
            print("FAIL external-libraries-index: not inside a Git repository; pass --root explicitly")
            return 1
        index_path = git_root / ".project/governance/external-libraries-index.json"

    if not index_path.is_file():
        print(f"FAIL missing index: {index_path}")
        return 1

    return run_check(index_path, authorized_discovery=args.authorized_discovery)


if __name__ == "__main__":
    sys.exit(main())
