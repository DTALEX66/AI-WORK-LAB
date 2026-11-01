#!/usr/bin/env python3
"""Every path-shaped reference in a navigation surface must resolve in the TRACKED tree, or be declared.

Two deliberate choices, both learned the hard way in this repo.

Resolution is against `git ls-files`, never against the filesystem. An ignored directory such as
`.project-local/` exists on the machine that wrote the sentence and does not exist on a fresh checkout, so
a filesystem test makes the verdict host-dependent -- the same class of defect as an authorization decision
computed with `Path.resolve()`. A directory reference counts as real when at least one tracked file sits
under it.

Why this exists: the authority index is the navigation surface for the whole chain and nothing checked it.
Measured on 2026-10-08 before the fix, section 3 sent readers to `docs/handoffs/` and `docs/audit/`,
directories that have not existed since the 2026-09 convergence, and section 2 named the config standard
without the date suffix that both the file on disk and AGENTS.md carry.

`--index` may be repeated to judge named surfaces only. With no argument the scan is widened to every
tracked markdown file under `docs/current/`; the four navigation surfaces in NAVIGATION_SURFACES are
held to a stricter rule (a navigation surface that yields no references is a broken checker, while an
ordinary prose page that makes no tree claim is allowed and counted in `no_tree_claims`), and the whole
run refuses to pass below a measured reference floor.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from posixpath import normpath

NAVIGATION_SURFACES = (
    "docs/current/workflow-assistance/workflow/active-authority-index.md",
    "docs/current/workflow-assistance-README.md",
    "docs/current/workflow-assistance-TROUBLESHOOTING.md",
    "docs/current/workflow-assistance/workflow/project-definition.md",
)
# Widened 2026-10-08 from those four files to every tracked markdown under the current-documentation
# root: 38 surfaces, 359 references, and 60 of them pointed at something the tree does not have. That
# included eleven commands a reader would run and watch fail (`python scripts/workflow/...`) written
# inside fenced blocks, which is the one place a doc stops being description and becomes an instruction.
SCOPED_ROOT = "docs/current/"
# The live open-task register is bootstrap step 6 of the authority chain -- a reader navigates from it --
# so it is guarded too, even though it lives outside docs/current. Measured on 2026-10-08: 333 references,
# 68 of them naming something the tracked tree does not have, across 26 rows. Unlike a prose page it cannot
# simply be fixed: a register row cites deleted paths, client-home layouts and model-cache names on purpose,
# because the sentence is about the thing that is not here. So the surface carries its own exemptions, in
# the row, as `DECLARATION` tokens below.
EXTRA_SURFACES = ("taskpacks/current/OPEN-TASK-REGISTER.md",
                  "apps/observer/frontend/DESIGN.md",
                  "apps/observer/frontend/SCREEN_SPEC.md")
# Measured floor, not a snapshot: below this the extractor is broken, not the documentation.
REFS_FLOOR = 300
# Re-measured 2026-10-08 after the extension widening: the register yields 393 references (333 at
# 097320d0, before the row rewrites of task #26). The floor moves with the measurement rather than with
# the row count, so a row retirement is a decision and not a silent shrink of the scan.
# Owner 2026-10-09 replaced the 186-row historical register with 21 UI-first tasks.
# The old bytes are frozen, and the current register now carries six real entry references.
# Rebaseline this surface only; strict non-empty parsing, broken-reference rejection,
# documentation and design floors, and the existing negative controls remain unchanged.
REGISTER_REFS_FLOOR = 5
# Per-surface floors for the design contract, measured 2026-10-08 at 34 and 10 references (24 and 9 before
# the stylesheet suffixes were recognised). Below these the extractor stopped reading the file; the
# documents are short, so the register's floor would be instantly wrong for them.
SURFACE_REF_FLOORS = {"apps/observer/frontend/DESIGN.md": 25,
                      "apps/observer/frontend/SCREEN_SPEC.md": 8}
# Widened 2026-10-08 to include the stylesheet and component-file suffixes. The design contract surfaces
# cite `*.css`, `*.scss` and `*.vue` paths in their densest column, and a list without them guarded
# DESIGN.md in name only: measured, adding them takes the judged references over the scanned surfaces from
# 837 to 854 and convicted 6 real claims that had never been looked at.
EXTENSIONS = ("md", "json", "py", "ts", "tsx", "yml", "yaml", "example", "lock", "txt",
              "sh", "bash", "ps1", "css", "scss", "sass", "less", "vue", "svelte")
FILE_REF = re.compile(r"`([^`\s]*/[^`\s]*\.(?:%s))`" % "|".join(EXTENSIONS))
DIR_REF = re.compile(r"`([^`\s]+/)`")
FENCE = re.compile(r"^```(\w*)")
# a reference containing one of these is not a name the tree can answer to, so it is never even tried:
# `<...>`/`~/...`/`$VAR/...` are placeholders this repo's prose already uses for client homes, `*` is a
# glob, `%` marks the Windows environment form (`%LOCALAPPDATA%\hermes`) that names an installed per-user
# root, `…` is how this project writes an elided path (`docs/current/…/examples/governance.yml`), and a
# backslash means the literal is a regex source or a Windows path -- `/\bCPU\b/` in a parity row is a
# pattern a test asserts on, never a file.
PLACEHOLDER_MARKERS = ("<", ">", "*", "$", "~", "%", "…", "\\")
DECLARATION = re.compile(r"\[no-tree-claim (?P<code>[A-Z_]+) ref=(?P<ref>[^\]]+?)\]")
DECLARATION_CODES = {
    "DELETED": "the row exists to name something that was deleted or moved; the removal is re-verified in git",
    "NEVER_EXISTED": "the name was never tracked in any ref; the row exists to say that",
    "CLIENT_HOME": "a per-user agent home outside the repository",
    "INSTALLED_APP": "a file inside a vendor-installed application tree",
    "BUILD_OUTPUT": "generated build or dependency output that is not tracked",
    "UNTRACKED_LOCAL": "untracked and ignored by design, though it sits inside the repository boundary",
    "MODEL_CACHE": "a shared model or toolchain library root, not this repository",
    "CROSS_PROJECT": "a path owned by another project and quoted as such",
    "ILLUSTRATIVE": "an operand in an example of what a checker must reject, not a claim about the tree",
    "SERVED_ROUTE": "an HTTP path a running process answers (`GET /control-shell.css`), written the way "
                    "the server documents it; the identical spelling with a leading slash is also how "
                    "this checker reads a repository-root file claim, so the sentence has to say which",
}
LOWER_SEGMENT = re.compile(r"^[a-z0-9._-]+$")


def looks_like_path(ref: str) -> bool:
    """Reject backticked terms that merely contain a slash.

    Two real cases decided this rule. `GUI/TUI` in the troubleshooting doc is a mode pair and would
    otherwise fire as a missing file. `/WORK-LAB-AUTHORITY.md` is the top-level authority itself, written
    root-absolute: a rule that required a lowercase first *character* dropped it silently, which is worse
    than a false positive because the checker would then claim to guard a surface while excluding its most
    important pointer.
    """
    if ref.startswith(("/", "./", "../")):
        return True
    if not ref or ref[0].isupper():
        return False
    first = ref.split("/", 1)[0]
    return bool(LOWER_SEGMENT.match(first))

# Declared non-repo references, each with the measured reason. A declaration whose path starts resolving
# in the tracked tree is itself a failure, so this list cannot quietly become a hiding place.
DECLARED_NON_PATHS: dict[str, str] = {
    ".project-local/": "the git-ignored in-boundary runtime and evidence root; nothing under it is "
                       "tracked by design, so it must never be judged against git ls-files",
}
# This list stays one entry long on purpose. It used to also declare `skills/`, `bin/` and
# `.codex/AGENTS.md`, and that turned out to be a bug in the checker rather than in the docs: the README
# wrote those bare names for the user's Hermes Home and Codex home, while the same spellings appeared in
# 仓库结构 meaning repository directories. One string-keyed declaration cannot tell the two referents
# apart, so it hid the stale map entry. The prose now says `$HERMES_HOME/skills/`, `$HERMES_HOME/bin/` and
# `$CODEX_HOME/AGENTS.md` -- the notation this repo already uses elsewhere -- and a placeholder is skipped
# rather than excused.
#
# Anything else belongs in the sentence that cites it, as an in-row `[no-tree-claim CROSS_PROJECT ref=…]`
# token: measured 2026-10-08, DESIGN.md's reference-systems table cites five paths inside *other* projects'
# repositories, and a global declaration would have muted those five spellings in every surface forever --
# `frontend/src/styles/` is exactly the kind of name this repo's own frontend could be mis-written as. An
# in-row token is scoped to the page, must excuse a reference the page actually makes, and goes stale the
# day the tree answers to the name.


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists() and (parent / "services").is_dir():
            return parent
    raise SystemExit("AUTHORITY_INDEX_PATHS_FAIL cannot locate WORK-LAB root")


def tracked_paths(root: Path) -> list[str]:
    """The tracked tree as git names it, with non-ASCII paths left intact.

    Plain `git ls-files` quotes and octal-escapes any path outside ASCII and wraps it in double quotes, so
    every Chinese-named file arrived as `"docs/history/…/WORK-LAB_UI_\\346\\267\\261…_v2/verification/
    model_tests.txt"` -- a name no reference in a document can spell, which made the checker convict a
    correct citation to a real tracked file as an unresolved one. `-c core.quotePath=false` with `-z` is
    what this repository's other index readers already do; splitting on NUL and never stripping keeps a
    path whose real name has leading or trailing spaces a path.
    """
    raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z"],
                         cwd=root, capture_output=True, check=True).stdout
    return [entry.decode("utf-8", "replace") for entry in raw.split(b"\0") if entry]


def references(text: str) -> list[tuple[int, str, str]]:
    r"""Backticked references, plus the first-column token of a language-less fenced map.

    A directory map written in a fenced block is normative prose -- the README's 仓库结构 listed `bin/`,
    `skills/` and `scripts/workflow/` as repository directories with no backticks around them, and a
    backtick-only reader would have called that clean. Only the leading token counts, because that is how
    an aligned map writes its path, and only in an unlabelled or `text` fence: a ```bash transcript's first
    token is a command or an output fragment (`usr/bin/bash:`, `d/All\`), not a claim about the tree.
    """
    rows: list[tuple[int, str, str]] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), 1):
        opener = FENCE.match(line.strip())
        if opener:
            if fence is None:
                fence = (opener.group(1) or "text").lower()
            else:
                fence = None
            continue
        for match in FILE_REF.finditer(line):
            if looks_like_path(match.group(1)):
                rows.append((number, match.group(1), "file"))
        for match in DIR_REF.finditer(line):
            if looks_like_path(match.group(1)):
                rows.append((number, match.group(1), "directory"))
        if fence not in ("text", "markdown", "md") or not line.strip():
            continue
        token = line.strip().split()[0]
        if "/" not in token or not looks_like_path(token):
            continue
        if token.endswith(":") or "\\" in token:
            continue
        if not claims_a_path(token):
            continue
        if token in {row[1] for row in rows if row[0] == number}:
            continue
        rows.append((number, token, "directory" if token.endswith("/") else "file"))
    return rows


def claims_a_path(token: str) -> bool:
    """A fenced map entry is a tree claim only when it is written as a file or a directory.

    Measured on the widened scan: `origin/main SHA/tree` and `/interrupt` were the only two entries that
    fired with neither a trailing slash nor a known extension, and neither is a path -- one is a git ref,
    the other a command the user types. Requiring the same shape a backticked reference needs is not a
    widening of the blind spot either: the extension list already bounds what a backtick can claim, and
    the two rules cannot drift because both are built from EXTENSIONS.
    """
    if token.endswith("/"):
        return True
    return token.endswith(tuple("." + ext for ext in EXTENSIONS))


def is_placeholder(ref: str) -> bool:
    return any(marker in ref for marker in PLACEHOLDER_MARKERS)


def anchored(target: str, ref: str) -> str:
    """Repo-relative form of a reference, resolving `../` against the surface that writes it.

    The README links `../../.github/workflows/work-lab-gate.yml` from `docs/current/`, which is a real
    tracked file once the dots are folded; judging the literal string would call it missing.
    """
    rel = ref.lstrip("/")  # a leading slash here means repo-root-relative, not a filesystem root
    if ".." not in rel:
        return rel
    # PurePosixPath keeps `..` segments untouched, so the folding is done by normpath
    return normpath(PurePosixPath(PurePosixPath(target).parent / rel).as_posix())


def candidates(target: str, ref: str) -> list[str]:
    """Every repo-relative form a reference could legitimately mean, root form first.

    `anchored()` folds `../` but leaves a bare `src/...` at the repository root, which is wrong for a
    document that lives in a subdirectory: `apps/observer/frontend/DESIGN.md` citing
    `src/theme/tokens.ts` means the file beside itself, and that file exists. The document-relative
    form is tried only when the root form fails, so this can never excuse a reference that used to
    resolve — a root-anchored path that stops existing still reports broken.
    """
    primary = anchored(target, ref)
    sibling = (PurePosixPath(PurePosixPath(target).parent) / primary).as_posix()
    return [primary] if primary == sibling else [primary, sibling]


def declared(ref: str) -> str | None:
    """The global declaration covering this reference: exact, or an untracked directory prefix."""
    if ref in DECLARED_NON_PATHS:
        return ref
    for entry in DECLARED_NON_PATHS:
        if entry.endswith("/") and (ref == entry or ref.startswith(entry)):
            return entry
    return None


def covered(ref: str, exemption: str) -> bool:
    """Whether an in-row declaration answers this reference: exact, or a declared directory's child.

    A page that cites one file deep inside another project's tree (`packages/grafana-data/src/themes/…`)
    is making one claim about one foreign root, so the token is written at the directory. The scope is the
    surface that carries the token, which is what makes this safe where the global list is not: a stale or
    over-broad exemption here can only hide rot inside one document, and the residue rule below still
    refuses a token that excuses nothing in that document.
    """
    return ref == exemption or (exemption.endswith("/") and ref.startswith(exemption))


def resolves(tracked: list[str], ref: str, kind: str) -> bool:
    if kind == "directory":
        return any(path.startswith(ref) for path in tracked)
    return ref in tracked


def declarations(text: str) -> list[tuple[int, str, str]]:
    """(line, code, ref) for every in-row `no-tree-claim` token."""
    return [(text[:match.start()].count("\n") + 1, match.group("code"), match.group("ref").strip())
            for match in DECLARATION.finditer(text)]


def _git_paths(root: Path, filter_: str, pattern: str) -> bool:
    proc = subprocess.run(["git", "log", "--all", "-M", f"--diff-filter={filter_}", "--format=%H",
                           "--", pattern], cwd=root, capture_output=True)
    return proc.returncode == 0 and bool(proc.stdout.strip())


def deleted_in_history(root: Path, ref: str) -> bool:
    """A DELETED claim must be checkable: the name appears as a deletion or rename in some ref.

    Three measured adjustments. `--diff-filter=D` alone is not enough -- 942b8e06 and 6bd0bd55 carried these
    files as R100/R081 renames, so a rule looking only for D calls a real removal unverified. A register row
    names the tail of a path (`web/`), which git will not match unless the pattern may start deeper in the
    tree. And a row that names a directory (`scripts/workflow/`) is proven by its contents: history stores
    files, never directory entries, so the `under it` form is tried last.
    """
    patterns = [ref, "*" + ref]
    if ref.endswith("/"):
        stem = ref.rstrip("/")
        # measured: `git log -- '*web/'` finds nothing while `-- '*web/*'` finds five commits, because
        # history names files, not directory entries -- the proof of a deleted directory is its contents
        patterns += [f"{stem}/*", f"*{stem}/*", f"{stem}/**", f"*{stem}/**"]
    return any(_git_paths(root, "DR", pattern) for pattern in patterns)


def never_in_history(root: Path, ref: str) -> bool:
    """NEVER_EXISTED is the stronger claim: no add, delete or rename of this name in any ref."""
    patterns = [ref, "*" + ref]
    if ref.endswith("/"):
        stem = ref.rstrip("/")
        patterns += [f"{stem}/*", f"*{stem}/*", f"{stem}/**", f"*{stem}/**"]
    return not any(_git_paths(root, "ADRMTC", pattern) for pattern in patterns)


def check(root: Path, tracked: list[str], target: str) -> tuple[list, list, list]:
    """(considered rows, unresolved rows, declaration problems) for one surface, empty if absent.

    A considered row is `(line, ref, kind, exempt)` -- `exempt` means the surface itself carries a
    `no-tree-claim` token for that reference, which is reported rather than silently dropped so a run can
    always answer "how much did the exemptions swallow today".
    """
    index = root / target
    if not index.is_file():
        return [], [], []
    raw = index.read_text(encoding="utf-8")
    tokens = declarations(raw)
    # strip the tokens before extracting, so a declared name cannot be counted as a reference of its own
    body = DECLARATION.sub("", raw)
    rows = []
    for number, ref, kind in references(body):
        if is_placeholder(ref):
            continue
        options = candidates(target, ref)
        hit = next((c for c in options
                    if resolves(tracked, c, kind) or declared(c) is not None), None)
        rows.append((number, hit if hit is not None else options[0], kind))
    broken = [row for row in rows
              if declared(row[1]) is None and not resolves(tracked, row[1], row[2])]

    exempt: set[str] = set()
    problems: list[tuple[int, str]] = []
    for line, code, ref in tokens:
        anchored_ref = anchored(target, ref)
        if code not in DECLARATION_CODES:
            problems.append((line, f"unknown reason code {code!r}; the vocabulary is "
                                   f"{'/'.join(sorted(DECLARATION_CODES))}"))
            continue
        kind = "directory" if anchored_ref.endswith("/") else "file"
        token_options = candidates(target, ref)
        if any(resolves(tracked, c, kind) or declared(c) is not None for c in token_options):
            problems.append((line, f"declares `{ref}` as a non-tree claim, but the tree answers to it "
                                   "-- the exemption now hides a live path; fix the sentence instead"))
            continue
        if not any(covered(row[1], token_options[0]) for row in broken):
            problems.append((line, f"declares `{ref}`, which this surface does not ask about at all "
                                   "-- either the pointer was fixed and the token is residue, or the "
                                   "spelling differs from the reference it excuses"))
            continue
        if code == "DELETED" and not deleted_in_history(root, anchored_ref):
            problems.append((line, f"declares `{ref}` as deleted or moved, but no deletion or rename of "
                                   "that name exists in any ref"))
            continue
        if code == "NEVER_EXISTED" and not never_in_history(root, anchored_ref):
            problems.append((line, f"declares `{ref}` as never existing, but the name does appear in git "
                                   "history -- it was tracked at some point, so say so and use DELETED"))
            continue
        exempt.add(anchored_ref)

    unresolved = [row for row in broken
                  if not any(covered(row[1], e) for e in exempt)]
    rows = [(*row, any(covered(row[1], e) for e in exempt)) for row in rows]

    # a global declaration goes stale when the tree contradicts what it asserted, so the test is run on
    # the declaration itself: ".project-local/" means "nothing under here is tracked", and one tracked file
    # under it makes the whole entry false regardless of which child row mentioned it
    problems.extend(
        (0, f"declared as non-repo but tracked now: {entry} -- drop the declaration")
        for entry in DECLARED_NON_PATHS
        if resolves(tracked, entry.rstrip("/") + "/" if entry.endswith("/") else entry,
                    "directory" if entry.endswith("/") else "file"))
    return rows, unresolved, problems


def scanned_surfaces(tracked: list[str]) -> list[str]:
    """Every tracked markdown under the current-documentation root, plus the named extras, from git."""
    surfaces = [path for path in tracked
                if path.startswith(SCOPED_ROOT) and path.endswith(".md")]
    return sorted(set(surfaces) | set(EXTRA_SURFACES))


def strict_surfaces() -> set[str]:
    """Surfaces where "no references at all" is a broken checker rather than a prose page."""
    return set(NAVIGATION_SURFACES) | set(EXTRA_SURFACES)


def floors() -> dict[str, int]:
    """Per-scope measured floors: a run whose extractor matched almost nothing is not a clean scan."""
    return {SCOPED_ROOT: REFS_FLOOR,
            **{target: SURFACE_REF_FLOORS.get(target, REGISTER_REFS_FLOOR)
               for target in EXTRA_SURFACES}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", action="append", default=None,
                    help="repo-relative markdown surface to check; repeatable, defaults to the widened scan")
    args = ap.parse_args(argv)

    root = repo_root()
    widened = args.index is None
    tracked = tracked_paths(root)
    if not tracked:
        print("AUTHORITY_INDEX_PATHS_FAIL git ls-files returned nothing -- nothing can resolve against "
              "an empty tracked set, which is a broken checker, not a clean tree")
        return 1
    targets = scanned_surfaces(tracked) if widened else list(args.index)

    failed_targets = 0
    total_refs = total_broken = total_exempt = silent_surfaces = 0
    refs_by_scope: dict[str, int] = {}
    strict = strict_surfaces()
    for target in targets:
        if not (root / target).is_file():
            # a named surface that is gone is not "no references"; only the widened scan may answer
            # "this file exists and makes no tree claim" as a pass
            print(f"AUTHORITY_INDEX_PATHS_FAIL {target} is not a tracked file in this checkout")
            failed_targets += 1
            continue
        rows, broken, problems = check(root, tracked, target)
        exempt = sum(1 for row in rows if len(row) > 3 and row[3])
        navigation = target in strict
        if not rows and navigation:
            print(f"AUTHORITY_INDEX_PATHS_FAIL {target} yielded refs=0 -- a navigation surface with "
                  "nothing to check is either a rewritten page or a broken extractor, and neither is a "
                  "pass")
            failed_targets += 1
            continue
        if not rows:
            silent_surfaces += 1
        scope = target if target in EXTRA_SURFACES else SCOPED_ROOT
        refs_by_scope[scope] = refs_by_scope.get(scope, 0) + len(rows)
        total_refs += len(rows)
        total_broken += len(broken)
        total_exempt += exempt
        kinds: dict[str, int] = {}
        for row in rows:
            kinds[row[2]] = kinds.get(row[2], 0) + 1
        flag = "FAIL" if broken or problems else "PASS"
        print(f"AUTHORITY_INDEX_PATHS_{flag} target={target} refs={len(rows)} "
              f"files={kinds.get('file', 0)} directories={kinds.get('directory', 0)} "
              f"broken={len(broken)} declared_in_row={exempt} declaration_problems={len(problems)} "
              f"global_declarations={len(DECLARED_NON_PATHS)} "
              f"navigation={'yes' if navigation else 'no'}")
        for number, ref, kind in broken:
            print(f"  line {number}: `{ref}` is not a tracked {kind}")
        for line, message in problems:
            print(f"  line {line}: {message}")
        failed_targets += 1 if (broken or problems) else 0

    print(f"AUTHORITY_INDEX_PATHS_TOTAL targets={len(targets)} refs={total_refs} "
          f"broken={total_broken} declared_in_row={total_exempt} "
          f"no_tree_claims={silent_surfaces} failed_targets={failed_targets}")
    if widened:
        for scope, floor in floors().items():
            counted = refs_by_scope.get(scope, 0)
            if counted < floor:
                print(f"AUTHORITY_INDEX_PATHS_FAIL {scope} produced refs={counted}, below the measured "
                      f"floor {floor} -- an extractor that matches almost nothing reports a clean tree "
                      "it never looked at")
                return 1
    if not widened and total_refs == 0:
        # The floor above only guards the default scan, so a named run had no capability check at all:
        # `--index <file>` on an extractor that matched nothing used to print zero broken and exit 0.
        print("AUTHORITY_INDEX_PATHS_FAIL the named surfaces produced no references at all; nothing was "
              "judged, which is not a pass")
        return 1
    return 1 if failed_targets else 0


if __name__ == "__main__":
    raise SystemExit(main())
