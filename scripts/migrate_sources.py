# SPDX-License-Identifier: MIT
"""Migrate the two source repos' P1 capability surfaces into AI-WORK-LAB.

Copies (read-only sources, target-only writes) with a per-file manifest:

DESIGN-LAB (HEAD c4359bb, anchor 9882a89 preserved on the side):
  src/design_lab                          -> domains/design/design_lab
  packages/capabilities/reconstruction    -> packages/capabilities/reconstruction
  design-lab/schemas                      -> packages/contracts/schemas
  apps/workbench                          -> apps/workbench            (compat UI, STITCH redesigns later)
  integrations/hosts/adobe/...            -> integrations/hosts/adobe/...

WORK-LAB (HEAD a8cc2fb == anchor):
  packages/client-neutral-core/scripts/{canonical_store, repair_pack_projection,
    repair_state, repair_verification, issue_projection, project_temp}.py
                                          -> domains/work/workflow_core/
  services/control/control_service.py     -> domains/work/control/control_service.py

Documented REPAIRs applied on the copies:
  * repository-root anchors: files moved one level deeper, parents[N] -> parents[N+1]
  * work workflow_core: bare sibling imports -> package-relative imports
Every copy records source/target SHA-256 and never touches the source repos.

Re-execution safety (2026-10-30 audit, section 六). The previous version deleted
each destination tree with ``shutil.rmtree`` before copying. Two consequences made
it unusable on a live candidate: the tree was gone at the moment a copy failed
(no transactional switch), and re-running it did not prove idempotence — it proved
only that the sources had not changed, while silently discarding every fix anyone
had applied to the target (including the F01 import and root repairs this
repository depends on). The measured cost was real: a bulk re-copy during this
rework reverted ``domains/work/control/sidecar.py`` to its pre-fix bytes.

The engine now plans first and writes the bytes it expects:

* the default mode is ``--plan`` — it reads both trees, reports every would-be
  difference and writes nothing to the target at all;
* ``--apply`` writes file by file and never deletes: an extra file in a
  destination directory is reported as ``UNMANAGED``, not removed;
* deletion is opt-in (``--prune``) and only ever removes paths this tool's own
  previous manifest recorded;
* ``--modified=fail`` (default) refuses to run over a target whose managed files
  were edited, so an accidental rebuild of a fixed candidate is a loud refusal
  instead of a silent undo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

TARGET_ROOT = Path(r"D:\All projects\AI-WORK-LAB")
WORK_SOURCE_ROOT = Path(r"D:\All projects\WORK-LAB")
DESIGN_SOURCE_ROOT = Path(r"D:\All projects\DESIGN-LAB")

OUT_MANIFEST = Path("migration/copies.json")

TREE_COPIES = [
    (DESIGN_SOURCE_ROOT, "src/design_lab", "domains/design/design_lab"),
    (DESIGN_SOURCE_ROOT, "packages/capabilities/reconstruction", "packages/capabilities/reconstruction"),
    (WORK_SOURCE_ROOT, "packages/contracts", "packages/contracts"),
    (DESIGN_SOURCE_ROOT, "design-lab/schemas", "packages/contracts/schemas-design"),
    # reconstruction/contracts.py resolves schemas at <repo-root>/design-lab/schemas
    # in a checkout; keep that layout in the target root for the migrated package.
    (DESIGN_SOURCE_ROOT, "design-lab/schemas", "design-lab/schemas"),
    (DESIGN_SOURCE_ROOT, "design-lab/readiness", "design-lab/readiness"),
    (DESIGN_SOURCE_ROOT, "apps/workbench", "apps/workbench"),
    (DESIGN_SOURCE_ROOT, "integrations/hosts/adobe/photoshop-reconstruction",
     "integrations/hosts/adobe/photoshop-reconstruction"),
    # packaged repo_resource layout (what the wheel force-include carries):
    # design_lab/resources/repo/design-lab/<...> wins before any checkout fallback.
    (DESIGN_SOURCE_ROOT, "design-lab/schemas", "domains/design/design_lab/resources/repo/design-lab/schemas"),
    (DESIGN_SOURCE_ROOT, "design-lab/config", "domains/design/design_lab/resources/repo/design-lab/config"),
    (DESIGN_SOURCE_ROOT, "design-lab/domain-packs", "domains/design/design_lab/resources/repo/design-lab/domain-packs"),
    (DESIGN_SOURCE_ROOT, "design-lab/production", "domains/design/design_lab/resources/repo/design-lab/production"),
    (DESIGN_SOURCE_ROOT, "design-lab/readiness", "domains/design/design_lab/resources/repo/design-lab/readiness"),
]

PACKAGED_STATE_COPIES = [
    # state_resources packaged state schemas: design_lab/resources/state/<name>
    (DESIGN_SOURCE_ROOT, "design-lab/schemas/state", "domains/design/design_lab/resources/state"),
]

AUTOMATION_PACKED_FILES = [
    # automation_connectors resolves these straight under resources/repo/ (source_root=())
    (DESIGN_SOURCE_ROOT, "integrations/adapter-registry.json",
     "domains/design/design_lab/resources/repo/integrations/adapter-registry.json"),
    (DESIGN_SOURCE_ROOT,
     "docs/history/record-archive-2026-10-28-design-automation/ARCHIVE-MANIFEST.json",
     "domains/design/design_lab/resources/repo/docs/history/record-archive-2026-10-28-design-automation/ARCHIVE-MANIFEST.json"),
]

FILE_COPIES = [
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/canonical_store.py",
     "domains/work/workflow_core/canonical_store.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/repair_pack_projection.py",
     "domains/work/workflow_core/repair_pack_projection.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/repair_state.py",
     "domains/work/workflow_core/repair_state.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/repair_verification.py",
     "domains/work/workflow_core/repair_verification.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/issue_projection.py",
     "domains/work/workflow_core/issue_projection.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/project_temp.py",
     "domains/work/workflow_core/project_temp.py"),
    (WORK_SOURCE_ROOT, "services/control/control_service.py",
     "domains/work/control/control_service.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/evidence_range_reader.py",
     "domains/work/control/evidence_range_reader.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/path_text.py",
     "domains/work/control/path_text.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/plan_candidate.py",
     "domains/work/control/plan_candidate.py"),
    (WORK_SOURCE_ROOT, "services/task-governance/permission_gate.py",
     "domains/work/control/permission_gate.py"),
    (WORK_SOURCE_ROOT, "services/orchestration/sidecar.py",
     "domains/work/control/sidecar.py"),
    (WORK_SOURCE_ROOT, "services/orchestration/sidecar_lock.py",
     "domains/work/control/sidecar_lock.py"),
    (WORK_SOURCE_ROOT, "services/orchestration/sse_hub.py",
     "domains/work/control/sse_hub.py"),
    (WORK_SOURCE_ROOT, "services/orchestration/sidecar_endpoint.py",
     "domains/work/control/sidecar_endpoint.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/snapshot_api.py",
     "domains/work/control/snapshot_api.py"),
    (WORK_SOURCE_ROOT, "services/orchestration/composition_root.py",
     "domains/work/control/composition_root.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/open_task_register_projection.py",
     "domains/work/control/open_task_register_projection.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/product_project.py",
     "domains/work/control/product_project.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/project_identity_resolver.py",
     "domains/work/control/project_identity_resolver.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/solution_library.py",
     "domains/work/control/solution_library.py"),
    (WORK_SOURCE_ROOT, "services/orchestration/live_gate.py",
     "domains/work/control/live_gate.py"),
    (WORK_SOURCE_ROOT, "services/orchestration/sse_revision.py",
     "domains/work/control/sse_revision.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/snapshot_validator.py",
     "domains/work/control/snapshot_validator.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/workspace_evidence.py",
     "domains/work/control/workspace_evidence.py"),
    # legacy regression tests, migrated to run on the new paths (V08)
    (WORK_SOURCE_ROOT, "tests/workflow-assistance/test_repair_state.py",
     "tests/legacy/work/test_repair_state.py"),
    (WORK_SOURCE_ROOT, "tests/workflow-assistance/test_repair_pack_projection.py",
     "tests/legacy/work/test_repair_pack_projection.py"),
    (WORK_SOURCE_ROOT, "tests/workflow-assistance/test_repair_verification.py",
     "tests/legacy/work/test_repair_verification.py"),
    (DESIGN_SOURCE_ROOT, "design-lab/tests/test_knowledge_library.py",
     "tests/legacy/design/test_knowledge_library.py"),
    (DESIGN_SOURCE_ROOT, "design-lab/tests/test_assistance_plan.py",
     "tests/legacy/design/test_assistance_plan.py"),
    (DESIGN_SOURCE_ROOT, "design-lab/tests/test_target_profile.py",
     "tests/legacy/design/test_target_profile.py"),
    (WORK_SOURCE_ROOT, "packages/client-neutral-core/scripts/artifact_flow_policy.py",
     "domains/work/workflow_core/artifact_flow_policy.py"),
    (WORK_SOURCE_ROOT, "services/task-governance/completion_authority.py",
     "domains/work/control/completion_authority.py"),
    # capability-library inputs read from the repository root
    (DESIGN_SOURCE_ROOT, "vendor/sources.lock.json", "vendor/sources.lock.json"),
    (DESIGN_SOURCE_ROOT, "vendor/sources.revisions.json", "vendor/sources.revisions.json"),
    (DESIGN_SOURCE_ROOT, "research/candidates/CANDIDATE-TAXONOMY.json",
     "research/candidates/CANDIDATE-TAXONOMY.json"),
]

# (target file, old fragment, new fragment, reason) -- exact-substring patches.
PATCHES = [
    ("domains/design/design_lab/runtime/paths.py",
     "PROJECT_ROOT = Path(__file__).resolve().parents[3]",
     "PROJECT_ROOT = Path(__file__).resolve().parents[4]",
     "repo-root anchor: design_lab moved src/ -> domains/design/, depth +1"),
    ("domains/design/design_lab/reconstruction/__init__.py",
     "Path(__file__).resolve().parents[3]",
     "Path(__file__).resolve().parents[4]",
     "reconstruction bridge now points at migrated packages/capabilities/reconstruction"),
    ("domains/design/design_lab/analysis/capability_library.py",
     "Path(__file__).resolve().parents[3]",
     "Path(__file__).resolve().parents[4]",
     "repo-root anchor depth +1"),
    ("domains/design/design_lab/assurance/research_store.py",
     "parents[3]",
     "parents[4]",
     "PROJECT_ROOT anchor depth +1 (packaged-first resolution unchanged)"),
    ("domains/design/design_lab/adapters/photoshop_com.py",
     "Path(__file__).resolve().parents[3]",
     "Path(__file__).resolve().parents[4]",
     "legacy-assemble.jsx resource anchor depth +1"),
    ("domains/design/design_lab/domain_packs.py",
     "Path(__file__).resolve().parents[2]",
     "Path(__file__).resolve().parents[3]",
     "REPO_ROOT anchor depth +1"),
    ("domains/design/design_lab/workbench.py",
     "Path(__file__).resolve().parents[2]",
     "Path(__file__).resolve().parents[3]",
     "apps/workbench anchor depth +1 (compat UI migrated to target apps/workbench)"),
    ("domains/work/workflow_core/repair_state.py",
     "\nimport issue_projection\n",
     "\nfrom . import issue_projection\n",
     "sibling scripts became one package: bare import -> relative import"),
    ("domains/work/workflow_core/repair_state.py",
     "\nimport repair_pack_projection as projection\n",
     "\nfrom . import repair_pack_projection as projection\n",
     "sibling scripts became one package: bare import -> relative import"),
    ("domains/work/workflow_core/repair_state.py",
     "\nimport repair_verification as verification\n",
     "\nfrom . import repair_verification as verification\n",
     "sibling scripts became one package: bare import -> relative import"),
    ("domains/work/workflow_core/repair_state.py",
     "from canonical_store import CanonicalStore",
     "from .canonical_store import CanonicalStore",
     "sibling scripts became one package: bare import -> relative import"),
    ("domains/work/workflow_core/repair_verification.py",
     "\nimport issue_projection\n",
     "\nfrom . import issue_projection\n",
     "sibling scripts became one package: bare import -> relative import"),
    ("domains/work/control/control_service.py",
     '''_ROOT = Path(__file__).resolve().parents[2]
for _entry in (
    _ROOT / "services" / "task-governance",
    _ROOT / "services" / "orchestration",
    _ROOT / "packages" / "client-neutral-core" / "scripts",
):
    sys.path.insert(0, str(_entry))
''',
     '''# MIGRATION (AI-WORK-LAB 2026-10-30): the WORK-LAB sys.path bootstrap is removed;
# sibling modules now live in this package (domains/work/control) and
# domains/work/workflow_core, imported relatively below. _ROOT is the target
# repository root (parents[3] of domains/work/control/control_service.py).
_ROOT = Path(__file__).resolve().parents[3]
''',
     "WORK-LAB layout bootstrap replaced by package-relative imports"),
    ("domains/work/control/control_service.py",
     "from canonical_store import CanonicalStore  # noqa: E402",
     "from ..workflow_core.canonical_store import CanonicalStore  # noqa: E402",
     "canonical_store moved to domains/work/workflow_core"),
    ("domains/work/control/control_service.py",
     "from evidence_range_reader import name_is_sensitive  # noqa: E402",
     "from .evidence_range_reader import name_is_sensitive  # noqa: E402",
     "bare import -> relative import"),
    ("domains/work/control/control_service.py",
     "from permission_gate import ActionKind, PermissionGate, Policy, RiskTier  # noqa: E402",
     "from .permission_gate import ActionKind, PermissionGate, Policy, RiskTier  # noqa: E402",
     "bare import -> relative import"),
    ("domains/work/control/control_service.py",
     "from plan_candidate import (R_AUTHORIZED, SELF_CONFER_FIELDS, build_candidate,  # noqa: E402",
     "from .plan_candidate import (R_AUTHORIZED, SELF_CONFER_FIELDS, build_candidate,  # noqa: E402",
     "bare import -> relative import"),
    ("domains/work/control/control_service.py",
     "from project_temp import fixture_dir  # noqa: E402",
     "from ..workflow_core.project_temp import fixture_dir  # noqa: E402",
     "project_temp moved to domains/work/workflow_core"),
    ("domains/work/control/control_service.py",
     '''from path_text import (  # noqa: E402  single home for the text rule: see path_text's docstring''',
     '''from .path_text import (  # noqa: E402  single home for the text rule: see path_text's docstring''',
     "bare import -> relative import"),
    ("domains/work/control/evidence_range_reader.py",
     "from path_text import inside_root, path_is_anchored  # noqa: E402",
     "from .path_text import inside_root, path_is_anchored  # noqa: E402",
     "bare import -> relative import"),
    ("domains/work/workflow_core/project_temp.py",
     "from evidence_range_reader import name_is_sensitive  # noqa: E402",
     "from ..control.evidence_range_reader import name_is_sensitive  # noqa: E402",
     "evidence_range_reader moved to domains/work/control"),    ("domains/work/control/control_service.py",
     "from sidecar import _allowed_origin, _is_loopback_host  # noqa: E402",
     "from .sidecar import _allowed_origin, _is_loopback_host  # noqa: E402",
     "bare import -> relative import"),
    ("domains/work/control/control_service.py",
     "from sidecar_endpoint import read_descriptor, validate_descriptor  # noqa: E402",
     "from .sidecar_endpoint import read_descriptor, validate_descriptor  # noqa: E402",
     "bare import -> relative import"),
    ("domains/work/control/control_service.py",
     "from snapshot_api import project_task_record  # noqa: E402",
     "from .snapshot_api import project_task_record  # noqa: E402",
     "bare import -> relative import"),
    ("domains/work/control/sidecar.py",
     "from sidecar_lock import SingleInstanceLock",
     "from .sidecar_lock import SingleInstanceLock",
     "bare import -> relative import"),
    ("domains/work/control/sidecar.py",
     "from canonical_store import CanonicalStore",
     "from ..workflow_core.canonical_store import CanonicalStore",
     "canonical_store moved to domains/work/workflow_core"),
    ("domains/work/control/sidecar.py",
     "import evidence_range_reader",
     "from . import evidence_range_reader",
     "bare import -> relative import"),
    ("domains/work/control/sidecar.py",
     "from sse_hub import HEARTBEAT_SECONDS, LIVE, LiveProjection, SNAPSHOT, STALE, render_sse_frames",
     "from .sse_hub import HEARTBEAT_SECONDS, LIVE, LiveProjection, SNAPSHOT, STALE, render_sse_frames",
     "bare import -> relative import"),
    ("domains/work/control/sse_hub.py",
     "from canonical_store import CanonicalStore",
     "from ..workflow_core.canonical_store import CanonicalStore",
     "canonical_store moved to domains/work/workflow_core"),
    ("domains/work/control/composition_root.py",
     "from canonical_store import CanonicalStore",
     "from ..workflow_core.canonical_store import CanonicalStore",
     "canonical_store moved to domains/work/workflow_core"),
    ("domains/work/control/composition_root.py",
     "from open_task_register_projection import (",
     "from .open_task_register_projection import (",
     "bare import -> relative import"),
    ("domains/work/control/composition_root.py",
     "from product_project import ProductProject, ProjectRootBinding",
     "from .product_project import ProductProject, ProjectRootBinding",
     "bare import -> relative import"),
    ("domains/work/control/composition_root.py",
     "from project_identity_resolver import ApprovedProjectIndex",
     "from .project_identity_resolver import ApprovedProjectIndex",
     "bare import -> relative import"),
    ("domains/work/control/composition_root.py",
     "from snapshot_api import build_snapshot",
     "from .snapshot_api import build_snapshot",
     "bare import -> relative import"),
    ("domains/work/control/project_identity_resolver.py",
     "from product_project import (",
     "from .product_project import (",
     "bare import -> relative import"),
    ("domains/work/control/sidecar.py",
     "from composition_root import build_v3_snapshot, load_approved_index",
     "from .composition_root import build_v3_snapshot, load_approved_index",
     "bare import -> relative import"),
    ("domains/work/control/sidecar.py",
     "import repair_pack_projection",
     "from ..workflow_core import repair_pack_projection",
     "repair_pack_projection moved to domains/work/workflow_core"),
    ("domains/work/control/sidecar.py",
     "import solution_library",
     "from . import solution_library",
     "bare import -> relative import"),
    ("domains/work/control/sidecar.py",
     "from live_gate import evaluate_live",
     "from .live_gate import evaluate_live",
     "bare import -> relative import"),
    ("domains/work/control/sidecar.py",
     "from sse_revision import SseRevisionHub",
     "from .sse_revision import SseRevisionHub",
     "bare import -> relative import"),
    ("domains/work/control/sidecar.py",
     "from snapshot_validator import validate_snapshot",
     "from .snapshot_validator import validate_snapshot",
     "bare import -> relative import"),
    ("domains/work/control/sidecar.py",
     "from workspace_evidence import load_workspace_evidence",
     "from .workspace_evidence import load_workspace_evidence",
     "bare import -> relative import"),
    # --- unified-backend kernel extension: keep the design route table intact,
    # --- let the composition root append /api/v1 routes handled by delegates.
    ("domains/design/design_lab/http_service.py",
     "def make_server(service, token, port=0, *, local_session=False):",
     "def make_server(service, token, port=0, *, local_session=False, extra_routes=(), delegates=()):",
     "AI-WORK-LAB fusion: appendable route table + delegate handlers"),
    ("domains/design/design_lab/http_service.py",
     """    workers = NativeWorkers(service)

    class Handler(BaseHTTPRequestHandler):""",
     """    workers = NativeWorkers(service)

    def _route_table():
        return tuple(ROUTES) + tuple(extra_routes)

    def _resolve(action, match, handler):
        for delegate in delegates:
            fn = getattr(delegate, action, None)
            if fn is not None:
                return fn(handler, match)
        return getattr(handler, action)(match)

    class Handler(BaseHTTPRequestHandler):""",
     "AI-WORK-LAB fusion: route/delegate resolver"),
    ("domains/design/design_lab/http_service.py",
     """                for route in ROUTES:
                    if route.method != self.command:
                        continue
                    target = route_path if route.path_only else self.path
                    if route.exact:
                        if target == route.pattern:
                            return getattr(self, route.action)(None)
                        continue
                    match = re.fullmatch(route.pattern, target)
                    if match is not None and route.accepts(match):
                        return getattr(self, route.action)(match)""",
     """                for route in _route_table():
                    if route.method != self.command:
                        continue
                    target = route_path if route.path_only else self.path
                    if route.exact:
                        if target == route.pattern:
                            return _resolve(route.action, None, self)
                        continue
                    match = re.fullmatch(route.pattern, target)
                    if match is not None and route.accepts(match):
                        return _resolve(route.action, match, self)""",
     "AI-WORK-LAB fusion: dispatch over appended routes/delegates"),
    # --- legacy tests re-pointed at the migrated layout ---
    ("tests/legacy/work/test_repair_state.py",
     '''ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "services" / "control", ROOT / "packages" / "client-neutral-core" / "scripts"):
    sys.path.insert(0, str(entry))''',
     '''ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))''',
     "WORK-LAB layout bootstrap -> target root on sys.path"),
    ("tests/legacy/work/test_repair_state.py",
     "import control_service  # noqa: E402",
     "from domains.work.control import control_service  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_state.py",
     "import project_temp  # noqa: E402",
     "from domains.work.workflow_core import project_temp  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_state.py",
     "import repair_pack_projection as projection  # noqa: E402",
     "from domains.work.workflow_core import repair_pack_projection as projection  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_state.py",
     "import repair_state  # noqa: E402",
     "from domains.work.workflow_core import repair_state  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_state.py",
     "from canonical_store import RETENTION_EXEMPT_TABLES, CanonicalStore  # noqa: E402",
     "from domains.work.workflow_core.canonical_store import RETENTION_EXEMPT_TABLES, CanonicalStore  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_pack_projection.py",
     "ROOT = Path(__file__).resolve().parents[2]",
     "ROOT = Path(__file__).resolve().parents[3]",
     "target-root anchor depth"),
    ("tests/legacy/work/test_repair_pack_projection.py",
     '_load("repair_pack_projection", "packages/client-neutral-core/scripts/repair_pack_projection.py")',
     '_load("repair_pack_projection", "domains/work/workflow_core/repair_pack_projection.py")',
     "module moved to migrated workflow_core"),
    ("tests/legacy/work/test_repair_verification.py",
     '''ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))''',
     '''ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))''',
     "WORK-LAB layout bootstrap -> target root on sys.path"),
    ("tests/legacy/work/test_repair_verification.py",
     "import issue_projection  # noqa: E402",
     "from domains.work.workflow_core import issue_projection  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_verification.py",
     "import project_temp  # noqa: E402",
     "from domains.work.workflow_core import project_temp  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_verification.py",
     "import repair_pack_projection as projection  # noqa: E402",
     "from domains.work.workflow_core import repair_pack_projection as projection  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_verification.py",
     "import repair_state  # noqa: E402",
     "from domains.work.workflow_core import repair_state  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_verification.py",
     "import repair_verification as rv  # noqa: E402",
     "from domains.work.workflow_core import repair_verification as rv  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/work/test_repair_verification.py",
     "from canonical_store import CanonicalStore  # noqa: E402",
     "from domains.work.workflow_core.canonical_store import CanonicalStore  # noqa: E402",
     "package import on migrated layout"),
    ("tests/legacy/design/test_knowledge_library.py",
     "REPO = Path(__file__).resolve().parents[2]",
     "REPO = Path(__file__).resolve().parents[3]",
     "target-root anchor depth"),
    ("tests/legacy/design/test_assistance_plan.py",
     "REPO = Path(__file__).resolve().parents[2]",
     "REPO = Path(__file__).resolve().parents[3]",
     "target-root anchor depth"),
    ("tests/legacy/design/test_target_profile.py",
     "REPO = Path(__file__).resolve().parents[2]",
     "REPO = Path(__file__).resolve().parents[3]",
     "target-root anchor depth"),
    ("domains/work/workflow_core/canonical_store.py",
     "    from artifact_flow_policy import secret_value_paths  # noqa: PLC0415 - shared predicate, no cycle",
     "    from .artifact_flow_policy import secret_value_paths  # noqa: PLC0415 - shared predicate, no cycle",
     "lazy sibling import -> relative (module-level site)"),
    ("domains/work/workflow_core/canonical_store.py",
     "        from artifact_flow_policy import secret_value_paths  # noqa: PLC0415 - shared predicate, no cycle",
     "        from .artifact_flow_policy import secret_value_paths  # noqa: PLC0415 - shared predicate, no cycle",
     "lazy sibling import -> relative (occurrence 1)"),
    ("domains/work/workflow_core/canonical_store.py",
     "        from artifact_flow_policy import secret_value_paths  # noqa: PLC0415 - shared predicate, no cycle",
     "        from .artifact_flow_policy import secret_value_paths  # noqa: PLC0415 - shared predicate, no cycle",
     "lazy sibling import -> relative (occurrence 2)"),
    ("domains/work/workflow_core/canonical_store.py",
     "    import project_temp",
     "    from . import project_temp",
     "lazy sibling import -> relative"),
    ("tests/legacy/work/test_repair_pack_projection.py",
     '_load("issue_projection", "packages/client-neutral-core/scripts/issue_projection.py")',
     '_load("issue_projection", "domains/work/workflow_core/issue_projection.py")',
     "module moved to migrated workflow_core"),
    ("tests/legacy/work/test_repair_verification.py",
     '(ROOT / "services/task-governance/completion_authority.py")',
     '(ROOT / "domains/work/control/completion_authority.py")',
     "authority module migrated to domains/work/control"),
    ("tests/legacy/work/test_repair_verification.py",
     '"services/task-governance/completion_authority.py or move the verdict there"',
     '"domains/work/control/completion_authority.py or move the verdict there"',
     "authority path reference updated"),
    ("tests/legacy/design/test_knowledge_library.py",
     "(REPO / 'src/design_lab/knowledge_library.py')",
     "(REPO / 'domains/design/design_lab/knowledge_library.py')",
     "source-scan target moved to migrated design package"),
]


INIT_FILES = [
    "domains/__init__.py",
    "domains/design/__init__.py",
    "domains/work/__init__.py",
    "domains/work/workflow_core/__init__.py",
    "domains/work/control/__init__.py",
]




def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


#: Destination-relative posix paths whose bytes are expected to differ from the
#: source, because this tool applies a documented patch to them.
PATCHED_TARGETS = frozenset(rel for rel, _old, _new, _reason in PATCHES)


class MigrationRefused(RuntimeError):
    """A preflight condition that makes writing the target unsafe."""


def _skipped(rel_parts) -> bool:
    return any(part == "__pycache__" or part.endswith((".pyc", ".pyo")) for part in rel_parts)


def expected_bytes(source: Path, target_rel: str) -> bytes:
    """The exact bytes this tool intends to leave at ``target_rel``.

    For a patched file that is the source text with every declared patch applied in
    order; for anything else it is the source bytes verbatim. Comparing against
    THIS rather than against the raw source is what keeps a correctly repaired
    candidate from reading as "modified" and refusing itself.

    The line-ending detail is not cosmetic, and it is the reason the first version
    of this checker mis-reported six files. The previous script read the source with
    ``Path.read_text(encoding="utf-8")`` — universal newlines, so a CRLF source
    became ``\\n`` text, multi-line patch anchors matched, and ``write_text`` then
    translated ``\\n`` back to ``\\r\\n`` on Windows when it landed. An unpatched
    file went through ``shutil.copy2`` instead and kept the source's own endings.
    So the expected on-disk bytes of a *patched* file are "source text with newlines
    folded, patches applied, re-expanded to os.linesep" — not a raw byte splice of a
    CRLF source and an LF anchor, which never matches anything.
    """
    payload = source.read_bytes()
    patches = [(old, new) for rel, old, new, _reason in PATCHES if rel == target_rel]
    if not patches:
        return payload
    text = payload.decode("utf-8").replace("\r\n", "\n")
    for old, new in patches:
        if old not in text:
            raise MigrationRefused("PATCH_ANCHOR_ABSENT " + target_rel + ": the declared anchor "
                                   + repr(old[:60]) + " is not in the source text once its line "
                                     "endings are folded; this repair no longer matches the file "
                                     "it claims to fix")
        text = text.replace(old, new, 1)
    if os.linesep != "\n":
        text = text.replace("\n", os.linesep)
    return text.encode("utf-8")


def _same_content(left: bytes, right: bytes) -> bool:
    """Text equality regardless of line-ending convention."""
    return left.replace(b"\r\n", b"\n") == right.replace(b"\r\n", b"\n")


def copy_tree(src: Path, dst: Path) -> list:
    """Write the tree file by file. Nothing here deletes."""
    records = []
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if _skipped(rel.parts):
            continue
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        records.append({"source": str(path), "target": str(target),
                        "sha256_source": sha256_file(path),
                        "sha256_target": sha256_file(target)})
    return records


def destinations(target_root: Path = None):
    """Every (kind, source, destination, destination-relative) pair this tool owns."""
    root = target_root or TARGET_ROOT
    rows = []
    for repo, src_rel, dst_rel in TREE_COPIES:
        rows.append(("tree", repo / src_rel, root / dst_rel, dst_rel))
    for repo, src_rel, dst_rel in PACKAGED_STATE_COPIES + AUTOMATION_PACKED_FILES + FILE_COPIES:
        rows.append(("file", repo / src_rel, root / dst_rel, dst_rel))
    return rows


def intended_set(target_root: Path = None) -> set:
    """Every destination-relative path this tool intends to own."""
    intended = set()
    for _kind, source, _destination, dst_rel in destinations(target_root):
        if not source.exists():
            continue
        if source.is_dir():
            for path in source.rglob("*"):
                if path.is_dir() or _skipped(path.relative_to(source).parts):
                    continue
                relative = PurePosixPath(dst_rel) / path.relative_to(source).as_posix()
                intended.add(relative.as_posix())
        else:
            intended.add(dst_rel)
    for rel in INIT_FILES:
        intended.add(rel)
    intended.add(OUT_MANIFEST.as_posix())
    return intended


def _entry(path: Path, target: Path, target_rel: str) -> dict:
    row = {"source": str(path), "target": target_rel, "kind": "copy"}
    try:
        intended = expected_bytes(path, target_rel)
    except MigrationRefused as exc:
        row.update(state="PATCH_ANCHOR_ABSENT", reason=str(exc))
        return row
    row["sha256_source"] = sha256_bytes(path.read_bytes())
    row["sha256_intended"] = sha256_bytes(intended)
    if not target.is_file():
        row.update(state="would_write")
        return row
    actual = target.read_bytes()
    row["sha256_target"] = sha256_bytes(actual)
    if actual == intended:
        row.update(state="identical")
    elif _same_content(actual, intended):
        # same content, different line endings: reported as its own state so a
        # reviewer never reads a CRLF difference as somebody's edit, and so the
        # apply step does not rewrite 22 files for nothing
        row.update(state="EOL_ONLY", reason="identical text; the on-disk line endings differ "
                                           "from what write_text produced historically")
    else:
        row.update(state="MODIFIED", reason="the target holds bytes this tool would not write")
    return row


def build_plan(target_root: Path = TARGET_ROOT) -> dict:
    """Compare the bytes this tool intends against the target. Writes nothing."""
    entries = []
    for _kind, source, _destination, dst_rel in destinations(target_root):
        if not source.exists():
            entries.append(dict(kind="missing-source", source=str(source), target=dst_rel,
                                state="SOURCE_ABSENT"))
            continue
        if source.is_dir():
            for path in sorted(source.rglob("*")):
                if path.is_dir() or _skipped(path.relative_to(source).parts):
                    continue
                target_rel = (PurePosixPath(dst_rel) / path.relative_to(source).as_posix()).as_posix()
                entries.append(_entry(path, target_root / target_rel, target_rel))
            continue
        entries.append(_entry(source, target_root / dst_rel, dst_rel))
    summary = {}
    for row in entries:
        summary[row["state"]] = summary.get(row["state"], 0) + 1
    owned = intended_set(target_root)
    unmanaged = []
    for _kind, _source, destination, dst_rel in destinations(target_root):
        if not destination.is_dir():
            continue
        for path in sorted(destination.rglob("*")):
            if path.is_dir() or _skipped(path.relative_to(destination).parts):
                continue
            relative = (PurePosixPath(dst_rel) / path.relative_to(destination).as_posix()).as_posix()
            if relative not in owned:
                unmanaged.append(relative)
    return {"target_root": str(target_root), "entries": entries, "summary": summary,
            "unmanaged": sorted(set(unmanaged))}


def apply_plan(plan: dict, *, allow_modified: bool = False) -> dict:
    """Write the planned bytes. Deletes nothing. Refuses a repaired candidate."""
    refused = [row for row in plan["entries"] if row["state"] == "PATCH_ANCHOR_ABSENT"]
    if refused:
        raise MigrationRefused(refused[0]["reason"])
    modified = [row for row in plan["entries"] if row["state"] == "MODIFIED"]
    if modified and not allow_modified:
        raise MigrationRefused(
            "TARGET_MODIFIED " + repr(len(modified)) + " managed file(s) hold bytes this tool would "
            "not write, for example " + repr(modified[0]["target"]) + ". Re-running the copy would "
            "undo repairs already present in the candidate; name them first, or pass "
            "--allow-modified when the source really is the newer truth.")
    root = Path(plan["target_root"])
    written = []
    for row in plan["entries"]:
        if row["state"] not in ("would_write", "MODIFIED"):
            continue
        payload = expected_bytes(Path(row["source"]), row["target"])
        target = root / PurePosixPath(row["target"]).as_posix()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / (target.name + ".migrating")
        try:
            temporary.write_bytes(payload)
        except OSError as exc:
            # a deep rehearsal root can push a packaged path past Windows' classic
            # 260-character limit; say which path and how long, not a bare traceback
            raise MigrationRefused(
                "TARGET_WRITE_FAILED " + type(exc).__name__ + " on " + str(target)
                + " (length " + repr(len(str(target))) + "): the destination root is too deep "
                "to hold this tree on Windows; retry with a shorter --target-root") from None
        try:
            # write-then-move: an interruption leaves the previous bytes in place
            # rather than deleting the tree first and half-refilling it
            os.replace(temporary, target)
        except OSError:
            # the failed attempt's temp file is this tool's own litter; leaving it
            # behind would put a stray *.migrating in the tree an auditor hashes
            try:
                os.remove(temporary)
            except OSError:
                pass
            raise
        written.append({"target": row["target"], "sha256_target": sha256_bytes(payload)})
    return {"written": len(written), "modified_overwritten": len(modified),
            "unmanaged_left_in_place": len(plan["unmanaged"])}


def prune_report(target_root: Path, manifest_path: Path) -> dict:
    """Name the paths a previous manifest recorded that this plan no longer wants."""
    if not manifest_path.is_file():
        return {"refused": "PRUNE_REFUSED no previous manifest at " + str(manifest_path)
                + "; without it there is no evidence of what this tool wrote"}
    previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    recorded = set()
    for group in previous.get("copies", []):
        for record in group.get("records", []):
            try:
                recorded.add(Path(record["target"]).resolve().relative_to(
                    target_root.resolve()).as_posix())
            except (ValueError, OSError):
                continue
    owned = intended_set(target_root)
    return {"recorded": len(recorded),
            "removable": sorted(recorded - owned),
            "note": "listed only. This tool never deletes; a human removes what it names."}


def main(argv=None) -> int:
    global TARGET_ROOT
    parser = argparse.ArgumentParser(description="Plan or apply the two-repo source migration.")
    parser.add_argument("--plan", action="store_true", help="read-only comparison (default)")
    parser.add_argument("--apply", action="store_true", help="write the planned bytes")
    parser.add_argument("--confirm", help="must equal REBUILD-MIGRATION for --apply")
    parser.add_argument("--allow-modified", action="store_true",
                        help="explicitly overwrite files the candidate has since repaired")
    parser.add_argument("--prune", action="store_true",
                        help="report paths a previous manifest recorded and this plan no longer wants")
    parser.add_argument("--json-out", type=Path, help="where to write the plan report")
    parser.add_argument("--target-root", type=Path,
                        help="destination root (isolated rehearsal; the default is this repository)")
    args = parser.parse_args(argv)

    if args.target_root is not None:
        candidate = Path(args.target_root).resolve()
        if not candidate.is_dir():
            print("TARGET_ROOT_MISSING " + str(candidate), file=sys.stderr)
            return 2
        TARGET_ROOT = candidate
    plan = build_plan(TARGET_ROOT)
    summary = plan["summary"]
    report = {"target_root": str(TARGET_ROOT), "summary": summary,
              "unmanaged": plan["unmanaged"],
              "refusals": [row for row in plan["entries"]
                           if row["state"] in ("MODIFIED", "PATCH_ANCHOR_ABSENT")][:200],
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if args.prune:
        report["prune"] = prune_report(TARGET_ROOT, TARGET_ROOT / OUT_MANIFEST)
    if args.apply:
        if args.confirm != "REBUILD-MIGRATION":
            print("APPLY_CONFIRMATION_REQUIRED pass --confirm REBUILD-MIGRATION", file=sys.stderr)
            return 2
        if args.target_root is None and args.confirm == "REBUILD-MIGRATION":
            report["apply"] = apply_plan(plan, allow_modified=args.allow_modified)
        else:
            report["apply"] = apply_plan(plan, allow_modified=args.allow_modified)
        manifest = {"generated_at": report["generated_at"], "work_head": WORK_SOURCE_ROOT.name,
                    "target_root": str(TARGET_ROOT),
                    "copies": [{"kind": "plan", "files": len(plan["entries"]),
                                "records": [{"source": row["source"],
                                             "target": str(TARGET_ROOT / PurePosixPath(
                                                 row["target"]).as_posix()),
                                             "sha256_source": row.get("sha256_source", ""),
                                             "sha256_target": row.get(
                                                 "sha256_target", row.get("sha256_intended", ""))}
                                            for row in plan["entries"] if "target" in row]}],
                    "patches": [{"file": rel, "reason": reason, "old": old.strip(),
                                 "new": new.strip()} for rel, old, new, reason in PATCHES],
                    "inits": list(INIT_FILES)}
        manifest_path = TARGET_ROOT / OUT_MANIFEST
        # the parent may not exist yet on an empty rehearsal root
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"target_root": str(TARGET_ROOT), "summary": summary,
                      "unmanaged_count": len(plan["unmanaged"])}, ensure_ascii=False))
    if args.apply:
        return 0
    return 1 if (summary.get("PATCH_ANCHOR_ABSENT") or summary.get("MODIFIED")) else 0


if __name__ == "__main__":
    sys.exit(main())
