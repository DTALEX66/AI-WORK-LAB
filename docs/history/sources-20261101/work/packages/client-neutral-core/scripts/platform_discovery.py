"""Read-only platform discovery for Codex/Hermes logical instances (WL3-100).

Discovers package -> executable -> launcher -> config root -> profile -> active
process metadata without reading credentials, sessions, or private bodies.
Windows: App Execution Alias (PATH), Start Menu shortcuts, running process
images. Degrades gracefully to UNAVAILABLE when nothing is found; never
auto-uninstalls or mutates anything.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import platform_identity as identity
import software_installation_identity as sii


@dataclass
class DiscoveredEntry:
    package_identity: str
    executable_realpath: str
    launcher_id: str
    launcher_target: str | None
    binary_digest: str | None
    effective_config_root: str | None
    profile_id: str | None
    discovered_version: str | None
    freshness: str = "FRESH"
    active_process: bool = False
    source: str = "unknown"
    logical_instance_id: str | None = None


def _sha256_file(path: Path) -> str | None:
    import hashlib

    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _realpath(candidate: str | Path) -> str | None:
    try:
        resolved = Path(candidate).resolve()
        return str(resolved) if resolved.is_file() else None
    except OSError:
        return None


def _which(name: str) -> str | None:
    return shutil.which(name)


def _config_root_home(directory: str | None) -> str | None:
    if not directory:
        return None
    path = Path(directory).expanduser()
    return str(path) if path.is_dir() else None


def _version_from_executable(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, "--version"],
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
            timeout=10,
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip()
        return output.splitlines()[0][:120] if output else None
    except (OSError, subprocess.SubprocessError):
        return None


def _running_processes() -> set[str]:
    """Best-effort process image names (Windows tasklist or ps)."""
    names: set[str] = set()
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            for line in (result.stdout or "").splitlines():
                fields = line.split(",")
                if len(fields) >= 1:
                    names.add(fields[0].strip('"').lower())
        else:
            result = subprocess.run(
                ["ps", "-eo", "comm"],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            for line in (result.stdout or "").splitlines():
                name = line.strip().lower()
                if name:
                    names.add(Path(name).name)
    except (OSError, subprocess.SubprocessError):
        pass
    return names


def _windows_start_menu_shortcuts() -> list[Path]:
    """Read Start Menu .lnk files (names only; contents are never parsed)."""
    shortcuts: list[Path] = []
    if os.name != "nt":
        return shortcuts
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for link in root.rglob("*.lnk"):
                shortcuts.append(link)
        except OSError:
            continue
    return shortcuts


def _find_existing(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _hermes_gui_launcher() -> Path | None:
    """Locate the managed Hermes desktop launcher (vbs) without parsing it."""
    if os.name != "nt":
        return None
    home = Path(os.environ.get("HERMES_HOME", "")).expanduser() if os.environ.get("HERMES_HOME") else Path.home() / ".hermes"
    appdata = Path(os.environ.get("APPDATA", "")).expanduser() / "hermes"
    # Baseline 2026-08-23: entry = OFFICIAL standard format (Electron Hermes.exe),
    # never a custom .vbs launcher invented by WORK-LAB.
    return _find_existing(
        [
            appdata / "hermes-agent" / "apps" / "desktop" / "release" / "win-unpacked" / "Hermes.exe",
            home / "hermes-agent" / "apps" / "desktop" / "release" / "win-unpacked" / "Hermes.exe",
        ]
    )


def discover_codex() -> list[DiscoveredEntry]:
    entries: list[DiscoveredEntry] = []
    codex = _which("codex")
    config_root = _config_root_home(os.environ.get("CODEX_HOME") or "~/.codex")
    running = _running_processes()
    launcher_target = None
    if codex:
        real = _realpath(codex)
        if real:
            launcher_target = codex
            entries.append(
                DiscoveredEntry(
                    package_identity="codex-cli",
                    executable_realpath=real,
                    launcher_id="codex-path",
                    launcher_target=launcher_target,
                    binary_digest=_sha256_file(Path(real)),
                    effective_config_root=config_root,
                    profile_id="codex-user",
                    discovered_version=_version_from_executable(real),
                    active_process=Path(real).name.lower() in running,
                    source="app-execution-alias/path",
                    logical_instance_id="codex",
                )
            )
    else:
        entries.append(
            DiscoveredEntry(
                package_identity="codex-cli",
                executable_realpath="",
                launcher_id="codex-path",
                launcher_target=None,
                binary_digest=None,
                effective_config_root=config_root,
                profile_id="codex-user",
                discovered_version=None,
                active_process=False,
                source="missing",
                logical_instance_id="codex",
            )
        )
    return entries


def discover_hermes() -> list[DiscoveredEntry]:
    entries: list[DiscoveredEntry] = []
    hermes = _which("hermes")
    config_root = _config_root_home(os.environ.get("HERMES_HOME") or "~/.hermes")
    running = _running_processes()
    real = _realpath(hermes) if hermes else None
    if real:
        entries.append(
            DiscoveredEntry(
                package_identity="hermes-agent",
                executable_realpath=real,
                launcher_id="hermes-path",
                launcher_target=hermes,
                binary_digest=_sha256_file(Path(real)),
                effective_config_root=config_root,
                profile_id="hermes-default",
                discovered_version=_version_from_executable(real),
                active_process=Path(real).name.lower() in running,
                source="path",
                logical_instance_id="hermes",
            )
        )
    else:
        entries.append(
            DiscoveredEntry(
                package_identity="hermes-agent",
                executable_realpath="",
                launcher_id="hermes-path",
                launcher_target=None,
                binary_digest=None,
                effective_config_root=config_root,
                profile_id="hermes-default",
                discovered_version=None,
                active_process=False,
                source="missing",
                logical_instance_id="hermes",
            )
        )
    gui = _hermes_gui_launcher()
    if gui:
        # GUI launcher observation: same logical install; when the CLI exists
        # we share its realpath so identity resolves to ALIAS_DUPLICATE (two
        # launchers, one install) instead of a false DUAL_INSTALLATION. The
        # .vbs body is never parsed.
        target = real if real else str(gui)
        digest = _sha256_file(Path(real)) if real else _sha256_file(gui)
        entries.append(
            DiscoveredEntry(
                package_identity="hermes-agent",
                executable_realpath=target,
                launcher_id="hermes-gui-exe",
                launcher_target=str(gui),
                binary_digest=digest,
                effective_config_root=config_root,
                profile_id="hermes-default",
                discovered_version=None,
                active_process="hermes" in running,
                source="desktop-launcher",
                logical_instance_id="hermes",
            )
        )
    return entries


def discover_cc_switch() -> list[DiscoveredEntry]:
    entries: list[DiscoveredEntry] = []
    config_root = _config_root_home(os.environ.get("CC_SWITCH_HOME") or "~/.cc-switch")
    running = _running_processes()
    executable = shutil.which("cc-switch")
    real = _realpath(executable) if executable else None
    active = any("cc-switch" in name or "ccswitch" in name for name in running)
    entries.append(
        DiscoveredEntry(
            package_identity="cc-switch",
            executable_realpath=real or "",
            launcher_id="cc-switch-config",
            launcher_target=executable,
            binary_digest=_sha256_file(Path(real)) if real else None,
            effective_config_root=config_root,
            profile_id="cc-switch-default",
            discovered_version=_version_from_executable(real) if real else None,
            active_process=active,
            source="config-root" if config_root else "missing",
            logical_instance_id="cc-switch",
        )
    )
    return entries


# ---------------------------------------------------------------------------
# P0-07 / TaskPack §22, §29: read-only software installation discovery.
# ---------------------------------------------------------------------------
# The software WORK-LAB manages. Real discovery probes ONLY the declared
# install roots / executable of each entry — public install metadata. It never
# reads user config / data / credentials and never writes. A fresh install is
# located by the §11 resolution order (user-declared -> worklab-recommended ->
# vendor default). ``expected_existing`` records where a *valid* install was
# last confirmed so "expected D, observed C" resolves to LOCATION_DRIFT.
SOFTWARE_CANDIDATE_INVENTORY: list[dict[str, Any]] = [
    {
        "software_id": "deepseek-harness",
        "package_identity": "deepseek-harness",
        # AG-07 (2026-10-01): the OFFICIAL build installs at the vendor default
        # per-user path, declared here via %LOCALAPPDATA% so no drive letter is
        # pinned. The old community root is kept only as a legacy probe: it now
        # holds nothing but the .dsh data directory, so it must not be reported
        # as the install root.
        "install_roots": [
            "%LOCALAPPDATA%/Programs/DeepSeek Harness",
            "D:/All projects/DSH",
        ],
        "executables": ["DeepSeek Harness.exe", "DSH Desktop.exe"],
        "expected_existing": None,
        "config_root_env": None,
        "os_managed": False,
        "install_type": "official_per_user_electron",
    },
    {
        "software_id": "hermes-agent",
        "package_identity": "hermes-agent",
        "install_roots": [],
        "executables": ["Hermes.exe"],
        "expected_existing": None,
        "config_root_env": "HERMES_HOME",
        "os_managed": False,
        "install_type": "community_desktop_release",
    },
    {
        "software_id": "openai-codex",
        "package_identity": "openai-codex",
        "install_roots": [],
        "executables": ["codex"],
        "expected_existing": None,
        "config_root_env": "CODEX_HOME",
        "os_managed": False,
        "install_type": "native_package_manager",
    },
    {
        "software_id": "cc-switch",
        "package_identity": "cc-switch",
        "install_roots": [],
        "executables": ["cc-switch"],
        "expected_existing": None,
        "config_root_env": "CC_SWITCH_HOME",
        "os_managed": False,
        "install_type": "portable",
    },
    {
        "software_id": "open-human",
        "package_identity": "open-human",
        "install_roots": [],
        "executables": ["openhuman"],
        "expected_existing": None,
        "config_root_env": None,
        "os_managed": False,
        "install_type": "unknown",
    },
    {
        "software_id": "open-design",
        "package_identity": "open-design",
        "install_roots": [],
        "executables": ["open-design"],
        "expected_existing": None,
        "config_root_env": None,
        "os_managed": False,
        "install_type": "unknown",
    },
]


_PERCENT_VAR_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")


def _expand_root(raw_root: str) -> str:
    """Expand a declared install root portably, including ``%VAR%`` on any platform.

    ``os.path.expandvars`` honours ``%VAR%`` only on Windows; on POSIX it leaves that
    form untouched and expands only ``$VAR``. Because this inventory declares vendor
    DEFAULTS in Windows form (``%LOCALAPPDATA%/Programs/...``), relying on it meant
    the probe silently failed to resolve those roots anywhere except Windows — found
    by CI running the suite on Linux, where ``%WL_TEST_INSTALL_ROOT%`` stayed literal
    and the probe reported no install root at all.

    The declared form is Windows-like, so expand that form explicitly and
    case-insensitively (Windows environment variables are case-insensitive), then
    still let ``os.path.expandvars`` handle whatever POSIX-style form a caller used.
    """
    expanded = str(raw_root)
    for _ in range(4):  # bounded: a var may itself contain a var, but not forever
        replaced = _PERCENT_VAR_RE.sub(
            lambda m: os.environ.get(m.group(1))
            or os.environ.get(m.group(1).upper())
            or m.group(0),
            expanded,
        )
        if replaced == expanded:
            break
        expanded = replaced
    expanded = os.path.expandvars(expanded)
    return os.path.expanduser(expanded)


def _probe_install(candidate: dict[str, Any]) -> dict[str, Any]:
    """Read-only probe of one software's declared install roots. No writes,
    no user config / data / credentials reads.

    Two correctness rules learned from the 2026-10-01 DSH reinstall:

    * roots are environment-expanded, so a vendor-default root can be declared
      as ``%LOCALAPPDATA%/Programs/...`` instead of hardcoding one machine's
      drive letter (a pinned path rots the moment the user reinstalls);
    * a root that actually CONTAINS the declared executable wins over one that
      merely exists. The previous first-existing-directory-wins rule reported
      the stale leftover community directory ``D:/All projects/DSH`` as the DSH
      install root even though its executable is gone, producing a misleading
      ``SINGLE_UNVERIFIED`` in the snapshot's software[] projection.
    """
    install_root: str | None = None
    executable: str | None = None
    fallback_root: str | None = None
    for raw_root in candidate.get("install_roots", []):
        expanded = _expand_root(raw_root)
        probe = Path(expanded)
        if not probe.is_dir():
            continue
        if fallback_root is None:
            fallback_root = str(probe)
        for exe_name in candidate.get("executables", []):
            exe_path = probe / exe_name
            if exe_path.is_file():
                return {
                    "install_root": str(probe),
                    "executable_realpath": str(exe_path.resolve()),
                    "os_managed": bool(candidate.get("os_managed")),
                    "install_type": candidate.get("install_type"),
                    "config_root_env": candidate.get("config_root_env"),
                }
    # No root carried the executable: report the directory that exists, if any,
    # with executable None so the resolver can classify it as unverified rather
    # than pretending it is a valid install.
    if fallback_root is not None:
        install_root = fallback_root
    return {
        "install_root": install_root,
        "executable_realpath": executable,
        "os_managed": bool(candidate.get("os_managed")),
        "install_type": candidate.get("install_type"),
        "config_root_env": candidate.get("config_root_env"),
    }


def discover_software_installations(
    inventory: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """§22 read-only software installation discovery.

    Probes ONLY the declared install roots / executable of each managed
    software and classifies each via the shared :mod:`software_installation_identity`
    resolver (single source of truth — no second engine). Degrades to
    ``install_root=None`` when nothing is found; a fresh install is located by
    the §11 resolution order, never a silent C: vendor default. Pass a custom
    ``inventory`` to make discovery fully deterministic (fixtures).
    """
    inv = inventory if inventory is not None else SOFTWARE_CANDIDATE_INVENTORY
    observations: list[dict[str, Any]] = []
    for candidate in inv:
        probe = _probe_install(candidate)
        software_id = candidate["software_id"]
        observed_roots = [probe["install_root"]] if probe["install_root"] else []
        cls = sii.classify_installation(
            expected_existing=candidate.get("expected_existing"),
            observed=observed_roots,
            verified=bool(probe["executable_realpath"]),
            os_managed=probe["os_managed"],
        )
        record = sii.preflight_identity_record(
            software_id=software_id,
            expected_existing=candidate.get("expected_existing"),
            observed=observed_roots,
            verified=bool(probe["executable_realpath"]),
            os_managed=probe["os_managed"],
        )
        record.update(
            package_identity=candidate.get("package_identity", software_id),
            install_root=probe["install_root"],
            executable_realpath=probe["executable_realpath"],
            install_type=probe["install_type"],
        )
        record["location_status"] = cls["location_status"]
        observations.append(record)
    return observations


def resolve_software_installation(
    software_id: str,
    *,
    user_declared: str | None = None,
    observed: list[str] | None = None,
    expected_existing: str | None = None,
    verified: bool = False,
    os_managed: bool = False,
    relocation_requested: bool = False,
) -> dict[str, Any]:
    """§23 single canonical resolver: classify one software's install location
    and return a software-installation-identity contract record. Pure; all
    inputs are already-discovered facts."""
    return sii.preflight_identity_record(
        software_id=software_id,
        user_declared=user_declared,
        observed=observed or [],
        expected_existing=expected_existing,
        verified=verified,
        os_managed=os_managed,
        relocation_requested=relocation_requested,
    )


def discover_all() -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for entry in discover_codex() + discover_hermes() + discover_cc_switch():
        observations.append(
            {
                "logical_instance_id": entry.logical_instance_id,
                "package_identity": entry.package_identity,
                "executable_realpath": entry.executable_realpath,
                "launcher_id": entry.launcher_id,
                "launcher_target": entry.launcher_target,
                "binary_digest": entry.binary_digest,
                "effective_config_root": entry.effective_config_root,
                "profile_id": entry.profile_id,
                "discovered_version": entry.discovered_version,
                "freshness": entry.freshness,
                "active_process": entry.active_process,
                "source": entry.source,
            }
        )
    return observations


def resolve_current_platform() -> dict[str, Any]:
    """Run real discovery and classify identities via the canonical resolver."""
    observations = discover_all()
    resolved = identity.resolve_identity(observations)
    resolved["discovery_source"] = "real-platform-probe"
    resolved["probed"] = {
        "codex_cli": _which("codex") is not None,
        "hermes_cli": _which("hermes") is not None,
        "hermes_gui_launcher": _hermes_gui_launcher() is not None,
        "cc_switch_config_root": _config_root_home(os.environ.get("CC_SWITCH_HOME") or "~/.cc-switch") is not None,
        "os": os.name,
        "start_menu_links": len(_windows_start_menu_shortcuts()),
    }
    return resolved


if __name__ == "__main__":
    print(json.dumps(resolve_current_platform(), ensure_ascii=False, indent=2, default=str))
