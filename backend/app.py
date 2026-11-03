# SPDX-License-Identifier: MIT
"""Composition root: one process, one loopback server, both domains.

Binds the migrated DESIGN-LAB ProjectService to the workspace, opens the
unified envelope store and the WORK-LAB canonical store under the workspace's
``.project-local/ai-work-lab/`` root, reconciles interrupted attempts before
serving, and mounts the /api/v1 delegate onto the migrated server kernel.

Loopback only, bearer-token only: make_server pins Host to 127.0.0.1:<port>
and refuses everything else; the token travels on stdin (never argv, files or
URLs), the same protocol the DESIGN-LAB launcher uses.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
if str(TARGET_ROOT) not in sys.path:
    sys.path.insert(0, str(TARGET_ROOT))
DESIGN_PACKAGE_ROOT = TARGET_ROOT / "domains" / "design"
if str(DESIGN_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(DESIGN_PACKAGE_ROOT))

from design_lab.http_service import make_server  # noqa: E402
from design_lab.knowledge_library import KnowledgeLibrary  # noqa: E402
from design_lab.assistance_plan import AssistancePlans  # noqa: E402
from design_lab.runtime.paths import PathPolicyError  # noqa: E402
from design_lab.service import ProjectService  # noqa: E402
from design_lab.target_profile import TargetProfiles  # noqa: E402

from backend import __version__  # noqa: E402
from backend.core.human_gate import ApprovalLedger  # noqa: E402
from backend.core.qualifications import QualificationLedger  # noqa: E402
from backend.core.unified_store import UnifiedStore  # noqa: E402
from backend.core.workpacks import WorkPacks  # noqa: E402
from backend.v1 import V1API, V1_ROUTES  # noqa: E402
from backend.workspace import WorkspaceRefused, guard as workspace_guard  # noqa: E402


def build_workspace(workspace_root: Path) -> dict:
    workspace_root = Path(workspace_root)
    # Guarded before anything is created: the old order made the runtime root first and let the
    # path policy refuse afterwards, so a refused start still left a half-built workspace behind.
    verdict = workspace_guard(workspace_root, TARGET_ROOT)
    if verdict is not None:
        raise WorkspaceRefused(verdict["reason"], verdict["workspace"], verdict["detail"])
    local_root = workspace_root / ".project-local" / "ai-work-lab"
    local_root.mkdir(parents=True, exist_ok=True)
    try:
        service = ProjectService(str(workspace_root))
        reconciled = service.reconcile_interrupted_attempts()
    except PathPolicyError as exc:
        # Anything the migrated policy still refuses -- an escaping ambient PROJECT_LOCAL_ROOT, a
        # link in the path -- arrives here as the same one-line answer, not as a traceback.
        raise WorkspaceRefused("WORKSPACE_PATH_REFUSED", workspace_root, str(exc),
                               next_action="unset PROJECT_LOCAL_ROOT, or pass --workspace under a "
                                           "directory you own, then re-run") from None
    unified = UnifiedStore(local_root / "unified.sqlite3")
    work = WorkPacks(local_root / "work-store.sqlite3",
                     grants_path=local_root / "trusted-grants.json")
    api = V1API(
        design_service=service,
        unified=unified,
        work=work,
        knowledge_factory=KnowledgeLibrary,
        plans_factory=AssistancePlans,
        profiles_factory=TargetProfiles,
        version=__version__,
        approvals=ApprovalLedger(local_root / "human-approvals.json"),
        qualifications=QualificationLedger(local_root / "qualifications.json"),
        repo_root=TARGET_ROOT,
        local_root=local_root,
        workspace_root=workspace_root.resolve(),
    )
    # Record this candidate's own read probes before serving: qualification is
    # earned at startup by observing the real local subjects, never by a request.
    api.run_startup_probes()
    return {"service": service, "unified": unified, "work": work, "api": api,
            "reconciled": reconciled, "local_root": local_root}


def build_server(workspace_root: Path, token: str, port: int = 0):
    """Caller owns the returned HTTPServer's lifetime (serve_forever / shutdown)."""
    context = build_workspace(workspace_root)
    httpd = make_server(context["service"], token, port,
                        extra_routes=V1_ROUTES, delegates=(context["api"],))
    return httpd, context
