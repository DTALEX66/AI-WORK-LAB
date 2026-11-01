"""Five-dimension runtime baseline, dimensions 1+2, measured read-only on this machine.

AGENTS.md mandates that every managed software surface has (1) one unique canonical entry —
the vendor-shipped official binary, never an invented launcher such as a .vbs — and (2) a
desktop shortcut whose target chain resolves end to end (TargetPath, WorkingDirectory and
IconLocation that are named must exist). Nothing is fixed by drive-letter literals: expected
locations come from the repo's own declarations (config/capability-matrix.json clients[],
config/software-registry.json, config/config-ownership.json adapter_defaults, AGENTS.md
dimension 1) and are resolved through environment layers (%LOCALAPPDATA%, DSH_HOME,
HERMES_HOME, CODEX_CLI read from HKCU\\Environment) and the uninstall registry — the DSH
"RESOLVE_AT_RUNTIME_NOT_HARDCODED" policy.

Safety contract enforced by this tool:
  * read-only everywhere; registry reads only; no install, no repair, no re-pin;
  * no GUI application and no target binary is ever launched — .lnk files are read via a
    hand-rolled [MS-SHLLINK] byte parser (LinkInfo TargetPath) plus an independent
    WScript.Shell field cross-check (CreateShortcut reads fields only; .Run is never
    called);
  * no file contents are read — only path strings and existence verdicts are recorded.

Verdicts reuse the project's own fail-closed location_status vocabulary, loaded at runtime
from packages/contracts/schemas/workflow/software-installation-identity.schema.json so this
projection cannot drift from the contract. ENTRY_NOT_RESOLVED is the project's probe-level
"could not measure this machine" state (scripts/audit/executor_live_probe.py) and is a red
finding, never a green. UNKNOWN is never reported as 0 or as "fine".

Usage:
    python scripts/audit/entry_baseline_readback.py [--out docs/audits/ENTRY_BASELINE_2026-10-08.json]
Exit: 0 after a completed measurement (a red verdict is a finding, not a crash);
      2 if a declaration source file or the vocabulary contract cannot be read.
"""
from __future__ import annotations

import argparse
import glob as globlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PureWindowsPath

REPO = Path(__file__).resolve().parents[2]
CAPABILITY_MATRIX = REPO / "config" / "capability-matrix.json"
SOFTWARE_REGISTRY = REPO / "config" / "software-registry.json"
CONFIG_OWNERSHIP = REPO / "config" / "config-ownership.json"
IDENTITY_SCHEMA = REPO / "packages" / "contracts" / "schemas" / "workflow" / "software-installation-identity.schema.json"

# The single state outside the location_status enum: the project's own probe-level
# "could not measure" state, spelled exactly as scripts/audit/executor_live_probe.py uses it.
ENTRY_NOT_RESOLVED = "ENTRY_NOT_RESOLVED"

DEFAULT_OUT = "docs/audits/ENTRY_BASELINE_2026-10-08.json"


def scratch_root() -> Path:
    """Temp files stay inside the project Git root (AGENTS.md data boundary): honour an
    already-set TMPDIR/TEMP/TMP, otherwise fall back to .project-local/runs in this repo."""
    for var in ("TMPDIR", "TEMP", "TMP"):
        val = env(var)
        if val and Path(val).is_dir():
            return Path(val)
    root = REPO / ".project-local" / "runs" / "entry-baseline"
    root.mkdir(parents=True, exist_ok=True)
    return root

# Per-surface env layers that can silently redirect a launch (ERR-088 trap family).
ENV_LAYER_FOR = {"deepseek-harness": ("DSH_HOME",), "codex": ("CODEX_CLI",), "hermes": ("HERMES_HOME",)}


# ---------------------------------------------------------------------------
# vocabulary anti-drift
# ---------------------------------------------------------------------------
def load_location_vocabulary() -> tuple[list[str], str]:
    """location_status enum read from the contract schema at runtime (never re-invented)."""
    schema = json.loads(IDENTITY_SCHEMA.read_text(encoding="utf-8"))
    enum = schema["properties"]["location_status"]["enum"]
    if not isinstance(enum, list) or "LOCATION_DRIFT" not in enum:
        raise ValueError("location_status enum unreadable/unexpected in " + str(IDENTITY_SCHEMA))
    return enum, IDENTITY_SCHEMA.relative_to(REPO).as_posix()


# ---------------------------------------------------------------------------
# pure MS-SHLLINK parser (TargetPath / WorkingDirectory / IconLocation), no I/O
# ---------------------------------------------------------------------------
def _u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def _u16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]


def ansi_codec() -> str:
    """The codec a shell link's ANSI fields must be read with, chosen once for this whole file.

    Windows stores those bytes in the system ANSI codepage, and `mbcs` is the only name that means
    "whatever this machine's is". Off Windows there is no system ANSI codepage and looking `mbcs` up
    raises LookupError -- which is how the cross-platform gate died on the Linux runner (finding W03 of
    the 2026-10-11 cloud audit, `test_entry_baseline_projection.py:195`) while every Windows host stayed
    green. cp1252 is the declared reading assumption there, so the synthetic fixture and any ASCII-only
    real path round-trip identically on both hosts. The assumption is carried in the parse result rather
    than hidden, because a genuinely codepage-936 shortcut read on a Linux runner is not something this
    function can honestly resolve.
    """
    return "mbcs" if os.name == "nt" else "cp1252"


