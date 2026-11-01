"""Observation layer for the radar candidate chain (incremental sidecar).

Addresses the 2026-09-15 cloud-audit static findings on radar_core.py
WITHOUT rewriting the 17-field Candidate or the existing discover()
contract.  This module is a pure additive sidecar: radar_core.py is
untouched, so test_radar.py's hard contracts (17 fields, dedupe/sort,
honest-empty-source, deterministic receipt) stay byte-stable.

  F1 discover() first-writer-wins discards later price/license/version
     updates -> ObservationLedger.diff() keeps every original observation
     and emits new / superseded / conflict / removed relations instead of
     silently dropping the later one.
  F2 Candidate defaults (stars=0, surfaces=False) conflate UNKNOWN with
     CONFIRMED-FALSE -> Observation stores None (unknown) vs False
     (confirmed absent) distinctly; to_dict preserves the distinction.
  F3 StaticSourceAdapter.available() confuses "legitimately empty result"
     with "source unavailable" -> SourceReport carries an explicit
     fetch_status (FETCH_OK / FETCH_EMPTY / UNAVAILABLE / ERROR), plus
     coverage / items_count / last_success_at, decoupled from "has items".
  F4 Candidate has no structured price-validity / entitlement /
     standard-version / cross-project fit -> Observation carries a
     structured PriceRecord + entitlement + standard_version + fits
     sidecar (unknown stays unknown, never filled with 0).
  F5 min_stars + stars-desc sort does not generalise to models/papers/
     standards/plans -> rank_signal(entity_kind) routes the ranking signal.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

# Repo convention: service files are loaded by file path in the gate runner
# (services/ is not a resolvable package on sys.path there), so the only
# sibling import must be annotation-only. Candidate/SourceAdapter appear in
# type hints only; `from __future__ import annotations` keeps them unevaluated.
if TYPE_CHECKING:
    from services.radar.radar_core import Candidate, SourceAdapter


class FetchStatus:
    """F3: a source's own answer state, independent of whether it has items."""
    FETCH_OK = "fetch_ok"          # answered, >=1 item
    FETCH_EMPTY = "fetch_empty"   # answered, zero items (legit, not unavailable)
    UNAVAILABLE = "unavailable"   # not reachable / not installed
    ERROR = "error"               # fetch raised


class EntityKind:
    """F5: what the discovered thing actually is.  The ranking signal is
    chosen by kind, so stars are not forced onto models/papers/plans."""
    REPO = "repo"
    MODEL = "model"
    PAPER = "paper"
    STANDARD = "standard"
    PLAN = "plan"
    SERVICE = "service"


# Fields whose change between two same-version observations is a genuine
# conflict (not a supersede).  Tracked explicitly so the diff is stable.
_TRACKED = ("price.amount", "price.currency", "license",
            "standard_version", "commit")


@dataclass
class PriceRecord:
    """F4: a timed, provider-qualified price observation.  amount=None means
    UNKNOWN and must not be rendered as 0 (audit WL-R07/W07)."""
    amount: Optional[float] = None
    currency: str = ""
    provider: str = ""
    billing: str = ""          # per_million_tokens / per_request / free / entitlement
    region: str = ""
    valid_from: str = ""
    valid_to: str = ""
    as_of: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_unknown(self) -> bool:
        return self.amount is None


@dataclass
class Observation:
    """One source's observation of one entity.  A sidecar, NOT the 17-field
    Candidate.  unknown (None) and confirmed-absent (False) are kept apart."""
    entity: str                                    # canonical_url (stable id)
    entity_kind: str = EntityKind.REPO
    source: str = ""
    observed_at: str = ""
    observation_version: int = 1
    # F2: distinct unknown vs confirmed
    stars: Optional[int] = None                    # None=unknown, 0=confirmed zero
    downloads: Optional[int] = None
    surfaces: Dict[str, Optional[bool]] = field(default_factory=dict)
    # F4: structured sidecar
    price: Optional[PriceRecord] = None
    entitlement: str = ""
    standard_version: str = ""
    fits: Dict[str, str] = field(default_factory=dict)   # project -> why
    license: str = ""
    commit: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)                            # asdict keeps nested None
        return d

    def get(self, dotted: str) -> Any:
        """Read a dotted path (e.g. 'price.amount') for tracked-field diff."""
        node: Any = self
        for part in dotted.split("."):
            if isinstance(node, dict):
                node = node.get(part)
            else:
                node = getattr(node, part, None)
        return node


