"""Deploy global rules — sync the global boundaries to each software's rule file.

Authoritative reference: docs/decisions/global-execution-standard.md (global
boundaries). This tool maintains a hardcoded mirror of the four global
boundary rules (GLOBAL_BOUNDARIES below) and inserts/updates them into each
software's rule file via a managed block (marker-delimited), so a change to
the source is carried by hand into GLOBAL_BOUNDARIES and then propagated to
all targets. Idempotent.

Note: the path '.project/governance/global-execution-standard.md' no longer
exists (2026-09 directory convergence moved the global standard to
docs/decisions/); keep the authoritative text in docs/decisions/ and keep
GLOBAL_BOUNDARIES in sync with it manually.
"""
from __future__ import annotations

import re
from pathlib import Path

# Single source of truth (key -> zh/en text)
GLOBAL_BOUNDARIES = [
    ("safety-ef", "E/F盘禁访", "Never access E:\\ or F:\\ without explicit per-path, per-operation authorization in the current request."),
    ("data-boundary", "数据边界", "All task data (temp, cache, logs, artifacts) stays inside the project .hermes/; no spill to user home, other projects, or shared libraries."),
    ("official-first", "官方优先", "Software updates follow official releases only; never privately build/package versions."),
    ("skill-discipline", "技能调用纪律", "Before executing a task, check the skill-call index / scan SKILL.md, load the matching skill, and record the mapping; never just start."),
]

MARKER_BEGIN = "<!-- GLOBAL-RULES-MANAGED-BLOCK BEGIN -->"
MARKER_END = "<!-- GLOBAL-RULES-MANAGED-BLOCK END -->"


def _block(zh: bool) -> str:
    lines = [MARKER_BEGIN]
    for key, zh_name, en_text in GLOBAL_BOUNDARIES:
        if zh:
            # zh rendering: use zh name as heading + en text
            lines.append(f"- [{zh_name}] {en_text}")
        else:
            lines.append(f"- {en_text}")
    lines.append(MARKER_END)
    return "\n".join(lines)


def sync_file(path: Path, zh: bool) -> bool:
    """Insert/update the managed block in a target rule file."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    block = _block(zh)
    pattern = re.compile(rf"{re.escape(MARKER_BEGIN)}.*?{re.escape(MARKER_END)}", re.DOTALL)
    if pattern.search(text):
        new_text = pattern.sub(block.replace("\\", "\\\\"), text)
    else:
        new_text = text.rstrip() + "\n\n" + block + "\n"
    path.write_text(new_text, encoding="utf-8")
    return True


TARGETS = [
    # Hermes only: Codex is governed by sync_codex_global_assets.py
    # (WORKFLOW-ASSISTANCE MANAGED CODEX OVERLAY block), not this tool —
    # dual managed blocks on the same file caused guidance_owned_block_drift.
    (Path(r"C:\Users\ALEX\AppData\Local\hermes\SOUL.md"), True),   # Hermes (zh)
]


def deploy() -> dict:
    results = {}
    for path, zh in TARGETS:
        ok = sync_file(path, zh)
        results[str(path)] = "synced" if ok else "missing"
    return results


if __name__ == "__main__":
    import json
    print(json.dumps(deploy(), indent=1))
