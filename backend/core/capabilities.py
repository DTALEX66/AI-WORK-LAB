# SPDX-License-Identifier: MIT
"""Capability catalog: declared specification + earned qualification.

Audit F10 found the old catalog deriving `VERIFIED` from constants ("plans is
implemented, therefore verified"), from a SQLite file existing, and from the
FTS5 compile option — and then `_derive` handed `can_invoke=true` to a capability
whose authorization was still REQUIRED. None of those observations said anything
about the candidate that was actually running.

Split now:

* ``CATALOG_SPEC`` is a *declaration* — what code exists, what phase it belongs
  to, what it would need. Its own axis is `implementation`, and it can never
  write `qualification`;
* qualification comes only from backend.core.qualifications, i.e. from a probe
  record bound to this candidate version, this operation and this scope;
* with no record the answer is NOT_PROBED and `can_invoke` is false. That is
  fail-closed by construction, not by a default someone remembered to set;
* a host, model or external executor keeps NOT_PROBED/NOT_GRANTED. A successful
  probe of the built-in local surface is never read as a probe of the host.
"""
from __future__ import annotations

from pathlib import Path

from backend.core.qualifications import derive

#: implementation vocabulary: what exists in this build, not what was proven.
IMPLEMENTED = "IMPLEMENTED"
PARTIAL = "PARTIAL"
DECLARED = "DECLARED"
DEFERRED = "DEFERRED"

#: (capability_id, domain, operation, implementation, dependency, phase,
#:  connection, authorization, source_refs, probeable_locally)
SPEC = (
    ("core.projects", "core", "projects.read_write", IMPLEMENTED, "SATISFIED", "P1",
     "NOT_REQUIRED", "NOT_REQUIRED", ["migration/mapping.csv#family:project"], True),
    ("core.tasks", "core", "tasks.attempts.results.verifications", IMPLEMENTED, "SATISFIED", "P1",
     "NOT_REQUIRED", "NOT_REQUIRED", ["migration/mapping.csv#family:task"], True),
    ("design.knowledge.search", "design", "knowledge.search", IMPLEMENTED, "UNKNOWN", "P1",
     "NOT_REQUIRED", "NOT_REQUIRED", ["design:src/design_lab/knowledge_library.py"], True),
    ("design.plans", "design", "plans.read", IMPLEMENTED, "UNKNOWN", "P1",
     "NOT_REQUIRED", "NOT_REQUIRED", ["design:src/design_lab/assistance_plan.py"], True),
    ("design.target_profiles", "design", "target_profiles.read", IMPLEMENTED, "UNKNOWN", "P1",
     "NOT_REQUIRED", "NOT_REQUIRED", ["design:src/design_lab/target_profile.py"], True),
    ("work.repair_packs", "work", "repair_pack.lifecycle", IMPLEMENTED, "UNKNOWN", "P1",
     "NOT_REQUIRED", "REQUIRED", ["work:packages/client-neutral-core/scripts/repair_state.py"], True),
    ("work.solution_library.search", "work", "solutions.search", IMPLEMENTED, "UNKNOWN", "P1",
     "NOT_REQUIRED", "NOT_REQUIRED",
     ["work:packages/client-neutral-core/scripts/solution_library.py",
      "domains/work/control/solution_library.py"], True),
    ("work.observer.read_surface", "work", "observer.snapshot_reads", IMPLEMENTED, "UNKNOWN", "P1",
     "NOT_REQUIRED", "NOT_REQUIRED", ["domains/work/control/sidecar.py"], True),
    ("work.control_operations", "work", "control.operations.write", PARTIAL, "UNKNOWN", "P1",
     "NOT_REQUIRED", "REQUIRED", ["domains/work/control/control_service.py#ControlPlane"], True),
    ("backend.http_surface", "core", "http.loopback_api", IMPLEMENTED, "SATISFIED", "P1",
     "NOT_REQUIRED", "NOT_REQUIRED", ["design:src/design_lab/http_service.py"], True),
    # -- declared code whose real qualification needs a gated host/executor probe --
    ("design.native_hosts", "design", "native_host.invoke", IMPLEMENTED, "UNKNOWN", "P2",
     "NOT_PROBED", "NOT_GRANTED",
     ["design:src/design_lab/native_workers.py", "design:src/design_lab/adapters/photoshop_com.py"],
     False),
    ("design.reconstruction", "design", "reconstruction.run", IMPLEMENTED, "UNKNOWN", "P3",
     "NOT_PROBED", "NOT_GRANTED", ["design:packages/capabilities/reconstruction"], False),
    ("design.generative", "design", "generative.invoke", IMPLEMENTED, "UNKNOWN", "P3",
     "NOT_PROBED", "NOT_GRANTED", ["design:src/design_lab/creative"], False),
    ("work.executors", "work", "executor.invoke", PARTIAL, "UNKNOWN", "P2",
     "NOT_PROBED", "NOT_GRANTED", ["work:config/adapter-registry.json"], False),
    ("work.execution_federation", "work", "federation.dispatch", DEFERRED, "UNKNOWN", "P3",
     "NOT_PROBED", "NOT_GRANTED", ["work:services/execution-federation"], False),
    ("work.collectors", "work", "collector.run", IMPLEMENTED, "UNKNOWN", "P2",
     "NOT_PROBED", "NOT_GRANTED",
     ["domains/work/orchestration/collectors.py (迁入；默认不自动运行)"], False),
    # -- honest contract-only surfaces --
    ("core.evolution", "core", "self_improvement.candidate", DECLARED, "UNKNOWN", "P3",
     "NOT_REQUIRED", "NOT_GRANTED", ["08_前后端交接约定.json#ImprovementCandidate"], False),
    ("integrations.knowledge_candidate", "integrations", "knowledge_candidate.export",
     IMPLEMENTED, "UNKNOWN", "P1合同/P3深度AAOS", "NOT_PROBED", "NOT_GRANTED",
     ["design:src/design_lab/assurance/knowledge_feedback.py"], False),
    ("work.session_continuity", "work", "session.continue", DEFERRED, "UNKNOWN", "P2",
     "NOT_PROBED", "NOT_GRANTED", ["work:services/memory"], False),
    ("data.migration", "core", "business_data.migrate_verify", IMPLEMENTED, "UNKNOWN", "P1",
     "NOT_REQUIRED", "REQUIRED", ["scripts/migrate_business_data.py"], True),
)

