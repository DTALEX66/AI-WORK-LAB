"""NF-01 rule semantic: what may legally transfer vs. what stays forbidden.

Clarifies the broad root-rule phrasing ("inside the project Git root" and
"no prompt/response bodies") WITHOUT weakening the data boundary:

  * A *user-published business artifact* (audit / task document the user
    explicitly selected to ship, or an immutable task-package / receipt
    reference) may flow to an authorized target material space.
  * *Private session libraries, native conversation logs, telemetry bodies
    and credentials* are NEVER auto-mirrored.  Telemetry keeps only
    references + minimal metadata.
  * A project's *temporary* offline / model preference is scoped to that
    project (or a task) and never becomes a global forcing on another
    project.

Pure and deterministic: no filesystem, no network, no native private store
is read.  Every decision carries its reason so callers fail-closed on the
sensitive path while non-sensitive work keeps moving.  Unknown artifact
kinds are never silently allowed.
"""
from __future__ import annotations

import re
from typing import Any

# Business artifact classes that MAY transfer when the user authorized the batch.
ALLOWED_ARTIFACT_KINDS = frozenset({
    "user_published_audit",
    "user_published_task",
    "immutable_task_package_ref",
    "receipt_ref",
})

# Classes that are NEVER auto-mirrored, even when an `authorized` flag is set.
FORBIDDEN_ARTIFACT_KINDS = frozenset({
    "private_session",
    "conversation_log",
    "telemetry_body",
    "credential",
    "account_key",
    "browser_data",
})

DECISIONS = ("ALLOW", "PENDING_AUTHORIZATION", "ISOLATE", "REJECT")

# Secret-ish key names (checked anywhere in the nested payload, not just top level).
_SECRET_KEY_RE = re.compile(
    r"(api_?key|access_?token|auth_?token|secret|password|passwd|cvc|private_?key|credential|bearer)",
    re.IGNORECASE,
)
# Self-identifying provider families: the prefix alone proves the string carries a key, so this
# pattern is deliberately UNANCHORED and is applied with ``search``. Anchoring it to the whole value
# is the defect measured 2026-10-26 -- ``provider="github ghp_A1a1..."`` and
# ``note="rotated ghp_... on tuesday"`` both cleared the screen and were written to
# ``canonical.sqlite``, because a real key is rarely the only text in a free-text field.
#
# Every branch carries a ``(?<![A-Za-z0-9])`` opener because a substring search alone is too wide.
# Measured the same day: the collectors' own identifier ``task-ledger-<sha16>`` contains the run
# "sk-ledger-<32 hex>", so an unguarded ``sk-`` branch refused every telemetry write in the store
# (3 errors in ``tests/workflow-assistance/test_collectors.py``). A credential prefix has to START a
# run, not sit inside an English word; ``_`` is excluded from the lookbehind on purpose, so a key
# pasted after an underscore (``token_sk-...``) is still caught.
#
# ``Bearer``/``Basic`` additionally require a credential-shaped run after the scheme word. The
# whitespace alone was not enough once the branch became unanchored: ``note="Bearer tokens are
# rotated weekly"`` is documentation, while ``Authorization: Bearer eyJhbGci...`` is a live token.
_SELF_IDENTIFYING_SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:ghp_|gho_|ghs_|github_pat_)[A-Za-z0-9_]{4,}"
    r"|(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"
    r"|(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}"
    r"|(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{6,}"
    r"|(?<![A-Za-z0-9])AIza[0-9A-Za-z_-]{30,}"
    r"|(?<![A-Za-z0-9])Bearer\s+[A-Za-z0-9._~+/=-]{16,}"
    r"|(?<![A-Za-z0-9])Basic [A-Za-z0-9+/=]{16,}"
)
# The ambiguous high-entropy alternative (a bare 64+ character base64-looking run) stays
# WHOLE-STRING anchored with \A..\Z. Unanchoring it is the false-positive disaster the acceptance
# criteria name: content digests, commit SHAs, blob hashes and long file names all contain such a
# run somewhere inside ordinary text, and only a value that IS nothing but that run is suspicious.
_OPAQUE_SECRET_VALUE_RE = re.compile(r"\A[A-Za-z0-9+/]{64,}={0,2}\Z")
# Union kept under the historical name for callers that need a boolean only; ``search`` is the
# intended operator (``match`` on a standalone credential still succeeds, so pre-existing
# references keep working). Production screens go through :func:`_secret_shape`.
_SECRET_VALUE_RE = re.compile(
    f"(?:{_SELF_IDENTIFYING_SECRET_RE.pattern})|(?:{_OPAQUE_SECRET_VALUE_RE.pattern})"
)
# A value that is only hexadecimal is a digest (commit SHA, content hash, error fingerprint), not a key.
_DIGEST_RE = re.compile(r"^[0-9a-fA-F]{32,}$")

