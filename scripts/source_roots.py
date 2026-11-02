# SPDX-License-Identifier: MIT
"""The only place the three roots outside this checkout are resolved.

Before this file existed the same three directories were spelled two different ways in
seven generators and four test files -- an absolute literal
(``Path(r"D:\\All projects\\WORK-LAB")``) and a sibling of the checkout
(``REPO_ROOT.parent / "WORK-LAB"``). A reviewer who wanted to ask "what happens once the
two source repositories are deleted" therefore had no single switch: rewriting one
spelling left the other pointing at the real neighbour, and the generator that is
*supposed* to answer ``SOURCE_REPO_ABSENT`` read the untouched spelling, found the
sources, and reported register drift instead. That is a wrong-typed refusal, and it is
the reason this module exists.

The switch is now the environment: set ``AWL_SOURCE_ROOT_WORK`` /
``AWL_SOURCE_ROOT_DESIGN`` / ``AWL_SOURCE_ROOT_ARCHIVE`` to paths that do not exist and
every consumer in the repository enters the same state without a single byte being
rewritten. Unset, they fall back to the positions this checkout has always used.

Absence is a *named state*, not an exception. A generator that cannot read a root has to
say which root, on this machine, it could not observe -- and must stay able to tell that
apart from a register that really did drift.
"""
from __future__ import annotations

import os
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: The three roots a consumer may need, in the order the cut statement names them.
ROOT_NAMES = ("work", "design", "archive")

#: Environment variable that overrides each root. One name per root, so a reviewer can
#: set exactly the three values and nothing else.
ENVIRONMENT = {
    "work": "AWL_SOURCE_ROOT_WORK",
    "design": "AWL_SOURCE_ROOT_DESIGN",
    "archive": "AWL_SOURCE_ROOT_ARCHIVE",
}

#: Where the sources have always sat for this working copy: neighbours of the checkout.
DEFAULTS = {
    "work": REPO_ROOT.parent / "WORK-LAB",
    "design": REPO_ROOT.parent / "DESIGN-LAB",
    "archive": REPO_ROOT.parent / "Project Archiving",
}

#: What a probe records for a root this machine cannot read. A sentinel rather than an
#: empty string, because "" is a value a real code path can produce and would then be
#: indistinguishable from "the repository exists and has no HEAD".
SOURCE_ROOT_ABSENT = "<source-root-absent>"


def resolve(name: str) -> pathlib.Path:
    """The root for ``name``: the environment override wins, else this checkout's neighbour.

    An override that is set but empty is treated as unset -- a reviewer who exports the
    variable with no value did not choose a path, and silently resolving to the current
    directory would read as "the sources are here".
    """
    if name not in ENVIRONMENT:
        raise KeyError("unknown source root %r; the resolver knows %s"
                       % (name, ", ".join(ROOT_NAMES)))
    override = os.environ.get(ENVIRONMENT[name], "")
    if override.strip():
        return pathlib.Path(override)
    return DEFAULTS[name]


def work_root() -> pathlib.Path:
    """The read-only WORK-LAB checkout (migration lineage only; never a write target)."""
    return resolve("work")


def design_root() -> pathlib.Path:
    """The read-only DESIGN-LAB checkout (migration lineage only; never a write target)."""
    return resolve("design")


def archive_root() -> pathlib.Path:
    """The read-only unified archive (INTEGRATION_POLICY §5); this repository never cleans it."""
    return resolve("archive")


def absent_roots() -> list[dict]:
    """Every root this machine cannot read, named and attributed to its switch.

    Returns ``[]`` when all three are present, so a caller can distinguish "nothing is
    missing" from "something is missing" without parsing a message.
    """
    missing = []
    for name in ROOT_NAMES:
        root = resolve(name)
        if not root.is_dir():
            missing.append({"name": name, "root": str(root), "override": ENVIRONMENT[name],
                            "default": str(DEFAULTS[name]),
                            "reason": ("no %s root at %s on this machine (%s is %s)"
                                       % (name, root, ENVIRONMENT[name],
                                          "set to a path that does not exist"
                                          if os.environ.get(ENVIRONMENT[name], "").strip()
                                          else "unset, so the default position was used"))})
    return missing


def sample_absent_root() -> pathlib.Path:
    """A path that cannot exist while this checkout does -- the probe's stand-in for a deleted source.

    Derived from the resolver's own defaults rather than spelled out: the first version of
    the closure probe hard-coded a drive letter, so it could only ever ask about one
    machine, and a probe that cannot be pointed elsewhere proves nothing about the switch.
    """
    return DEFAULTS["work"].parent / ("awl-gone-%d-WORK-LAB" % os.getpid())
