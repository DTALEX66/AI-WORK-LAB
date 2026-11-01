"""P0-07 / TaskPack §9-29: pure Software Installation Identity resolver.

This is the **Observed User State evidence layer** — it answers "what is
actually installed where, and does that match intent?" It is NOT a fourth
authority (§12): the five-dimension baseline + official standard + user
configuration still decide *what should be true*; this module only classifies
*what is actually true* and enforces the §42 iron rules:

    已有安装 -> 先发现 -> 验证身份 -> 原位维护
    未安装   -> 用户配置优先 -> 项目推荐 -> 官方默认
    位置冲突 -> Fail Closed
    重复安装 -> Fail Closed
    软件更新 != 软件迁移
    更新不得隐式改变安装位置
    更新后必须重新验证真实安装位置

Everything here is a pure function over structured inputs (no filesystem, no
process listing, no credential access) so DSH and other adapters can drive it
with fixtures and the §35 negative tests can assert the exact fail-closed
verdicts. Discovery of real facts lives in ``platform_discovery.py`` / the
adapters; this module resolves *identity + location status + update decision*.
"""
from __future__ import annotations

from typing import Any

# §13: the unified installation status vocabulary. A single boolean
# ``installed`` is explicitly NOT enough — these states are the contract.
LOCATION_STATUS = (
    "NOT_INSTALLED",
    "SINGLE_VERIFIED",
    "SINGLE_UNVERIFIED",
    "LOCATION_DRIFT",
    "DUAL_INSTALLATION",
    "MISSING_EXPECTED_INSTALL",
    "RELOCATION_REQUESTED",
    "OS_MANAGED",
)

# §11: user-location resolution order (index 0 = highest priority).
LOCATION_RESOLUTION_ORDER = (
    "user_declared_location",
    "observed_existing_location",
    "os_registered_location",
    "worklab_recommended_location",
    "vendor_default_location",
)

# §14: allowed update modes. UPDATE != RELOCATION (§15).
UPDATE_MODES = (
    "IN_PLACE_ONLY",
    "RELOCATION",
    "FRESH_INSTALL",
    "BLOCKED",
    "PRESERVE_OFFICIAL_CHANNEL",
)


def _norm(path: str | None) -> str:
    """Normalise a Windows path for identity comparison (case-insensitive,
    separator-collapsed, no trailing slash). Non-strings normalise to ''."""
    if not path:
        return ""
    # Collapse Windows separators so "D:\All\projects" and "D:/All/projects"
    # are identity-equal (str(Path(...)) emits backslashes on Windows).
    return str(path).strip().replace("\\", "/").rstrip("/").casefold()


