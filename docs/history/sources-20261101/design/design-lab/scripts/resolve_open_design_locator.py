#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shared fail-closed Open Design executable locator.

Cloud audit 2026-09-25 Prompt B agent-authorized slice (DL-CLOUD-2026-09-25 F2).

Replaces the two hard-coded owner-machine executable defaults in
``configure_open_design_windows.py`` and ``doctor_open_design_windows.py`` with a
single, portable, fail-closed locator so the owner-machine path assumption
exists in exactly one place (the B4 locator gate inventory states this dedupe
explicitly).

Resolution order (fixed and documented; *never* downloads / clones / installs):

  1. an explicitly supplied value (the ``--open-design-exe`` CLI argument)
  2. the ``OPEN_DESIGN_EXE`` environment variable
  3. ``shutil.which`` on ``PATH``

When none resolves, the locator returns ``path=None`` with the full list of
checked locations and an actionable fix message. It performs no network access,
no install, and no file write.

The optional Win32 ``App Paths`` registry probe remains a documented
owner-gated extension, deliberately left out of this stdlib-portable slice;
see the B4 inventory entry (env -> PATH -> fail-closed here, registry first
in the full TaskPack refactor).
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ENV_VAR = "OPEN_DESIGN_EXE"
_EXE_NAMES = ("Open Design", "Open Design.exe", "opendesign", "opendesign.exe")


@dataclass(frozen=True)
class ExeResolution:
    """Result of a fail-closed executable resolution (no side effects)."""
    path: Optional[Path]
    method: Optional[str]  # explicit / env / path / None
    checked: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.path is not None and self.path.exists()


def resolve_open_design_exe(explicit: Optional[str] = None) -> ExeResolution:
    """Resolve the Open Design executable; fail closed when unresolved."""
    if explicit:
        p = Path(explicit)
        return ExeResolution(
            path=p if p.exists() else None,
            method="explicit" if p.exists() else None,
            checked=[f"explicit: {explicit}"],
        )

    env = os.environ.get(ENV_VAR)
    if env:
        p = Path(env)
        if p.exists():
            return ExeResolution(path=p, method="env", checked=[f"env: {ENV_VAR}={env}"])
        env_note = f"env: {ENV_VAR}={env} (does not exist)"
    else:
        env_note = f"env: {ENV_VAR}=absent"

    checked = [env_note]
    for name in _EXE_NAMES:
        found = shutil.which(name)
        if found:
            return ExeResolution(
                path=Path(found), method="path",
                checked=checked + [f"PATH: which({name!r}) -> {found}"],
            )
        checked.append(f"PATH: which({name!r})=absent")
    return ExeResolution(path=None, method=None, checked=checked)


def resolver_receipt(explicit: Optional[str] = None) -> str:
    """Human-readable fail-closed receipt (no install, no download, ever)."""
    res = resolve_open_design_exe(explicit)
    if res.found:
        return (
            f"OPEN_DESIGN_EXE_RESOLVED via {res.method}: {res.path}\n"
            f"checked: {'; '.join(res.checked)}"
        )
    return (
        "OPEN_DESIGN_EXE_UNRESOLVED (fail-closed; no download or install was attempted)\n"
        "checked locations:\n"
        + "".join(f"  - {c}\n" for c in res.checked)
        + "fix: set OPEN_DESIGN_EXE, put the exe on PATH, or pass --open-design-exe explicitly."
    )


if __name__ == "__main__":
    import sys
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    print(resolver_receipt(explicit))
    raise SystemExit(0 if resolve_open_design_exe(explicit).found else 1)
