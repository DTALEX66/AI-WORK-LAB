from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_lines import normalize_context_lines, render_context_lines

DEFAULT_OUTPUT = Path(".project-local/artifacts/context-pack.md")
MAX_SECTION_CHARS = 8000
# Keep a new-session handoff inside the portable token policy default. Callers may
# explicitly raise this up to the documented 30k hard ceiling for audits.
DEFAULT_MAX_CHARS = 12000
HARD_MAX_CHARS = 30000

# C1: machine authorities the pack resolves dynamically — no second, hand-maintained
# path list. The authority index is the source of truth for which files carry
# top-level authority; module-ownership.json is the source of truth for which
# source surfaces exist. Legacy docs/mcp and docs/absorption roots were removed
# at the 2026-09 directory convergence and are no longer declared here.
AUTHORITY_INDEX = ".project/governance/project-authority-index.json"
TASKPACK_AUTHORITY_INDEX = ".project/governance/taskpack-authority-index.json"
MODULE_OWNERSHIP = ".project/governance/module-ownership.json"
PROJECT_DATA_BOUNDARY = ".project/governance/project-data-boundary.json"
ERROR_LEDGER = "taskpacks/current/error-ledger.json"

# Always-included top-level materials (machine-truth, current-tree paths only).
SELECTED_TOP_MATERIALS = (
    "README.md",
    "AGENTS.md",
    "WORK-LAB-AUTHORITY.md",
    AUTHORITY_INDEX,
    TASKPACK_AUTHORITY_INDEX,
)

# Workflow docs that survive the 2026-09 convergence (declared, current-tree).
# docs/mcp/* and docs/absorption/* are gone; a declared-but-missing entry is
# marked MISSING explicitly, never silently skipped (C1: 缺少材料必须显式标记).
SELECTED_WORKFLOW_DOCS = (
    "docs/current/workflow-assistance/workflow/project-definition.md",
    "docs/current/workflow-assistance/workflow/gateway-cron-delivery.md",
    "docs/current/workflow-assistance/workflow/agent-evaluation.md",
    "docs/current/workflow-assistance/workflow/context-pack.md",
    "docs/current/workflow-assistance/workflow/local-quality-gates.md",
    "docs/current/workflow-assistance/workflow/ui-skin-system.md",
    "docs/current/workflow-assistance/workflow/project-data-boundary.md",
)

SELECTED_CONFIG = (
    "config/config.yaml",
    "config/SOUL.md",
)

INVENTORY_FALLBACK_ROOTS = (
    "packages/client-neutral-core/scripts",
    "packages/client-neutral-core/bin",
    "services/orchestration",
    "scripts",
    "tests",
)

FORBIDDEN_PATH_PARTS = {
    ".git",
    ".hermes",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "venv",
    ".venv",
    "logs",
    "cache",
}

FORBIDDEN_FILE_NAMES = {
    ".env",
    "auth.json",
    "state.db",
    "cookies.txt",
}

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*['\"]?[^\\s'\"]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"npm_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
)


def run_git(root: Path, *args: str, check: bool = False) -> str:
    # git writes UTF-8, so the capture must say so. Relying on ``text=True`` alone
    # uses the locale codec (GBK on this machine), and then any commit message,
    # branch name or path containing a non-GBK character (an em dash is enough)
    # kills the reader thread: the decode error leaves ``stdout`` as None and the
    # failure surfaces far away as ``AttributeError: 'NoneType' ... strip``.
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or "").strip() or (result.stdout or "").strip())
    return redact((result.stdout or "").strip())


def git_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        raise SystemExit("build_context_pack: not inside a Git repository")
    return Path(result.stdout.strip()).resolve()