# Shape classes named in refusals. A refusal reports the field and ONE of these strings -- never the
# matched value, which would put the credential into the log, the exception text and the test artifact.
SHAPE_SELF_IDENTIFYING = "self-identifying-key-shape"
SHAPE_OPAQUE_HIGH_ENTROPY = "opaque-high-entropy-shape"
SHAPE_KEY_NAME = "field-name-suggests-credential"


def _secret_shape(value: str) -> str | None:
    """Shape class of a credential *value*, or ``None`` when the value is not key-shaped."""
    if _SELF_IDENTIFYING_SECRET_RE.search(value) is not None:
        return SHAPE_SELF_IDENTIFYING
    if _OPAQUE_SECRET_VALUE_RE.search(value) is not None:
        return SHAPE_OPAQUE_HIGH_ENTROPY
    return None


def _walk_keys(node: Any, path: str = "") -> list[tuple[str, Any]]:
    """Yield (dotted_path, value) for every leaf / nested mapping entry."""
    out: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            dotted = f"{path}.{key}" if path else str(key)
            if isinstance(value, (dict, list)):
                out.extend(_walk_keys(value, dotted))
            else:
                out.append((dotted, value))
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            dotted = f"{path}[{idx}]" if path else f"[{idx}]"
            if isinstance(value, (dict, list)):
                out.extend(_walk_keys(value, dotted))
            else:
                out.append((dotted, value))
    return out


def secret_value_paths(artifact: Any) -> list[str]:
    """Dotted paths whose VALUE is a credential shape, regardless of which key carries it.

    ``find_nested_secrets`` answers "may this artifact transfer at all" -- strict, because quarantine is
    cheap. A canonical store needs the complementary question, "am I about to write a credential into
    durable state", and there the same blob shape is a false positive on ordinary data: a SHA-256 error
    fingerprint, a commit SHA and a content digest are all 32+ characters of base64-shaped text. Measured
    2026-10-10 -- without the digest exemption the worker's own task loop was refused at
    ``checkpoint.error_fingerprint``. So a pure-hexadecimal value of 32+ characters is treated as what it
    is in this repository: a digest. A real key almost never is, and the provider prefixes (``sk``,
    ``AKIA``, ``ghp_``, ``Bearer``) stay fully enforced -- in fact every self-identifying family needs at
    least one non-hexadecimal character, so a value satisfying ``_DIGEST_RE`` can never have come from the
    unanchored family branch: widening that branch cannot erode the digest exemption.
    """
    hits: list[str] = []
    for path, value in _walk_keys(artifact):
        if not isinstance(value, str) or _secret_shape(value) is None:
            continue
        if _DIGEST_RE.match(value):
            continue
        hits.append(path)
    return hits


def secret_shape_classes(artifact: Any) -> dict[str, str]:
    """Map each secret-carrying dotted path to its shape class name.

    Companion to :func:`find_nested_secrets` for callers that have to write a refusal down: the class
    name is what belongs in a log or an exception message, because the matched value would put the
    credential into the very artifact the refusal is trying to keep clean.
    """
    classes: dict[str, str] = {}
    for path, value in _walk_keys(artifact):
        if _SECRET_KEY_RE.search(path):
            classes[path] = SHAPE_KEY_NAME
            continue
        if isinstance(value, str):
            shape = _secret_shape(value)
            if shape is not None:
                classes[path] = shape
    return classes