def _dedupe(paths: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for p in paths:
        key = _norm(p)
        if key and key not in seen:
            seen[key] = p
    return list(seen.values())


def classify_installation(
    *,
    user_declared: str | None = None,
    expected_existing: str | None = None,
    observed: list[str] | None = None,
    os_registered: list[str] | None = None,
    verified: bool = False,
    os_managed: bool = False,
    relocation_requested: bool = False,
) -> dict[str, Any]:
    """Return the §13 ``location_status`` + resolution basis for one software.

    Pure. Inputs are *already-discovered* facts (see platform_discovery / the
    adapter). No scanning, no I/O, no credential reads.
    """
    observed_roots = _dedupe(observed or [])
    registered_roots = _dedupe(os_registered or [])
    expected_key = _norm(expected_existing)
    user_key = _norm(user_declared)

    # §14 OS_MANAGED: Store / AppX / OS package manager -> keep official channel.
    if os_managed:
        return {
            "location_status": "OS_MANAGED",
            "canonical_candidate": None,
            "basis": "OS-managed package; preserve official channel, do not relocate",
        }

    # §20 Case D / §11.3: we expected an install at a known candidate that is
    # gone. If other installs were found instead it is drift, otherwise a
    # missing expected install — NEVER a silent vendor-default fallback.
    if expected_key and expected_key not in {_norm(r) for r in observed_roots} \
            and expected_key not in {_norm(r) for r in registered_roots}:
        if observed_roots or registered_roots:
            return {
                "location_status": "LOCATION_DRIFT",
                "canonical_candidate": None,
                "basis": f"expected {expected_existing!r} not observed; found {observed_roots or registered_roots}",
            }
        return {
            "location_status": "MISSING_EXPECTED_INSTALL",
            "canonical_candidate": None,
            "basis": f"expected install {expected_existing!r} absent; no vendor-default fallback",
        }

    # §13 / §20 Case C: more than one distinct real install -> DUAL, fail closed.
    if len(observed_roots) > 1:
        return {
            "location_status": "DUAL_INSTALLATION",
            "canonical_candidate": None,
            "basis": f"multiple installs present {observed_roots}; determine canonical instance, do not auto-delete",
        }

    single = observed_roots[0] if observed_roots else (registered_roots[0] if registered_roots else None)
    if single is not None:
        has_install = True
    else:
        has_install = False

    if has_install:
        # §28: user declared one location, a different install is observed ->
        # conflict. Fail closed (intent vs fact).
        if user_key and _norm(single) != user_key:
            return {
                "location_status": "LOCATION_DRIFT",
                "canonical_candidate": single,
                "basis": f"user declared {user_declared!r} but observed install {single!r}; conflict",
            }
        status = "SINGLE_VERIFIED" if verified else "SINGLE_UNVERIFIED"
        return {
            "location_status": status,
            "canonical_candidate": single,
            "basis": "single install observed; " + ("identity verified" if verified else "identity not yet verified"),
        }

    # §13 / §20 Case E: nothing detected -> fresh install is the only lawful path.
    if relocation_requested:
        return {
            "location_status": "RELOCATION_REQUESTED",
            "canonical_candidate": user_declared,
            "basis": "relocation requested with no existing install",
        }
    return {
        "location_status": "NOT_INSTALLED",
        "canonical_candidate": user_declared,
        "basis": "no install detected; fresh install follows resolution order "
        "(user_declared -> worklab -> vendor default)",
    }


def plan_update(
    *,
    location_status: str,
    install_root: str | None = None,
    proposed_install_root: str | None = None,
    verified: bool = False,
    os_managed: bool = False,
    relocation_requested: bool = False,
    relocation_approved: bool = False,
    user_declared: str | None = None,
) -> dict[str, Any]:
    """Return the §14/§15 update decision for one software.

    Enforces ``UPDATE != RELOCATION``: a plain update may change version /
    binary / compatible runtime but must NOT move the install root. Any root
    change is a RELOCATION that needs explicit approval. Returns a dict shaped
    like the software-update-preflight contract (``update_mode`` + reasons).
    """
    proposed_key = _norm(proposed_install_root)
    current_key = _norm(install_root)
    reasons: list[str] = []

    if location_status == "OS_MANAGED" or os_managed:
        return {"update_mode": "PRESERVE_OFFICIAL_CHANNEL", "location_status": location_status,
                "relocation": False, "blocked": False, "reasons": ["OS_MANAGED_PRESERVE_OFFICIAL_CHANNEL"]}

    if location_status == "NOT_INSTALLED":
        # §14: only NOT_INSTALLED may enter Fresh Install; location = user ->
        # worklab -> vendor default (no fallback to a C: vendor default when the
        # user had a fixed D: expectation).
        target = user_declared or proposed_install_root or "worklab-recommended-or-vendor-default"
        return {"update_mode": "FRESH_INSTALL", "location_status": location_status,
                "fresh_target": target, "relocation": False, "blocked": False,
                "reasons": ["IN_PLACE_UPDATE_OK"]}

    # A single verified install: in-place only, unless a root change is proposed.
    root_change = (proposed_key and current_key and proposed_key != current_key) or \
        (proposed_key and not current_key and location_status in ("MISSING_EXPECTED_INSTALL",))
    if root_change:
        if relocation_requested and relocation_approved:
            return {"update_mode": "RELOCATION", "location_status": location_status,
                    "relocation": True, "blocked": False,
                    "reasons": ["RELOCATION_APPROVED"]}
        if relocation_requested:
            # §35 Test 6: relocation requested but NOT explicitly approved -> FAIL.
            return {"update_mode": "BLOCKED", "location_status": location_status,
                    "relocation": True, "blocked": True,
                    "reasons": ["RELOCATION_NOT_APPROVED"]}
        return {"update_mode": "BLOCKED", "location_status": location_status,
                "relocation": False, "blocked": True,
                "reasons": ["INSTALL_ROOT_CHANGE_REQUIRES_EXPLICIT_RELOCATION"]}

    if location_status == "SINGLE_VERIFIED" or (location_status == "SINGLE_UNVERIFIED" and verified):
        return {"update_mode": "IN_PLACE_ONLY", "location_status": location_status,
                "relocation": False, "blocked": False, "reasons": ["IN_PLACE_UPDATE_OK"]}

    # §14 block rules.
    if location_status == "SINGLE_UNVERIFIED":
        reasons.append("SINGLE_UNVERIFIED_IDENTITY_VALIDATION_FIRST")
    if location_status == "LOCATION_DRIFT":
        reasons.append("LOCATION_DRIFT_UPDATE_BLOCKED")
    if location_status == "DUAL_INSTALLATION":
        reasons.append("DUAL_INSTALLATION_UPDATE_BLOCKED")
    if location_status == "MISSING_EXPECTED_INSTALL":
        reasons.append("MISSING_EXPECTED_INSTALL_NO_VENDOR_FALLBACK")
    return {"update_mode": "BLOCKED", "location_status": location_status,
            "relocation": False, "blocked": True, "reasons": reasons}


def location_readback(before: dict[str, Any], after: dict[str, Any], *,
                      is_relocation: bool = False) -> dict[str, Any]:
    """§18: after a write, compare BEFORE/AFTER install_root + executable_realpath.

    A plain UPDATE must leave install_root unchanged; otherwise it is a
    LOCATION_READBACK_FAIL even if the new version starts fine.
    """
    before_root = _norm(before.get("install_root"))
    after_root = _norm(after.get("install_root"))
    if is_relocation:
        passed = after_root != before_root  # relocation *must* move
    else:
        passed = before_root == after_root
    return {
        "install_root_unchanged": before_root == after_root,
        "location_readback_passed": passed,
        "fail_reason": None if passed else "LOCATION_READBACK_FAIL",
    }


def overall_result(*, version_verification: str, behavior_verification: str,
                   location_verification: str) -> str:
    """§19: installer exit 0 is NOT enough. Any FAIL -> overall FAIL."""
    checks = {"version": version_verification, "behavior": behavior_verification,
              "location": location_verification}
    failures = sorted(k for k, v in checks.items() if v not in ("PASS",))
    return "FAIL" if failures else "PASS"


def preflight_identity_record(*, software_id: str, **classify_kwargs: Any) -> dict[str, Any]:
    """Build a software-installation-identity contract record (observed state)."""
    c = classify_installation(**classify_kwargs)
    return {
        "schema_version": "workflow/software-installation-identity/v1",
        "software_id": software_id,
        "installed": c["location_status"] not in ("NOT_INSTALLED", "MISSING_EXPECTED_INSTALL"),
        "location_status": c["location_status"],
        "observed_existing_location": c.get("canonical_candidate"),
        "location_basis": c.get("basis"),
    }


def build_update_preflight(
    *,
    software_id: str,
    location_status: str,
    install_root: str | None = None,
    proposed_install_root: str | None = None,
    verified: bool = False,
    os_managed: bool = False,
    relocation_requested: bool = False,
    relocation_approved: bool = False,
    user_declared: str | None = None,
    before: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """§34 Preflight step — build a software-update-preflight contract record.

    Pure. Binds the intended write to an installation identity and returns the
    fail-closed preflight verdict (``update_mode`` + ``reasons`` +
    ``location_readback_required``). ``location_readback_passed`` stays None
    here; the adapter fills it after the write via :func:`location_readback`
    and sets ``overall`` via :func:`overall_result`. Conforms to
    ``workflow/software-update-preflight/v1``.
    """
    plan = plan_update(
        location_status=location_status,
        install_root=install_root,
        proposed_install_root=proposed_install_root,
        verified=verified,
        os_managed=os_managed,
        relocation_requested=relocation_requested,
        relocation_approved=relocation_approved,
        user_declared=user_declared,
    )
    update_mode = plan["update_mode"]
    # A plain UPDATE or approved RELOCATION requires an after-write location
    # readback (§18). FRESH_INSTALL / BLOCKED get no readback (nothing to
    # compare against). The preflight schema's `after` is a non-nullable object,
    # so omit the key entirely when a readback is not required.
    readback_required = update_mode in ("IN_PLACE_ONLY", "RELOCATION")
    record: dict[str, Any] = {
        "schema_version": "workflow/software-update-preflight/v1",
        "software_id": software_id,
        "update_mode": update_mode,
        "location_status": location_status,
        "approved_operation": (
            "RELOCATION" if (relocation_requested and relocation_approved)
            else ("UPDATE" if not plan["relocation"] else None)
        ),
        "relocation_approved": bool(relocation_approved),
        "before": before or {
            "install_root": install_root,
            "executable_realpath": None,
        },
        "location_readback_required": readback_required,
        "location_readback_passed": None,
        "overall": "PENDING" if not plan["blocked"] else "FAIL",
        "reasons": plan["reasons"],
    }
    if readback_required:
        record["after"] = {"install_root": None, "executable_realpath": None}
    return record
