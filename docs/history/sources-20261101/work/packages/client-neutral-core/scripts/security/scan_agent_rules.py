#!/usr/bin/env python3
"""Scan agent rule/prompt files for common safety issues.

Usage:
  python scripts/security/scan_agent_rules.py [paths...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")
INJECTION = re.compile(
    "|".join(
        (
            r"ignore (all )?(previous|prior) instructions",
            "system" + r"\s+prompt",
            "developer" + r"\s+message",
            r"exfiltrate",
            r"send .*token",
            r"curl .*\|\s*(sh|bash)",
            r"powershell -encodedcommand",
        )
    ),
    re.I,
)
SECRET_HINT = re.compile(r"(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}", re.I)

# PowerShell parses an unquoted "@{" as a hashtable literal, so git revision
# shorthand (@{upstream}, @{u}, @{push}, @{1}, @{-1}) dies before git runs
# ("hashtable not terminated"). Require quoted shorthand or explicit refs.
PS_REVISION_HAZARD = re.compile(r"(?<!['\"])@\{[A-Za-z0-9_.-]+\}")
POWERSHELL_REMOVE_ITEM = re.compile(r"^\s*(?!#).*\bRemove-Item\b", re.I | re.M)
POWERSHELL_LITERAL_PATH = re.compile(r"(?<!\w)-LiteralPath\b", re.I)
POWERSHELL_STOP = re.compile(r"(?<!\w)-ErrorAction\s+Stop\b", re.I)
POWERSHELL_POSTCONDITION = re.compile(r"\bTest-Path\s+-LiteralPath\b", re.I)

EXTS = {
    '.md', '.txt', '.yaml', '.yml', '.json', '.toml',
    '.py', '.sh', '.bash', '.ps1', '.psm1', '.cmd', '.bat',
}
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ROOTS = (
    REPO_ROOT / "templates",
    REPO_ROOT / "skills",
    REPO_ROOT / "docs",
    REPO_ROOT / "config",
    REPO_ROOT / "bin",
    REPO_ROOT / "scripts",
    REPO_ROOT / ".github",
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "setup.sh",
    REPO_ROOT / "setup.ps1",
)
SKIP_PARTS = {".git", ".hermes", "__pycache__", "node_modules", ".venv", "venv"}

# Declarative exceptions for files whose *purpose* is to define the exact
# phrases this scanner looks for (injection detectors / vocabulary tables).
# Keeping them out of the allowlist would flag the detector itself; each entry
# must name the file and the reason in the comment above it.
INJECTION_ALLOWLIST = {
    # scripts/ci/verify_skill_mcp_consistency.py: defines the injection-regex
    # and trigger-vocabulary used to verify MCP consistency tooling.
    "scripts/ci/verify_skill_mcp_consistency.py",
}


def scan_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return [f'{path}: non-utf8 text']
    issues: list[str] = []
    if ZERO_WIDTH.search(text):
        issues.append(f'{path}: hidden zero-width/BOM character')
    if INJECTION.search(text):
        rel = path.relative_to(REPO_ROOT).as_posix() if path.is_absolute() else path.as_posix()
        if rel not in INJECTION_ALLOWLIST:
            issues.append(f'{path}: prompt-injection-like phrase')
    if SECRET_HINT.search(text):
        issues.append(f'{path}: possible hardcoded secret')
    if path.suffix.lower() in ('.sh', '.bash'):
        raw = path.read_bytes()
        if b'\r\n' in raw:
            issues.append(
                f'{path}: CRLF line endings in a shell script cause "bad '
                f'interpreter" on Windows/Unix; keep LF and declare the tree '
                f'in .gitattributes (git add --renormalize)'
            )
    if path.suffix.lower() in ('.ps1', '.psm1'):
        cleanup_matches = list(POWERSHELL_REMOVE_ITEM.finditer(text))
        for match in cleanup_matches:
            line_end = text.find('\n', match.start())
            command = text[match.start() : line_end if line_end >= 0 else len(text)]
            if not POWERSHELL_LITERAL_PATH.search(command) or not POWERSHELL_STOP.search(command):
                line = text.count('\n', 0, match.start()) + 1
                issues.append(
                    f'{path}:{line}: unsafe PowerShell cleanup; Remove-Item must use '
                    f'-LiteralPath and -ErrorAction Stop'
                )
        if cleanup_matches and not POWERSHELL_POSTCONDITION.search(text):
            issues.append(
                f'{path}: unsafe PowerShell cleanup; verify deletion with '
                f'Test-Path -LiteralPath and fail when the target remains'
            )
    for match in PS_REVISION_HAZARD.finditer(text):
        line = text.count('\n', 0, match.start()) + 1
        issues.append(
            f'{path}:{line}: unquoted @-brace git revision shorthand '
            f'({match.group(0)}) breaks PowerShell (hashtable parse); '
            f"single-quote it or use an explicit ref like 'origin/<branch>'"
        )
    return issues


def iter_scannable(root: Path):
    if root.is_file() and root.suffix.lower() in EXTS:
        yield root
        return
    if not root.exists():
        return
    for path in root.rglob("*"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in EXTS:
            yield path


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv[1:]] or list(DEFAULT_ROOTS)
    issues: list[str] = []
    for root in roots:
        for path in iter_scannable(root):
            if path.resolve() != Path(__file__).resolve():
                issues.extend(scan_file(path))
    if issues:
        print('\n'.join(issues))
        return 1
    print('scan_agent_rules: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