def find_nested_secrets(artifact: dict[str, Any]) -> list[str]:
    """Return the dotted paths that carry a secret key or value.

    Matches key names anywhere (top level, nested, list elements, and artifact
    path query params) plus provider-token *values* buried in free-text fields
    such as ``goal`` / ``next_step``.  Only the top key being removed is NOT
    sufficient — a secret hidden one level down is still caught.  Value shapes are
    searched, not matched whole, for the same reason as the store screen: a key
    pasted into a sentence is still a key, and quarantine here is fail-closed.
    """
    hits: list[str] = []
    for path, value in _walk_keys(artifact):
        if _SECRET_KEY_RE.search(path):
            hits.append(path)
            continue
        if isinstance(value, str) and _secret_shape(value) is not None:
            hits.append(path)
    return sorted(hits)


def classify_flow(artifact: dict[str, Any], *, authorized: bool) -> dict[str, Any]:
    """Decide whether one artifact may flow to an authorized material space.

    Fail-closed order: forbidden class -> REJECT; unknown class or missing
    authorization -> PENDING_AUTHORIZATION; authorized business artifact that
    still carries a nested secret -> ISOLATE (quarantined, secret not leaked);
    otherwise -> ALLOW.
    """
    kind = artifact.get("artifact_kind")
    result: dict[str, Any] = {
        "artifact_kind": kind,
        "authorized": authorized,
        "decision": None,
        "reasons": [],
    }
    if kind in FORBIDDEN_ARTIFACT_KINDS:
        result["decision"] = "REJECT"
        result["reasons"].append(
            f"{kind} is a forbidden auto-transfer class (private session library / "
            "telemetry body / credential); it never flows, even with an authorized flag"
        )
        return result
    if kind not in ALLOWED_ARTIFACT_KINDS:
        result["decision"] = "PENDING_AUTHORIZATION"
        result["reasons"].append(
            f"unknown artifact kind {kind!r}; not on the allowlist, so it is not "
            "auto-transferred"
        )
        return result
    if not authorized:
        result["decision"] = "PENDING_AUTHORIZATION"
        result["reasons"].append(
            "the user has not selected / authorized this batch for external transfer"
        )
        return result
    leaked = find_nested_secrets(artifact)
    if leaked:
        classes = secret_shape_classes(artifact)
        result["decision"] = "ISOLATE"
        # field + shape class only: the reason string is logged and copied into receipts, so the
        # matched value must never appear in it.
        result["reasons"].append(
            "authorized business artifact still carries nested secret(s) at "
            + ", ".join(f"{path} [{classes.get(path, SHAPE_OPAQUE_HIGH_ENTROPY)}]" for path in leaked)
        )
        result["leaked_keys"] = leaked
        return result
    result["decision"] = "ALLOW"
    result["reasons"].append("authorized business artifact, desensitized")
    return result


def is_project_scoped(pref: dict[str, Any]) -> bool:
    """A project-local temporary offline / model preference is scoped, not global."""
    return pref.get("scope") in ("project", "task") and not pref.get("global", False)


def effective_for_project(pref: dict[str, Any], target_project: str) -> dict[str, Any]:
    """The preference fields that actually apply to ``target_project``.

    A project/task-scoped preference applies ONLY to its own project; it is
    never carried to another project.  A deliberate global preference
    (``global=True``) is the one case that applies project-wide, and only that
    case is propagated — so a project A temporary offline setting cannot force
    project B's model behavior.
    """
    if is_project_scoped(pref) and pref.get("project_id") != target_project:
        return {}  # scoped to another project: zero fields reach the target
    if pref.get("global") or pref.get("project_id") == target_project:
        return dict(pref)
    return {}


def does_project_pref_leak(a_pref: dict[str, Any], target_project: str) -> bool:
    """True when a project A temporary preference would wrongly force project B.

    ``target_project`` is B.  A project/task-scoped A preference produces no
    fields for B (no leak).  It leaks only if it was deliberately marked
    global, which is a separate authorization — reported here so the caller
    can hold it, never auto-applied.
    """
    return bool(effective_for_project(a_pref, target_project)) and not is_project_scoped(a_pref)


def decide(artifact: dict[str, Any], *, authorized: bool) -> dict[str, Any]:
    """Stable public alias for :func:`classify_flow` (one call, one decision)."""
    return classify_flow(artifact, authorized=authorized)
