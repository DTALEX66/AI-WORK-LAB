"""P0-07 / §42: fail-closed POSTFLIGHT gate — after a software WRITE, re-verify
the real installation location and body state.

This module is the post-update twin of ``software_installation_identity``.
Preflight (§15-19, 34) proves the intended write is lawful BEFORE it happens;
this gate proves the install actually landed where it must, AFTER it happens.
It encodes the §42 iron rule verbatim:

    更新后必须重新验证真实安装位置

and the P0-07/§42 recurrence goal this gate locks down — that a software
UPDATE can never silently relocate, shrink, or re-seed the C-drive default
root again. The DSH 2026-09-20 evidence (recurrence scenarios this gate
guards against):

    (a) an NSIS silent install reset the desktop .lnk back to LOCALAPPDATA
        (launcher pinning failure),
    (b) an update loop emptied the official resources\\app code tree 45k -> 0
        (body integrity failure),
    (c) a frozen DSH_HOME[HKCU] made the launching process fall back to the
        C:\\Users\\ALEX\\.dsh default root (data root / C residue failure).

Pure: every input is a structured dict/str produced by a real-facts adapter
(the discovery layer), so the gate itself performs NO I/O — no filesystem,
no process listing, no credential reads, no auto-deletion of C-drive state
and no second updater (§40). All checks are fail-closed: any violation is a
FAIL; missing / unknown facts are UNVERIFIED (never fabricated as PASS).
"""
from __future__ import annotations

from typing import Any

from software_installation_identity import location_readback

# Contract identity — must equal the schema const.
POSTFLIGHT_SCHEMA_VERSION = "workflow/software-update-postflight/v1"

# Check names (closed set, mirrored by the schema enum).
CHECK_VERSION_READBACK = "version_readback"
CHECK_BODY_INTEGRITY = "body_integrity"
CHECK_LAUNCHER_PINNING = "launcher_pinning"
CHECK_DATA_ROOT_PINNING = "data_root_pinning"
CHECK_C_RESIDUE = "c_residue"
CHECK_RUNTIME_HEALTH = "runtime_health"
CHECK_LOCATION_READBACK = "location_readback"

CHECK_NAMES = (
    CHECK_VERSION_READBACK,
    CHECK_BODY_INTEGRITY,
    CHECK_LAUNCHER_PINNING,
    CHECK_DATA_ROOT_PINNING,
    CHECK_C_RESIDUE,
    CHECK_RUNTIME_HEALTH,
    CHECK_LOCATION_READBACK,
)

# Closed reason enum — must equal the schema reasons enum EXACTLY.
REASON_ALL_CHECKS_PASS = "POSTFLIGHT_ALL_CHECKS_PASS"
REASON_VERSION_READBACK_FAIL = "VERSION_READBACK_FAIL"
REASON_BODY_INTEGRITY_FAIL = "BODY_INTEGRITY_FAIL"
REASON_LAUNCHER_PINNING_FAIL = "LAUNCHER_PINNING_FAIL"
REASON_DATA_ROOT_PINNING_FAIL = "DATA_ROOT_PINNING_FAIL"
REASON_C_RESIDUE_DETECTED = "C_RESIDUE_DETECTED"
REASON_LOCATION_READBACK_FAIL = "LOCATION_READBACK_FAIL"
REASON_RUNTIME_HEALTH_UNVERIFIED = "RUNTIME_HEALTH_UNVERIFIED"
REASON_RUNTIME_HEALTH_FAIL = "RUNTIME_HEALTH_FAIL"
REASON_POSTFLIGHT_INCOMPLETE = "POSTFLIGHT_INCOMPLETE"

POSTFLIGHT_REASONS = (
    REASON_ALL_CHECKS_PASS,
    REASON_VERSION_READBACK_FAIL,
    REASON_BODY_INTEGRITY_FAIL,
    REASON_LAUNCHER_PINNING_FAIL,
    REASON_DATA_ROOT_PINNING_FAIL,
    REASON_C_RESIDUE_DETECTED,
    REASON_LOCATION_READBACK_FAIL,
    REASON_RUNTIME_HEALTH_UNVERIFIED,
    REASON_RUNTIME_HEALTH_FAIL,
    REASON_POSTFLIGHT_INCOMPLETE,
)

_PASS = "PASS"
_FAIL = "FAIL"
_UNVERIFIED = "UNVERIFIED"

_CHECK_STATUS = (_PASS, _FAIL, _UNVERIFIED)
_CHECK_NAME = CHECK_NAMES
_REASON = POSTFLIGHT_REASONS


def _norm(value: Any) -> str:
    """Normalise a Windows path for identity comparison: separators
    collapsed to '/', trailing slashes stripped, casefolded; empty -> ''."""
    if value is None:
        return ""
    return str(value).strip().replace("\\", "/").rstrip("/").casefold()