def _cstr(raw: bytes, start: int, unicode_: bool) -> str:
    if start >= len(raw):
        return ""
    if unicode_:
        # walk by 2-byte code units: a naive find(b"\x00\x00") truncates one byte early
        # when the final character's high byte abuts the terminator
        end = start
        while end + 1 < len(raw) and raw[end:end + 2] != b"\x00\x00":
            end += 2
        if end + 1 >= len(raw):
            return ""
        return raw[start:end].decode("utf-16-le", errors="replace")
    end = raw.find(b"\x00", start)
    if end < 0:
        return ""
    return raw[start:end].decode(ansi_codec(), errors="replace")


_PATHISH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|%)")


def parse_lnk(raw: bytes) -> dict:
    """Hand-rolled [MS-SHLLINK] field reader for TargetPath / WorkingDirectory /
    IconLocation. Pure over bytes; returns dict(target_path, working_directory,
    icon_location, arguments, name, local_base_path, parse_ok, parse_error)."""
    out: dict = {"parse_ok": False, "parse_error": None, "ansiCodec": ansi_codec()}
    if os.name != "nt":
        out["ansiCodecBasis"] = ("assumed cp1252: this host has no system ANSI codepage, so a"
                                  " shortcut written in another codepage may decode wrongly")
    try:
        if len(raw) < 76 or _u32(raw, 0) != 0x4C:
            out["parse_error"] = "header size != 0x4C"
            return out
        out["clsid_ok"] = raw[4:20] == bytes.fromhex("0114020000000000c000000000000046")
        flags = _u32(raw, 20)
        pos = 76
        if flags & 0x00000001:  # HasTargetIDList — walk items to the 0x0000 terminator
            while pos + 2 <= len(raw):
                sz = _u16(raw, pos)
                if sz == 0:
                    pos += 2
                    break
                pos += sz
        local_base = None
        if pos + 24 <= len(raw):
            li_len = _u32(raw, pos)
            if li_len >= 28:
                lbp_off = _u32(raw, pos + 16)  # LocalBasePathOffset
                if 0 < lbp_off < li_len:
                    start = pos + lbp_off
                    # encoding sniff: UTF-16 paths look like 'C\x00:\x00'; ANSI like 'C:\\'
                    uni = start + 1 < len(raw) and raw[start + 1] == 0x00 and 0x20 <= raw[start] < 0x7F
                    local_base = _cstr(raw, start, uni)
                pos += li_len
        out["local_base_path"] = local_base
        # StringData: counted strings (UTF-16 when header flag 0x10 is set — observed on
        # real shells; some tools omit zero-count slots, so slot POSITION is best-effort,
        # never the adjudication source). Used for name/arguments candidates only.
        uni = bool(flags & 0x00000010)
        p = pos
        strings: list[str] = []
        for _ in range(4):
            cnt = _u16(raw, p)
            p += 2
            if uni:
                strings.append(raw[p:p + cnt * 2].decode("utf-16-le", errors="replace"))
                p += cnt * 2
            else:
                strings.append(raw[p:p + cnt].decode(ansi_codec(), errors="replace"))
                p += cnt
        out["name"], relpath, out["working_directory"], out["arguments"] = strings
        # ExtraData blocks: [u32 BlockSize][u32 BlockSignature][data]. The Icon Location
        # and environment blocks carry a path-like string; extract the first pathish value
        # (heuristic; WScript cross-check confirms). Zero-length or blob blocks are skipped.
        icon = None
        while p + 8 <= len(raw):
            blen = _u32(raw, p)
            if blen < 8:
                break
            body = raw[p:p + blen]
            for off in (8, 12, 16, 20, 24):
                cand = _cstr(body, off, True).strip()
                head = cand.split(",")[0]
                if not icon and _PATHISH.match(cand) and PureWindowsPath(head).suffix.lower() in {".ico", ".exe", ".dll", ".msi", ".lnk"}:
                    icon = cand
            p += blen
        out["icon_location"] = icon
        # TargetPath: rooted LocalBasePath wins; relative values combine with
        # WorkingDirectory. A relative string alone is not trusted.
        target = local_base
        if target and out.get("working_directory") and not _PATHISH.match(target):
            target = str(PureWindowsPath(out["working_directory"]) / target)
        if not target and relpath and _PATHISH.match(relpath):
            target = relpath
        out["target_path"] = target
        out["parse_ok"] = True
    except (IndexError, struct.error, ValueError) as exc:
        out["parse_error"] = f"malformed shell link: {exc!r}"
    return out


# ---------------------------------------------------------------------------
# pure verdict decision — the pin surface of tests/ci/test_entry_baseline_projection.py
# ---------------------------------------------------------------------------
def _norm(path: str | None) -> str:
    if not path:
        return ""
    return str(path).strip().strip('"').replace("\\", "/").rstrip("/").casefold()


