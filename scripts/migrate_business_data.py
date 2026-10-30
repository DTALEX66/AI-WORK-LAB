# SPDX-License-Identifier: MIT
"""Controlled BUSINESS-DATA migration with failure-injection and restart readback.

Why this file exists (2026-10-30 independent audit, A06/V07 row + section 六):
``scripts/migrate_sources.py`` proves that *source files* copy repeatably. It says
nothing about the runtime databases — the WORK canonical store, the DESIGN state
database and the unified envelope — whose IDs, revisions, references and digests
are the actual business data. The audit refused to let those two things be
reported as one capability. This tool is the database half: it moves rows, and it
proves what happened by reading them back through the owning stores.

What it does
------------
1. prints a declarative contract (``--describe``): every data type this batch
   supports, its source and target schema version, the module that owns its
   writes, its ID namespace, revision/digest policy, references and how record
   counts are accounted. The contract is data, not comments.
2. preflights before the first write: target root exists, the target is not a
   protected path, it resolves inside a caller-declared allowed root (``..``,
   symlink and junction escapes refused), the target schema version and columns
   are compatible, cross-domain ID namespaces do not collide, references are not
   dangling, and every source row's own digest recomputes. Any refusal means a
   non-zero exit and zero rows written.
3. migrates with real semantics: primary-key upsert (never a duplicate append),
   ``revision`` / ``version`` / ``content_sha256`` copied verbatim, cross-domain
   IDs namespaced (``work:`` / ``design:``) instead of silently merged, and the
   DESIGN append-only tables written insert-or-verify because their storage
   triggers refuse an UPDATE by design.
4. runs inside SQLite transactions and can inject a REAL failure mid-batch — an
   exception (everything rolls back) or a hard process kill (``:kill``, where
   SQLite itself discards the uncommitted frames) — and can commit the target
   stores in order and fail after one of them (``--commit-in-order``), which
   rehearses the crash-between-stores case and is recovered by a retry.
5. rebuilds the derived DESIGN FTS index through the product's own
   ``KnowledgeLibrary.rebuild_index()``, drops it again, rebuilds it a second
   time, and compares the hit sets with the source store's.
6. reads key records back through brand-new connections AND brand-new
   ``UnifiedStore`` / ``CanonicalStore`` / ``ProjectService``-bound readers, and
   writes a machine-readable report (``--json-out``) carrying the contract, the
   preflight verdict, per-table row counts and digests before/after, the injected
   failure point, the rollback/retry verdict, the restart readback and the
   limitations.

Scope that does NOT relax
-------------------------
Real private databases stay NOT_RUN/BLOCKED. Pointing ``--source-root`` (or any
source/target path) at another checkout's runtime store, a ``.hermes`` directory,
the user profile, E:/F:, the audit evidence directory or this repository's live
``workspace/.project-local/ai-work-lab/`` refuses the run and names the
authorization that would be required. No flag overrides that in this build: the
rehearsal contract is "a caller-declared allow-root holding a copy", and the two
source repositories stay read-only for everyone.

Exit codes are part of the contract and are listed in ``describe_contract()``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DESIGN_PACKAGE_ROOT = REPO_ROOT / "domains" / "design"
if str(DESIGN_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(DESIGN_PACKAGE_ROOT))

TOOL_VERSION = "ai-work-lab/business-data-migration/v1"

#: Roles in the order the target stores are staged and committed.
ROLE_ORDER = ("work", "design", "unified")

#: Per-row digests are embedded in the report up to this many rows per table so a
#: rerun can be compared row by row; beyond it only the table fingerprint ships.
MAX_ROW_DIGESTS_IN_REPORT = 500

#: Paths that are never a legal target or source, whatever the caller says. The
#: live working libraries are the reason this list exists: an accidental
#: ``--target-unified`` pointed at them must fail before SQLite is opened.
PROTECTED_NAME_SEGMENTS = (
    ("/.project-local/ai-work-lab/", "the live fused working stores"),
    ("/.project-local/audit/", "audit evidence (the counterexample databases live here)"),
    ("/.hermes/", "WORK-LAB private agent directory"),
    ("/.venv/", "the interpreter environment"),
)

EXIT_OK = 0
EXIT_PREFLIGHT_REFUSED = 2
EXIT_SOURCE_REFUSED = 3
EXIT_INJECTED_ROLLBACK = 4
EXIT_PARTIAL_COMMIT = 5
EXIT_READBACK_FAILED = 6
#: SQLite itself refused a statement: the rows that were staged are gone, but a store that
#: already committed keeps them, and the report says which is which.
EXIT_SQL_REFUSED = 7


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fold(path: Path) -> str:
    return path.as_posix().casefold().rstrip("/") + "/"


def _drive_refused(text: str) -> str | None:
    drive = PureWindowsPath(text).drive
    if drive and drive[0].lower() in ("e", "f"):
        return ("E:/F: drives are protected storage; this build never reads or writes them "
                "(AGENTS.md scope rule, owner 2026-10-20 「E盘不动」)")
    return None


class Refused(Exception):
    """A preflight condition that stops the run before any row is written."""

    def __init__(self, code: str, detail: str, exit_code: int = EXIT_PREFLIGHT_REFUSED, **extra):
        super().__init__(code + " " + detail)
        self.code = code
        self.detail = detail
        self.exit_code = exit_code
        # structured facts a reviewer needs next to the sentence (which row, which key)
        self.extra = extra


class InjectedFailure(RuntimeError):
    """The deliberate mid-batch failure this tool exists to prove something about."""

    kill = False
    exit_code = 9


class ToolError(RuntimeError):
    """An internal fault that is not a refusal policy."""


# ---------------------------------------------------------------------------
# path policy
# ---------------------------------------------------------------------------

def protected_reason(candidate: Path) -> str | None:
    folded = candidate.as_posix().casefold()
    drive = _drive_refused(str(candidate))
    if drive:
        return drive
    for segment, who in PROTECTED_NAME_SEGMENTS:
        if segment in folded:
            return f"{segment.strip('/')} belongs to {who}"
    for repo in (REPO_ROOT.parent / "WORK-LAB", REPO_ROOT.parent / "DESIGN-LAB"):
        try:
            if not repo.exists():
                continue
            resolved = repo.resolve()
            if folded == _fold(resolved).rstrip("/"):
                return (f"{repo} is a source repository: read-only for every agent, and its "
                        "runtime stores are real user data")
            if folded.startswith(_fold(resolved)):
                return f"inside the source repository {repo}, which is read-only here"
        except OSError:
            continue
    try:
        home = Path.home().resolve()
    except OSError:
        home = None
    if home is not None and (folded == _fold(home).rstrip("/") or folded.startswith(_fold(home))):
        return ("under the user profile — real private data; this batch never reads a user's "
                "home databases")
    if folded == _fold(REPO_ROOT).rstrip("/") or folded.startswith(_fold(REPO_ROOT)):
        # Inside this repository, only a rehearsal scratch root may hold a migration
        # target: tracked code, the live workspace stores and the audit evidence must
        # never be a database destination.
        relative = folded[len(_fold(REPO_ROOT)):] or "(repository root)"
        if not relative.startswith(".project-local/runs/") and not relative.startswith(
                ".project-local/migration-rehearsal/"):
            return (f"inside this repository but not under .project-local/runs/ or "
                    f".project-local/migration-rehearsal/ ({relative}); a business-data "
                    "migration may only land in a rehearsal root")
    return None


def private_source_reason(candidate: Path) -> str | None:
    """What ``--source-root`` may not be: any real user data location."""
    folded = candidate.as_posix().casefold()
    drive = _drive_refused(str(candidate))
    if drive:
        return drive
    if "/.hermes" in folded:
        return ("a .hermes agent directory: WORK-LAB's private runtime data. Migrating it needs "
                "the owner's exact-path authorization plus a copy as the rehearsal source, "
                "because the live store is not a test fixture")
    try:
        home = Path.home().resolve()
    except OSError:
        home = None
    if home is not None and (folded == _fold(home).rstrip("/")
                             or folded.startswith(_fold(home))):
        return ("a path under the user profile (a real user database). This build only "
                "rehearses on synthetic fixtures; a real migration needs an explicit owner "
                "decision naming the source file, the destination copy and the rollback plan")
    return protected_reason(candidate)


AUTHORIZATION_NEEDED = (
    "what would be required: (1) an owner decision naming this exact source file, "
    "(2) an explicit copy of it placed under a caller-declared rehearsal root and passed as "
    "--target-*, (3) a rollback plan bound to the checksum of both, and (4) a separate "
    "authorisation for anything on E:/F: or holding credentials")


def refused_private_source(label: str, raw) -> None:
    """Name the real-data refusal before any containment check, with the authorization text."""
    candidate = Path(str(raw))
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    for probe in (candidate, Path(os.path.realpath(str(candidate)))):
        reason = private_source_reason(probe)
        if reason:
            raise Refused("SOURCE_ROOT_PRIVATE",
                          f"{label} {probe} is {reason}. Real private-library migration stays "
                          f"NOT_RUN/BLOCKED in this build. {AUTHORIZATION_NEEDED}",
                          exit_code=EXIT_SOURCE_REFUSED)


def _is_newer(stored, incoming) -> bool:
    """Does the target row carry a higher revision/instant than the source row?"""
    for cast in (int, float):
        try:
            return cast(stored) > cast(incoming)
        except (TypeError, ValueError):
            continue
    if isinstance(stored, str) and isinstance(incoming, str):
        return stored > incoming
    return False


def _lstat_is_link(path: Path) -> bool:
    try:
        meta = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(meta.st_mode):
        return True
    attributes = getattr(meta, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024))


def no_link_escape(path: Path, root: Path, label: str) -> None:
    """Refuse a path that reaches its root through a symlink or a junction."""
    chain = [path, *path.parents]
    try:
        stop = chain.index(root)
    except ValueError:
        raise Refused("PATH_OUTSIDE_ROOT", f"{label} {path} is not inside {root}") from None
    for part in chain[:stop + 1]:
        if _lstat_is_link(part):
            raise Refused("PATH_TRAVERSES_LINK",
                          f"{label} {path} reaches {root} through the link/junction {part}; a "
                          "migration target must be a plain directory chain, because a reparse "
                          "point would widen the write scope behind the caller's back")


def checked_path(raw, *, allowed_roots: list[Path], label: str) -> Path:
    """Resolve one caller-named path and prove it stays inside an allowed root."""
    if raw is None or not str(raw).strip():
        raise Refused("PATH_MISSING", f"{label} was not given")
    text = str(raw)
    drive = _drive_refused(text)
    if drive:
        raise Refused("PATH_PROTECTED", f"{label} {text}: {drive}")
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if ".." in candidate.parts:
        raise Refused("PATH_HAS_PARENT_TRAVEL",
                      f"{label} {candidate} contains '..'; pass the resolved path so the "
                      "containment check cannot be argued around")
    reason = protected_reason(candidate)
    if reason:
        raise Refused("PATH_PROTECTED", f"{label} {candidate} is a protected path: {reason}")
    resolved = Path(os.path.realpath(str(candidate)))
    reason = protected_reason(resolved)
    if reason:
        raise Refused("PATH_PROTECTED",
                      f"{label} resolves to a protected path: {resolved} ({reason})")
    inside = None
    for root in allowed_roots:
        if resolved == root or _fold(resolved).startswith(_fold(root)) or _fold(root) in (
                _fold(resolved.parent),):
            inside = root
            break
    if inside is None:
        raise Refused("PATH_OUTSIDE_ALLOWED_ROOT",
                      f"{label} {resolved} is not inside any --allow-root "
                      f"({[str(r) for r in allowed_roots]}); this tool writes only paths the "
                      "caller declared as allowed roots")
    # the chain as the caller WROTE it, then the chain as the filesystem resolves it: a
    # link that stays inside the allowed root is still a link, and realpath alone would
    # let it disappear from the evidence
    no_link_escape(candidate, inside, label)
    no_link_escape(resolved, inside, label)
    return resolved


# ---------------------------------------------------------------------------
# schema facts, introspected from the live modules
# ---------------------------------------------------------------------------

def work_schema_facts() -> dict:
    from domains.work.workflow_core import canonical_store
    return {"module_SCHEMA_VERSION_constant": canonical_store.SCHEMA_VERSION,
            "required_schema_migrations": [2, 3, 4, 5, 6],
            "wal_tables": list(canonical_store.WAL_TABLES),
            "note": "migration 5 added action_plans.version/updated_at, 6 added solutions "
                    "revisions; a store below either one cannot hold the ledger this batch moves"}


def unified_schema_facts() -> dict:
    from backend.core import unified_store
    return {"digest_vocabulary": [unified_store.DIGEST_V1, unified_store.DIGEST_V2],
            "verification_axes": list(unified_store.VERIFICATION_AXES),
            "verification_outcomes": list(unified_store.VERIFICATION_OUTCOMES),
            "added_columns": [[table, column] for table, column in unified_store._ADDED_COLUMNS],
            "idempotency": "UNIQUE(task_id, idempotency_key) on attempts"}


def design_state_resources() -> dict:
    from design_lab.runtime import state_resources
    names = ("design-lab-state-knowledge-library-v1.sql",
             "design-lab-state-knowledge-judgement-v1.sql",
             "design-lab-state-assistance-plan-v1.sql",
             "design-lab-state-target-profile-v1.sql")
    return {"resource_names": list(names),
            "resolved_paths": [str(state_resources.state_schema(name)) for name in names],
            "note": "the DESIGN store has no version table; its identity is the state SQL "
                    "resource plus the append-only UPDATE/DELETE triggers this tool requires"}


#: required = must exist on BOTH sides for the type to migrate at all.
def data_types() -> list[dict]:
    return [
        {
            "key": "work.projects", "role": "work", "table": "projects",
            "source": {"role": "work", "table": "projects"},
            "primary_key": ["project_id"], "mode": "upsert", "staleness": None,
            "namespace": None, "id_namespace_note": "kept verbatim inside the WORK store",
            "columns": ["project_id", "root_path", "display_name", "registered_at", "status"],
            "required": ["project_id", "root_path", "registered_at"],
            "revision_column": None, "semantic_digest": None,
            "authority": "domains/work/workflow_core/canonical_store.py CanonicalStore.register_project",
            "references": [],
            "relations": "the WORK project registry the action-plan ledger is keyed by",
            "counts_as": "one row per registered WORK project",
        },
        {
            "key": "work.action_plans", "role": "work", "table": "action_plans",
            "source": {"role": "work", "table": "action_plans"},
            "primary_key": ["plan_id"], "mode": "upsert", "staleness": "version",
            "namespace": None, "id_namespace_note": "plan ids are ledger identities; kept verbatim",
            "columns": ["plan_id", "project_id", "status", "created_at", "approved_at",
                        "payload", "version", "updated_at"],
            "required": ["plan_id", "project_id", "status", "payload", "version", "updated_at"],
            "revision_column": "version",
            "semantic_digest": "sha256(payload text) — the store's own payloadDigest rule",
            "authority": "canonical_store.py CanonicalStore.save_action_plan (compare-and-swap on version)",
            "references": [["project_id", "work.projects"]],
            "relations": "one current row per task-pack ledger identity; payload cites solutions by id",
            "counts_as": "one row per plan identity (not per version)",
        },
        {
            "key": "work.solutions", "role": "work", "table": "solutions",
            "source": {"role": "work", "table": "solutions"},
            "primary_key": ["solution_id", "revision"], "mode": "immutable",
            "staleness": None, "namespace": None,
            "id_namespace_note": "(solution_id, revision) — a revision is addressed, never merged",
            "columns": ["solution_id", "revision", "title", "status", "software_id",
                        "software_version", "platform", "keywords", "recommended", "created_at",
                        "payload"],
            "required": ["solution_id", "revision", "title", "status", "keywords", "payload",
                         "recommended"],
            "revision_column": "revision",
            "semantic_digest": "sha256(payload text) — immutable revision bytes",
            "authority": "canonical_store.py CanonicalStore.save_solution (append-only revisions)",
            "references": [["payload.supersedes", "work.solutions"]],
            "relations": "revision N supersedes revision N-1; evidence cites a specific revision",
            "counts_as": "one row per (solution, revision)",
        },
        {
            "key": "work.collector_health", "role": "work", "table": "collector_health",
            "source": {"role": "work", "table": "collector_health"},
            "primary_key": ["name"], "mode": "upsert", "staleness": "updated_at",
            "namespace": None, "id_namespace_note": "collector name is the identity",
            "columns": ["name", "total_runs", "last_run_at", "last_success_at",
                        "consecutive_failures", "circuit_open_until", "dropped_count",
                        "refused_rows", "delivered_rows", "last_refusal_reason", "updated_at"],
            "required": ["name", "total_runs", "consecutive_failures", "updated_at"],
            "revision_column": "updated_at", "semantic_digest": None,
            "authority": "canonical_store.py CanonicalStore.upsert_collector_health (only named fields)",
            "references": [],
            "relations": "one row per collector; the issue projection's numerator/denominator",
            "counts_as": "one row per collector name",
        },
        {
            "key": "design.project", "role": "design", "table": "project",
            "source": {"role": "design", "table": "project"},
            "primary_key": ["project_id"], "mode": "immutable", "staleness": None,
            "namespace": None,
            "id_namespace_note": "design-side ids stay verbatim in the DESIGN store; the unified "
                                 "copy is namespaced",
            "columns": ["project_id", "display_name", "created_at"],
            "required": ["project_id", "display_name", "created_at"],
            "revision_column": None, "semantic_digest": None,
            "authority": "design_lab/runtime/asset_store.py create_project",
            "references": [],
            "relations": "owns assistance plans and every asset/brief reference",
            "counts_as": "one row per design project",
        },
        {
            "key": "design.assistance_plan", "role": "design", "table": "assistance_plan",
            "source": {"role": "design", "table": "assistance_plan"},
            "primary_key": ["plan_id"], "mode": "immutable", "staleness": None,
            "namespace": None, "id_namespace_note": "aplan-* identity, verbatim",
            "columns": ["plan_id", "project_id", "created_at"],
            "required": ["plan_id", "project_id", "created_at"],
            "revision_column": None, "semantic_digest": None,
            "authority": "design_lab/assistance_plan.py AssistancePlans.create",
            "references": [["project_id", "design.project"]],
            "relations": "one row per plan identity; the owning project never moves",
            "counts_as": "one row per plan identity",
        },
        {
            "key": "design.assistance_plan_revision", "role": "design",
            "table": "assistance_plan_revision",
            "source": {"role": "design", "table": "assistance_plan_revision"},
            "primary_key": ["plan_id", "revision"], "mode": "immutable", "staleness": None,
            "namespace": None,
            "id_namespace_note": "(plan_id, revision): an old revision is never written as current",
            "columns": ["plan_id", "revision", "objective", "output_type", "content_sha256",
                        "created_at", "created_by", "document_json"],
            "required": ["plan_id", "revision", "objective", "output_type", "content_sha256",
                         "document_json"],
            "revision_column": "revision",
            "semantic_digest": "assistance_plan._content_digest(document_json) must equal content_sha256",
            "authority": "assistance_plan.py AssistancePlans._write_revision",
            "references": [["plan_id", "design.assistance_plan"],
                           [["plan_id", "revision"], "design.assistance_plan_revision"]],
            "relations": "append-only; document_json pins KNOWLEDGE/ASSET/BRIEF revisions",
            "counts_as": "one row per (plan, revision)",
        },
        {
            "key": "design.assistance_plan_choice", "role": "design",
            "table": "assistance_plan_choice",
            "source": {"role": "design", "table": "assistance_plan_choice"},
            "primary_key": ["plan_id", "revision"], "mode": "immutable", "staleness": None,
            "namespace": None,
            "id_namespace_note": "a human gate record keyed by the revision it adopted",
            "columns": ["plan_id", "revision", "actor", "actor_kind", "chosen_at"],
            "required": ["plan_id", "revision", "actor", "actor_kind", "chosen_at"],
            "revision_column": "revision", "semantic_digest": None,
            "authority": "assistance_plan.py AssistancePlans.choose (CHECK actor_kind='human')",
            "references": [["plan_id", "design.assistance_plan"],
                           [["plan_id", "revision"], "design.assistance_plan_revision"]],
            "relations": "names which stored revision a named person adopted",
            "counts_as": "one row per adopted revision",
        },
        {
            "key": "design.knowledge_entry", "role": "design", "table": "knowledge_entry",
            "source": {"role": "design", "table": "knowledge_entry"},
            "primary_key": ["entry_id"], "mode": "immutable", "staleness": None,
            "namespace": None,
            "id_namespace_note": "kentry-* identity, verbatim (the library is global)",
            "columns": ["entry_id", "supersedes", "created_at", "created_by"],
            "required": ["entry_id", "created_at", "created_by"],
            "revision_column": None, "semantic_digest": None,
            "authority": "knowledge_library.py KnowledgeLibrary.create / import_entry",
            "references": [["supersedes", "design.knowledge_entry"]],
            "relations": "supersession is decided once at creation, at most one successor",
            "counts_as": "one row per entry identity",
        },
        {
            "key": "design.knowledge_entry_revision", "role": "design",
            "table": "knowledge_entry_revision",
            "source": {"role": "design", "table": "knowledge_entry_revision"},
            "primary_key": ["entry_id", "revision"], "mode": "immutable", "staleness": None,
            "namespace": None,
            "id_namespace_note": "(entry_id, revision); 'current' is MAX(revision) at read time, "
                                 "never a column",
            "columns": ["entry_id", "revision", "entry_type", "title", "summary",
                        "content_sha256", "recommended", "created_at", "created_by",
                        "document_json"],
            "required": ["entry_id", "revision", "entry_type", "title", "summary",
                         "content_sha256", "recommended", "document_json"],
            "revision_column": "revision",
            "semantic_digest": "knowledge_library._content_digest(document_json) must equal content_sha256",
            "authority": "knowledge_library.py KnowledgeLibrary._write_revision (the one writer)",
            "references": [["entry_id", "design.knowledge_entry"]],
            "relations": "canonical bytes; the FTS index is DERIVED from these rows",
            "counts_as": "one row per (entry, revision)",
        },
        {
            "key": "design.knowledge_judgement", "role": "design", "table": "knowledge_judgement",
            "source": {"role": "design", "table": "knowledge_judgement"},
            "primary_key": ["judgement_id"], "mode": "immutable", "staleness": None,
            "namespace": None, "id_namespace_note": "kjudge-* identity, verbatim",
            "columns": ["judgement_id", "entry_id", "kind", "revision", "value", "replaced_by",
                        "reason", "recorded_by", "recorded_at"],
            "required": ["judgement_id", "entry_id", "kind", "value", "reason", "recorded_by",
                         "recorded_at"],
            "revision_column": "revision", "semantic_digest": None,
            "authority": "knowledge_library.py KnowledgeLibrary.record_judgement (HUMAN only)",
            "references": [["entry_id", "design.knowledge_entry"],
                           ["replaced_by", "design.knowledge_entry"]],
            "relations": "a later human judgement about an entry; writes no revision",
            "counts_as": "one row per recorded judgement",
        },
        {
            "key": "design.target_profile_draft", "role": "design", "table": "target_profile_draft",
            "source": {"role": "design", "table": "target_profile_draft"},
            "primary_key": ["profile_id", "revision"], "mode": "immutable", "staleness": None,
            "namespace": None,
            "id_namespace_note": "tprof-* + revision; seeded profiles are config, never rows",
            "columns": ["profile_id", "revision", "support_state", "content_sha256",
                        "document_json", "created_at", "created_by"],
            "required": ["profile_id", "revision", "support_state", "content_sha256",
                         "document_json", "created_by"],
            "revision_column": "revision",
            "semantic_digest": "target_profile._digest(document minus content_sha256) must equal the column",
            "authority": "target_profile.py TargetProfiles.create (CHECK support_state='USER_DRAFT')",
            "references": [],
            "relations": "one person's draft at the selection panel, append-only",
            "counts_as": "one row per (draft profile, revision)",
        },
        {
            "key": "unified.projects", "role": "unified", "table": "projects",
            "source": {"role": "unified", "table": "projects"},
            "primary_key": ["project_id"], "mode": "upsert", "staleness": None,
            "namespace": None,
            "id_namespace_note": "envelope ids stay verbatim; domain copies arrive namespaced",
            "columns": ["project_id", "source", "display_name", "root_path", "data_origin",
                        "origin_provenance", "registered_at"],
            "required": ["project_id", "source", "display_name", "registered_at"],
            "revision_column": None, "semantic_digest": None,
            "authority": "backend/core/unified_store.py UnifiedStore.register_project",
            "references": [],
            "relations": "the outer envelope's project registry; tasks hang off it",
            "counts_as": "one row per project identity",
        },
        {
            "key": "unified.tasks", "role": "unified", "table": "tasks",
            "source": {"role": "unified", "table": "tasks"},
            "primary_key": ["task_id"], "mode": "upsert", "staleness": "revision",
            "namespace": None, "id_namespace_note": "task_id verbatim",
            "columns": ["task_id", "project_id", "kind", "lifecycle", "title", "input_refs",
                        "acceptance", "professional_required", "current_attempt_id", "revision",
                        "data_origin", "origin_provenance", "created_at", "updated_at"],
            "required": ["task_id", "project_id", "kind", "lifecycle", "title", "revision"],
            "revision_column": "revision", "semantic_digest": None,
            "authority": "unified_store.py UnifiedStore.create_task / set_task_lifecycle (CAS)",
            "references": [["project_id", "unified.projects"]],
            "relations": "current_attempt_id must name one of the task's own attempts",
            "counts_as": "one row per task",
        },
        {
            "key": "unified.attempts", "role": "unified", "table": "attempts",
            "source": {"role": "unified", "table": "attempts"},
            "primary_key": ["attempt_id"], "mode": "upsert", "staleness": "revision",
            "namespace": None, "id_namespace_note": "attempt_id verbatim",
            "columns": ["attempt_id", "task_id", "base_fingerprint", "execution_mode",
                        "executor_ref", "execution_state", "idempotency_key", "pack_plan_id",
                        "pack_ref", "binding_sha256", "candidate_version", "handoff", "revision",
                        "data_origin", "origin_provenance", "started_at", "finished_at",
                        "created_at", "updated_at"],
            "required": ["attempt_id", "task_id", "execution_mode", "idempotency_key", "revision"],
            "revision_column": "revision", "semantic_digest": None,
            "authority": "unified_store.py UnifiedStore.create_attempt (UNIQUE(task_id, idempotency_key))",
            "references": [["task_id", "unified.tasks"]],
            "relations": "a retry mints a new attempt; a failed one is never overwritten",
            "counts_as": "one row per attempt",
        },
        {
            "key": "unified.results", "role": "unified", "table": "results",
            "source": {"role": "unified", "table": "results"},
            "primary_key": ["result_id"], "mode": "upsert", "staleness": None,
            "namespace": None, "id_namespace_note": "result_id verbatim",
            "columns": ["result_id", "task_id", "attempt_id", "pack_id", "declared_result_id",
                        "subject_fingerprint", "artifact_refs", "content_sha256",
                        "digest_vocabulary", "binding", "candidate_version", "origin_chain",
                        "raw", "data_origin", "origin_provenance", "received_at"],
            "required": ["result_id", "task_id", "attempt_id", "content_sha256", "raw"],
            "revision_column": None,
            "semantic_digest": "unified_store.result_digest(raw, digest_vocabulary) must equal content_sha256",
            "authority": "unified_store.py UnifiedStore.record_result (relation checks in code)",
            "references": [["task_id", "unified.tasks"], ["attempt_id", "unified.attempts"]],
            "relations": "raw bytes are canonical; the digest vocabulary travels with the row",
            "counts_as": "one row per received result",
        },
        {
            "key": "unified.verifications", "role": "unified", "table": "verifications",
            "source": {"role": "unified", "table": "verifications"},
            "primary_key": ["verification_id"], "mode": "upsert", "staleness": None,
            "namespace": None, "id_namespace_note": "verification_id verbatim",
            "columns": ["verification_id", "result_id", "axis", "outcome", "subject_fingerprint",
                        "command_ref", "evidence_refs", "verifier_ref", "approval_ref",
                        "identity_state", "checks", "current_validity", "candidate_version",
                        "origin_chain", "detail", "data_origin", "origin_provenance", "observed_at"],
            "required": ["verification_id", "result_id", "axis", "outcome", "observed_at"],
            "revision_column": None, "semantic_digest": None,
            "authority": "unified_store.py UnifiedStore.record_verification",
            "references": [["result_id", "unified.results"]],
            "relations": "a verdict row never completes a task by itself; the latest per axis rules",
            "counts_as": "one row per verdict",
        },
        # --- cross-domain registry projections: this is where a same-named ID from two
        # domains would collide, so the namespace prefix is applied here.
        {
            "key": "unified.projects.registry_from_work", "role": "unified", "table": "projects",
            "source": {"role": "work", "table": "projects"},
            "primary_key": ["project_id"], "mode": "upsert", "staleness": None,
            "namespace": "work:", "projection": "work_registry",
            "id_namespace_note": "project_id becomes 'work:<project_id>' — never a bare id",
            "columns": ["project_id", "source", "display_name", "root_path", "data_origin",
                        "origin_provenance", "registered_at"],
            "projection_columns": ["project_id", "root_path", "display_name", "registered_at"],
            "required": ["project_id", "source", "display_name", "registered_at"],
            "required_source": ["project_id", "root_path", "registered_at"],
            "revision_column": None, "semantic_digest": None,
            "authority": "derived here from CanonicalStore projects; the source column reads 'work'",
            "references": [],
            "relations": "registry copy only: the authoritative row stays in the WORK store",
            "counts_as": "one row per WORK project, under the work: namespace",
        },
        {
            "key": "unified.projects.registry_from_design", "role": "unified", "table": "projects",
            "source": {"role": "design", "table": "project"},
            "primary_key": ["project_id"], "mode": "upsert", "staleness": None,
            "namespace": "design:", "projection": "design_registry",
            "id_namespace_note": "project_id becomes 'design:<project_id>' — never a bare id",
            "columns": ["project_id", "source", "display_name", "root_path", "data_origin",
                        "origin_provenance", "registered_at"],
            "projection_columns": ["project_id", "display_name", "created_at"],
            "required": ["project_id", "source", "display_name", "registered_at"],
            "required_source": ["project_id", "display_name", "created_at"],
            "revision_column": None, "semantic_digest": None,
            "authority": "derived here from the DESIGN state store's project table; source='design'",
            "references": [],
            "relations": "registry copy only: the authoritative row stays in the DESIGN store",
            "counts_as": "one row per design project, under the design: namespace",
        },
    ]


#: Tables that are derived receipts, authorisation records or event ledgers and are
#: NOT part of this batch; stating them here is what stops a later reader from
#: calling their absence a silent gap.
NOT_MIGRATED = {
    "design.knowledge_entry_fts": "derived FTS5 index: rebuilt by "
                                  "KnowledgeLibrary.rebuild_index, never copied (copying it "
                                  "would make it a second truth source)",
    "design.knowledge_index_state": "index receipt: rewritten by the rebuild, not by the migration",
    "design.asset / asset_version / design_brief / design_direction / prompt_result":
        "out of this batch's declared scope; a plan that pins one of them reports the pin as "
        "state=MISSING in the readback rather than pretending it moved",
    "work.telemetry_events / usage_samples / ci_runs / task_events / source_quality / growth_candidates":
        "event ledgers and collector samples: not business authority in this batch",
    "workspace/.project-local/ai-work-lab/trusted-grants.json / human-approvals.json / qualifications.json":
        "grant, approval and qualification ledgers are authorisation records, not data to move; "
        "a migration may never carry a grant with it",
}

PREFLIGHT_CHECKS = [
    "PATH_POLICY: every db path is caller-named, resolves inside --allow-root, has no '..' "
    "segment, reaches its root through no symlink/junction, and is not a protected path",
    "TARGET_ROOT_EXISTS: the migration creates databases inside a root that is already there; "
    "it does not build directory trees",
    "SOURCE_ROOT_NOT_PRIVATE: --source-root and every source db refuse a real user data location "
    "(user profile, .hermes, E:/F:, a source repository, the live working stores, audit evidence)",
    "TARGET_SCHEMA_COMPATIBLE: existing target tables keep their bytes — required columns must "
    "be present and, for append-only DESIGN tables, their UPDATE/DELETE triggers too; a WORK "
    "store whose schema_migrations do not cover 2..6, or a unified envelope missing the binding "
    "columns, is refused and NOT self-migrated",
    "TARGET_NOT_EMPTY: any target row this batch does not itself account for is refused unless "
    "--allow-existing is given (a production store is never a default target); --resume is the "
    "narrower retry mode, which accepts only rows this batch would have written",
    "ID_NAMESPACE: the target primary key is computed for every row; two rows landing on one key "
    "with different bytes are refused (ID_NAMESPACE_CONFLICT) rather than merged",
    "REFERENCE_INTEGRITY: every declared foreign key resolves against (this batch ∪ rows already "
    "in the target); unresolved rows are refused, or named and dropped with --on-dangling=drop, "
    "or namespaced with --on-dangling=assign only when exactly one domain can own them",
    "DIGEST_RECOMPUTES: every source row's own digest is re-derived with the owning module's "
    "function; a row that no longer hashes to what it publishes is refused — drift and a forged "
    "store look identical here, and neither is migratable",
    "TASK_COMPLETION_CLOSURE: a migrated COMPLETED task must still name an attempt that exists "
    "and belongs to it, or it is refused (the audit's F04 counterexample was exactly this)",
    "SUPERSESSION_CARDINALITY: at most one successor per DESIGN knowledge entry across target plus "
    "batch, because the storage trigger aborts the transaction anyway",
]


def describe_contract() -> dict:
    return {
        "tool": TOOL_VERSION,
        "script": "scripts/migrate_business_data.py",
        "purpose": "controlled BUSINESS-DATA migration + failure/recovery verification",
        "distinct_from": "scripts/migrate_sources.py (source-file copy, audit V07). This tool is "
                         "the database half the audit asked to be separated from it.",
        "schema_facts_are": "introspected from the live modules at run time, not restated from a "
                            "comment",
        "source_schema_versions": {
            "work": work_schema_facts(),
            "design": design_state_resources(),
            "unified": unified_schema_facts(),
        },
        "authoritative_writers": {spec["key"]: spec["authority"] for spec in data_types()},
        "id_namespaces": {spec["key"]: (spec["namespace"] or "(verbatim)") for spec in data_types()},
        "revision_policy": {spec["key"]: spec["revision_column"] for spec in data_types()},
        "digest_rules": {spec["key"]: (spec["semantic_digest"] or "row-canonical-sha256/v1")
                         for spec in data_types()},
        "references": {spec["key"]: spec["references"] for spec in data_types()},
        "relations": {spec["key"]: spec["relations"] for spec in data_types()},
        "record_counts": {spec["key"]: spec["counts_as"] for spec in data_types()},
        "data_types": data_types(),
        "write_semantics": {
            "upsert": "INSERT ... ON CONFLICT(pk) DO UPDATE SET every migrated column, so a "
                      "re-run never appends a duplicate; revision/version/content_sha256 are "
                      "written exactly as the source holds them",
            "immutable": "INSERT ... ON CONFLICT(pk) DO NOTHING, then the stored row is compared "
                         "byte-for-byte: identical = skipped and counted, different = refused. The "
                         "DESIGN append-only triggers refuse an UPDATE, so an in-place upsert "
                         "there would be a bug and the comparison is what makes a retry honest",
            "staleness_guard": "for upsert types with a revision column, a target row NEWER than "
                               "the source row is refused (STALE_WRITE_REFUSED): a migration must "
                               "not roll a live store backwards",
            "single_transaction": "one BEGIN IMMEDIATE + PRAGMA defer_foreign_keys per target "
                                  "store; all stores are staged, then committed",
        },
        "preflight_checks": PREFLIGHT_CHECKS,
        "failure_semantics": {
            "injected_exception": "--fail-at <role>:<table>:<n> raises inside the batch after n "
                                  "rows: every open transaction rolls back and the targets equal "
                                  "their pre-migration state",
            "injected_kill": "--fail-at <role>:<table>:<n>:kill calls os._exit inside the "
                             "transaction: no rollback call, no report, the process just dies; "
                             "SQLite discards the uncommitted frames and a fresh reader sees the "
                             "pre-migration state",
            "ordered_commit_crash": "--commit-in-order --fail-at commit:<role> commits the stores "
                                    "up to <role> then dies, leaving a genuinely partial target. "
                                    "Rerunning completes it: stores that already received their "
                                    "rows report identical skips, so nothing duplicates",
            "resume_vs_production_target": "--resume accepts a target that already holds EXACTLY "
                                           "the rows of this batch and refuses the moment it holds "
                                           "a row the batch does not account for "
                                           "(RESUME_FOREIGN_ROWS); merging into somebody else's "
                                           "store still needs the explicit --allow-existing, so "
                                           "the retry path does not loosen the production guard",
            "limitation": "three separate SQLite files have no distributed transaction. Rollback "
                          "is real for anything failing before the commit sequence; a failure "
                          "inside it is recovered by retry, not by undo",
        },
        "index_rebuild": {
            "table": "design.knowledge_entry_fts",
            "rule": "derived; deleted and rebuilt by the product's own "
                    "KnowledgeLibrary.rebuild_index(). Parity is measured three ways: the source "
                    "store's hit set, the target's hit set right after migration, and the target's "
                    "hit set after a deliberate index drop + rebuild",
            "source_is_never_written": "the source store is opened mode=ro; search parity against "
                                       "it is computed by SQL over its own rows, not by running "
                                       "the product writer on it",
        },
        "restart_readback": {
            "unified": "brand-new read-only UnifiedStore: get_project/get_task/get_attempt/"
                       "get_result/get_verification by exact id, completion_support() and "
                       "integrity_report()",
            "work": "brand-new readonly CanonicalStore: read_action_plan (version), read_solution "
                    "per revision, list_collector_health, integrity_check()",
            "design": "brand-new ProjectService bound to the target store: AssistancePlans.detail "
                      "+ AssistancePlans.revision(each stored revision), KnowledgeLibrary.detail, "
                      "TargetProfiles.detail",
        },
        "exit_codes": {
            str(EXIT_OK): "migrated, or --describe / --dry-run passed",
            str(EXIT_PREFLIGHT_REFUSED): "preflight refused; zero rows written",
            str(EXIT_SOURCE_REFUSED): "source points at real private data; refused, NOT_RUN",
            str(EXIT_INJECTED_ROLLBACK): "injected failure; every target rolled back",
            str(EXIT_PARTIAL_COMMIT): "injected failure between ordered commits; retry completes",
            str(EXIT_READBACK_FAILED): "rows were committed but the restart readback, or the "
                                       "derived-index rebuild, disagreed",
            str(EXIT_SQL_REFUSED): "SQLite itself refused a statement: uncommitted stores are "
                                   "rolled back, any store that had already committed is named "
                                   "in the report",
        },
        "scope": {
            "real_user_data_migration": "NOT_RUN / BLOCKED in this build",
            "why": "the only sources verified here are synthetic fixtures under a "
                   "caller-declared rehearsal root; real WORK-LAB / DESIGN-LAB / user-profile "
                   "databases are read-only to this tool and no flag overrides that",
            "to_lift_this": "an owner decision naming the exact source file, an explicit copy as "
                            "the migration target, and a rollback plan bound to a checksum of both",
        },
        "not_migrated": NOT_MIGRATED,
        "limitations": [
            "本轮只验证合成夹具（synthetic fixtures）：不代表任何真实用户数据库已经完成迁移，"
            "也不代表真实私有库迁移已可宣布完成。",
            "This run validates SYNTHETIC FIXTURES. It is not evidence that any real user "
            "database has been migrated, and no report written by this tool may be read as such.",
            "No distributed transaction across the three stores: the commit sequence is not "
            "atomic. Partial-commit recovery is proven by retry, not by undo.",
            "The DESIGN append-only stores are insert-or-verify by design: a migration cannot "
            "correct an already-stored revision, only refuse.",
            "Grants, human approvals and qualification records are never migrated, so a target "
            "store keeps its own authorisation state.",
            "Derived FTS rows are rebuilt, not copied: search parity is proven by the report's "
            "before/after hit sets, not by row counts.",
            "No E:/F: access, no credential read, no scan of a user profile.",
        ],
    }


# ---------------------------------------------------------------------------
# digest helpers (one definition each, imported from the owning module)
# ---------------------------------------------------------------------------

def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def row_digest(row: dict) -> str:
    return sha256_text(canonical_json({key: row[key] for key in sorted(row)}))


def table_fingerprint(pairs: list[tuple[str, str]]) -> str:
    """sha over the (pk, digest) pairs — the whole table's content witness."""
    return sha256_text(canonical_json(sorted(pairs)))


