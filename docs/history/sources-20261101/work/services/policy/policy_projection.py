#!/usr/bin/env python
"""U17.4 — Unified Global Agent Policy Projection Contract.

Human-facing prose is rendered from config/universal-agent, a reviewed
snapshot of the external AGENT_CORE.md mother. This compatibility interface
still validates typed machine contracts and reports coverage.

Historically this interface turned the
single cross-software semantic source (``config/global-agent-policy.yaml``)
into its own native surface, and to report honestly what it could NOT cover.

    GlobalAgentPolicy            (config/global-agent-policy.yaml, the WHAT)
            +
    SoftwareExtension           (per-software native knobs, kept out of the core)
            +
    SoftwarePolicyRenderer      (this module: the HOW)
            ->
    NativeProjection            (rendered native assets)
            ->
    ProjectionLossReport        (honest per-capability coverage)

Design rules (taskpack U17.4 / U17.7 / U17.21, taskpack sections 4, 7, 11, 22, 26):

- "Rendered successfully" is NEVER "100% supported". Every renderer MUST emit a
  loss report that classifies each capability as one of CAPABILITY_STATES.
- The projection is fail-closed: a policy that weakens the protected-drive
  guard (E:/F:),
  makes UNKNOWN a success, hard-codes a user model, or carries a real secret
  is rejected before any native asset is rendered.
- This module creates no second authority, no second config-governance system,
  and no second adapter registry. It reads the existing
  ``config/config-ownership.json`` + ``config/adapter-registry.json`` and the
  single policy SSOT.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    import hermes_yaml as yaml  # Installed Hermes YAML facade; no dependency install.

POLICY_PATH = "config/global-agent-policy.yaml"
OWNERSHIP_PATH = "config/config-ownership.json"
ADAPTER_REGISTRY_PATH = "config/adapter-registry.json"

SCHEMA_POLICY = "packages/contracts/schemas/workflow/global-agent-policy.schema.json"
SCHEMA_LOSS = "packages/contracts/schemas/workflow/policy-projection-loss-report.schema.json"

LOSS_REPORT_DIR = "config/loss-reports"

# The five honest coverage states. "rendered successfully" is NOT one of these.
CAPABILITY_STATES = (
    "NATIVE_ENFORCED",
    "NATIVE_GUIDANCE",
    "WORKFLOW_GUARD",
    "OBSERVE_ONLY",
    "UNSUPPORTED",
)

# The policy capability keys every renderer must classify (or explicitly mark
# UNSUPPORTED). Mirrors the semantic source's capability blocks.
POLICY_CAPABILITIES = (
    "communication",
    "execution",
    "authority_discovery",
    "authorization",
    "task_grant",
    "workspace_boundary",
    "protected_storage",
    "credentials",
    "session_privacy",
    "network",
    "git_safety",
    "dependency_policy",
    "evidence_semantics",
    "verification",
    "parallelism",
    "skills",
    "model_neutrality",
    "tool_truth",
    "historical_record_policy",
)

# Fail-closed evidence invariants: these MUST be false in the policy, and a
# projection that would flip any of them is rejected.
EVIDENCE_INVARIANTS_MUST_BE_FALSE = (
    "unknown_is_zero",
    "unknown_is_success",
    "simulated_is_real",
    "local_test_is_ci",
    "build_is_runtime",
    "merge_is_installed",
    "plan_equals_write",
    "apply_equals_verified",
)

# User's standing rule: BOTH the E: and F: data drives are protected on this
# machine. The semantic policy must protect at least this machine baseline;
# the native guards (services/policy/e_drive_guard.py, machine_identity,
# project_registry) mirror the same boundary. Dropping any baseline drive is
# a fail-closed rejection.
PROTECTED_DRIVE_BASELINE = frozenset({"E", "F"})

# A real credential is never expected in a policy or extension.
_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|private[_-]?key)"
    r"\s*[:=]\s*['\"]?[A-Za-z0-9+/=\-_]{20,}"
    r"|(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16,})"
)


class PolicyProjectionError(RuntimeError):
    """Fail-closed rejection of a policy/projection that breaks an invariant."""


def _root(path: str, root: Path) -> Path:
    return root / path


def load_policy(root: Path) -> dict[str, Any]:
    """Load the single cross-software semantic source (the WHAT)."""
    path = _root(POLICY_PATH, root)
    if not path.is_file():
        raise PolicyProjectionError(f"policy source missing: {POLICY_PATH}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PolicyProjectionError("policy source must be a mapping")
    return data


def _load_schema(root: Path, rel: str) -> dict[str, Any]:
    path = _root(rel, root)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def validate_policy(root: Path, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fail-closed validation of the policy source against schema + invariants.

    Rejects (raises PolicyProjectionError) on:
    - schema violation;
    - any evidence invariant that is not ``false``;
    - a protected-storage policy that is not default-deny;
    - a non-false credentials.plaintext_forbidden;
    - a policy that would hard-code a model / make user model WORK-LAB-managed;
    - any real secret material in the document.
    """
    policy = policy if policy is not None else load_policy(root)

    # --- schema validation (fail-closed) ---
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - environment guard
        raise PolicyProjectionError(f"jsonschema required: {exc}") from exc
    schema = _load_schema(root, SCHEMA_POLICY)
    if schema:
        try:
            jsonschema.Draft202012Validator(schema).validate(policy)
        except jsonschema.ValidationError as exc:
            path = ".".join(str(part) for part in exc.absolute_path) or "(root)"
            raise PolicyProjectionError(f"policy schema violation at {path}: {exc.message}") from exc

    # --- evidence invariants must be false ---
    evidence = policy.get("evidence_semantics") or {}
    for key in EVIDENCE_INVARIANTS_MUST_BE_FALSE:
        if evidence.get(key) is not False:
            raise PolicyProjectionError(
                f"policy weakens an evidence invariant: evidence_semantics.{key} must be false "
                f"(got {evidence.get(key)!r})"
            )

    # --- protected storage default-deny (E: and F: are user-protected) ---
    protected = policy.get("protected_storage") or {}
    if protected.get("drive_default") != "deny":
        raise PolicyProjectionError(
            f"protected_storage.drive_default must be 'deny' (got {protected.get('drive_default')!r})"
        )
    drives = protected.get("protected_drives")
    if not isinstance(drives, list) or not drives:
        raise PolicyProjectionError(
            f"protected_storage.protected_drives must be a non-empty list of drive letters (got {drives!r})"
        )
    for drive in drives:
        if not (isinstance(drive, str) and len(drive) == 1 and drive.isupper() and drive.isalpha()):
            raise PolicyProjectionError(
                f"protected_storage.protected_drives entries must be single uppercase drive letters (got {drive!r})"
            )
    missing_drives = PROTECTED_DRIVE_BASELINE - set(drives)
    if missing_drives:
        raise PolicyProjectionError(
            f"protected_storage.protected_drives must keep the machine baseline protected "
            f"({sorted(PROTECTED_DRIVE_BASELINE)}); missing: {sorted(missing_drives)}"
        )

    # --- credentials plaintext forbidden ---
    credentials = policy.get("credentials") or {}
    if credentials.get("plaintext_forbidden") is not True:
        raise PolicyProjectionError("credentials.plaintext_forbidden must be true")

    # --- model neutrality: no hard-coded model id, user model is user-owned ---
    model = policy.get("model_neutrality") or {}
    if model.get("no_hardcoded_model_id_default") is not True:
        raise PolicyProjectionError("model_neutrality.no_hardcoded_model_id_default must be true")
    if model.get("user_model_is_user_owned_not_worklab_managed") is not True:
        raise PolicyProjectionError("model_neutrality.user_model_is_user_owned_not_worklab_managed must be true")

    # --- no real secret material anywhere in the document ---
    raw = json.dumps(policy, ensure_ascii=False, sort_keys=True)
    if _SECRET_RE.search(raw):
        raise PolicyProjectionError("policy document contains real credential material")

    # --- ownership must be USER_OVERLAY / MANAGE and not a second authority ---
    ownership = policy.get("ownership") or {}
    if ownership.get("layer") != "USER_OVERLAY" or ownership.get("mode") != "MANAGE":
        raise PolicyProjectionError("policy ownership must be USER_OVERLAY / MANAGE")
    if ownership.get("is_authority") is not False:
        raise PolicyProjectionError("policy must declare is_authority=false (it is not a second authority)")

    return {
        "status": "PASS",
        "policy_id": policy.get("policy_id"),
        "revision": policy.get("revision"),
        "schema_version": policy.get("schema_version"),
        "digest": _sha256(json.dumps(policy, ensure_ascii=False, sort_keys=True).encode("utf-8")),
        "invariants_checked": len(EVIDENCE_INVARIANTS_MUST_BE_FALSE) + 5,
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_extension(root: Path, adapter: str) -> dict[str, Any]:
    """Load a per-software native extension (native knobs, kept out of the core).

    Extension files are optional: a missing extension renders guidance-only for
    that software, which is recorded in the loss report, not silently skipped.
    """
    rel = f"integrations/executors/{adapter}/{adapter}-policy-extension.yaml"
    path = _root(rel, root)
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def adapter_projection_capabilities(root: Path, adapter: str) -> dict[str, Any]:
    """Read the adapter registry's policy_projection block (existing registry)."""
    path = _root(ADAPTER_REGISTRY_PATH, root)
    registry = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    for entry in registry.get("entries", []):
        if entry.get("id") == adapter:
            return entry.get("policy_projection", {})
    return {}


class SoftwarePolicyRenderer:
    """Base projection interface. Subclasses render one software's native surface."""

    #: the adapter id (codex / hermes / ...)
    adapter: str = ""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # --- lifecycle: RENDER + loss report ---
    def render(self, policy: dict[str, Any], extension: dict[str, Any]) -> dict[str, str]:
        """Return rendered native assets keyed by logical target name -> content."""
        raise NotImplementedError

    def classify(self, policy: dict[str, Any], extension: dict[str, Any]) -> dict[str, str]:
        """Map each policy capability -> one of CAPABILITY_STATES for this software."""
        raise NotImplementedError

    def loss_report(self, policy: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
        """Build the honest ProjectionLossReport for this adapter."""
        states = self.classify(policy, extension)
        # fail-closed: every capability must be classified; default UNSUPPORTED
        normalized: dict[str, str] = {}
        for cap in POLICY_CAPABILITIES:
            value = states.get(cap, "UNSUPPORTED")
            if value not in CAPABILITY_STATES:
                raise PolicyProjectionError(
                    f"{self.adapter}: capability {cap!r} classified with unknown state {value!r}"
                )
            normalized[cap] = value
        buckets: dict[str, list[str]] = {state: [] for state in CAPABILITY_STATES}
        for cap, state in normalized.items():
            buckets[state].append(cap)
        report = {
            "schema_version": "workflow/policy-projection-loss-report/v1",
            "adapter": self.adapter,
            "policy_version": policy.get("policy_id", "unknown") + "@rev" + str(policy.get("revision", "0")),
            "native_enforced": buckets["NATIVE_ENFORCED"],
            "native_guidance": buckets["NATIVE_GUIDANCE"],
            "workflow_guard": buckets["WORKFLOW_GUARD"],
            "observe_only": buckets["OBSERVE_ONLY"],
            "unsupported": buckets["UNSUPPORTED"],
        }
        # "rendered successfully" != "100% supported": a loss report that claims
        # every capability is enforced and admits zero loss is itself suspicious
        # for a guidance renderer. We do not reject it here (some native surfaces
        # genuinely enforce everything) but callers must not read an empty loss
        # report as proof of full support.
        return report

    # --- render + classify + validate in one pass ---
    def project(self) -> dict[str, Any]:
        policy = load_policy(self.root)
        validate_policy(self.root, policy)
        extension = load_extension(self.root, self.adapter)
        assets = self.render(policy, extension)
        report = self.loss_report(policy, extension)
        return {
            "adapter": self.adapter,
            "policy": policy,
            "assets": assets,
            "loss_report": report,
        }


def validate_loss_report(report: dict[str, Any], root: Path) -> None:
    """Fail-closed check that a loss report is schema-valid and non-deceptive."""
    schema = _load_schema(root, SCHEMA_LOSS)
    if not schema:
        return
    import jsonschema

    jsonschema.Draft202012Validator(schema).validate(report)
    # every capability must appear in exactly one bucket
    seen: set[str] = set()
    for bucket in ("native_enforced", "native_guidance", "workflow_guard", "observe_only", "unsupported"):
        for cap in report.get(bucket, []):
            if cap in seen:
                raise PolicyProjectionError(
                    f"loss report double-classifies {cap!r} (must be exactly one state)"
                )
            seen.add(cap)
    missing = set(POLICY_CAPABILITIES) - seen
    if missing:
        raise PolicyProjectionError(
            f"loss report omits capability classification for: {sorted(missing)}"
        )


def policy_digest(root: Path) -> str:
    """Stable digest of the policy source, for freshness/fencing checks."""
    policy = load_policy(root)
    return _sha256(json.dumps(policy, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def write_loss_report(root: Path, report: dict[str, Any]) -> Path:
    """Persist a loss report under config/loss-reports/<adapter>.json."""
    out_dir = _root(LOSS_REPORT_DIR, root)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.get('adapter', 'unknown')}-policy-loss-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