def _windows_long_path(path: Path) -> Path:
    """Return a stable long-name path for existing Windows paths.

    GitHub Actions can expose the same temp directory as both
    ``C:\\Users\\runneradmin`` and the DOS 8.3 alias ``C:\\Users\\RUNNER~1``.
    ``Path.relative_to`` is purely lexical, so normalize existing path prefixes
    before containment checks.
    """
    if os.name != "nt":
        return path
    text = str(path)
    buffer_size = ctypes.windll.kernel32.GetLongPathNameW(text, None, 0)
    if buffer_size <= 0:
        return path
    buffer = ctypes.create_unicode_buffer(buffer_size)
    written = ctypes.windll.kernel32.GetLongPathNameW(text, buffer, buffer_size)
    if written <= 0:
        return path
    return Path(buffer.value)


def canonical_path(path: Path) -> Path:
    """Canonicalize a path, including Windows short-name aliases.

    Works for paths that do not exist yet by canonicalizing the nearest existing
    ancestor and appending the unresolved suffix.
    """
    resolved = path.resolve(strict=False)
    existing = resolved
    suffix: list[str] = []
    while not existing.exists() and existing != existing.parent:
        suffix.append(existing.name)
        existing = existing.parent
    existing = _windows_long_path(existing.resolve(strict=False))
    for part in reversed(suffix):
        existing = existing / part
    return existing


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        canonical_path(path).relative_to(canonical_path(parent))
        return True
    except ValueError:
        return False


