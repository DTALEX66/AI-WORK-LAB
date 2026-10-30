"""Authorized software probe — the only lawful way to run the migrated discovery.

F01's hard constraint is that the read path observes only: it must not start collectors,
probe models, touch user software or reach remote services. The discovery that came over
from WORK-LAB does all three kinds of heavy work:

- `platform_discovery.discover_software_installations()` stats declared install roots,
  which include `%LOCALAPPDATA%/Programs/...` and one hardcoded `D:/All projects/DSH`;
- `platform_discovery.discover_all()` / `resolve_current_platform()` additionally run
  `<executable> --version` and `tasklist` (or `ps`) as subprocesses and read
  `APPDATA` / `PROGRAMDATA` / `Path.home()` / Start Menu shortcuts.

None of that belongs on a snapshot read, and none of it may happen by accident. So this
module is the single explicit door, closed by default:

- every entry point requires the caller to pass `authorized=True`; without it a named
  `ProbeNotAuthorized` is raised and NOTHING is probed — no partial probe, no fallback;
- `composition_root` never calls any function here. It projects the registry with
  `locationStatus="NOT_PROBED"` and cites this module's `PROBE_STATE` as the reason, so
  the snapshot says "not looked" instead of pretending either health or absence;
- the result of an authorized run is returned to the caller only. It is not cached, not
  written to the store and not merged into the software projection, so one authorized
  probe cannot silently turn later un-authorized snapshots green.

`run_probe` is real code over the migrated `platform_discovery`, not a placeholder: when
authorized it performs exactly the discovery WORK-LAB performed, with the same record
shape, so an operator who authorizes it gets the same facts.
"""
from __future__ import annotations

from typing import Any

# The state a software row carries while nothing has been probed. Kept as one constant so
# the projection and this module can never spell the same state two different ways.
PROBE_STATE = "NOT_PROBED"
PROBE_REASON = ("默认零自动执行：安装位置未探测。快照读路径不启动发现；需要真实位置时由调用方显式授权 "
                "domains.work.orchestration.probe.run_probe(authorized=True)")
NOT_AUTHORIZED_CODE = "SOFTWARE_PROBE_NOT_AUTHORIZED"
PROCESS_PROBE_NOT_AUTHORIZED_CODE = "SOFTWARE_PROCESS_PROBE_NOT_AUTHORIZED"

__all__ = ["PROBE_STATE", "PROBE_REASON", "ProbeNotAuthorized", "probe_state_record",
           "run_probe", "run_process_probe"]


class ProbeNotAuthorized(RuntimeError):
    """Raised instead of probing. The name is the audit answer to "why is this NOT_PROBED"."""


def probe_state_record(software_id: str, *, display_name: str | None = None) -> dict[str, Any]:
    """The one honest record shape for "declared, not looked for" — no path, no version."""
    return {"softwareId": software_id, "displayName": display_name, "probeState": PROBE_STATE,
            "reason": PROBE_REASON}


def run_probe(inventory: list[dict[str, Any]] | None = None, *, authorized: bool = False,
              reason: str | None = None) -> list[dict[str, Any]]:
    """Real read-only install discovery, gated on an explicit `authorized=True`.

    `inventory` follows `platform_discovery.discover_software_installations`' own parameter: a caller
    passing one makes the probe deterministic (fixtures); passing None uses the module's declared
    candidate inventory. `reason` is recorded only to make the authorization auditable in the
    returned rows' provenance — it is not sent anywhere.
    """
    if authorized is not True:
        raise ProbeNotAuthorized(
            f"{NOT_AUTHORIZED_CODE}: software discovery is default-off; pass authorized=True after the "
            f"operator grants a read-only install probe (reason={reason!r})")
    from . import platform_discovery

    observations = platform_discovery.discover_software_installations(inventory)
    return [{**record, "probedVia": "orchestration.probe.run_probe", "authorizationReason": reason}
            for record in observations]


def run_process_probe(*, authorized: bool = False, reason: str | None = None) -> dict[str, Any]:
    """The subprocess-carrying discovery (`--version` execs + process listing), gated the same way.

    Separated from `run_probe` on purpose: the cheaper one only stats declared roots, this one runs
    programs. An authorization for one is not an authorization for the other.
    """
    if authorized is not True:
        raise ProbeNotAuthorized(
            f"{PROCESS_PROBE_NOT_AUTHORIZED_CODE}: running candidate executables and listing processes "
            f"is default-off; requires its own explicit grant (reason={reason!r})")
    from . import platform_discovery

    resolved = platform_discovery.resolve_current_platform()
    return {**resolved, "probedVia": "orchestration.probe.run_process_probe",
            "authorizationReason": reason}