def _cell(value: Any) -> Any:
    """Render a structured fact as a record-safe cell value: True/False/None
    stay JSON-native; anything else becomes a lowercase string."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return str(value).strip().casefold()


def _snap(src: dict[str, Any], key: str, default: Any = None) -> Any:
    """Read a snapshot fact, treating a present-but-None value as missing."""
    value = src.get(key, default)
    return default if value is None else value


def _check(name: str, status: str, expected: Any, observed: Any) -> dict[str, Any]:
    if status not in _CHECK_STATUS:
        raise ValueError(f"illegal check status: {status!r}")
    return {"name": name, "status": status, "expected": expected, "observed": observed}


def _version_check(*, target_version: str, after: dict[str, Any]) -> dict[str, Any]:
    """version_readback: observed version == target_version; missing -> UNVERIFIED."""
    observed = after.get("version")
    if observed is None:
        return _check(CHECK_VERSION_READBACK, _UNVERIFIED, target_version, None)
    if str(observed) == str(target_version):
        return _check(CHECK_VERSION_READBACK, _PASS, target_version, str(observed))
    return _check(CHECK_VERSION_READBACK, _FAIL, target_version, str(observed))


def _body_integrity_check(
    *,
    after: dict[str, Any],
    expected_code_tree_files_min: int | None,
    asar_expected: bool,
    uninstaller_expected: bool,
) -> dict[str, Any]:
    """body_integrity: official code tree not emptied, asar residue matches
    expectation, expected uninstaller present. Any violation -> FAIL."""
    observed_tree = after.get("code_tree_files")
    violations: list[str] = []
    if expected_code_tree_files_min is not None:
        if observed_tree is None or int(observed_tree) < int(expected_code_tree_files_min):
            violations.append(
                f"code_tree_files={_cell(observed_tree)} < min={expected_code_tree_files_min}"
            )
    observed_asar = _snap(after, "asar_residue", False)
    if bool(observed_asar) != bool(asar_expected):
        violations.append(f"asar_residue={_cell(observed_asar)} expected={_cell(asar_expected)}")
    observed_uninstaller = _snap(after, "uninstaller")
    if uninstaller_expected and not observed_uninstaller:
        violations.append("uninstaller missing")
    expected = {
        "code_tree_files_min": expected_code_tree_files_min,
        "asar_expected": bool(asar_expected),
        "uninstaller_expected": bool(uninstaller_expected),
    }
    observed = {
        "code_tree_files": observed_tree,
        "asar_residue": observed_asar,
        "uninstaller": observed_uninstaller,
    }
    if violations:
        return _check(
            CHECK_BODY_INTEGRITY, _FAIL, expected,
            {"observed": observed, "violations": violations},
        )
    return _check(CHECK_BODY_INTEGRITY, _PASS, expected, observed)


def _launcher_pinning_check(*, after: dict[str, Any], expected_install_root: str) -> dict[str, Any]:
    """launcher_pinning: every non-null launcher target must sit under the
    expected install root; a target pointing back to C: (or elsewhere) FAILs."""
    expected = _norm(expected_install_root)
    targets = after.get("launcher_targets") or []
    if not isinstance(targets, (list, tuple)):
        targets = [targets]
    bad = []
    for t in targets:
        if t is None:
            continue
        key = _norm(t)
        if not key:
            continue
        # Path-boundary check: target must equal the root or sit strictly
        # under it (a sibling like "d:/all projects/dsh2" must NOT pass).
        if key != expected and not key.startswith(expected + "/"):
            bad.append(str(t))
    observed = [None if t is None else str(t) for t in targets]
    if bad:
        return _check(
            CHECK_LAUNCHER_PINNING, _FAIL,
            {"under": str(expected_install_root)}, {"violating": bad},
        )
    return _check(
        CHECK_LAUNCHER_PINNING, _PASS,
        {"under": str(expected_install_root)}, observed,
    )


def _data_root_pinning_check(*, after: dict[str, Any], expected_data_root: str) -> dict[str, Any]:
    """data_root_pinning: after.data_root must equal the expected data root;
    any drift (e.g. fall-back to a C: default root) -> FAIL."""
    expected = _norm(expected_data_root)
    observed_value = after.get("data_root")
    if not observed_value or _norm(observed_value) != expected:
        return _check(CHECK_DATA_ROOT_PINNING, _FAIL, expected, _cell(observed_value))
    return _check(CHECK_DATA_ROOT_PINNING, _PASS, expected, str(observed_value))


def _c_residue_check(
    *, after: dict[str, Any], residue_watchlist: list[str] | None
) -> dict[str, Any]:
    """c_residue: no C-drive residue path may re-appear on the watchlist.
    Watchlist None/empty -> PASS (no watched residue declared)."""
    watchlist = [str(p) for p in (residue_watchlist or []) if p]
    residue = [str(p) for p in (_snap(after, "c_drive_residue", []) or [])]
    watched = {_norm(p) for p in watchlist}
    found = sorted({p for p in residue if _norm(p) in watched})
    observed = [None] if not found else found
    if found:
        return _check(CHECK_C_RESIDUE, _FAIL, {"watched": watchlist}, found)
    return _check(CHECK_C_RESIDUE, _PASS, {"watched": watchlist}, None)


def _runtime_health_check(*, after: dict[str, Any]) -> dict[str, Any]:
    """runtime_health: 'UNKNOWN'/missing -> UNVERIFIED (never fabricated as
    PASS); 'FAIL' -> FAIL; 'PASS' -> PASS."""
    observed_value = after.get("runtime_health")
    observed = _cell(observed_value) if observed_value is not None else None
    if observed in (_PASS, "pass"):
        return _check(CHECK_RUNTIME_HEALTH, _PASS, "PASS", "PASS")
    if observed in (_FAIL, "fail"):
        return _check(CHECK_RUNTIME_HEALTH, _FAIL, "PASS", "FAIL")
    return _check(CHECK_RUNTIME_HEALTH, _UNVERIFIED, "PASS", observed or "UNKNOWN")


def _location_readback_check(
    *, before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    """location_readback: reuses software_installation_identity.location_readback
    (a plain update must leave install_root unchanged; missing roots ->
    UNVERIFIED, drift -> FAIL)."""
    before_root = _norm(before.get("install_root"))
    after_root = _norm(after.get("install_root"))
    result = location_readback(before, after)
    readback_passed = bool(result.get("location_readback_passed")) and bool(
        before_root and after_root
    )
    expected = {"install_root": before_root or None, "unchanged": True}
    observed = {"install_root": after_root or None, "unchanged": before_root == after_root}
    if not readback_passed:
        if not before_root or not after_root:
            return _check(CHECK_LOCATION_READBACK, _UNVERIFIED, expected, observed)
        return _check(CHECK_LOCATION_READBACK, _FAIL, expected, observed)
    return _check(CHECK_LOCATION_READBACK, _PASS, expected, observed)


def run_postflight_checks(
    *,
    software_id: str,
    target_version: str,
    before: dict[str, Any],
    after: dict[str, Any],
    expected_install_root: str,
    expected_data_root: str,
    residue_watchlist: list[str] | None = None,
    expected_code_tree_files_min: int | None = None,
    asar_expected: bool = False,
    uninstaller_expected: bool = True,
) -> dict[str, Any]:
    """Run the §42 postflight gate over BEFORE/AFTER snapshots.

    Pure: no I/O. The adapter supplies ``before`` / ``after`` as structured
    facts (install_root, version, launcher_targets, data_root,
    c_drive_residue, code_tree_files, asar_residue, uninstaller,
    runtime_health). Every check is fail-closed: any violation -> overall
    FAIL; missing/unknown facts -> UNVERIFIED, which keeps overall at PENDING
    (never fabricated as PASS). ``location_readback_passed`` reuses
    ``software_installation_identity.location_readback`` — one engine, no
    second implementation (§22).
    """
    checks: list[dict[str, Any]] = [
        _version_check(target_version=target_version, after=after),
        _body_integrity_check(
            after=after,
            expected_code_tree_files_min=expected_code_tree_files_min,
            asar_expected=asar_expected,
            uninstaller_expected=uninstaller_expected,
        ),
        _launcher_pinning_check(after=after, expected_install_root=expected_install_root),
        _data_root_pinning_check(after=after, expected_data_root=expected_data_root),
        _c_residue_check(after=after, residue_watchlist=residue_watchlist),
        _runtime_health_check(after=after),
    ]
    location = _location_readback_check(before=before, after=after)
    checks.append(location)

    failures = [c for c in checks if c["status"] == _FAIL]
    unverified = [c for c in checks if c["status"] == _UNVERIFIED]

    if failures:
        overall = _FAIL
        reasons = [_FAIL_REASON_BY_NAME[c["name"]] for c in failures]
        reasons.append(REASON_POSTFLIGHT_INCOMPLETE)
    elif unverified:
        overall = "PENDING"
        reasons = []
        if any(c["name"] == CHECK_RUNTIME_HEALTH for c in unverified):
            reasons.append(REASON_RUNTIME_HEALTH_UNVERIFIED)
        reasons.append(REASON_POSTFLIGHT_INCOMPLETE)
    else:
        overall = _PASS
        reasons = [REASON_ALL_CHECKS_PASS]

    return {
        "schema_version": POSTFLIGHT_SCHEMA_VERSION,
        "software_id": software_id,
        "target_version": target_version,
        "before": before,
        "after": after,
        "checks": checks,
        "location_readback_passed": location["status"] == _PASS,
        "overall": overall,
        "reasons": reasons,
    }


_FAIL_REASON_BY_NAME = {
    CHECK_VERSION_READBACK: REASON_VERSION_READBACK_FAIL,
    CHECK_BODY_INTEGRITY: REASON_BODY_INTEGRITY_FAIL,
    CHECK_LAUNCHER_PINNING: REASON_LAUNCHER_PINNING_FAIL,
    CHECK_DATA_ROOT_PINNING: REASON_DATA_ROOT_PINNING_FAIL,
    CHECK_C_RESIDUE: REASON_C_RESIDUE_DETECTED,
    CHECK_RUNTIME_HEALTH: REASON_RUNTIME_HEALTH_FAIL,
    CHECK_LOCATION_READBACK: REASON_LOCATION_READBACK_FAIL,
}