@dataclass
class SourceReport:
    """F3: fetch/coverage state, decoupled from 'has items'."""
    name: str
    fetch_status: str = FetchStatus.UNAVAILABLE
    coverage: str = ""
    items_count: int = 0
    last_success_at: str = ""

    def available(self) -> bool:
        # A source that answered "zero updates" (FETCH_EMPTY) IS available.
        # Only UNAVAILABLE/ERROR are not.
        return self.fetch_status in (FetchStatus.FETCH_OK,
                                     FetchStatus.FETCH_EMPTY)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ObservationLedger:
    """Retains every observation per entity and diffs two passes into
    relations (replacing discover()'s lossy first-writer-wins for the
    candidate chain, while discover() itself is left untouched)."""

    def __init__(self) -> None:
        self._by_entity: Dict[str, List[Observation]] = {}

    def add(self, obs: Observation) -> None:
        self._by_entity.setdefault(obs.entity, []).append(obs)

    def entities(self) -> List[str]:
        return sorted(self._by_entity)

    def versions(self, entity: str) -> List[Observation]:
        return list(self._by_entity.get(entity, []))

    def latest(self, entity: str) -> Optional[Observation]:
        rows = self._by_entity.get(entity)
        if not rows:
            return None
        return max(rows, key=lambda o: (o.observation_version, o.observed_at))

    def diff(self, before: "ObservationLedger",
             after: "ObservationLedger") -> Dict[str, Dict[str, Any]]:
        """Return {entity: {relation, changed_fields, note}}.

        relation is one of: new, removed, unchanged, superseded, conflict.
        'superseded' = a strictly later observation changed a tracked field
        (the earlier original is KEPT, not deleted).  'conflict' = two
        observations at the SAME version disagree on a tracked field.
        """
        out: Dict[str, Dict[str, Any]] = {}
        for ent in sorted(set(before.entities()) | set(after.entities())):
            b, a = before.latest(ent), after.latest(ent)
            if b is None and a is not None:
                out[ent] = {"relation": "new"}
            elif a is None and b is not None:
                out[ent] = {"relation": "removed"}
            else:
                changed = _changed_fields(b, a)
                same_version = (b.observation_version == a.observation_version)
                a_newer = ((a.observation_version, a.observed_at) >
                           (b.observation_version, b.observed_at))
                if not changed:
                    out[ent] = {"relation": "unchanged"}
                elif same_version:
                    out[ent] = {"relation": "conflict",
                                "changed_fields": changed}
                elif a_newer:
                    out[ent] = {"relation": "superseded",
                                "changed_fields": changed}
                else:
                    out[ent] = {"relation": "unchanged"}
        return out


def _changed_fields(b: Observation, a: Observation) -> List[str]:
    changed = []
    for dotted in _TRACKED:
        if b.get(dotted) != a.get(dotted):
            changed.append(dotted)
    return changed


def rank_signal(kind: str) -> Tuple[str, ...]:
    """F5: choose the ranking signal by entity kind.  REPO keeps
    stars/growth (backward-compatible with discover()); other kinds do NOT
    force stars."""
    return {
        EntityKind.REPO: ("stars", "growth"),
        EntityKind.MODEL: ("downloads", "quality"),
        EntityKind.PAPER: ("recency", "citation"),
        EntityKind.STANDARD: ("maintenance", "adoption"),
        EntityKind.PLAN: ("cost_value", "entitlement"),
        EntityKind.SERVICE: ("capability_fit", "reliability"),
    }.get(kind, ("stars", "growth"))


def rank(rows: List[Observation], kind: str) -> List[Observation]:
    """Deterministic, kind-routed sort.  None-safe: unknown (None) sorts as
    the minimum so it never masquerades as a strong confirmed value."""
    sigs = rank_signal(kind)

    def key(o: Observation):
        vals = []
        for s in sigs:
            if s in ("stars", "downloads"):
                vals.append((o.stars if s == "stars" else o.downloads) or 0)
            else:
                vals.append(0)         # qualitative axes: no numeric proxy yet
        vals.append(o.entity)
        return vals

    return sorted(rows, key=key, reverse=True)


def build_ledger(adapters: List[SourceAdapter],
                 query: str) -> ObservationLedger:
    """Wrap injectable adapters into an ObservationLedger.  Adapters that
    implement an optional observe(query)->List[Observation] hook supply
    multi-version/unknown-aware observations directly; otherwise their
    collect() candidates are wrapped as version-1 observations.  Unknown
    numerics stay None (not 0)."""
    led = ObservationLedger()
    for a in adapters:
        observe = getattr(a, "observe", None)
        if callable(observe):
            for obs in observe(query):
                led.add(obs)
            continue
        for cand in a.collect(query):
            led.add(_candidate_to_observation(cand, a.name))
    return led


def _candidate_to_observation(c: Candidate, source: str) -> Observation:
    """Map the 17-field Candidate to an Observation without collapsing
    unknown into 0/false (F2).  stars/downloads of 0 are treated as
    unknown (the Candidate does not distinguish), so they become None."""
    return Observation(
        entity=c.canonical_url or f"{c.owner}/{c.repo}",
        source=source,
        stars=(c.stars if c.stars else None),
        downloads=(c.downloads if c.downloads else None),
        surfaces={"api": bool(c.api), "cli": bool(c.cli),
                  "mcp": bool(c.mcp)},
        license=c.license,
        commit=c.commit,
    )
