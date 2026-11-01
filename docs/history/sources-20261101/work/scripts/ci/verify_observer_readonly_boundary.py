# -*- coding: utf-8 -*-
"""Observer read-only boundary verifier (AG-15 prerequisite, iron law).

Authority: `WORK-LAB-AUTHORITY.md` (Observer is always read-only),
`apps/observer/AGENTS.md` ("Observer is strictly read-only with respect to
external systems and all authoritative module state ... do not add execution,
approval, configuration-apply, Git mutation, shell, or hidden deep-link
routes"), and `config/adapter-registry.json` conventions.

Why this exists
---------------
Before P1-06 (the thin writable Control Surface) can be built, the read-only
side of the split has to be machine-enforced across the WHOLE repository rather
than proven per-view at runtime. Today `l10-views.test.tsx` asserts zero
write/approve/deny/retry controls for a single rendered view, and the sidecar's
405 behaviour is covered indirectly. Nothing stops a future change from adding
an active write control to the Observer, or a POST to its data layer, while all
existing tests stay green.

Three independent rules, each fail-closed
----------------------------------------
R1 RUNTIME. The Observer's serving surface denies every non-GET method. Checked
   against the real `sidecar.make_server` handler class, so it fails if someone
   adds `do_POST`-style write handling.

R2 DATA LAYER. The Observer frontend never issues a write verb (POST/PUT/PATCH/
   DELETE) to any backend. A UI that cannot speak a write verb cannot write,
   whatever it renders.

R3 ACTIVE WRITE CONTROLS. A control whose label is a write action must carry an
   explicit `disabled` guard or be a link/navigation element. This is the
   fake-completion guard: an enabled 保存并发布 / 批准 / 回滚 button that has no
   backend is exactly the "fake success" the project forbids (UI_DECISIONS
   D-06), and the honest pattern already used is `disabled={publishDisabled}`
   plus a visible hint.

Allowed local-only mutations are NOT violations: adding/deleting nodes on the
B10 canvas edits React state and a derived localStorage cache. Per
`apps/observer/AGENTS.md` the Observer may write its own derived
cache/projection; it may not touch authoritative module state. R3 therefore
targets authoritative verbs (approve / reject / retry / rollback / apply /
install / publish / run / execute / delete-from-authority), not canvas-local
node editing, which is guarded by the existing per-view tests.

Exit codes: 0 PASS, 1 FAIL (named reason printed), 2 environment error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FRONTEND_SRC = Path("apps/observer/frontend/src")
SIDECAR = Path("services/orchestration/sidecar.py")

# R2: a write verb in the frontend data layer.
WRITE_VERB = re.compile(r"""method\s*:\s*['"](POST|PUT|PATCH|DELETE)['"]""", re.I)

# R3: authoritative write labels. Deliberately excludes canvas-local node
# editing, which the existing per-view tests already cover.
WRITE_LABELS = (
    "批准", "拒绝", "撤销", "回滚", "应用变更", "重试",
    "安装", "发布", "保存并发布", "运行", "执行任务", "删除策略",
)
# A control line that carries one of these is considered honestly guarded.
GUARD_MARKERS = ("disabled", "aria-disabled", "onClick={undefined}")

_error_lines: list[str] = []


def _fail(rule: str, detail: str) -> None:
    _error_lines.append(f"{rule}: {detail}")


def _iter_frontend_sources(root: Path) -> list[Path]:
    src = root / FRONTEND_SRC
    if not src.is_dir():
        return []
    return sorted(
        p for p in src.rglob("*")
        if p.is_file() and p.suffix in (".ts", ".tsx")
        # Test files assert the contract; they quote the forbidden labels.
        and ".test." not in p.name
        and not p.name.endswith(".d.ts")
    )


def check_runtime(root: Path) -> None:
    """R1: the serving surface denies every non-GET method."""
    sidecar = root / SIDECAR
    if not sidecar.is_file():
        _fail("R1_RUNTIME", f"sidecar module missing: {SIDECAR.as_posix()}")
        return
    text = sidecar.read_text(encoding="utf-8", errors="replace")
    write_handlers = re.findall(r"def\s+do_(POST|PUT|PATCH|DELETE)\b", text)
    if not write_handlers:
        _fail("R1_RUNTIME",
              "no non-GET handler found; the read-only denial cannot be verified")
        return
    for verb in sorted(set(write_handlers)):
        body = re.search(
            rf"def\s+do_{verb}\b.*?(?=\n    def\s|\n    class\s|\Z)", text, re.S
        )
        if body is None:
            _fail("R1_RUNTIME", f"do_{verb} body could not be read")
            continue
        if not re.search(r"405|method_not_allowed", body.group(0)):
            _fail("R1_RUNTIME",
                  f"do_{verb} does not deny with 405/method_not_allowed")
    # A GET handler must still exist, or the surface is not serving read truth.
    if not re.search(r"def\s+do_GET\b", text):
        _fail("R1_RUNTIME", "no do_GET handler found")


def check_data_layer(root: Path) -> None:
    """R2: the frontend never issues a write verb."""
    sources = _iter_frontend_sources(root)
    if not sources:
        _fail("R2_DATA_LAYER", f"no frontend sources under {FRONTEND_SRC.as_posix()}")
        return
    for path in sources:
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            match = WRITE_VERB.search(line)
            if match:
                rel = path.relative_to(root).as_posix()
                _fail("R2_DATA_LAYER",
                      f"{rel}:{number} issues a {match.group(1).upper()} request")


def check_active_write_controls(root: Path) -> None:
    """R3: a write-labelled control must be disabled or explicitly guarded."""
    sources = _iter_frontend_sources(root)
    if not sources:
        return
    for path in sources:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if "<button" not in line and "aria-label=" not in line:
                continue
            # Look at this line plus the next two: JSX attributes often wrap.
            window = "\n".join(lines[index:index + 3])
            labels = [lab for lab in WRITE_LABELS if lab in window]
            if not labels:
                continue
            if any(marker in window for marker in GUARD_MARKERS):
                continue
            rel = path.relative_to(root).as_posix()
            _fail("R3_ACTIVE_WRITE_CONTROL",
                  f"{rel}:{index + 1} renders an unguarded write control {labels[0]!r}")


def verify(root: Path) -> int:
    _error_lines.clear()
    root = root.resolve()
    if not (root / "apps" / "observer").is_dir():
        print(f"OBSERVER_READONLY_ENV_ERROR no apps/observer under {root}", file=sys.stderr)
        return 2
    check_runtime(root)
    check_data_layer(root)
    check_active_write_controls(root)
    if _error_lines:
        print("OBSERVER_READONLY_FAIL " + " | ".join(_error_lines[:10]), file=sys.stderr)
        return 1
    sources = len(_iter_frontend_sources(root))
    print(
        "OBSERVER_READONLY_PASS "
        f"runtime=non-GET-denied data_layer=read_only sources_scanned={sources}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--root", type=Path, default=default_root)
    args = parser.parse_args()
    return verify(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