def _private(module_name: str, name: str):
    try:
        module = __import__(module_name, fromlist=[name])
    except ImportError as exc:
        raise ToolError(f"MODULE_UNREADABLE {module_name}: {exc}") from None
    function = getattr(module, name, None)
    if function is None:
        raise ToolError(f"DIGEST_HELPER_MISSING {module_name}.{name} no longer exists; this tool "
                        "refuses to invent its own digest rule")
    return function


def _digest_of(function, row: dict) -> str:
    try:
        document = json.loads(row["document_json"])
    except (TypeError, ValueError):
        return "UNPARSEABLE_DOCUMENT"
    if not isinstance(document, dict):
        return "NOT_AN_OBJECT"
    return function(document)


def semantic_digests(type_key: str, row: dict) -> dict:
    """Re-derive what the row itself publishes; {} when it publishes no digest."""
    out: dict[str, str] = {}
    if type_key == "unified.results":
        from backend.core.unified_store import result_digest
        raw = row.get("raw")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                return {"recomputed": "UNPARSEABLE_RAW", "stored": str(row["content_sha256"])}
        out["recomputed"] = result_digest(raw, row.get("digest_vocabulary"))
        out["stored"] = str(row["content_sha256"])
    elif type_key == "design.assistance_plan_revision":
        out["recomputed"] = _digest_of(_private("design_lab.assistance_plan", "_content_digest"),
                                       row)
        out["stored"] = str(row["content_sha256"])
    elif type_key == "design.knowledge_entry_revision":
        out["recomputed"] = _digest_of(_private("design_lab.knowledge_library", "_content_digest"),
                                       row)
        out["stored"] = str(row["content_sha256"])
    elif type_key == "design.target_profile_draft":
        digest = _private("design_lab.target_profile", "_digest")
        try:
            document = json.loads(row["document_json"])
        except (TypeError, ValueError):
            return {"recomputed": "UNPARSEABLE_DOCUMENT", "stored": str(row["content_sha256"])}
        if isinstance(document, dict):
            document = dict(document, content_sha256=None)
        out["recomputed"] = digest(document)
        out["stored"] = str(row["content_sha256"])
    elif type_key in ("work.action_plans", "work.solutions"):
        payload = row.get("payload")
        out["recomputed"] = sha256_text(payload) if isinstance(payload, str) and payload else "ABSENT"
        out["stored"] = out["recomputed"]
    return out


