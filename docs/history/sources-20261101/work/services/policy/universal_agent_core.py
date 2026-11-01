"""Render the reviewed deployment snapshot of the user's external mother.

This module supplies prose only. Existing typed policy contracts still govern
their machine controls; rendering these rules never applies those controls.
Update AGENT_CORE.md at source first, then review a new snapshot and checksum.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def render_core_block(root: Path) -> str:
    folder = root / "config" / "universal-agent"
    meta = json.loads((folder / "source.json").read_text(encoding="utf-8"))
    data = (folder / "AGENT_CORE.md").read_bytes()
    if hashlib.sha256(data).hexdigest() != meta["sha256"]:
        raise ValueError("universal agent core snapshot checksum mismatch; review source first")
    version = meta["version"]
    return (
        f"## BEGIN UNIVERSAL_AGENT_CORE v{version}\n\n"
        f"来源：{meta['source']}\n"
        f"母版版本：{version}；SHA-256：{meta['sha256']}\n\n"
        f"{data.decode('utf-8-sig').strip()}\n\n"
        f"## END UNIVERSAL_AGENT_CORE v{version}"
    )
