"""Codex user-config sync (official baseline + user overlay).

Restores ONLY declared USER_OVERLAY fields into ~/.codex/config.toml after
Codex version updates/resets silently drop them. Official/default fields are
never touched; unknown fields are preserved (preserve_unknown).

Usage:
  codex_config_sync.py --check   # report drift only
  codex_config_sync.py --fix     # restore user fields (idempotent)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CODEX_CONFIG = Path.home() / ".codex" / "config.toml"
PROFILE = Path(__file__).resolve().parents[3] / "config" / "user-environment-profile.json"


def load_profile() -> dict:
    return json.loads(PROFILE.read_text(encoding="utf-8"))


def read_config() -> str:
    return CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.exists() else ""


def _set_key(text: str, section: str, key: str, value: str) -> tuple[str, bool]:
    """Set key=value inside [section]; create section if missing. Returns (text, changed)."""
    value_str = json.dumps(value) if isinstance(value, (str, int, float, bool)) else str(value)
    sec_re = re.compile(rf"^\[{re.escape(section)}\]\s*$", re.MULTILINE)
    m = sec_re.search(text)
    if not m:
        return text + f"\n[{section}]\n{key} = {value_str}\n", True
    # find key line inside section
    start = m.end()
    nxt = re.compile(r"^\[", re.MULTILINE).search(text, start)
    end = nxt.start() if nxt else len(text)
    seg = text[start:end]
    key_re = re.compile(rf"^{re.escape(key)}\s*=", re.MULTILINE)
    if key_re.search(seg):
        if f"{key} = {value_str}" in seg:
            return text, False
        seg2 = key_re.sub(f"{key} = {value_str}", seg, count=1)
        return text[:start] + seg2 + text[end:], True
    return text[:end] + f"{key} = {value_str}\n" + text[end:], True


def check() -> list[dict]:
    cfg = read_config()
    profile = load_profile()
    drift = []
    for path, expected in profile["fields"].items():
        section, _, key = path.partition(".")
        if f"{key} = " not in cfg:
            drift.append({"field": path, "expected": expected, "state": "MISSING"})
        elif f"{key} = {json.dumps(expected)}" not in cfg:
            drift.append({"field": path, "expected": expected, "state": "DIFF"})
    return drift


def fix() -> list[dict]:
    cfg = read_config()
    profile = load_profile()
    applied = []
    for path, expected in profile["fields"].items():
        section, _, key = path.partition(".")
        new_cfg, changed = _set_key(cfg, section, key, expected)
        if changed:
            applied.append({"field": path, "restored": expected})
            cfg = new_cfg
    if applied:
        CODEX_CONFIG.write_text(cfg, encoding="utf-8")
    return applied


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode == "--check":
        d = check()
        print("codex-config-sync: " + ("OK (user fields intact)" if not d else f"{len(d)} drift(s): {d}"))
        sys.exit(0 if not d else 1)
    elif mode == "--fix":
        a = fix()
        print("codex-config-sync: " + ("restored " + str(a) if a else "OK (nothing to restore)"))
        sys.exit(0)
    else:
        print("usage: --check | --fix")
        sys.exit(2)