# ---------------------------------------------------------------------------
# store plumbing
# ---------------------------------------------------------------------------

def ro_uri(path: Path) -> str:
    return f"file:{quote(Path(path).resolve().as_posix(), safe='/')}?mode=ro"


def open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise Refused("SOURCE_DB_MISSING", f"{path} is not a database file")
    try:
        conn = sqlite3.connect(ro_uri(path), uri=True)
        # prove the file is readable as a database before anything iterates it
        conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
    except sqlite3.Error as exc:
        raise Refused(
            "SOURCE_DB_UNREADABLE",
            f"{path} could not be opened read-only: {exc}. A WAL database needs its -wal and "
            "-shm sidecars to be present and readable; copy the whole set, or checkpoint the "
            "source with its owning store first. This tool never opens a source for writing.",
            exit_code=EXIT_SOURCE_REFUSED) from None
    conn.row_factory = sqlite3.Row
    return conn


def open_write(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def columns_of(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute("PRAGMA table_info(" + table + ")")]


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)).fetchone() is not None


def triggers_of(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}


def db_path_of(conn: sqlite3.Connection) -> str:
    return str(conn.execute("PRAGMA database_list").fetchone()[2])


#: (target role, target table) -> the spec that owns it, for key arithmetic.
SPEC_LOOKUP = {(spec["role"], spec["table"]): spec for spec in data_types()}

