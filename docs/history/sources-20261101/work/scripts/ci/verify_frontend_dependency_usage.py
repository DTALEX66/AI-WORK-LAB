#!/usr/bin/env python
"""Measure whether the observer front-end manifest matches the code that ships.

`npm ci` (CI step, work-lab-gate.yml) already refuses a lock that disagrees with `package.json`, so
version drift cannot pass silently. What nothing could see is the drift on the other two axes, both
measured 2026-10-26 while closing audit finding P2-7:

* a dependency that is declared, locked, installed, and imported by nobody. `recharts` sat in the
  manifest for exactly that reason -- it added install time and a licence surface to a bundle that
  never rendered a chart. `npm ci` is happy with an unused dependency; that is the gap.
* an import that resolves only because some other package happened to install it. Nothing in the
  manifest or the lock names it, so the build works locally and breaks on a clean runner.

Two directions, therefore: every production dependency must be imported by a file that is really
built, and every bare specifier that is imported must be declared. `@types/*` is the one exempted
family -- TypeScript resolves those from `typeRoots` without any import statement, so requiring a
reference would convict a correct setup.

Usage:
    python scripts/ci/verify_frontend_dependency_usage.py [--frontend PATH]
Exit: 0 agreement; 1 unused dependency or undeclared import; 2 the manifest cannot be read.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRONTEND = REPO_ROOT / "apps" / "observer" / "frontend"
SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
# Built output and installed trees are not sources: scanning dist/ would credit a bundle, and
# node_modules/ contains every dependency's own imports.
SKIPPED_DIRS = {"node_modules", "dist", "build", "coverage", ".vite"}
# A source alias (`@/components/...`) resolves inside this front-end, so it is not a package and must
# not be asked for in the manifest. Configs are consumers too -- tailwindcss is imported by
# postcss.config.js, not by src/ -- and are already covered, being `.js`/`.ts` files.
ALIASED_PREFIXES = ("@/", "./", "../")
NODE_BUILTINS = frozenset({
    "fs", "path", "os", "url", "util", "crypto", "http", "https", "net", "dns", "stream",
    "events", "buffer", "querystring", "zlib", "assert", "child_process", "module", "process",
})
# ``from 'x'`` / ``import 'x'`` / ``require('x')`` / ``import('x')`` in one pass.
IMPORT_RE = re.compile(
    r"""(?:from\s+|import\s+|require\(\s*|\bimport\(\s*)['"]([^'"]+)['"]""",
)
# The regex above also lands on prose ("derived from 'injected but invisible'"), so a hit only counts
# as an import when it is a legal module specifier. npm names cannot contain whitespace, and a
# ``node:`` prefix is a builtin by definition, not a manifest claim.
MODULE_SPECIFIER_RE = re.compile(r"\A[A-Za-z@][A-Za-z0-9@._/+~-]*\Z")


def declared_dependencies(manifest: dict) -> tuple[set[str], set[str]]:
    prod = set((manifest.get("dependencies") or {}).keys())
    dev = set((manifest.get("devDependencies") or {}).keys())
    return prod, dev


def package_name(specifier: str) -> str:
    """The manifest key an import specifier resolves to (`@scope/name/sub` -> `@scope/name`)."""
    parts = specifier.split("/")
    if specifier.startswith("@"):
        return "/".join(parts[:2]) if len(parts) > 1 else specifier
    return parts[0]


def source_files(frontend: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(frontend.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if any(part in SKIPPED_DIRS for part in path.relative_to(frontend).parts[:-1]):
            continue
        out.append(path)
    return out


def imported_names(frontend: Path) -> dict[str, str]:
    """Map each imported package name to the first file that imports it."""
    found: dict[str, str] = {}
    for path in source_files(frontend):
        text = path.read_text(encoding="utf-8", errors="replace")
        for specifier in IMPORT_RE.findall(text):
            if specifier.startswith(ALIASED_PREFIXES) or specifier.startswith("node:"):
                continue
            if not MODULE_SPECIFIER_RE.match(specifier):
                continue
            name = package_name(specifier)
            if name in NODE_BUILTINS:
                continue
            found.setdefault(name, str(path.relative_to(frontend)))
    return found


def audit(frontend: Path) -> dict[str, object]:
    manifest = json.loads((frontend / "package.json").read_text(encoding="utf-8"))
    prod, dev = declared_dependencies(manifest)
    imports = imported_names(frontend)
    declared = prod | dev
    unused = sorted(
        name for name in prod
        if name not in imports and not name.startswith("@types/")
    )
    undeclared = sorted(f"{name} (imported by {imports[name]})" for name in imports if name not in declared)
    return {
        "frontend": str(frontend),
        "production_dependencies": len(prod),
        "dev_dependencies": len(dev),
        "imported_names": len(imports),
        "unused": unused,
        "undeclared": undeclared,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--frontend", type=Path, default=DEFAULT_FRONTEND)
    args = parser.parse_args()
    frontend = args.frontend.resolve()
    if not (frontend / "package.json").is_file():
        print(f"DEP_MANIFEST_REFUSED no package.json under {frontend}")
        return 2
    try:
        report = audit(frontend)
    except json.JSONDecodeError as exc:
        print(f"DEP_MANIFEST_REFUSED package.json is not valid JSON: {exc}")
        return 2

    print(f"DEP_MANIFEST_CENSUS frontend={report['frontend']} "
          f"production={report['production_dependencies']} dev={report['dev_dependencies']} "
          f"imported={report['imported_names']}")
    if report["unused"] or report["undeclared"]:
        print(f"DEP_MANIFEST_FAIL unused={report['unused']} undeclared={report['undeclared']}")
        return 1
    print("DEP_MANIFEST_PASS unused=0 undeclared=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