def _in_temp(path: str | None, temp_roots: list[str]) -> bool:
    """NSIS silent-install trap: .lnk fields reset to the temp install directory."""
    n = _norm(path)
    if not n:
        return False
    if re.search(r"/temp/[~a-z]*ns[a-z0-9._-]*", n) or ".tmp/" in n + "/":
        return True
    return any(n.startswith(_norm(t) + "/") or n == _norm(t) for t in temp_roots if t)


def decide(res: dict) -> dict:
    """Pure verdict for one surface from a pre-collected resolution dict; no I/O.

    Keys: readback_error, os_managed, relocation_requested, install_roots (distinct
    existing product roots), expected_roots (env-resolved declared locations),
    shortcut (dict: lnk_path, target, target_exists, working_dir, working_dir_exists,
    icon, icon_named, icon_exists), shortcuts (all desktop matches), auxiliary_layers,
    unconfirmed (list[str]), wscript_agree, invented_launcher, require_desktop,
    cli_resolved, cli_paths, temp_roots.
    Returns {verdict, reason, canonical_candidate}; verdicts come from the schema
    location_status enum plus ENTRY_NOT_RESOLVED.
    """
    temp_roots = res.get("temp_roots") or []
    if res.get("readback_error"):
        return {"verdict": ENTRY_NOT_RESOLVED,
                "reason": f"real-machine readback did not complete: {res['readback_error']}",
                "canonical_candidate": None}
    if res.get("os_managed"):
        return {"verdict": "OS_MANAGED",
                "reason": "OS/package-managed install channel; preserve official channel, do not relocate",
                "canonical_candidate": None}
    if res.get("relocation_requested"):
        return {"verdict": "RELOCATION_REQUESTED",
                "reason": "relocation requested with no existing approved install",
                "canonical_candidate": None}

    def result(verdict: str, reason: str, cand: str | None = None) -> dict:
        return {"verdict": verdict, "reason": reason, "canonical_candidate": cand}

    roots = res.get("install_roots") or []
    reg_norm: dict[str, str] = {}
    for r in roots:
        if _norm(r):
            reg_norm.setdefault(_norm(r), r)
    reg_roots = list(reg_norm.values())
    expected = res.get("expected_roots") or []
    sc = res.get("shortcut")
    shortcuts = res.get("shortcuts") if res.get("shortcuts") is not None else ([sc] if sc else [])
    live_norm: dict[str, str] = {}
    for s in shortcuts:
        if s and s.get("target_exists") and s.get("target"):
            live_norm.setdefault(_norm(s["target"]), s["target"])
    live_targets = sorted(live_norm.values())
    sc_root = str(PureWindowsPath(sc["target"]).parent) if sc and sc.get("target_exists") else None
    observed = reg_roots + ([sc_root] if sc_root else [])

    # NSIS / invented-launcher traps convict before any "single +1" comfort.
    if sc:
        if res.get("invented_launcher"):
            return result("LOCATION_DRIFT",
                          f"entry is an invented script/shell launcher, not the vendor binary: {sc.get('lnk_path')}")
        if _in_temp(sc.get("target"), temp_roots):
            return result("LOCATION_DRIFT",
                          f"shortcut TargetPath points into the temp install directory (NSIS reset trap): {sc['target']}")
        if _in_temp(sc.get("icon"), temp_roots):
            return result("LOCATION_DRIFT",
                          f"shortcut IconLocation points into the temp install directory (NSIS reset trap): {sc['icon']}",
                          sc.get("target"))

    def path_match(a: str, b: str) -> bool:
        na, nb = _norm(a), _norm(b)
        return na == nb or na.startswith(nb + "/") or nb.startswith(na + "/")

    if len(reg_norm) > 1 or len(live_targets) > 1:
        return result("DUAL_INSTALLATION",
                      f"multiple distinct install locations: roots={reg_roots} live shortcut targets={live_targets}")
    if sc_root and reg_norm and not any(path_match(sc_root, r) for r in reg_roots):
        return result("LOCATION_DRIFT",
                      f"installed path and shortcut target disagree: {reg_roots[0]} vs {sc['target']}")

    if sc and not sc.get("target_exists"):
        if reg_roots:
            return result("LOCATION_DRIFT",
                          f"shortcut target does not exist while an install does: {sc['target']!r} vs {reg_roots[0]}")
        if expected:
            return result("MISSING_EXPECTED_INSTALL",
                          f"desktop shortcut target is dead and the declared expected install {expected} is absent")
        return result("NOT_INSTALLED",
                      f"desktop shortcut exists but its TargetPath is dead: {sc['target']}; nothing installed was found")

    if not observed and not live_targets:
        if expected:
            return result("MISSING_EXPECTED_INSTALL",
                          f"declared expected install {expected} absent; no vendor-default fallback permitted")
        if res.get("require_desktop"):
            return result("NOT_INSTALLED", "no desktop shortcut and no install detected on any declared source")
        if not res.get("cli_resolved"):
            return result("NOT_INSTALLED", "no install registered and no PATH entry resolved")

    if expected and (observed or live_targets):
        if not any(path_match(e, o) for e in expected for o in observed + live_targets):
            return result("LOCATION_DRIFT",
                          f"declared expected location {expected} not matched by observed install {observed or live_targets}")

    if sc and res.get("wscript_agree") is False:
        return result("SINGLE_UNVERIFIED",
                      "hand MS-SHLLINK parser and WScript.Shell disagree on the shortcut TargetPath; "
                      "measurement integrity unconfirmed", sc.get("target"))

    if sc and sc.get("target_exists"):
        if sc.get("working_dir") and not sc.get("working_dir_exists"):
            return result("SINGLE_UNVERIFIED",
                          f"named WorkingDirectory does not exist: {sc['working_dir']}", sc["target"])
        if sc.get("icon_named") and not sc.get("icon_exists"):
            return result("SINGLE_UNVERIFIED",
                          f"named IconLocation does not exist: {sc['icon']}", sc["target"])
    if res.get("require_desktop") and not sc and (observed or expected):
        return result("SINGLE_UNVERIFIED",
                      "an install exists but no desktop shortcut was found — dimension 2 unconfirmed",
                      observed[0] if observed else None)

    if res.get("unconfirmed"):
        cand = observed[0] if observed else (sc or {}).get("target") or (res.get("cli_paths") or [None])[0]
        return result("SINGLE_UNVERIFIED",
                      "entry resolves once but not fully confirmable read-only: " + "; ".join(res["unconfirmed"]), cand)

    cand = (live_targets[0] if live_targets else None) or (observed[0] if observed else None) \
        or (sc or {}).get("target") or (res.get("cli_paths") or [None])[0]
    return result("SINGLE_VERIFIED", "exactly one entry and its chain resolves end to end", cand)