APPEND_ONLY_TRIGGERS = {
    "design.knowledge_entry": ["knowledge_entry_no_update", "knowledge_entry_no_delete"],
    "design.knowledge_entry_revision": ["knowledge_entry_revision_no_update",
                                        "knowledge_entry_revision_no_delete"],
    "design.assistance_plan": ["assistance_plan_no_update", "assistance_plan_no_delete"],
    "design.assistance_plan_revision": ["assistance_plan_revision_no_update",
                                        "assistance_plan_revision_no_delete"],
    "design.assistance_plan_choice": ["assistance_plan_choice_no_update",
                                      "assistance_plan_choice_no_delete"],
    "design.target_profile_draft": ["target_profile_draft_no_update",
                                    "target_profile_draft_no_delete"],
}


def read_table(conn: sqlite3.Connection, table: str, cols: list[str]) -> list[dict]:
    if not table_exists(conn, table) or not cols:
        return []
    order = ", ".join(f'"{column}"' for column in cols)
    rows = conn.execute(f"SELECT {order} FROM {table} ORDER BY rowid").fetchall()
    return [{column: row[column] for column in cols} for row in rows]


def current_revision_documents(conn: sqlite3.Connection) -> dict[str, dict]:
    """entry_id -> the parsed MAX(revision) document, from the canonical revision rows."""
    if not table_exists(conn, "knowledge_entry_revision"):
        return {}
    out = {}
    rows = conn.execute(
        "SELECT r.entry_id, r.revision, r.document_json FROM knowledge_entry_revision r"
        " WHERE r.revision = (SELECT MAX(x.revision) FROM knowledge_entry_revision x"
        "                     WHERE x.entry_id = r.entry_id) ORDER BY r.entry_id").fetchall()
    for row in rows:
        try:
            out[row["entry_id"]] = json.loads(row["document_json"])
        except (TypeError, ValueError):
            continue
    return out


#: The product's searchable fields, restated here only to MEASURE the index, never to write it.
KNOWLEDGE_SEARCH_FIELDS = ("title", "summary", "body", "domain_tags", "task_tags", "target_tools")


def index_hit_set(conn: sqlite3.Connection, term: str) -> list[str]:
    """The FTS5 trigram hit set for one term, read straight off the store's own index."""
    if not table_exists(conn, "knowledge_entry_fts"):
        return []
    try:
        rows = conn.execute("SELECT DISTINCT entry_id FROM knowledge_entry_fts"
                            " WHERE knowledge_entry_fts MATCH ?", ('"' + term + '"',)).fetchall()
    except sqlite3.OperationalError:
        return []
    return sorted(row[0] for row in rows)


def text_hit_set(conn: sqlite3.Connection, term: str) -> list[str]:
    """Entries whose CURRENT revision bytes contain the term (the fallback's own rule)."""
    needle = term.casefold()
    hits = []
    for entry_id, document in current_revision_documents(conn).items():
        for field in KNOWLEDGE_SEARCH_FIELDS:
            value = document.get(field)
            text = ", ".join(value) if isinstance(value, list) else str(value or "")
            if needle in text.casefold():
                hits.append(entry_id)
                break
    return sorted(hits)


def search_set(conn: sqlite3.Connection, term: str) -> dict:
    """The same intersection the product search computes for one term."""
    fts = index_hit_set(conn, term)
    text = text_hit_set(conn, term)
    if len(term) >= 3:
        chosen = sorted(set(fts) & set(text)) if fts else text
        mechanism = "TRIGRAM" if fts else "TRIGRAM_EMPTY_THEN_FALLBACK"
    else:
        chosen = text
        mechanism = "SHORT_FALLBACK"
    return {"term": term, "mechanism": mechanism, "fts_hits": fts, "text_hits": text,
            "hits": chosen}


# ---------------------------------------------------------------------------
# target schema initialisation (the owning module's own DDL, additive)
# ---------------------------------------------------------------------------

def init_target_work(path: Path) -> str:
    from domains.work.workflow_core.canonical_store import CanonicalStore
    if path.is_file():
        return "EXISTED"
    store = CanonicalStore(path)
    store.close()
    return "CREATED"


def init_target_unified(path: Path) -> str:
    from backend.core.unified_store import UnifiedStore
    if path.is_file():
        return "EXISTED"
    store = UnifiedStore(path)
    store.close()
    return "CREATED"


def init_target_design(path: Path, project_root: Path) -> str:
    from design_lab import assistance_plan, knowledge_library, target_profile
    existed = path.is_file()
    for module in (knowledge_library, assistance_plan, target_profile):
        conn = module.connect(str(path), project_root=str(project_root))
        try:
            conn.commit()
        finally:
            conn.close()
    return "EXISTED (tables added if missing)" if existed else "CREATED"


# ---------------------------------------------------------------------------
# the migration
# ---------------------------------------------------------------------------

