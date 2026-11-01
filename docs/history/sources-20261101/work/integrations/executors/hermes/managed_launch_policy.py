"""Launch constraints for WORK-LAB-managed Hermes invocations (review finding A-3).

Observed behaviour: ``hermes chat --ignore-user-config`` is **not** a "no model"
mode. It falls back to a built-in default and calls ``openrouter`` / ``z-ai/glm-5.2``
against the user's real account, which returned HTTP 402 on cost grounds
(``max_tokens`` 131072 far above the affordable budget). That route is not
declared in the user's ``config.yaml``.

Scope, stated precisely
-----------------------
This constrains **only** launches that WORK-LAB manages: its adapters, gates,
tests and any script it runs. It cannot and does not govern commands the user
types by hand, and it does not delete or disable the OpenRouter credentials,
which may serve other approved purposes. The claim is "WORK-LAB's own entry
points do not take this route", not "the user's manual commands are controlled".

The check is deliberately a hard failure rather than a warning: a managed run
that reaches an unapproved provider is a cost-boundary violation, and the
ruling classifies it as blocking for automated release.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Sequence

# flag -> why it is refused for managed runs
FORBIDDEN_MANAGED_FLAGS: Mapping[str, str] = {
    "--ignore-user-config": (
        "bypasses the user's configuration and reaches a built-in default route "
        "(openrouter/z-ai/glm-5.2) that WORK-LAB has not approved and that may bill the user"
    ),
}

FORBIDDEN_MANAGED_PREFIXES: Sequence[str] = tuple(FORBIDDEN_MANAGED_FLAGS)


class ManagedLaunchRefused(RuntimeError):
    """Raised when a WORK-LAB-managed launch would take an unapproved route."""


def forbidden_flags(argv: Iterable[str]) -> list[str]:
    """Return the managed-forbidden flags present in ``argv``."""

    found = []
    for token in argv:
        text = str(token)
        if text in FORBIDDEN_MANAGED_FLAGS:
            found.append(text)
            continue
        # tolerate --flag=value spellings
        for flag in FORBIDDEN_MANAGED_PREFIXES:
            if text.startswith(flag + "="):
                found.append(flag)
    return found


def assert_managed_argv(argv: Iterable[str], *, what: str = "managed hermes launch") -> None:
    """Fail closed when a managed launch uses an unapproved route."""

    hits = forbidden_flags(argv)
    if not hits:
        return
    detail = "; ".join(f"{flag}: {FORBIDDEN_MANAGED_FLAGS[flag]}" for flag in hits)
    raise ManagedLaunchRefused(
        f"MANAGED_LAUNCH_REFUSED {what} uses a flag WORK-LAB does not permit. {detail}. "
        "Use an explicitly approved configuration scope instead, and verify the route that "
        "actually took effect."
    )


def describe_policy() -> dict[str, object]:
    """Machine-readable policy summary for evidence and review."""

    return {
        "scope": (
            "WORK-LAB-managed launches only (adapters, gates, tests, project scripts). "
            "The user's own manual commands are outside this policy, and no credential is "
            "modified or removed by it."
        ),
        "forbidden": dict(FORBIDDEN_MANAGED_FLAGS),
        "enforcement": "hard failure (ManagedLaunchRefused); managed runs fail closed",
    }