_SPEC_FIELDS = ("capability_id", "domain", "operation", "implementation", "dependency", "phase",
                "connection_state", "authorization", "source_refs", "locally_probeable")

CATALOG_SPEC = tuple({**dict(zip(_SPEC_FIELDS, row)), "source_refs": list(row[8])}
                     for row in SPEC)

#: Kept so a reader of the old module still finds the vocabulary it expects.
DATA_ORIGIN = "live"


def derive_catalog(*, spec=CATALOG_SPEC, version: dict, ledger, design_routes: int = 0,
                   work_store_ok: bool = False, unified_store_ok: bool = False,
                   probe_runner=None) -> list[dict]:
    """The catalog as served: specification + earned qualification.

    `probe_runner` is called at most once per process, before the first read, so
    a request can report what this candidate actually showed rather than what a
    constant claimed. It never *writes* a qualification from the request path.
    """
    if probe_runner is not None:
        probe_runner()
    entries = []
    for capability in spec:
        row = ledger.latest_for(capability["capability_id"], capability["operation"]) \
            if ledger is not None else None
        derived = derive(dict(capability), row, version=version)
        entries.append({
            "capability_id": capability["capability_id"],
            "source_refs": list(capability["source_refs"]),
            "domain": capability["domain"],
            "operation": capability["operation"],
            "implementation": capability["implementation"],
            "phase": capability["phase"],
            "locally_probeable": capability["locally_probeable"],
            "can_probe": capability["implementation"] in (IMPLEMENTED, PARTIAL),
            "declared_by": "backend.core.capabilities.CATALOG_SPEC (declaration only)",
            "candidate_version": version["digest"],
            "data_origin": DATA_ORIGIN,
            "design_routes_declared": design_routes,
            **derived,
        })
    return entries


# Back-compat shim: the previous signature was build_catalog(design_routes=…,
# work_store_ok=…, unified_store_ok=…). It no longer mints qualification; it
# reports NOT_PROBED for everything, which is the honest answer without a ledger.
def build_catalog(**kwargs):
    from backend.core.qualifications import candidate_version
    version = candidate_version(Path(kwargs.pop("repo_root", Path(__file__).resolve().parents[2])))
    return derive_catalog(version=version, ledger=None, **kwargs)
