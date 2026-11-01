"""WLG-030: global validation-tier vocabulary and event contract.

The global layer defines exactly these tiers; each project maps its own
semantic gates to them. WORK-LAB never adds a command the project did not
declare, and never interprets full/exact-SHA on a project's behalf.

Events below are the canonical cross-project observation events.
"""

from __future__ import annotations

GLOBAL_TIERS = ("TARGETED", "STAGE", "NIGHTLY", "RC", "RELEASE")

# WORK-LAB consumes the following events from external project endpoints;
# it never fabricates or reinterprets project business facts.
OBSERVATION_EVENTS = (
    "project.profile.loaded",
    "gate.plan.observed",
    "ci.run.observed",
    "stage.qualification.recorded",
    "release.evidence.observed",
)


def validate_tiers(tiers) -> bool:
    """A project gate tier list must be a non-empty subset of GLOBAL_TIERS."""
    if not tiers:
        return False
    return all(t in GLOBAL_TIERS for t in tiers)
