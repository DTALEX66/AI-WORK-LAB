"""Radar core (WL-370 / ch 32): multi-source candidate discovery.

ch 32 names thirteen external sources and a Candidate record of seventeen
fields.  By the ch 35 external-asset rule WORK-LAB never vendors the
external repos / models / runtimes it discovers — a Candidate IS a
metadata-only record (url, license, install recipe, capability), not a
downloaded artifact.  Sources are injectable adapters; without a live
source a collector is honestly UNAVAILABLE rather than fabricating a hit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


class RadarSource:
    """The thirteen ch 32 sources."""

    GITHUB = "github"
    HUGGINGFACE = "huggingface"
    MODELSOURCE = "modelscope"
    WATCHA = "watcha"
    PRODUCT_HUNT = "product_hunt"
    OPENROUTER = "openrouter"
    ARTIFICIAL_ANALYSIS = "artificial_analysis"
    REPLICATE = "replicate"
    MCP_REGISTRY = "mcp_registry"
    GLAMA = "glama"
    SMITHERY = "smithery"
    HF_PAPERS = "hf_papers"
    ARXIV = "arxiv"

    ALL = (GITHUB, HUGGINGFACE, MODELSOURCE, WATCHA, PRODUCT_HUNT,
           OPENROUTER, ARTIFICIAL_ANALYSIS, REPLICATE, MCP_REGISTRY,
           GLAMA, SMITHERY, HF_PAPERS, ARXIV)
    _MEMBERS = frozenset(ALL)

    @classmethod
    def is_valid(cls, s: str) -> bool:
        return s in cls._MEMBERS


@dataclass
class Candidate:
    """One discovered external asset.  Metadata ONLY (ch 35) — no body.

    The seventeen ch 32 fields; capability/surface booleans describe what
    the candidate offers, and they feed the scoring weights in ch 33.
    """

    canonical_url: str
    repo: str = ""
    owner: str = ""
    commit: str = ""
    license: str = "unknown"
    stars: int = 0
    growth: float = 0.0                 # recent delta, normalised 0..1
    downloads: int = 0
    api: bool = False
    cli: bool = False
    mcp: bool = False
    windows: bool = False
    local: bool = False
    cost: str = "unknown"              # free / tiered / paid
    risk: str = "unknown"             # low / medium / high
    project_fit: str = ""            # why this fits WORK-LAB
    usage: str = ""                  # observed usage signal

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceAdapter:
    """Interface every ch 32 source is fronted behind."""

    name: str = "source"

    def available(self) -> bool:
        raise NotImplementedError

    def collect(self, query: str) -> List[Candidate]:
        raise NotImplementedError


class RadarCore:
    """Aggregates the injectable source adapters into a deduplicated,
    query-scoped candidate set.  Deterministic ordering so a given set of
    adapters + query always yields the same list."""

    SCHEMA = "work-lab/radar-core/v1"

    def __init__(self, adapters: Optional[List[SourceAdapter]] = None) -> None:
        self._adapters = list(adapters or [])

    def add_source(self, adapter: SourceAdapter) -> None:
        self._adapters.append(adapter)

    def discover(self, query: str,
                  min_stars: int = 0) -> List[Candidate]:
        seen: Dict[str, Candidate] = {}
        for adapter in self._adapters:
            if not adapter.available():
                continue             # honest skip; do not fabricate
            for cand in adapter.collect(query):
                key = cand.canonical_url or f"{cand.owner}/{cand.repo}"
                if not key:
                    continue
                if cand.stars < min_stars:
                    continue
                # first-writer wins; later duplicates keep the earlier one
                if key not in seen:
                    seen[key] = cand
        rows = list(seen.values())
        rows.sort(key=lambda c: (c.stars, c.growth, c.canonical_url),
                  reverse=True)
        return rows

    def sources(self) -> List[str]:
        return [a.name for a in self._adapters]

    def available_sources(self) -> List[str]:
        return [a.name for a in self._adapters if a.available()]

    def receipt_sha256(self, candidates: List[Candidate]) -> str:
        import hashlib
        payload = json.dumps(
            [c.to_dict() for c in candidates], sort_keys=True,
            ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class StaticSourceAdapter(SourceAdapter):
    """A source backed by an in-memory candidate table.  The default in
    tests and in the no-live-backend case: it is 'available' when it holds
    at least one record, so an empty adapter is honestly unavailable.
    """

    def __init__(self, name: str, candidates: Optional[List[Candidate]] = None) -> None:
        self.name = name
        self._candidates = list(candidates or [])

    def available(self) -> bool:
        return bool(self._candidates)

    def collect(self, query: str) -> List[Candidate]:
        q = (query or "").lower()
        hits: List[Candidate] = []
        for c in self._candidates:
            hay = " ".join(
                str(getattr(c, f, "")) for f in
                ("repo", "owner", "project_fit", "usage", "canonical_url")
            ).lower()
            if not q or q in hay:
                hits.append(c)
        return hits