class Migration:
    def __init__(self, args):
        self.args = args
        self.types = data_types()
        self.refusals: list[dict] = []
        self.warnings: list[dict] = []
        self.findings: list[dict] = []
        self.assignments: list[dict] = []
        self.committed: list[str] = []
        self.foreign_target_rows: dict[str, int] = {}
        self.occupied_target_rows: dict[str, int] = {}
        self.injected_fired = False
        self.index_rebuild_failed: str | None = None
        self.index_receipt: dict | None = None
        self.plan_rows_existing: dict[str, int] = {}
        self.plan: dict[str, dict] = {}
        self.fail_at = self._parse_fail(args.fail_at)
        self.report: dict = {
            "tool": TOOL_VERSION,
            "generated_at": _now(),
            "argv": {key: (str(value) if isinstance(value, Path) else value)
                     for key, value in vars(args).items()},
            "outcome": "NOT_STARTED",
        }

    # -- small utilities ------------------------------------------------------
    def _note(self, bucket: str, code: str, detail: str, **extra):
        entry = {"code": code, "detail": detail}
        entry.update(extra)
        getattr(self, bucket).append(entry)

    def _parse_fail(self, spec):
        if not spec:
            return None
        kill = str(spec).endswith(":kill")
        body = str(spec)[:-5] if kill else str(spec)
        parts = body.split(":")
        if len(parts) == 2 and parts[0] == "commit":
            return {"kind": "commit", "role": parts[1], "table": None, "after": None,
                    "kill": kill, "spec": spec}
        if len(parts) == 3:
            role, table, count = parts
            try:
                after = int(count)
            except ValueError as exc:
                raise Refused("FAIL_AT_MALFORMED", f"--fail-at row count {count!r} is not a number"
                              ) from exc
            return {"kind": "rows", "role": role, "table": table, "after": after, "kill": kill,
                    "spec": spec}
        raise Refused("FAIL_AT_MALFORMED",
                      "--fail-at wants <role>:<table>:<n>[:kill] or commit:<role>[:kill], got "
                      + repr(spec))

    # -- paths ------------------------------------------------------------
    def resolve_paths(self):
        args = self.args
        allowed: list[Path] = []
        for raw in list(args.allow_root) + [args.target_root]:
            if not raw:
                continue
            root = Path(str(raw))
            if not root.is_dir():
                raise Refused("ALLOW_ROOT_MISSING",
                              f"allowed root {root} does not exist; the caller must point at a "
                              "directory that is already there")
            resolved = Path(os.path.realpath(str(root)))
            reason = protected_reason(resolved)
            if reason:
                raise Refused("ALLOW_ROOT_PROTECTED", f"{resolved} is protected: {reason}")
            if resolved not in allowed:
                allowed.append(resolved)
        if not allowed:
            raise Refused("ALLOW_ROOT_REQUIRED",
                          "no --allow-root/--target-root given: this tool writes only paths the "
                          "caller declared as allowed, so an unguarded invocation is a refusal")
        self.allowed_roots = allowed
        refused_private_source("--source-root", args.source_root)
        args.source_root = checked_path(args.source_root, allowed_roots=allowed,
                                       label="--source-root")
        args.target_root = checked_path(args.target_root, allowed_roots=allowed,
                                       label="--target-root")
        if not args.target_root.is_dir():
            raise Refused("TARGET_ROOT_MISSING",
                          f"target root {args.target_root} must be an existing directory")
        reason = private_source_reason(args.target_root)
        if reason:
            raise Refused("TARGET_PROTECTED",
                          f"--target-root {args.target_root} is {reason}")
        both = [args.source_root, args.target_root]
        for role in ROLE_ORDER:
            for side in ("source", "target"):
                name = f"{side}_{role}"
                if side == "source":
                    refused_private_source(f"--source-{role}", getattr(args, name))
                path = checked_path(getattr(args, name), allowed_roots=both,
                                   label=f"--{name.replace('_', '-')}")
                setattr(args, name, path)
            if not getattr(args, "source_" + role).is_file():
                raise Refused("SOURCE_DB_MISSING",
                              f"--source-{role} {getattr(args, 'source_' + role)} is not a "
                              "database file")

    # -- schema compatibility ----------------------------------------------
    def check_role_level(self, conn: sqlite3.Connection, role: str, *, side: str):
        """Store-wide version witnesses, before any per-type column question."""
        label = f"{side}:{role}"
        if role == "work":
            if not table_exists(conn, "schema_migrations"):
                raise Refused("TARGET_SCHEMA_UNSUPPORTED" if side == "target"
                              else "SOURCE_SCHEMA_UNSUPPORTED",
                              f"{label} has no schema_migrations table, so its version is "
                              "unknowable and nothing may be decided about it")
            versions = {int(row[0]) for row in conn.execute("SELECT version FROM schema_migrations")}
            required = {2, 3, 4, 5, 6}
            if not required <= versions:
                raise Refused("TARGET_SCHEMA_VERSION_MISMATCH" if side == "target"
                              else "SOURCE_SCHEMA_VERSION_MISMATCH",
                              f"{label} records schema_migrations {sorted(versions)}; this batch "
                              f"needs {sorted(required)} (5 = action_plans.version, 6 = solutions "
                              "revisions). The tool will not ALTER a store it is auditing: run "
                              "the owning migration first.")
        if role == "unified" and side == "target":
            from backend.core import unified_store
            for table, column in unified_store._ADDED_COLUMNS:
                if not table_exists(conn, table):
                    continue
                if column not in columns_of(conn, table):
                    raise Refused("TARGET_SCHEMA_VERSION_MISMATCH",
                                  f"target:unified.{table} lacks column {column}, added by the "
                                  "binding contract. Opening it read-write would ALTER it and "
                                  "hide the mismatch, so the migration refuses first.")

    def check_schema(self, side: str):
        """Per data type, against the table that side actually reads or writes."""
        conns = self.source_conns if side == "source" else self.target_readers
        done: set[tuple] = set()
        for spec in self.types:
            if side == "source":
                conn = conns[spec["source"]["role"]]
                table = spec["source"]["table"]
                required = spec.get("required_source", spec["required"])
            else:
                conn = conns[spec["role"]]
                table = spec["table"]
                required = spec.get("required_target", spec["required"])
            marker = (id(conn), table, tuple(required))
            if marker in done:
                continue
            done.add(marker)
            if not table_exists(conn, table):
                if side == "source":
                    self._note("warnings", "SOURCE_TABLE_ABSENT",
                               f"{spec['key']}: source table {table} does not exist in "
                               f"{db_path_of(conn)}; the type contributes zero rows",
                               type=spec["key"])
                else:
                    raise Refused("TARGET_SCHEMA_MISSING_TABLE",
                                  f"target table {table} needed by {spec['key']} does not exist; "
                                  "pass --init-targets to create it through the owning module's "
                                  "DDL")
                continue
            have = set(columns_of(conn, table))
            missing = [column for column in required if column not in have]
            if missing:
                raise Refused("TARGET_SCHEMA_MISSING_COLUMNS" if side == "target"
                              else "SOURCE_SCHEMA_MISSING_COLUMNS",
                              f"{side}:{table} lacks required column(s) {missing} declared by "
                              f"{spec['key']}")
            if side == "target" and spec["mode"] == "immutable":
                needed = APPEND_ONLY_TRIGGERS.get(spec["key"], [])
                absent = [name for name in needed if name not in triggers_of(conn)]
                if absent:
                    raise Refused("TARGET_APPEND_ONLY_INVARIANT_MISSING",
                                  f"target:{spec['role']}.{table} has no {absent} trigger(s). "
                                  "Without them an 'immutable' write could silently rewrite a "
                                  "cited revision, so the batch refuses instead of trusting its "
                                  "own SQL")

    # -- preflight ------------------------------------------------------------
    def build_plan(self):
        args = self.args
        self.source_conns = {role: open_read_only(getattr(args, "source_" + role))
                             for role in ROLE_ORDER}
        self.target_readers = {role: open_read_only(getattr(args, "target_" + role))
                               for role in ROLE_ORDER}
        try:
            for role in ROLE_ORDER:
                self.check_role_level(self.source_conns[role], role, side="source")
            for role in ROLE_ORDER:
                self.check_role_level(self.target_readers[role], role, side="target")
            self.check_schema("source")
            self.check_schema("target")
            self._read_source_rows()
            self._check_target_empty()
            self._check_namespaces()
            self._check_digests()
            self._check_references()
            self._check_completion_closure()
            self._check_supersession()
            self._recheck_digests_after_rewrites()
        finally:
            for conn in self.target_readers.values():
                conn.close()
            for conn in self.source_conns.values():
                conn.close()

    def _check_target_empty(self):
        """Runs after the batch's own row set is known, so a retry can be recognised.

        ``TARGET_NOT_EMPTY`` protects a production store from being used as a default
        destination. A retry of THIS batch after an interruption is a different thing: the
        rows already there are the rows this batch would have written. ``--resume`` accepts
        only that case — every existing row must be one this batch intends, byte-for-byte —
        and refuses the moment the target holds anything the batch does not account for.
        """
        intended: dict[tuple[str, str], set] = {}
        for spec in self.types:
            wanted = intended.setdefault((spec["role"], spec["table"]), set())
            wanted.update(self._pk_of(spec, row) for row in self.plan[spec["key"]]["source_rows"])
        occupied: dict[str, int] = {}
        foreign: dict[str, int] = {}
        for (role, table), pks in intended.items():
            conn = self.target_readers[role]
            if not table_exists(conn, table):
                continue
            keys = SPEC_LOOKUP[(role, table)]["primary_key"]
            order = ", ".join(f'"{column}"' for column in keys)
            existing = {tuple(str(row[column]) for column in keys)
                        for row in conn.execute(f"SELECT {order} FROM {table}")}
            name = f"{role}.{table}"
            if existing:
                occupied[name] = len(existing)
            if existing - pks:
                foreign[name] = len(existing - pks)
            self.plan_rows_existing[name] = len(existing & pks)
        self.occupied_target_rows = occupied
        self.foreign_target_rows = foreign
        if not occupied:
            return
        if self.args.resume:
            if foreign:
                raise Refused("RESUME_FOREIGN_ROWS",
                              f"--resume was refused because the target holds rows this batch "
                              f"does not account for: {foreign}. A retry may only continue what it "
                              "started; merging into a store somebody else wrote needs "
                              "--allow-existing and a reviewed plan",
                              foreign=foreign)
            return
        if self.args.allow_existing:
            self._note("warnings", "TARGET_OVERLAY_AUTHORISED",
                       f"the target already holds rows{(' outside this batch ' + str(foreign)) if foreign else ''};"
                       " writing on top of them was authorised explicitly",
                       occupied=occupied, foreign=foreign)
            return
        raise Refused("TARGET_NOT_EMPTY",
                      f"target store(s) already hold rows {occupied}. A live production database "
                      "is never a default migration target: inspect it, back it up, then re-run "
                      "with --allow-existing if the merge is really authorised, or with --resume "
                      "if this is the retry of an interrupted run of this same batch",
                      occupied=occupied, foreign=foreign)

    def _read_source_rows(self):
        for spec in self.types:
            source = self.source_conns[spec["source"]["role"]]
            target = self.target_readers[spec["role"]]
            table = spec["source"]["table"]
            source_cols = set(columns_of(source, table)) if table_exists(source, table) else set()
            target_cols = set(columns_of(target, spec["table"])) \
                if table_exists(target, spec["table"]) else set()
            if spec.get("projection"):
                # a projection reads the SOURCE columns it is derived from and writes the
                # TARGET envelope columns; the two column sets are not the same table
                read = [column for column in spec["projection_columns"] if column in source_cols]
                columns = [column for column in spec["columns"] if column in target_cols]
                rows = [self._project_row(spec, row) for row in read_table(source, table, read)]
            else:
                columns = [column for column in spec["columns"]
                           if column in source_cols and column in target_cols]
                rows = read_table(source, table, columns)
            self.plan[spec["key"]] = {"spec": spec, "columns": columns, "source_rows": rows,
                                      "target_pks": [], "dropped": [], "rewrites": [],
                                      "digests": {}, "migrated": 0, "identical": 0}

    def _project_row(self, spec, row: dict) -> dict:
        from backend.core import origins
        origin = origins.check(self.args.data_origin)
        if spec["projection"] == "work_registry":
            return {"project_id": spec["namespace"] + str(row["project_id"]), "source": "work",
                    "display_name": row.get("display_name") or str(row["project_id"]),
                    "root_path": row.get("root_path"), "data_origin": origin,
                    "origin_provenance": origins.PROVENANCE_ENFORCED,
                    "registered_at": row.get("registered_at") or _now()}
        return {"project_id": spec["namespace"] + str(row["project_id"]), "source": "design",
                "display_name": row.get("display_name") or str(row["project_id"]),
                "root_path": str(self.args.source_root), "data_origin": origin,
                "origin_provenance": origins.PROVENANCE_ENFORCED,
                "registered_at": row.get("created_at") or _now()}

    def _pk_of(self, spec, row):
        return tuple(str(row[column]) for column in spec["primary_key"])

    def _check_namespaces(self):
        seen: dict[tuple[str, tuple], dict] = {}
        for key, entry in self.plan.items():
            spec = entry["spec"]
            for row in entry["source_rows"]:
                identity = (spec["role"] + "." + spec["table"], self._pk_of(spec, row))
                digest = row_digest(row)
                previous = seen.get(identity)
                if previous is None:
                    seen[identity] = {"type": key, "digest": digest}
                    continue
                if previous["digest"] == digest:
                    self._note("warnings", "IDENTICAL_ROW_TWO_TYPES",
                               f"{previous['type']} and {key} both write the same row bytes to "
                               f"{identity[0]} pk={list(identity[1])}; written once",
                               pk=list(identity[1]))
                    continue
                raise Refused("ID_NAMESPACE_CONFLICT",
                              f"{previous['type']} and {key} both write {identity[0]} "
                              f"pk={list(identity[1])} with different content "
                              f"({previous['digest'][:12]}… vs {digest[:12]}…). Cross-domain ids "
                              "are namespaced precisely so this cannot be resolved by merging: "
                              "either a prefix is missing or a source already squats a reserved id")
            entry["target_pks"] = [self._pk_of(spec, row) for row in entry["source_rows"]]
        self.identity_map = seen

    def _check_digests(self):
        for key, entry in self.plan.items():
            spec = entry["spec"]
            for row in entry["source_rows"]:
                entry["digests"][self._pk_of(spec, row)] = self._digest_pair(key, spec, row)

    def _digest_pair(self, key: str, spec, row: dict) -> dict:
        digests = semantic_digests(key, row)
        if digests and digests["recomputed"] != digests["stored"]:
            raise Refused("SOURCE_DIGEST_MISMATCH",
                          f"{key} row {list(self._pk_of(spec, row))} publishes {digests['stored']} "
                          f"but recomputes to {digests['recomputed']}. A row that no longer hashes "
                          "to what it claims is not migrated and not rewritten: it is evidence of "
                          "drift or of a forged store",
                          pk=list(self._pk_of(spec, row)))
        return {"row": row_digest(row), "semantic": digests}

    def _recheck_digests_after_rewrites(self):
        """Namespace assignment changes a value, so the digest map is rebuilt from the rows
        that will actually be written."""
        for key, entry in self.plan.items():
            if not entry["rewrites"]:
                continue
            spec = entry["spec"]
            entry["digests"] = {self._pk_of(spec, row): self._digest_pair(key, spec, row)
                                for row in entry["source_rows"]}

    def _known_keys(self):
        known = set()
        for key, entry in self.plan.items():
            for pk in entry["target_pks"]:
                known.add((key, pk))
        for conn in self.target_readers.values():
            for spec in self.types:
                if not table_exists(conn, spec["table"]):
                    continue
                order = ", ".join(f'"{column}"' for column in spec["primary_key"])
                try:
                    rows = conn.execute(f"SELECT {order} FROM {spec['table']}").fetchall()
                except sqlite3.OperationalError:
                    continue
                for row in rows:
                    known.add((spec["key"], tuple(str(row[column]) for column in
                                                  spec["primary_key"])))
        return known

    def _project_owners(self, value: str, known) -> list[str]:
        owners = []
        if ("unified.projects", (value,)) in known:
            owners.append("(bare)")
        if ("unified.projects.registry_from_work", ("work:" + value,)) in known:
            owners.append("work:")
        if ("unified.projects.registry_from_design", ("design:" + value,)) in known:
            owners.append("design:")
        return owners

    def _resolve_reference(self, spec, row, ref):
        """(target_type, pk) to look up, or None when the reference is absent by design."""
        column, target_type = ref
        if isinstance(column, list):
            return target_type, tuple(str(row[name]) for name in column)
        if column.endswith(".supersedes"):
            try:
                payload = json.loads(row.get("payload") or "{}")
            except (TypeError, ValueError):
                return None
            pointer = payload.get("supersedes") if isinstance(payload, dict) else None
            if not isinstance(pointer, dict):
                return None
            return target_type, (str(pointer.get("solutionId")), str(pointer.get("revision")))
        value = row.get(column.split(".")[-1])
        if value is None or value == "":
            return None
        if spec["key"] == "unified.tasks" and column == "project_id":
            return "PROJECT", str(value)
        return target_type, (str(value),)

    def _check_references(self):
        known = self._known_keys()
        changed = True
        while changed:
            changed = False
            for key, entry in list(self.plan.items()):
                spec = entry["spec"]
                if not spec["references"] or not entry["source_rows"]:
                    continue
                keep, drop = [], []
                for row in entry["source_rows"]:
                    missing = []
                    for ref in spec["references"]:
                        resolved = self._resolve_reference(spec, row, ref)
                        if resolved is None:
                            continue
                        kind, value = resolved
                        if kind == "PROJECT":
                            owners = self._project_owners(value, known)
                            if not owners:
                                missing.append((ref[0], value, []))
                            elif "(bare)" in owners:
                                continue
                            elif len(owners) == 1:
                                self._assign_project(entry, row, value, owners[0])
                            elif len(owners) > 1:
                                choice = self._choose_namespace(value, owners)
                                if choice is None:
                                    raise Refused(
                                        "ID_NAMESPACE_AMBIGUOUS",
                                        f"a unified row cites project {value!r} while "
                                        f"{sorted(owners)} all exist in the registry. A same-name "
                                        "cross-domain id is never resolved by guessing: pass "
                                        "--project-namespace=work|design together with "
                                        "--on-dangling=assign to state which one owns it")
                                self._assign_project(entry, row, value, choice)
                            continue
                        if (kind, value) not in known:
                            missing.append((ref[0], list(value), kind))
                    if missing:
                        drop.append({"row": {column: row[column] for column in spec["primary_key"]},
                                     "missing": missing})
                    else:
                        keep.append(row)
                if not drop:
                    continue
                if self.args.on_dangling == "refuse":
                    first = drop[0]
                    raise Refused("DANGLING_REFERENCE",
                                  f"{key} row {list(first['row'].values())} points at "
                                  f"{first['missing']}, which neither this batch nor the target "
                                  "contains. Dangling rows are not migrated silently: repair the "
                                  "source, or pass --on-dangling=drop to record their removal "
                                  f"({len(drop)} row(s) affected in this type)")
                if self.args.on_dangling == "assign":
                    raise Refused("DANGLING_REFERENCE",
                                  f"{key}: {len(drop)} row(s) still dangle after namespace "
                                  "assignment (e.g. "
                                  f"{list(drop[0]['row'].values())}); assignment found no single "
                                  "owning domain, so nothing is guessed")
                entry["source_rows"] = keep
                entry["target_pks"] = [self._pk_of(spec, row) for row in keep]
                entry["dropped"].extend(drop)
                self._note("findings", "DANGLING_REFERENCE_DROPPED",
                           f"{key}: {len(drop)} row(s) removed because their references resolve "
                           "nowhere", type=key,
                           dropped=[{"pk": list(item["row"].values()),
                                     "missing": [[column, value, kind]
                                                 for column, value, kind in item["missing"]]}
                                    for item in drop])
                known = self._known_keys()
                changed = True

    def _choose_namespace(self, value: str, owners: list[str]):
        wanted = self.args.project_namespace
        if wanted is None:
            return None
        prefix = wanted + ":"
        return prefix if prefix in owners else None

    def _assign_project(self, entry, row, value: str, namespace: str) -> None:
        row["project_id"] = namespace + value
        record = {"column": "project_id", "from": value, "to": namespace + value,
                  "pk": list(self._pk_of(entry["spec"], row)),
                  "reason": f"the cited project exists only in the {namespace} namespace",
                  "authorised_by": ("--project-namespace" if self.args.project_namespace
                                    else "--on-dangling=assign")}
        entry["rewrites"].append(record)
        self.assignments.append(record)

    def _check_completion_closure(self):
        """A COMPLETED task must still name an attempt of its own (audit F04)."""
        attempts = {self._pk_of(self.plan["unified.attempts"]["spec"], row)[0]
                    for row in self.plan["unified.attempts"]["source_rows"]}
        tasks = {self._pk_of(self.plan["unified.tasks"]["spec"], row)[0]: row
                 for row in self.plan["unified.tasks"]["source_rows"]}
        for task_id, row in tasks.items():
            if row.get("lifecycle") != "COMPLETED":
                continue
            named = row.get("current_attempt_id")
            if not named:
                raise Refused("COMPLETION_CLOSURE_BROKEN",
                              f"unified.tasks {task_id} says COMPLETED but names no attempt")
            own = [entry["attempt_id"] for entry in
                   self.plan["unified.attempts"]["source_rows"] if entry["task_id"] == task_id]
            if named not in own and named not in attempts:
                raise Refused("COMPLETION_CLOSURE_BROKEN",
                              f"unified.tasks {task_id} names current attempt {named}, which is "
                              "not one of its attempts; a completion claim that points at nothing "
                              "is the counterexample this batch must not carry over")

    def _check_supersession(self):
        claims: dict[str, list[str]] = {}
        entry = self.plan.get("design.knowledge_entry")
        for row in (entry or {}).get("source_rows", []):
            if row.get("supersedes"):
                claims.setdefault(str(row["supersedes"]), []).append(str(row["entry_id"]))
        conn = self.target_readers["design"]
        if table_exists(conn, "knowledge_entry"):
            for row in conn.execute("SELECT entry_id, supersedes FROM knowledge_entry"):
                if row["supersedes"]:
                    claims.setdefault(str(row["supersedes"]), []).append(str(row["entry_id"]))
        forked = {key: value for key, value in claims.items() if len(value) > 1}
        if forked:
            raise Refused("SUPERSESSION_CONFLICT",
                          f"knowledge entries {forked} would have more than one successor; the "
                          "storage trigger aborts this transaction anyway, so the batch refuses "
                          "before writing")

    # -- writing ------------------------------------------------------------
    def write(self):
        args = self.args
        conns = {role: open_write(getattr(args, "target_" + role)) for role in ROLE_ORDER}
        counters: dict[str, int] = {}
        attempted = {"count": 0}
        try:
            for role in ROLE_ORDER:
                conns[role].execute("BEGIN IMMEDIATE")
                conns[role].execute("PRAGMA defer_foreign_keys=ON")
            for spec in self.types:
                entry = self.plan[spec["key"]]
                if not entry["source_rows"]:
                    continue
                self._write_type(conns[spec["role"]], spec, entry, counters, attempted)
            if (self.fail_at and self.fail_at["kind"] == "commit" and not args.commit_in_order):
                self._raise_injected("before any commit", attempted["count"])
            for role in ROLE_ORDER:
                conns[role].commit()
                self.committed.append(role)
                if (args.commit_in_order and self.fail_at and self.fail_at["kind"] == "commit"
                        and self.fail_at["role"] == role):
                    self._raise_injected("after committing " + role, attempted["count"])
            self._rebuild_design_index()
            return list(self.committed)
        except sqlite3.Error as error:
            rolled_back = []
            for role in ROLE_ORDER:
                if role in self.committed:
                    continue
                try:
                    conns[role].rollback()
                    rolled_back.append(role)
                except sqlite3.Error:
                    pass
            self.report["sql_failure"] = {
                "error": f"{type(error).__name__}: {error}",
                "rolled_back_stores": rolled_back,
                "already_committed_stores": list(self.committed),
                "note": "SQLite refused a statement (a constraint the preflight did not name). "
                        "Nothing was forced through; the stores that never committed are back "
                        "at their pre-migration state"}
            raise Refused("SQL_WRITE_REFUSED",
                          f"the target store refused the write: {type(error).__name__}: {error}. "
                          f"Rolled back: {rolled_back}; already committed: "
                          f"{list(self.committed)}", exit_code=EXIT_SQL_REFUSED) from None
        except InjectedFailure as failure:
            if failure.kill:
                # A real interruption: die inside the transaction. No rollback call, no report,
                # no checkpoint. SQLite owns the uncommitted frames.
                sys.stderr.write(str(failure) + "\n")
                sys.stderr.flush()
                os._exit(failure.exit_code)
            rolled_back = []
            for role in ROLE_ORDER:
                if role in self.committed:
                    continue
                try:
                    conns[role].rollback()
                    rolled_back.append(role)
                except sqlite3.Error as exc:
                    self._note("refusals", "ROLLBACK_FAILED", f"{role}: {exc}")
            self.report["failure_injection"] = {
                "spec": self.fail_at["spec"] if self.fail_at else None,
                "rows_attempted_before_failure": attempted["count"],
                "rolled_back_stores": rolled_back,
                "already_committed_stores": list(self.committed),
                "injection": str(failure)}
            raise
        finally:
            for conn in conns.values():
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            for spec in self.types:
                self.plan[spec["key"]]["migrated"] = len(self.plan[spec["key"]]["source_rows"])

    def _raise_injected(self, where: str, count: int):
        self.injected_fired = True
        failure = InjectedFailure(f"INJECTED_FAILURE at {self.fail_at['spec']} ({where}) after "
                                  f"{count} row write attempt(s)")
        failure.kill = bool(self.fail_at["kill"])
        raise failure

    def _write_type(self, conn, spec, entry, counters, attempted):
        name = f"{spec['role']}.{spec['table']}"
        columns = entry["columns"]
        table = spec["table"]
        pk = spec["primary_key"]
        quoted = ", ".join(f'"{column}"' for column in columns)
        quoted_pk = ", ".join(f'"{column}"' for column in pk)
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f'"{column}"=excluded."{column}"' for column in columns
                            if column not in pk)
        if spec["mode"] == "upsert" and updates:
            statement = (f"INSERT INTO {table} ({quoted}) VALUES ({placeholders}) "
                         f"ON CONFLICT({quoted_pk}) DO UPDATE SET {updates}")
        else:
            statement = (f"INSERT INTO {table} ({quoted}) VALUES ({placeholders}) "
                         f"ON CONFLICT({quoted_pk}) DO NOTHING")
        existing = {}
        if table_exists(conn, table):
            rows = conn.execute(f"SELECT {quoted} FROM {table}").fetchall()
            for row in rows:
                existing[tuple(str(row[column]) for column in pk)] = \
                    {column: row[column] for column in columns}
        identical = 0
        for row in entry["source_rows"]:
            key = self._pk_of(spec, row)
            self._maybe_inject(spec, counters, attempted)
            self._guard_stale(spec, key, row, existing)
            cursor = conn.execute(statement, [row[column] for column in columns])
            if cursor.rowcount == 0 and key in existing:
                if row_digest(existing[key]) != row_digest(row):
                    raise Refused("IMMUTABLE_ROW_CONFLICT",
                                  f"{spec['key']} {list(key)} already exists in the target with "
                                  "different bytes. Revisions are immutable there: the migration "
                                  "refuses rather than rewriting a cited row")
                identical += 1
            attempted["count"] += 1
        entry["identical"] = identical
        # the injection must be reachable even when the named table is shorter than the
        # threshold: "fail once this table has been written" is what the spec says
        if (self.fail_at and self.fail_at["kind"] == "rows" and not self.injected_fired
                and self.fail_at["role"] == spec["role"]
                and self.fail_at["table"] == spec["table"]
                and counters.get(name, 0) >= self.fail_at["after"]):
            self._raise_injected(f"after {name}", attempted["count"])

    def _guard_stale(self, spec, key, row, existing):
        column = spec.get("staleness")
        if not column or key not in existing:
            return
        stored, incoming = existing[key].get(column), row.get(column)
        if stored is None or incoming is None:
            return
        if _is_newer(stored, incoming) and not self.args.force_overwrite_newer:
            raise Refused("STALE_WRITE_REFUSED",
                          f"{spec['key']} {list(key)} is at {column}={stored} in the target while "
                          f"the source carries {incoming}; a migration must not roll a live store "
                          "backwards. Pass --force-overwrite-newer only on an owner decision")

    def _maybe_inject(self, spec, counters, attempted):
        if not self.fail_at or self.fail_at["kind"] != "rows":
            return
        if self.fail_at["role"] != spec["role"] or self.fail_at["table"] != spec["table"]:
            return
        name = spec["role"] + "." + spec["table"]
        counters[name] = counters.get(name, 0) + 1
        if counters[name] > self.fail_at["after"]:
            self._raise_injected(name, attempted["count"])

    # -- index + readback ----------------------------------------------------
    def _design_service(self, root: Path, db: Path):
        from design_lab.service import ProjectService
        service = ProjectService(str(root))
        service.database = service.paths.database_path(str(db))
        return service

    def _rebuild_design_index(self):
        """Rebuild the derived index through the product's own writer.

        A failure here happens AFTER the canonical rows committed, so it is not a rollback
        case: it is reported, it fails the run, and the readback below shows the index as it
        actually stands. Silent success would be the dishonest option.
        """
        from design_lab.knowledge_library import KnowledgeLibrary
        try:
            service = self._design_service(self.args.target_root, self.args.target_design)
            receipt = KnowledgeLibrary(service).rebuild_index()
        except (sqlite3.Error, ValueError, ToolError) as error:
            self.index_rebuild_failed = f"{type(error).__name__}: {error}"
            return
        self.index_rebuild_failed = None
        self.index_receipt = {"indexed": receipt["indexed"], "rebuilt_at": receipt["rebuilt_at"],
                              "index": receipt["index"]}

    def index_state(self) -> dict:
        conn = open_read_only(self.args.target_design)
        try:
            rows = int(conn.execute("SELECT COUNT(DISTINCT entry_id) FROM knowledge_entry_revision"
                                    ).fetchone()[0])
            indexed = int(conn.execute("SELECT COUNT(DISTINCT entry_id) FROM knowledge_entry_fts"
                                        ).fetchone()[0])
        finally:
            conn.close()
        return {"revision_rows_covering_entries": rows, "indexed_entries": indexed}

    def drop_index_rows(self) -> dict:
        conn = open_write(self.args.target_design)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM knowledge_entry_fts")
            conn.commit()
        finally:
            conn.close()
        return self.index_state()

    def target_table_state(self) -> dict:
        out = {}
        for role in ROLE_ORDER:
            conn = open_read_only(getattr(self.args, "target_" + role))
            try:
                for spec in self.types:
                    if spec["role"] != role or not table_exists(conn, spec["table"]):
                        continue
                    name = f"{role}.{spec['table']}"
                    have = set(columns_of(conn, spec["table"]))
                    read = [column for column in spec["columns"] if column in have]
                    rows = read_table(conn, spec["table"], read)
                    pairs = []
                    for row in rows:
                        pk = [str(row[column]) for column in spec["primary_key"]
                              if column in have]
                        pairs.append((canonical_json(pk), row_digest(row)))
                    entry = {"rows": len(rows), "fingerprint": table_fingerprint(pairs)}
                    if len(pairs) <= MAX_ROW_DIGESTS_IN_REPORT:
                        entry["per_row"] = [{"pk": json.loads(pk), "digest": digest}
                                            for pk, digest in pairs]
                        entry["per_row_complete"] = True
                    else:
                        entry["per_row"] = []
                        entry["per_row_complete"] = False
                        entry["note"] = (f"{len(pairs)} rows exceed the {MAX_ROW_DIGESTS_IN_REPORT}"
                                         "-row digest cap; the table fingerprint still covers every "
                                         "row")
                    out.setdefault(name, entry)
                    out[name] = entry
            finally:
                conn.close()
        return out

    def source_search_sets(self, terms: list[str]) -> dict:
        conn = open_read_only(self.args.source_design)
        try:
            return {term: search_set(conn, term) for term in terms}
        finally:
            conn.close()

    def target_search_sets(self, terms: list[str]) -> dict:
        conn = open_read_only(self.args.target_design)
        try:
            return {term: search_set(conn, term) for term in terms}
        finally:
            conn.close()

    def product_search(self, terms: list[str]) -> dict:
        """The product's own reader, on the TARGET store only (never the source)."""
        from design_lab.knowledge_library import KnowledgeLibrary
        library = KnowledgeLibrary(self._design_service(self.args.target_root,
                                                        self.args.target_design))
        out = {}
        for term in terms:
            answer = library.search(query=term, limit=200)
            out[term] = {"strategy": answer["strategy"], "total": answer["total"],
                         "hits": sorted(row["knowledge_entry_id"] for row in answer["entries"]),
                         "index": answer["index"], "explanation": answer["explanation"]}
        return out

    def readback(self) -> dict:
        """Brand-new connections AND brand-new store objects, addressed by exact id."""
        args = self.args
        out: dict = {"unified": {}, "work": {}, "design": {}, "problems": []}
        from backend.core.unified_store import UnifiedStore, result_digest
        from domains.work.workflow_core.canonical_store import CanonicalStore

        unified = UnifiedStore.open_readonly(args.target_unified)
        try:
            projects = []
            for spec in self.types:
                if spec["role"] == "unified" and spec["table"] == "projects":
                    projects += [row["project_id"] for row in self.plan[spec["key"]]["source_rows"]]
            out["unified"]["projects"] = []
            for project_id in projects:
                stored = unified.get_project(project_id)
                out["unified"]["projects"].append({
                    "project_id": project_id, "read_back": stored is not None,
                    "digest": row_digest(stored) if stored else None,
                    "source": stored["source"] if stored else None,
                    "data_origin": stored["data_origin"] if stored else None})
                if stored is None:
                    out["problems"].append("UNIFIED_PROJECT_NOT_READ " + str(project_id))
            out["unified"]["tasks"] = []
            for row in self.plan["unified.tasks"]["source_rows"]:
                task_id = row["task_id"]
                stored = unified.get_task(task_id)
                if stored is None:
                    out["problems"].append("UNIFIED_TASK_NOT_READ " + task_id)
                    out["unified"]["tasks"].append({"task_id": task_id, "read_back": False})
                    continue
                support = unified.completion_support(task_id)
                out["unified"]["tasks"].append({
                    "task_id": task_id, "read_back": True, "revision": stored["revision"],
                    "revision_preserved": stored["revision"] == row["revision"],
                    "project_id_preserved": stored["project_id"] == row["project_id"],
                    "lifecycle": stored["lifecycle"], "attempt_count": len(stored["attempts"]),
                    "result_count": len(stored["results"]),
                    "completion_support": support["supported"],
                    "completion_problems": support["problems"]})
                if stored["revision"] != row["revision"]:
                    out["problems"].append("UNIFIED_TASK_REVISION_MOVED " + task_id)
            out["unified"]["attempts"] = []
            for row in self.plan["unified.attempts"]["source_rows"]:
                stored = unified.get_attempt(row["attempt_id"])
                out["unified"]["attempts"].append({
                    "attempt_id": row["attempt_id"], "read_back": stored is not None,
                    "revision": stored["revision"] if stored else None,
                    "revision_preserved": bool(stored) and stored["revision"] == row["revision"],
                    "idempotency_key": stored["idempotency_key"] if stored else None,
                    "idempotency_key_preserved": bool(stored) and stored["idempotency_key"]
                    == row["idempotency_key"]})
                if not stored or stored["revision"] != row["revision"]:
                    out["problems"].append("UNIFIED_ATTEMPT_BAD " + row["attempt_id"])
            out["unified"]["results"] = []
            for row in self.plan["unified.results"]["source_rows"]:
                stored = unified.get_result(row["result_id"])
                if stored is None:
                    out["problems"].append("UNIFIED_RESULT_NOT_READ " + row["result_id"])
                    out["unified"]["results"].append({"result_id": row["result_id"],
                                                      "read_back": False})
                    continue
                recomputed = result_digest(stored["raw"], stored.get("digest_vocabulary"))
                ok = recomputed == stored["content_sha256"] == row["content_sha256"]
                out["unified"]["results"].append({
                    "result_id": row["result_id"], "read_back": True,
                    "content_sha256": stored["content_sha256"], "recomputed": recomputed,
                    "digest_ok": ok, "verifications": len(stored["verifications"]),
                    "raw_equal": stored["raw"] == json.loads(row["raw"])})
                if not ok:
                    out["problems"].append("UNIFIED_RESULT_DIGEST_BAD " + row["result_id"])
            out["unified"]["verifications"] = []
            for row in self.plan["unified.verifications"]["source_rows"]:
                stored = unified.get_verification(row["verification_id"])
                out["unified"]["verifications"].append({
                    "verification_id": row["verification_id"], "read_back": stored is not None,
                    "axis": stored["axis"] if stored else None,
                    "outcome": stored["outcome"] if stored else None,
                    "result_id_preserved": bool(stored) and stored["result_id"] == row["result_id"]})
                if stored is None:
                    out["problems"].append("UNIFIED_VERIFICATION_NOT_READ "
                                           + row["verification_id"])
            integrity = unified.integrity_report()
            out["unified"]["integrity_report"] = {
                "counts": integrity["counts"], "problems": integrity["problems"][:50],
                "problem_count": len(integrity["problems"])}
        finally:
            unified.close()

        work = CanonicalStore(args.target_work, readonly=True)
        try:
            out["work"]["action_plans"] = []
            for row in self.plan["work.action_plans"]["source_rows"]:
                stored = work.read_action_plan(row["plan_id"])
                if stored is None:
                    out["problems"].append("WORK_PLAN_NOT_READ " + row["plan_id"])
                    out["work"]["action_plans"].append({"plan_id": row["plan_id"],
                                                        "read_back": False})
                    continue
                ok = (int(stored["version"]) == int(row["version"])
                      and stored["payloadDigest"] == sha256_text(row["payload"]))
                out["work"]["action_plans"].append({
                    "plan_id": row["plan_id"], "read_back": True, "version": stored["version"],
                    "version_preserved": int(stored["version"]) == int(row["version"]),
                    "status": stored["status"], "payload_digest": stored["payloadDigest"],
                    "digest_ok": ok})
                if not ok:
                    out["problems"].append("WORK_PLAN_NOT_PRESERVED " + row["plan_id"])
            out["work"]["solutions"] = []
            for row in self.plan["work.solutions"]["source_rows"]:
                stored = work.read_solution(row["solution_id"], int(row["revision"]))
                if stored is None:
                    out["problems"].append("WORK_SOLUTION_NOT_READ "
                                           + f"{row['solution_id']}@{row['revision']}")
                    continue
                ok = (stored["payloadDigest"] == sha256_text(row["payload"])
                      and bool(stored["recommended"]) == bool(row["recommended"]))
                out["work"]["solutions"].append({
                    "solution_id": row["solution_id"], "revision": stored["revision"],
                    "read_back": True, "recommended": stored["recommended"],
                    "payload_digest": stored["payloadDigest"], "digest_ok": ok})
                if not ok:
                    out["problems"].append("WORK_SOLUTION_NOT_PRESERVED "
                                           + f"{row['solution_id']}@{row['revision']}")
            out["work"]["collector_health"] = []
            stored_health = {row["name"]: row for row in work.list_collector_health()}
            for row in self.plan["work.collector_health"]["source_rows"]:
                stored = stored_health.get(row["name"])
                if stored is None:
                    out["problems"].append("WORK_HEALTH_NOT_READ " + str(row["name"]))
                    continue
                out["work"]["collector_health"].append({
                    "name": row["name"], "read_back": True,
                    "total_runs": stored["total_runs"],
                    "consecutive_failures": stored["consecutive_failures"],
                    "values_match": (stored["total_runs"] == row["total_runs"]
                                     and stored["consecutive_failures"]
                                     == row["consecutive_failures"])})
                if not out["work"]["collector_health"][-1]["values_match"]:
                    out["problems"].append("WORK_HEALTH_NOT_PRESERVED " + str(row["name"]))
            out["work"]["integrity_check"] = work.integrity_check()
            out["work"]["newest_changes"] = work.newest_changes()
        finally:
            work.close()

        service = self._design_service(self.args.target_root, args.target_design)
        from design_lab.assistance_plan import AssistancePlans
        from design_lab.knowledge_library import KnowledgeLibrary
        from design_lab.target_profile import TargetProfiles
        plans = AssistancePlans(service)
        library = KnowledgeLibrary(service)
        profiles = TargetProfiles(service)

        out["design"]["assistance_plans"] = []
        revision_rows = self.plan["design.assistance_plan_revision"]["source_rows"]
        for row in self.plan["design.assistance_plan"]["source_rows"]:
            try:
                detail = plans.detail(row["project_id"], row["plan_id"])
            except Exception as exc:  # a refusal IS a readback result; report it, never hide it
                out["problems"].append(f"DESIGN_PLAN_READBACK_FAILED {row['plan_id']}: {exc}")
                continue
            own = [item for item in revision_rows if item["plan_id"] == row["plan_id"]]
            listed = {int(item["revision"]): item["content_sha256"] for item in detail["revisions"]}
            preserved = all(int(item["revision"]) in listed
                            and listed[int(item["revision"])] == item["content_sha256"]
                            for item in own)
            top = max(int(item["revision"]) for item in own) if own else None
            per_revision = []
            for item in sorted(own, key=lambda entry: int(entry["revision"])):
                try:
                    single = plans.revision(row["project_id"], row["plan_id"], int(item["revision"]))
                    per_revision.append({"revision": single["revision"],
                                         "digest_ok": single["content_sha256"]
                                         == item["content_sha256"],
                                         "is_latest": single["is_latest"],
                                         "is_chosen": single["is_chosen"],
                                         "provided": single["provided"]})
                except Exception as exc:
                    per_revision.append({"revision": int(item["revision"]), "error": str(exc)})
                    out["problems"].append(f"DESIGN_REVISION_READBACK_FAILED {row['plan_id']}: {exc}")
            latest_ok = detail["latest_revision"] == top
            out["design"]["assistance_plans"].append({
                "plan_id": row["plan_id"], "read_back": True,
                "latest_revision": detail["latest_revision"], "latest_revision_expected": top,
                "latest_revision_ok": latest_ok, "choice": detail["choice"],
                "reference_status": detail["reference_status"],
                "analysis_summary": detail["analysis_summary"],
                "all_revisions_preserved": bool(preserved), "per_revision": per_revision,
                "states": detail["states"]})
            if not preserved or not latest_ok:
                out["problems"].append("DESIGN_PLAN_REVISIONS_MISSING " + row["plan_id"])

        out["design"]["knowledge_entries"] = []
        knowledge_revisions = self.plan["design.knowledge_entry_revision"]["source_rows"]
        for row in self.plan["design.knowledge_entry"]["source_rows"]:
            try:
                detail = library.detail(row["entry_id"])
            except Exception as exc:
                out["problems"].append(f"DESIGN_KNOWLEDGE_READBACK_FAILED {row['entry_id']}: {exc}")
                continue
            own = [item for item in knowledge_revisions if item["entry_id"] == row["entry_id"]]
            listed = {int(item["revision"]): item["content_sha256"] for item in detail["revisions"]}
            preserved = all(int(item["revision"]) in listed
                            and listed[int(item["revision"])] == item["content_sha256"]
                            for item in own)
            out["design"]["knowledge_entries"].append({
                "entry_id": row["entry_id"], "read_back": True,
                "latest_revision": detail["latest_revision"],
                "recommended_revision": detail["recommended_revision"],
                "recommendation_basis": detail["recommendation_basis"],
                "status": detail["status"], "superseded_by": detail["superseded_by"],
                "judgements": len(detail["judgements"]), "unreadable_count": detail["unreadable_count"],
                "all_revisions_preserved": bool(preserved), "index": detail["index"]})
            if not preserved:
                out["problems"].append("DESIGN_KNOWLEDGE_REVISIONS_MISSING " + row["entry_id"])

        out["design"]["target_profiles"] = []
        for row in self.plan["design.target_profile_draft"]["source_rows"]:
            try:
                detail = profiles.detail(row["profile_id"])
            except Exception as exc:
                out["problems"].append(f"DESIGN_PROFILE_READBACK_FAILED {row['profile_id']}: {exc}")
                continue
            ok = (detail["content_sha256"] == row["content_sha256"]
                  and int(detail.get("revision", 0)) == int(row["revision"]))
            out["design"]["target_profiles"].append({
                "profile_id": row["profile_id"], "read_back": True,
                "revision": detail.get("revision"), "content_sha256": detail["content_sha256"],
                "digest_ok": ok, "support_state": detail["support_state"],
                "executable": detail["executable"]})
            if not ok:
                out["problems"].append("DESIGN_PROFILE_NOT_PRESERVED " + row["profile_id"])
        with closing(open_read_only(self.args.target_design)) as conn:
            out["design"]["integrity_check"] = "PRAGMA integrity_check: " + str(
                conn.execute("PRAGMA integrity_check").fetchone()[0])
        return out


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--describe", action="store_true",
                        help="print the declarative migration contract as JSON and exit")
    parser.add_argument("--source-root", help="directory holding the three source databases")
    parser.add_argument("--source-work", help="source WORK canonical store")
    parser.add_argument("--source-design", help="source DESIGN state database")
    parser.add_argument("--source-unified", help="source unified envelope store")
    parser.add_argument("--target-root", help="destination workspace root (must exist)")
    parser.add_argument("--target-work", help="destination WORK canonical store")
    parser.add_argument("--target-design", help="destination DESIGN state database")
    parser.add_argument("--target-unified", help="destination unified envelope store")
    parser.add_argument("--allow-root", action="append", default=[],
                        help="a root this run may write (repeatable)")
    parser.add_argument("--init-targets", action="store_true",
                        help="create any missing target store through its owning module's DDL")
    parser.add_argument("--allow-existing", action="store_true",
                        help="permit a target that already holds rows")
    parser.add_argument("--resume", action="store_true",
                        help="retry of an interrupted run: accept a target that already holds "
                             "exactly the rows this batch would write, refuse anything else")
    parser.add_argument("--on-dangling", choices=("refuse", "drop", "assign"), default="refuse")
    parser.add_argument("--project-namespace", choices=("work", "design"), default=None,
                        help="explicit owner for a task project id present in both namespaces")
    parser.add_argument("--data-origin", choices=("live", "demo", "test"), default="test",
                        help="origin recorded for registry rows minted by this run")
    parser.add_argument("--force-overwrite-newer", action="store_true",
                        help="authorise writing over a target row newer than the source")
    parser.add_argument("--fail-at", metavar="SPEC",
                        help="<role>:<table>:<n>[:kill] or commit:<role>[:kill]")
    parser.add_argument("--commit-in-order", action="store_true",
                        help="commit the stores one by one so a mid-sequence failure is real")
    parser.add_argument("--dry-run", action="store_true", help="preflight only, write nothing")
    parser.add_argument("--search-term", action="append", default=[],
                        help="term whose hit sets must match between source and target")
    parser.add_argument("--verify-index", action="store_true",
                        help="after migration, drop the derived FTS index and rebuild it again")
    parser.add_argument("--json-out", type=Path, help="where to write the machine report")
    return parser


