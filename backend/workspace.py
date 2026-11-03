# SPDX-License-Identifier: MIT
"""What a workspace must contain before the unified backend may run in it, and the one way to create it.

``python -m backend`` used to reach the migrated path policy and die there: on a fresh clone the
default ``workspace/`` does not exist (it is Git-excluded), so ``ProjectService`` raised
``PathPolicyError('owning project marker is missing')`` and the CLI produced a bare traceback with
nothing on stdout -- no reason a launcher can branch on, and one side effect behind it, because
``build_workspace`` created ``workspace/.project-local/ai-work-lab/`` before the policy was reached.

This module owns the contract instead:

* :func:`guard` answers without writing anything, and distinguishes "not initialised" (the ordinary,
  fixable case, with the exact next command) from "this path may not be a workspace" (a file, a drive
  root, a UNC share, or a directory that contains this checkout -- a marker there would turn the
  repository itself into someone's project root);
* :func:`init` is the only writer. It is explicit, it never overwrites an existing marker, and it is
  content-preserving when one already exists;
* :class:`WorkspaceRefused` carries the reason to the CLI so the failure is one JSON line the
  workbench can show as a next step rather than a stack trace.

The policy itself is not weakened here: :mod:`design_lab.runtime.paths` still decides what a valid
owning project is. This only refuses to be the reason a first run looks like a crash.
"""
from __future__ import annotations

import os
from pathlib import Path

MARKER = "AGENTS.md"

#: What the marker says. It identifies the workspace as a project root for the path policy; it is
#: deliberately not a copy of this repository's own agent instructions, and says so, because a reader
#: who finds `AGENTS.md` inside `workspace/` must not take it for governance of the product.
MARKER_TEXT = """# Workspace marker / 工作区标记

This file exists because the unified backend's path policy requires an owning-project marker at the
root of any directory it runs a workspace in. It marks **this directory as a workspace**, not as a
source checkout, and it is not project governance: the product's own instructions live in the
repository root's `AGENTS.md`, which this file does not replace or modify.

这个文件的存在是因为统一后端的运行路径策略要求：任何被当作工作区启动的目录，其根上必须有一个
"归属项目"标记。它只表明**本目录是一个工作区**（运行数据落在本目录的 `.project-local/` 下），
不代表这里是源码仓，也不是项目治理文件；项目自身的说明在仓库根的 `AGENTS.md`，与此无关。

Created by `python -m backend --init`. Deleting it stops the backend from starting here, which is
the intended way to say "this workspace is no longer in use".
"""

INIT_COMMAND = "python -m backend --init --workspace <path>"


class WorkspaceRefused(Exception):
    """A workspace the backend will not run in, stated in the CLI's own words.

    Carries the fields the launcher prints, so a reason never has to be recovered from a string.
    """

    def __init__(self, reason: str, workspace, detail: str, next_action: str | None = None):
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.workspace = str(workspace)
        self.detail = detail
        self.next_action = next_action or INIT_COMMAND

    def as_payload(self) -> dict:
        return {"status": "ERROR", "reason": self.reason, "workspace": self.workspace,
                "policy_detail": self.detail, "next_action": self.next_action}


def _target(workspace_root) -> Path:
    return Path(os.path.abspath(str(Path(str(workspace_root)).expanduser())))


def guard(workspace_root, repo_root) -> dict | None:
    """The refusal for this path, or ``None`` when the backend may run in it. Writes nothing.

    Ordered from "this can never be a workspace" to "it is a workspace that has not been
    initialised", because only the second one has a command to run.
    """
    raw = str(workspace_root)
    target = _target(workspace_root)
    repo = Path(os.path.abspath(str(repo_root)))
    if raw.startswith("\\\\") or str(target).startswith("\\\\"):
        return {"reason": "WORKSPACE_IS_A_NETWORK_PATH", "workspace": str(target),
                "detail": "network paths cannot be pinned to a project root", "fixable": False}
    if target.exists() and not target.is_dir():
        return {"reason": "WORKSPACE_IS_A_FILE", "workspace": str(target),
                "detail": "a file is named as the workspace root", "fixable": False}
    if target.parent == target:
        return {"reason": "WORKSPACE_IS_A_DRIVE_ROOT", "workspace": str(target),
                "detail": "a drive or volume root cannot be a workspace", "fixable": False}
    if repo == target or target in repo.parents:
        return {"reason": "WORKSPACE_CONTAINS_REPOSITORY", "workspace": str(target),
                "detail": "this path is or contains the checkout %s, so a marker here would make "
                          "the repository itself someone's project root" % repo, "fixable": False}
    if not (target / MARKER).is_file():
        return {"reason": "WORKSPACE_NOT_INITIALIZED", "workspace": str(target),
                "detail": "%s is missing, and the path policy requires an owning-project marker"
                          % MARKER, "fixable": True}
    return None


def init(workspace_root, repo_root) -> dict:
    """Create the workspace marker, once, without ever overwriting what is already there.

    Returns what it did -- including the ``already`` case, which writes nothing at all -- and raises
    :class:`WorkspaceRefused` for the paths that can never be workspaces.
    """
    target = _target(workspace_root)
    verdict = guard(target, repo_root)
    if verdict is not None and not verdict["fixable"]:
        raise WorkspaceRefused(verdict["reason"], verdict["workspace"], verdict["detail"],
                               next_action="choose a directory you own, or a directory inside this "
                                           "checkout, and re-run --init")
    target.mkdir(parents=True, exist_ok=True)
    marker = target / MARKER
    if marker.is_file():
        return {"status": "WORKSPACE_ALREADY_INITIALIZED", "workspace": str(target),
                "marker": MARKER, "marker_written": False,
                "marker_bytes": marker.stat().st_size,
                "note": "an existing marker is never overwritten"}
    marker.write_text(MARKER_TEXT, encoding="utf-8", newline="\n")
    return {"status": "WORKSPACE_INITIALIZED", "workspace": str(target), "marker": MARKER,
            "marker_written": True, "marker_bytes": marker.stat().st_size,
            "runtime_root": str(target / ".project-local" / "ai-work-lab"),
            "note": "created by the unified backend's own init path; delete the marker to retire "
                    "this workspace"}