# ---------------------------------------------------------------------------
# real-machine readback (registry / paths / .lnk bytes; never launches a target)
# ---------------------------------------------------------------------------
def env(name: str, default: str = "") -> str:
    return os.environ.get(name) or default


def expand(path: str | None) -> str | None:
    return os.path.expandvars(os.path.expanduser(path)) if path else path


def reg_uninstall_rows() -> list[dict]:
    import winreg
    rows = []
    hives = [("HKCU", winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", False),
             ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", False),
             ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", True)]
    for label, hive, root, wow in hives:
        try:
            key = winreg.OpenKey(hive, root)
        except OSError:
            continue
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(key, i)
            except OSError:
                break
            i += 1
            try:
                sk = winreg.OpenKey(key, sub)
                vals = {v: (winreg.QueryValueEx(sk, v)[0] if _has(sk, v) else None)
                        for v in ("DisplayName", "DisplayVersion", "InstallLocation", "UninstallString")}
                winreg.CloseKey(sk)
            except OSError:
                continue
            rows.append({"hive": label, "wow6432": wow, "root": root, "subkey": sub, **vals})
    return rows


def _has(key, name: str) -> bool:
    import winreg
    try:
        winreg.QueryValueEx(key, name)
        return True
    except OSError:
        return False


def reg_env_layer(name: str) -> tuple[bool, str]:
    """HKCU\\Environment read (DSH_HOME / CODEX_CLI / HERMES_HOME / Path layers)."""
    import winreg
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        return True, str(winreg.QueryValueEx(k, name)[0])
    except OSError:
        return False, ""


def desktop_dirs() -> list[dict]:
    dirs = []
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        redirect = str(winreg.QueryValueEx(k, "Desktop")[0])
    except OSError:
        redirect = ""
    seen: set[str] = set()
    for label, raw, src in (("user_desktop", redirect or os.path.join(env("USERPROFILE"), "Desktop"),
                             "HKCU\\...\\User Shell Folders\\Desktop"),
                            ("public_desktop", os.path.join(env("PUBLIC", r"C:\Users\Public"), "Desktop"),
                             "%PUBLIC%\\Desktop")):
        p = expand(raw)
        if p and _norm(p) not in seen and Path(p).is_dir():
            seen.add(_norm(p))
            dirs.append({"label": label, "path": p, "registrySource": src})
    return dirs


def scan_shortcuts(dirs: list[dict]) -> list[dict]:
    found = []
    for d in dirs:
        for lnk in sorted(Path(d["path"]).glob("*.lnk")):
            rec = parse_lnk(lnk.read_bytes())
            rec["lnk_path"] = str(lnk)
            rec["origin"] = d["label"]
            found.append(rec)
    return found


def wscript_fields(lnk_paths: list[str]) -> dict[str, dict]:
    """Independent WScript.Shell field read of TargetPath/Arguments/WorkingDirectory/
    IconLocation. CreateShortcut exposes fields only — the target is never Run. The vbs
    lives in the temp dir only for the duration of the call and is deleted there; it is
    a measurement reader, never a launcher placed where a user could open it. (On this
    build `cscript //U` over a pipe yields empty stdout, and `-` stdin is treated as a
    filename, so the cross-check uses a temp file without //U and decodes the console
    codepage.) Failure returns {} and the affected rows carry an explicit unconfirmed
    note rather than a green."""
    if not lnk_paths:
        return {}
    scratch = Path(tempfile.mkdtemp(prefix="entry-baseline-lnk-", dir=str(scratch_root())))
    vbs = scratch / "readlnk.vbs"
    lines = ["Dim ws, s", 'Set ws = CreateObject("WScript.Shell")']
    for i, p in enumerate(lnk_paths):
        esc = p.replace('"', '""')
        lines.append(f'Set s = ws.CreateShortcut("{esc}")')
        lines.append(f'WScript.Echo "REC{i}|T|" & s.TargetPath & "|A|" & s.Arguments & "|W|" & s.WorkingDirectory & "|I|" & s.IconLocation')
    try:
        vbs.write_bytes(("\r\n".join(lines) + "\r\n").encode(ansi_codec(), errors="replace"))
    except OSError:
        return {}
    out: dict[str, dict] = {}
    try:
        proc = subprocess.run(["cscript.exe", "//nologo", "//E:vbscript", str(vbs)],
                              capture_output=True, timeout=90)
        raw = proc.stdout
        text = (raw[2:].decode("utf-16-le", errors="replace") if raw[:2] == b"\xff\xfe"
                else raw.decode(ansi_codec(), errors="replace"))
        for line in text.splitlines():
            m = re.match(r"REC(\d+)\|T\|(.*?)\|A\|(.*?)\|W\|(.*?)\|I\|(.*)$", line.strip())
            if m:
                i, t, a, w, ic = m.groups()
                if int(i) < len(lnk_paths):
                    out[lnk_paths[int(i)]] = {"target": t, "arguments": a, "working_dir": w, "icon": ic}
    except (OSError, subprocess.TimeoutExpired):
        return {}
    finally:
        try:
            vbs.unlink()
            scratch.rmdir()
        except OSError:
            pass
    return out


def path_dirs() -> list[str]:
    _, user_path = reg_env_layer("Path")
    import winreg
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
        machine_path = str(winreg.QueryValueEx(k, "Path")[0])
    except OSError:
        machine_path = ""
    parts: list[str] = []
    for p in (machine_path + ";" + user_path).split(";") if (user_path or machine_path) else os.pathsep.split(";"):
        e = expand(p.strip())
        if e and Path(e).is_dir() and e not in parts:
            parts.append(e)
    return parts


def which_all(exe_names: tuple[str, ...], dirs: list[str]) -> list[str]:
    hits = []
    for d in dirs:
        for n in exe_names:
            c = os.path.join(d, n)
            if os.path.isfile(c) and c not in hits:
                hits.append(c)
    return hits


# ---------------------------------------------------------------------------
# declared entry forms — AGENTS.md dimension 1 verbatim + software-registry
# officialSource; expected roots are %VAR% formulas resolved at runtime, never
# drive-letter literals (DSH policy: RESOLVE_AT_RUNTIME_NOT_HARDCODED).
# ---------------------------------------------------------------------------
FORMS = {
    "hermes": {
        "declared": "official desktop app (apps/desktop/release/win-unpacked/Hermes.exe, AGENTS.md dim1) + hermes CLI",
        "needles": ("hermes",), "exe_names": {"hermes.exe"},
        "require_desktop": True, "scan_path": True, "cli_names": ("hermes.exe", "hermes.cmd"),
        "expected_env_roots": (r"%LOCALAPPDATA%\hermes\hermes-agent",),
        "entry_candidates": (r"%LOCALAPPDATA%\hermes\bin\hermes.exe",)},
    "codex": {
        "declared": "single repo wrapper: packages/client-neutral-core/bin/codex (bash) + packages/client-neutral-core/bin/codex.cmd (AGENTS.md dim1)",
        "needles": ("codex",), "exe_names": set(),
        "require_desktop": False, "scan_path": True, "cli_names": ("codex.exe",),
        "expected_env_roots": (),
        "candidate_globs": (r"%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe",),
        "repo_wrappers": ("packages/client-neutral-core/bin/codex", "packages/client-neutral-core/bin/codex.cmd"),
        "overlay_globs": (r"%LOCALAPPDATA%\hermes\bin\codex", r"%LOCALAPPDATA%\hermes\bin\codex.cmd")},
    "deepseek-harness": {
        "declared": "official vendor build at the vendor default per-user path, resolved from the uninstall key / shortcut TargetPath (never hardcoded)",
        "needles": ("deepseek harness",), "exe_names": {"deepseek harness.exe"},
        "require_desktop": True, "scan_path": False, "cli_names": (),
        "expected_env_roots": (r"%LOCALAPPDATA%\Programs\DeepSeek Harness",),
        "candidate_globs": ()},
    "cc-switch": {
        "declared": "single desktop shortcut to the installed official executable (AGENTS.md dim1)",
        "needles": ("cc switch",), "exe_names": {"cc-switch.exe"},
        "require_desktop": True, "scan_path": False, "cli_names": (),
        "expected_env_roots": (), "candidate_globs": ()},
    "open-design": {
        "declared": "single desktop shortcut to the installed official executable (AGENTS.md dim1)",
        "needles": ("open design",), "exe_names": {"open design.exe"},
        "require_desktop": True, "scan_path": False, "cli_names": (),
        "expected_env_roots": (r"%LOCALAPPDATA%\Programs\Open Design",), "candidate_globs": ()},
    "openhuman": {
        "declared": "single desktop shortcut to the installed official executable (AGENTS.md dim1)",
        "needles": ("openhuman", "open human"), "exe_names": {"openhuman.exe"},
        "require_desktop": True, "scan_path": False, "cli_names": (),
        "expected_env_roots": (r"%LOCALAPPDATA%\OpenHuman",), "candidate_globs": ()},
    "github": {
        "declared": "official GitHub CLI executable (delivery platform; not a desktop client)",
        "needles": ("github cli",), "exe_names": set(),
        "require_desktop": False, "scan_path": True, "cli_names": ("gh.exe",),
        "expected_env_roots": (), "candidate_globs": ()},
}


def collect_surface(sid: str, c_row: dict, soft: dict, ownership: dict, reg_rows: list[dict],
                    lnks: list[dict], wsx: dict[str, dict], pdirs: list[str],
                    env_layers: dict, dirs: list[dict], now: str) -> dict:
    form = FORMS[sid]
    scope = {"registry_status": c_row.get("registry_status"),
             "ownership_mode": (ownership.get(sid) or {}).get("mode"),
             "official_source": soft.get("officialSource"),
             "legacy_observe": c_row.get("registry_status") == "legacy_observe"}
    res: dict = {
        "scope": scope,
        "readback_error": None, "os_managed": False, "relocation_requested": False,
        "install_roots": [], "expected_roots": [expand(e) for e in form["expected_env_roots"]],
        "auxiliary_layers": [], "unconfirmed": [], "shortcuts": [],
        "require_desktop": form["require_desktop"],
        "temp_roots": [expand(env("TEMP")), expand(env("TMP")), os.path.join(expand(env("LOCALAPPDATA")), "Temp")],
        "readback": [
            {"source": "registry", "key": "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall "
                                        "+ HKLM equivalents (read-only enumeration)", "at": now},
            {"source": "desktop .lnk scan", "dirs": [d["path"] for d in dirs], "at": now}],
    }

    reg_matches = [r for r in reg_rows if r["DisplayName"]
                   and any(n in r["DisplayName"].lower() for n in form["needles"])]
    for r in reg_matches:
        entry = {"source": "registry", "key": f"{r['hive']}\\{r['root']}\\{r['subkey']}",
                 "DisplayName": r["DisplayName"], "DisplayVersion": r["DisplayVersion"],
                 "InstallLocation": r["InstallLocation"]}
        res["readback"].append(entry)
        loc = (r["InstallLocation"] or "").strip().strip('"')
        if loc:
            if Path(loc).is_dir():
                res["install_roots"].append(loc)
            else:
                res["unconfirmed"].append(
                    f"uninstall key {r['hive']}\\{r['subkey']} registers InstallLocation {loc!r} that does not exist")

    matches = []
    for l in lnks:
        ws = wsx.get(l["lnk_path"])
        tgt = ((ws or {}).get("target") or l.get("target_path") or "")
        name = Path(tgt).name.lower() if tgt else ""
        if name and any(name == n for n in form["exe_names"]):
            matches.append(l)
    desktop_matches = [l for l in matches if l.get("origin") in ("user_desktop", "public_desktop")]

    for l in desktop_matches:
        ws = wsx.get(l["lnk_path"])
        hand_tgt = l.get("target_path")
        agree = None
        if ws is not None:
            agree = bool(ws["target"]) and _norm(ws["target"]) == _norm(hand_tgt)
        icon = ((ws or {}).get("icon") or l.get("icon_location") or "").strip()
        icon_path = icon.split(",")[0].strip() if icon else ""
        target = (ws or {}).get("target") or hand_tgt or ""
        wd = (ws or {}).get("working_dir") or l.get("working_directory") or ""
        tgt_name = Path(target).name.lower() if target else ""
        if tgt_name in {"wscript.exe", "cscript.exe", "mshta.exe", "powershell.exe"} or \
                target.lower().endswith((".vbs", ".js")):
            res["invented_launcher"] = True
        rec = {"lnk_path": l["lnk_path"], "origin": l.get("origin"), "target": target,
               "target_exists": bool(target) and os.path.isfile(target),
               "arguments": (ws or {}).get("arguments") or l.get("arguments") or "",
               "working_dir": wd, "working_dir_exists": (bool(wd) and Path(wd).is_dir()) if wd else None,
               "icon": icon_path, "icon_named": bool(icon_path),
               "icon_exists": bool(icon_path) and os.path.isfile(icon_path),
               "hand_parse_ok": bool(l.get("parse_ok")), "wscript_agree": agree,
               "hand_parse_error": l.get("parse_error")}
        res["shortcuts"].append(rec)
        if ws is None:
            res["unconfirmed"].append(
                f"no WScript cross-check for {l['lnk_path']}: hand parser alone "
                "(StringData slot order is positional best-effort)")
        if agree is False:
            res["unconfirmed"].append(
                f"WScript disagrees with hand parser for {l['lnk_path']}: hand={hand_tgt!r} wscript={ws['target']!r}")
    # prefer the user-desktop shortcut as the adjudicated one; keep all for duplicate detection
    pref = [s for s in res["shortcuts"] if s["origin"] == "user_desktop"] or res["shortcuts"]
    res["shortcut"] = pref[0] if pref else None
    if res["shortcut"]:
        res["wscript_agree"] = res["shortcut"]["wscript_agree"]
        if len(res["shortcuts"]) > 1:
            res["readback"].append({"source": "duplicate-desktop-shortcuts",
                                    "paths": [s["lnk_path"] for s in res["shortcuts"]]})

    if form["require_desktop"] and not res["shortcuts"] and (reg_matches or res["install_roots"]):
        res["unconfirmed"].append("no desktop shortcut found for an installed surface (dimension 2 entry absent)")

    # declared candidate globs / repo wrappers / overlay launchers / PATH
    for g in form.get("candidate_globs", ()):
        for hit in sorted(globlib.glob(expand(g), recursive=True)):
            res["install_roots"].append(str(Path(hit).parent)) \
                if _norm(Path(hit).parent) not in {_norm(r) for r in res["install_roots"]} else None
            res["readback"].append({"source": "declared candidate glob", "glob": g, "hit": hit})
    for g in form.get("entry_candidates", ()):
        ex = expand(g)
        hit = bool(ex) and Path(ex).is_file()
        res["auxiliary_layers"].append({"kind": "declared_entry_candidate", "path": ex, "exists": hit})
        res["readback"].append({"source": "declared entry candidate", "path": ex, "exists": hit})
        if not hit:
            res["unconfirmed"].append(f"declared CLI entry candidate missing: {g}")
    for w in form.get("repo_wrappers", ()):
        p = REPO / w
        exists = p.is_file()
        res.setdefault("entry_points", []).append({"kind": "repo_wrapper", "path": str(p), "exists": exists})
        res["readback"].append({"source": "repo wrapper", "path": str(p), "exists": exists})
        if not exists:
            res["unconfirmed"].append(f"declared repo wrapper missing: {w}")
    for g in form.get("overlay_globs", ()):
        ex = expand(g)
        hit = bool(ex) and Path(ex).is_file()
        res["auxiliary_layers"].append({"kind": "hermes_overlay_launcher", "path": ex, "exists": hit})
        if not hit:
            res["unconfirmed"].append(
                f"declared Hermes overlay launcher absent at {ex} (AGENTS.md managed bin/ asset; "
                "repo wrapper remains the only resolvable entry)")
    if form["scan_path"]:
        cli = which_all(tuple(form["cli_names"]), pdirs)
        res["cli_paths"] = cli
        res["cli_resolved"] = bool(cli)
        if len({str(Path(c).parent) for c in cli}) > 1:
            res["unconfirmed"].append(f"multiple PATH directories hit the declared entry: {cli}")
        res["readback"].append({"source": "PATH dirs from HKLM Session Manager + HKCU Environment",
                                "hits": cli})
    # soft registry / capability evidence trail for this surface
    res["readback"].append({"source": "config/software-registry.json", "softwareId": sid,
                            "officialSource": soft.get("officialSource")})
    for var in ENV_LAYER_FOR.get(sid, ()):
        lay = env_layers.get(var)
        if lay and lay.get("in_hkcu_environment"):
            res["auxiliary_layers"].append({"kind": "env_layer", "var": var, **lay})
            res["readback"].append({"source": "registry", "key": f"HKCU\\Environment\\{var}", "value": lay["value"]})
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    for src in (CAPABILITY_MATRIX, SOFTWARE_REGISTRY, CONFIG_OWNERSHIP, IDENTITY_SCHEMA):
        if not src.is_file():
            print(f"ENTRY_BASELINE_NOT_RUN declaration absent {src}")
            return 2
    try:
        vocabulary, vocab_source = load_location_vocabulary()
    except (OSError, ValueError, KeyError) as exc:
        print(f"ENTRY_BASELINE_NOT_RUN vocabulary unreadable {exc!r}")
        return 2

    matrix = json.loads(CAPABILITY_MATRIX.read_text(encoding="utf-8"))
    softreg = json.loads(SOFTWARE_REGISTRY.read_text(encoding="utf-8"))
    ownership = json.loads(CONFIG_OWNERSHIP.read_text(encoding="utf-8")).get("adapter_defaults", {})
    soft_by_id = {s["softwareId"]: s for s in softreg["software"]}

    # Surfaces enumerated from the repo's own declarations: capability-matrix clients[] is
    # the in-scope set; manifest_only_clients[] (registry_status blocked) are declared out
    # of launch-entry scope and recorded as such rather than judged.
    surfaces = matrix["clients"]
    out_of_scope = [c["id"] for c in matrix.get("manifest_only_clients", [])]

    now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.gmtime(time.time() + 8 * 3600))
    dirs = desktop_dirs()
    reg_error = None
    try:
        reg_rows = reg_uninstall_rows()
    except OSError as exc:
        reg_rows, reg_error = [], repr(exc)
    lnks = scan_shortcuts(dirs)
    wsx = wscript_fields([l["lnk_path"] for l in lnks])
    pdirs = path_dirs()

    env_layers = {}
    for var in ("DSH_HOME", "HERMES_HOME", "CODEX_CLI"):
        present, value = reg_env_layer(var)
        env_layers[var] = {"in_hkcu_environment": present,
                           "value": value if present else None,
                           "resolved": expand(value) if value else None,
                           "exists": (Path(expand(value)).is_dir() if value else None)}

    rows_out, counts = [], {}
    for c in surfaces:
        sid = c["id"]
        if sid not in FORMS:
            row = {"surface": sid, "verdict": ENTRY_NOT_RESOLVED,
                   "reason": "no declared entry form for this client id in the dimension-1 table",
                   "canonical_candidate": None}
        else:
            try:
                res = collect_surface(sid, c, soft_by_id.get(sid, {}), ownership, reg_rows,
                                      lnks, wsx, pdirs, env_layers, dirs, now)
            except Exception as exc:  # noqa: BLE001 — a resolver failure is a red row, not a crash
                res = {"readback_error": f"resolver exception {exc!r}", "require_desktop": False,
                       "install_roots": [], "unconfirmed": [], "auxiliary_layers": [], "readback": []}
            if reg_error:
                res["readback_error"] = f"uninstall registry unreadable: {reg_error}"
            verdict = decide(res)
            if verdict["verdict"] not in vocabulary and verdict["verdict"] != ENTRY_NOT_RESOLVED:
                verdict = {"verdict": ENTRY_NOT_RESOLVED,
                           "reason": f"verdict {verdict['verdict']!r} is outside the contract vocabulary",
                           "canonical_candidate": None}
            form = FORMS[sid]
            row = {"surface": sid, "display_name": soft_by_id.get(sid, {}).get("displayName", sid),
                   "declared_form": form["declared"], "scope": res.get("scope") or
                   {"registry_status": c.get("registry_status"),
                    "ownership_mode": (ownership.get(sid) or {}).get("mode"),
                    "official_source": soft_by_id.get(sid, {}).get("officialSource"),
                    "legacy_observe": c.get("registry_status") == "legacy_observe"},
                   "verdict": verdict["verdict"], "reason": verdict["reason"],
                   "canonical_candidate": verdict["canonical_candidate"],
                   "install_roots": res.get("install_roots"), "expected_roots": res.get("expected_roots"),
                   "shortcut": res.get("shortcut"), "shortcuts": res.get("shortcuts"),
                   "cli_paths": res.get("cli_paths"), "entry_points": res.get("entry_points"),
                   "auxiliary_layers": res.get("auxiliary_layers"), "readback": res.get("readback"),
                   "observed_at": now}
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        rows_out.append(row)

    report = {
        "schema": "work-lab/entry-baseline-readback/v1",
        "tool": "scripts/audit/entry_baseline_readback.py",
        "rerun_command": ".project-local/toolchains/wl-py311/Scripts/python.exe scripts/audit/entry_baseline_readback.py --out docs/audits/ENTRY_BASELINE_2026-10-08.json",
        "observed_at": now,
        "readOnly": True,
        "launchedProcesses": False,
        "authority_sources": ["config/capability-matrix.json#clients[].registry_status",
                              "config/software-registry.json#software[].officialSource",
                              "config/config-ownership.json#adapter_defaults",
                              "AGENTS.md#five-dimension-runtime-baseline dimensions 1-2"],
        "vocabulary": {"location_status_enum": vocabulary, "enum_source": vocab_source,
                       "extra_state": ENTRY_NOT_RESOLVED,
                       "extra_state_source": "scripts/audit/executor_live_probe.py (probe-level could-not-measure state)"},
        "desktop_dirs_read": dirs,
        "hkcu_environment_layers": env_layers,
        "counts": counts,
        "out_of_scope_declared": {"ids": out_of_scope,
                                  "basis": "capability-matrix manifest_only_clients[] registry_status=blocked — no declared local launch entry form"},
        "not_verified": [
            "chain resolves but no binary was launched — 'opens correctly' is unproven",
            "file version resources / hashes not read — version agreement is not asserted here",
            "Start Menu launchers not adjudicated (desktop is the dimension-2 authority)",
            "Store (AppX) runtime layer for the codex wrapper was not queried by this tool",
            "working-dir/icon agreement between hand parser and WScript is recorded but only TargetPath disagreement downgrades a row"],
        "safety_note": ("No process launch, no registry write, no shortcut change, no file-content read. "
                        ".lnk TargetPath parsed from bytes ([MS-SHLLINK] LinkInfo) and cross-checked with a "
                        "WScript.Shell stdin field read (CreateShortcut fields only; the target is never Run)."),
        "rows": rows_out,
    }
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(json.dumps(report, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode("utf-8"))
    print(f"record -> {(out.relative_to(REPO)).as_posix()}")
    print(f"surfaces={len(rows_out)} counts={json.dumps(counts, ensure_ascii=False)}")
    for r in rows_out:
        cand = r.get("canonical_candidate") or r.get("reason")
        print(f"  {r['surface']:18} {r['verdict']:22} {str(cand)[:96]}")
    print("ENTRY_BASELINE_DONE")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