REQUIRED_ARGS = ("source_root", "source_work", "source_design", "source_unified",
                 "target_root", "target_work", "target_design", "target_unified")


def main(argv=None) -> int:
    # The contract and the report carry Chinese quotations from the owner decisions; a
    # cp936 console would otherwise mangle stdout on the caller's side.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.describe:
        print(json.dumps(describe_contract(), ensure_ascii=False, indent=2))
        return EXIT_OK
    missing = [name for name in REQUIRED_ARGS if not getattr(args, name)]
    if missing:
        parser.error("missing required argument(s): "
                     + ", ".join("--" + name.replace("_", "-") for name in missing)
                     + " (or run --describe to read the contract)")
    migration = Migration(args)
    try:
        migration.resolve_paths()
        if args.init_targets:
            migration.report["target_init"] = {
                "work": init_target_work(args.target_work),
                "design": init_target_design(args.target_design, args.target_root),
                "unified": init_target_unified(args.target_unified)}
        for role in ROLE_ORDER:
            target = getattr(args, "target_" + role)
            if not target.is_file():
                raise Refused("TARGET_DB_MISSING",
                              f"--target-{role} {target} does not exist; pass --init-targets to "
                              "create it through the owning module's DDL, or point at a store that "
                              "is already there")
        migration.build_plan()
        migration.report["source_root"] = str(args.source_root)
        migration.report["target_root"] = str(args.target_root)
        migration.report["preflight"] = {
            "passed": True, "checks": PREFLIGHT_CHECKS, "refusals": [],
            "warnings": migration.warnings, "findings": migration.findings,
            "on_dangling": args.on_dangling, "data_origin": args.data_origin,
            "resume": bool(args.resume),
            "foreign_target_rows": migration.foreign_target_rows,
            "occupied_target_rows": migration.occupied_target_rows,
            "target_rows_already_matching_this_batch": migration.plan_rows_existing,
            "types": {key: {"source_rows": len(entry["source_rows"]),
                            "dropped_dangling": len(entry["dropped"]),
                            "namespace_assigned": len(entry["rewrites"]),
                            "columns": entry["columns"]}
                      for key, entry in migration.plan.items()}}
        migration.report["targets_before"] = migration.target_table_state()
        if args.search_term:
            migration.report["search_sets_source"] = migration.source_search_sets(args.search_term)
        migration.report["index_before_migration"] = migration.index_state()
        if args.dry_run:
            migration.report["outcome"] = "PREFLIGHT_ONLY_ZERO_WRITES"
            return EXIT_OK
        migration.write()
        migration.report["commit"] = {
            "mode": "ordered" if args.commit_in_order else "all-or-nothing",
            "outcome": "COMMITTED", "committed_stores": migration.committed,
            "rows_written": sum(len(entry["source_rows"]) for entry in migration.plan.values()),
            "rows_identical_skipped": sum(entry["identical"] for entry in migration.plan.values()),
            "namespace_assigned": migration.assignments}
        migration.report["index_rebuild"] = migration.index_receipt
        migration.report["index_rebuild_error"] = migration.index_rebuild_failed
        migration.report["targets_after"] = migration.target_table_state()
        migration.report["index_after_migration"] = migration.index_state()
        if args.search_term:
            migration.report["search_sets_target"] = migration.target_search_sets(args.search_term)
            migration.report["product_search_target"] = migration.product_search(args.search_term)
        if args.verify_index and args.search_term:
            before = migration.report["search_sets_target"]
            dropped = migration.drop_index_rows()
            hits_dropped = migration.target_search_sets(args.search_term)
            migration._rebuild_design_index()
            hits_rebuilt = migration.target_search_sets(args.search_term)
            product_rebuilt = migration.product_search(args.search_term)
            source = migration.report["search_sets_source"]
            migration.report["index_cycle"] = {
                "terms": args.search_term,
                "hits_after_migration": {term: value["hits"] for term, value in before.items()},
                "index_state_after_delete": dropped,
                "hits_with_empty_index": {term: value["hits"] for term, value in hits_dropped.items()},
                "index_state_after_rebuild": migration.index_state(),
                "hits_after_rebuild": {term: value["hits"] for term, value in hits_rebuilt.items()},
                "product_search_after_rebuild": {term: {"strategy": value["strategy"],
                                                        "total": value["total"],
                                                        "hits": value["hits"]}
                                                 for term, value in product_rebuilt.items()},
                "equal_to_source": all(hits_rebuilt[term]["hits"] == source[term]["hits"]
                                       for term in args.search_term),
                "equal_to_post_migration": all(hits_rebuilt[term]["hits"] == before[term]["hits"]
                                               for term in args.search_term)}
        migration.report["restart_readback"] = migration.readback()
        if migration.index_rebuild_failed or migration.report["restart_readback"]["problems"]:
            migration.report["outcome"] = "READBACK_DISAGREED"
            return EXIT_READBACK_FAILED
        migration.report["outcome"] = "MIGRATED_AND_READ_BACK"
        return EXIT_OK
    except Refused as refusal:
        migration.report["preflight"] = {"passed": False, "warnings": migration.warnings,
                                         "findings": migration.findings}
        migration.report["refusal"] = {"code": refusal.code, "detail": refusal.detail,
                                       **refusal.extra}
        migration.report["outcome"] = ("REFUSED_ZERO_WRITES" if not migration.committed
                                       else "REFUSED_AFTER_A_COMMIT_ALREADY_LANDED")
        return refusal.exit_code
    except InjectedFailure as failure:
        if failure.kill:
            return EXIT_INJECTED_ROLLBACK
        migration.report["outcome"] = ("ROLLED_BACK_TO_PRE_MIGRATION_STATE"
                                       if not migration.committed else
                                       "COMMITTED_STORES_KEPT_REST_ROLLED_BACK")
        migration.report.setdefault("failure_injection", {
            "spec": migration.fail_at["spec"] if migration.fail_at else None,
            "injection": str(failure)})
        try:
            migration.report["targets_after"] = migration.target_table_state()
        except Refused as exc:
            migration.report["targets_after"] = {"error": str(exc)}
        return EXIT_PARTIAL_COMMIT if migration.committed else EXIT_INJECTED_ROLLBACK
    except ToolError as error:
        migration.report["refusal"] = {"code": "TOOL_ERROR", "detail": str(error)}
        migration.report["outcome"] = "TOOL_ERROR"
        return EXIT_PREFLIGHT_REFUSED
    finally:
        contract = describe_contract()
        migration.report["contract"] = contract
        migration.report["limitations"] = contract["limitations"]
        migration.report["real_data_migration"] = {
            "status": "NOT_RUN",
            "reason": "blocked scope: only synthetic fixtures under a caller-declared rehearsal "
                      "root were migrated; no real user database was read or written"}
        if migration.warnings:
            migration.report.setdefault("preflight", {})["warnings"] = migration.warnings
        write_report(args.json_out, migration.report)


def write_report(path, report: dict) -> None:
    if path is None:
        return
    path = Path(path)
    if protected_reason(path.resolve() if path.is_absolute() else Path.cwd() / path):
        sys.stderr.write("REPORT_PATH_PROTECTED " + str(path) + "\n")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