def require_ignored_output(root: Path, output: Path) -> None:
    output = canonical_path(output)
    root = canonical_path(root)
    if not is_relative_to(output, root):
        raise SystemExit(f"output path escapes project root: {output}")
    relative = output.relative_to(root).as_posix()
    probe = subprocess.run(
        ["git", "check-ignore", "-q", relative],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if probe.returncode != 0:
        raise SystemExit(f"output path is not git-ignored: {relative}")


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def safe_rel(path: Path) -> str:
    return path.as_posix().replace("\\", "/")


def forbidden_path(relative: Path) -> bool:
    parts = set(relative.parts)
    return bool(parts & FORBIDDEN_PATH_PARTS) or relative.name in FORBIDDEN_FILE_NAMES


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_safe_text(root: Path, relative: str, max_chars: int = MAX_SECTION_CHARS) -> str | None:
    path = root / relative
    if not is_relative_to(path, root) or not path.is_file() or forbidden_path(Path(relative)):
        return None
    data = path.read_text(encoding="utf-8", errors="replace")
    data = redact(data)
    if len(data) > max_chars:
        return data[:max_chars] + f"\n\n[truncated at {max_chars} characters]\n"
    return data


def read_json_safe(root: Path, relative: str) -> dict | None:
    path = root / relative
    if not is_relative_to(path, root) or not path.is_file() or forbidden_path(Path(relative)):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def authority_materials(root: Path) -> list[str]:
    """C1: resolve the top-authority + CURRENT + OPEN material set from the
    authority index itself, not from a second hand-written path list."""
    materials = list(SELECTED_TOP_MATERIALS)
    index = read_json_safe(root, AUTHORITY_INDEX)
    if index:
        for key in ("topHumanAuthority", "topMachineAuthority"):
            value = index.get(key)
            if isinstance(value, str) and value not in materials:
                materials.append(value)
        scoped = index.get("scopedAuthorities")
        if isinstance(scoped, dict):
            for value in scoped.values():
                if isinstance(value, str) and value not in materials:
                    materials.append(value)
        current = index.get("currentTaskpack")
        if isinstance(current, str) and current not in materials:
            materials.append(current)
        open_register = index.get("currentOpenTaskRegister")
        if isinstance(open_register, str) and open_register not in materials:
            materials.append(open_register)
    else:
        # Index unreadable: fall back to the declared machine-truth paths (still
        # current-tree, not historical roots) and let the missing-marker surface
        # the gap explicitly rather than silently.
        for fallback in (
            "WORK-LAB-AUTHORITY.md",
            TASKPACK_AUTHORITY_INDEX,
            "taskpacks/current/OPEN-TASK-REGISTER.md",
        ):
            if fallback not in materials:
                materials.append(fallback)
    return materials


def inventory_roots(root: Path) -> list[str]:
    """C1: the tracked-inventory roots come from module-ownership machine truth.

    The module roots + root-owned paths are declared by
    ``.project/governance/module-ownership.json``; legacy top-level
    bin/skills/templates roots were removed at the 2026-09 convergence and are
    not declared here. A missing/invalid index falls back to the module
    source-surface roots only.
    """
    roots: list[str] = []
    ownership = read_json_safe(root, MODULE_OWNERSHIP)
    if ownership:
        modules = ownership.get("modules")
        if isinstance(modules, dict):
            for module in modules.values():
                if isinstance(module, dict):
                    path = module.get("path")
                    if isinstance(path, str):
                        roots.append(path)
        owned = ownership.get("rootOwnedPaths")
        if isinstance(owned, list):
            roots.extend(str(item) for item in owned if isinstance(item, str))
    if not roots:
        roots.extend(INVENTORY_FALLBACK_ROOTS)
    deduped: list[str] = []
    for item in roots:
        if item not in deduped:
            deduped.append(item)
    return deduped


def tracked_inventory(root: Path, limit: int = 300) -> list[str]:
    raw = []
    for item_root in inventory_roots(root):
        try:
            raw.extend(run_git(root, "ls-files", item_root).splitlines())
        except Exception:
            continue
    seen: set[str] = set()
    safe: list[str] = []
    for item in raw:
        relative = Path(item)
        if item in seen or forbidden_path(relative):
            continue
        seen.add(item)
        safe.append(item)
    return safe[:limit]


def skill_inventory(root: Path) -> list[str]:
    """C1: skill inventory derives from the module-ownership machine truth.

    Skills live under the declared workflow-assistance module root; the count
    comes from the actual on-disk inventory, never a historical fixed number.
    """
    skills_root: Path | None = None
    ownership = read_json_safe(root, MODULE_OWNERSHIP)
    if ownership:
        modules = ownership.get("modules")
        if isinstance(modules, dict):
            for module in modules.values():
                if isinstance(module, dict) and module.get("owner") == "workflow":
                    skills_root = root / str(module.get("path", "")) / "skills"
                    break
    if skills_root is None:
        skills_root = root / "packages" / "client-neutral-core" / "skills"
    if not skills_root.exists():
        return []
    items = []
    for skill in sorted(skills_root.rglob("SKILL.md")):
        rel = skill.parent.relative_to(skills_root)
        items.append(safe_rel(rel))
    return items


def _register_head(root: Path, max_chars: int = 4000) -> str | None:
    """Known state / open tasks: the single live register's head (statuses +
    reconciliation notes), bounded so it cannot blow the pack budget."""
    index = read_json_safe(root, AUTHORITY_INDEX)
    if index and isinstance(index.get("currentOpenTaskRegister"), str):
        relative = index["currentOpenTaskRegister"]
    else:
        relative = "taskpacks/current/OPEN-TASK-REGISTER.md"
    text = read_safe_text(root, relative, max_chars=max_chars)
    if text is None:
        return None
    return text


def _error_ledger_head(root: Path, max_chars: int = 3000) -> str | None:
    """Known failures: the open error-ledger head (bounded, redacted)."""
    data = read_json_safe(root, ERROR_LEDGER)
    if data is None:
        return None
    entries = data.get("errors")
    if not isinstance(entries, list):
        entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return None
    summary = data.get("summary")
    lines: list[str] = []
    if summary:
        lines.append(f"summary: {json.dumps(summary, ensure_ascii=False, sort_keys=True)}")
    for entry in entries[:10]:
        if not isinstance(entry, dict):
            continue
        lines.append(
            json.dumps(
                {key: entry.get(key) for key in ("id", "status", "phase", "evidence_level", "title") if entry.get(key) is not None},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    text = "\n".join(lines)
    return text[:max_chars] + ("\n[truncated]" if len(text) > max_chars else "")


def _critical_constraints(root: Path, ownership: dict | None, boundary: dict | None) -> str:
    """C1: key constraints that must survive compression, front-loaded.

    Owner + allowed/forbidden paths + data boundary come from the machine
    authorities, not from prose memory.
    """
    lines: list[str] = []
    if ownership:
        single_writer = ownership.get("singleWriter")
        lines.append(f"- Single-writer checkout: {'yes' if single_writer else 'unknown'}.")
        modules = ownership.get("modules")
        if isinstance(modules, dict):
            for name, module in modules.items():
                if isinstance(module, dict):
                    lines.append(f"- Module {name}: root `{module.get('path')}`, owner `{module.get('owner')}`.")
        owned = ownership.get("rootOwnedPaths")
        if isinstance(owned, list) and owned:
            lines.append("- Root-owned paths: " + ", ".join(f"`{p}`" for p in owned))
    if boundary:
        forbidden = boundary.get("forbiddenExternalRoots")
        if isinstance(forbidden, list) and forbidden:
            lines.append("- Forbidden external roots: " + ", ".join(f"`{p}`" for p in forbidden))
        runtime = boundary.get("runtimeRoot")
        if runtime:
            lines.append(f"- Runtime/task-artifact root: `{runtime}`.")
    return "\n".join(lines)


def build_context_pack(
    root: Path,
    max_chars: int = DEFAULT_MAX_CHARS,
    context_lines: list[dict[str, object]] | None = None,
    context_project_id: str | None = None,
) -> str:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    head = run_git(root, "rev-parse", "--short", "HEAD") or "unknown"
    branch = run_git(root, "branch", "--show-current") or "unknown"
    status = run_git(root, "status", "--short", "--branch")
    recent = run_git(root, "log", "-5", "--oneline", "--date=short")
    inventory = tracked_inventory(root)
    skills = skill_inventory(root)

    ownership = read_json_safe(root, MODULE_OWNERSHIP)
    boundary = read_json_safe(root, PROJECT_DATA_BOUNDARY)
    register_head = _register_head(root)
    ledger_head = _error_ledger_head(root)

    # Authority material set resolved from the index (C1: no second path list).
    materials = authority_materials(root) + list(SELECTED_WORKFLOW_DOCS) + list(SELECTED_CONFIG)

    # W08: two lists, because the pack has two kinds of content. `sections` is required -- constraints, the
    # live register head, open failures, the recovery checklist. Everything that merely helps (git status,
    # inventories, reminders, file excerpts) goes to `optional_sections` and is dropped WHOLE and BY NAME
    # when the budget runs out, instead of the old prefix cut, which could land inside the checklist.
    sections: list[str] = []
    optional_sections: list[str] = []
    sections.append(
        "# Workflow-assistance Context Pack\n\n"
        "Generated for a new Hermes Agent / CC Switch / Codex handoff. "
        "This is a project-local ignored artifact, not a committed source file.\n\n"
        f"- Generated UTC: `{now}`\n"
        f"- Project root: `{root}`\n"
        f"- Branch: `{branch}`\n"
        f"- HEAD: `{head}`\n"
        # W08 (2026-10-15): two identities, because there are two different texts. The rendered digest covers
        # what the reader actually got; the candidate digest covers every section the pack WOULD have carried.
        # One number could not answer both questions, and the old single digest was computed before the final
        # prefix cut -- so it named a text nobody would ever read.
        f"- Content SHA-256 (rendered): `filled-after-render`\n"
        f"- Candidate SHA-256 (all sections, before declared omission): `candidate-digest-placeholder`\n"
    )
    sections.append(
        "## Safety Boundary\n\n"
        "- This pack is generated from tracked, allowlisted workflow assets plus git metadata.\n"
        "- It excludes `.env`, `auth.json`, `state.db`, `.hermes/`, logs, caches, installed dependencies and session data.\n"
        "- Secret-like values are redacted before rendering.\n"
        "- It strengthens the global Hermes Agent + CC Switch + Codex workflow; it is not proof that live Hermes has reloaded these assets.\n"
    )
    constraints = _critical_constraints(root, ownership, boundary)
    if constraints:
        sections.append(
            "## Critical Constraints (must survive compression)\n\n"
            f"{constraints}\n"
        )
    if context_lines:
        project_id = context_project_id or root.name
        safe_lines = normalize_context_lines(context_lines, project_id=project_id)
        sections.append(render_context_lines(safe_lines))
    optional_sections.append(f"## Git Status\n\n```text\n{status}\n```\n")
    optional_sections.append(f"## Recent Commits\n\n```text\n{recent}\n```\n")

    # C1: explicit missing-material markers — a generation success is NOT proof
    # of a complete recovery; whatever the index declares but the tree lacks is
    # listed here, never silently dropped.
    present: list[str] = []
    missing: list[str] = []
    for relative in materials:
        text = read_safe_text(root, relative)
        if text is None:
            missing.append(relative)
        else:
            present.append(relative)
    if missing:
        sections.append(
            "## Missing Materials (explicit — do not reconstruct from memory)\n\n"
            + "\n".join(f"- MISSING `{item}`" for item in missing)
            + "\n"
        )
    if register_head:
        sections.append(f"## Current Task State (live register head)\n\n```text\n{register_head.rstrip()}\n```\n")
    if ledger_head:
        sections.append(f"## Known Failures (open error-ledger head)\n\n```text\n{ledger_head.rstrip()}\n```\n")
    optional_sections.append(
        "## Portable Asset Inventory\n\n"
        + "\n".join(f"- `{item}`" for item in inventory)
        + ("\n- ... truncated ..." if len(inventory) >= 300 else "")
        + "\n"
    )
    optional_sections.append(
        "## Skill Inventory (from module-ownership machine truth; count is live, not historical)\n\n"
        + ("\n".join(f"- `{item}`" for item in skills) if skills else "_No skills found._")
        + f"\n- total: {len(skills)}\n"
    )
    sections.append(
        "## Recovery Checklist (generation success != recovery complete)\n\n"
        "- Verify HEAD/branch against the authority baseline before acting; an unmerged PR is not main.\n"
        "- A historical or archived path is not a current path; use only the declared current-tree materials above.\n"
        "- A task without a receipt is not complete; check the live register + error ledger before claiming done.\n"
        "- After a session or executor change, re-resolve the critical constraints section (owner, forbidden roots, single-writer) from the machine authorities.\n"
        "- Acceptance: `python services/orchestration/run_quality_gate.py verify`; rollback = revert the last merge to the frozen pre-convergence anchor in WORK-LAB-AUTHORITY.md §13.\n"
    )
    optional_sections.append(
        "## Handoff Reminders\n\n"
        "- Distinguish repo updated, live Hermes Home synced, and current session loaded.\n"
        "- Use `/reload-skills` or `/reset` after live skill/config changes when needed.\n"
        "- Gateway running is not the same as messaging platform delivery configured.\n"
        "- Keep one writer per checkout; context-pack generation is evidence/handoff, not completed product work by itself.\n"
        "- If output is used in another project, regenerate inside that project so paths and git evidence match.\n"
    )
    # W08: the excerpts are the pack's bulk, and they are the ONLY part allowed to disappear. Everything
    # appended above them (constraints, live register head, open failures, recovery checklist) is required;
    # the old code cut the RENDERED STRING at the budget, which could land inside the recovery checklist --
    # the section that exists precisely to say what a receiver must not assume.
    excerpts: list[tuple[str, str]] = []
    for relative in present:
        text = read_safe_text(root, relative)
        if text is None:
            continue
        excerpts.append((relative, f"## Excerpt: `{relative}`\n\n```text\n{text.rstrip()}\n```\n"))

    droppable: list[tuple[str, str]] = [(s.split("\n", 1)[0].removeprefix("## "), s)
                                        for s in optional_sections]
    droppable += excerpts
    required = "\n".join(sections).rstrip() + "\n"
    candidate = required + "".join(text + "\n" for _, text in droppable)
    # The digest is the pack's *content* identity, so it must not cover the generation stamp: hashing the stamp
    # in made every render produce a new digest, which turned "quote the pack by its content SHA" into a claim
    # that only held while two renders happened inside the same second. A slower pack (more sections to read)
    # crossed that boundary and the drift gate went red on two consecutive renders in one batch.
    def _stable(text: str) -> str:
        return "\n".join(line for line in text.splitlines() if not line.startswith("- Generated UTC:"))

    def _blank_placeholders(text: str) -> str:
        return (text.replace("filled-after-render", "")
                    .replace("candidate-digest-placeholder", ""))

    candidate_digest = sha256_text(_blank_placeholders(_stable(candidate)))[:16]

    def _omitted_block(names: list[str], *, detailed: bool) -> str:
        if not names:
            return ""
        head = "## Omitted Sections (declared — whole sections dropped, never cut mid-section)\n\n"
        if detailed:
            return (head + "- " + ", ".join(f"`{name}`" for name in names)
                    + f"\n- total omitted: {len(names)}; regenerate with a larger `--max-chars` to read them\n")
        # Second tier, for a budget too small even for the list of names. The omission is still declared and
        # counted -- what degrades is the detail, never the fact.
        return head + f"- {len(names)} section(s) omitted; this budget could not hold even their names\n"

    def _render(included: list[tuple[str, str]], names: list[str], *, detailed: bool = True) -> str:
        body = required + "".join(text + "\n" for _, text in included)
        if names:
            body = body + _omitted_block(names, detailed=detailed) + "\n"
        return body

    kept: list[tuple[str, str]] = list(droppable)
    dropped: list[str] = []
    # Fit by dropping whole sections, then RE-CHECK: the omitted block grows with every name added, so a
    # single forward pass can overshoot by exactly the lines it later appends. Measured 2026-10-15: reserving
    # the worst case up front made the pack refuse at its own 12000-character default, which would have turned
    # a truncation defect into an outage.
    while len(_render(kept, dropped)) > max_chars and kept:
        dropped.insert(0, kept.pop()[0])
    content = _render(kept, dropped)
    if len(content) > max_chars:
        # The detail of the omission list is the next thing to give; the required sections and the fact of the
        # omission are not.
        content = _render(kept, dropped, detailed=False)
    if len(content) > max_chars:
        # Required material alone does not fit. Refusing is the honest answer: emitting a prefix would ship a
        # pack that looks complete and is not, which is the failure this budget exists to prevent.
        raise SystemExit(
            f"CONTEXT_PACK_REQUIRED_EXCEEDS_BUDGET required_sections={len(required)} chars "
            f"budget={max_chars}: every section above the droppable list is required, so there is nothing "
            f"left to drop; raise --max-chars or shorten the live register/ledger heads.")
    rendered_digest = sha256_text(_blank_placeholders(_stable(content)))[:16]
    content = (content.replace("filled-after-render", rendered_digest)
                      .replace("candidate-digest-placeholder", candidate_digest))
    return content


def write_context_pack(root: Path, output: Path, max_chars: int) -> Path:
    root = canonical_path(root)
    if not output.is_absolute():
        output = root / output
    require_ignored_output(root, output)
    output = canonical_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = build_context_pack(root, max_chars=max_chars)
    output.write_text(content, encoding="utf-8")
    return output


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a redacted, project-local context pack for Hermes/Codex handoff."
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Project path inside the target Git repository (default: cwd).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output file, relative to project root by default. Must be git-ignored.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help="Maximum rendered characters before truncation.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the rendered pack instead of writing the output file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not 1 <= args.max_chars <= HARD_MAX_CHARS:
        raise SystemExit(f"--max-chars must be between 1 and {HARD_MAX_CHARS}")
    root = git_root(args.project).resolve()
    if args.stdout:
        print(build_context_pack(root, max_chars=args.max_chars), end="")
        return 0
    output = write_context_pack(root, args.output, args.max_chars)
    relative = output.relative_to(canonical_path(root)).as_posix()
    print(f"context_pack={relative}")
    print(f"chars={len(output.read_text(encoding='utf-8'))}")
    print(f"utf8_bytes={output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
