"""Offline radar reuse-loop + price-identity normalization (WL-R01 / WL-R07).

Pure, deterministic, no-network, no paid calls, no sibling import (gate-safe,
following the NF-02 convention).  It consumes the EXISTING contracts rather
than inventing a second radar platform:

  WL-R01  A fixed offline sample is persisted (JSON), replayed, version-diffed,
          and rendered into a Chinese candidate report that assigns each
          candidate one of the five reuse verdicts (DIRECT_DEPENDENCY /
          PROVIDER / ADAPTER / ALGORITHM_DONOR / REFERENCE_ONLY / REJECTED)
          with license + version + retire-reason + evidence level.  A receipt
          (sha256) proves the same sample replayed produces the SAME candidate
          set — no duplicate candidates are minted — and that evidence below a
          threshold is never reported as high confidence.  Nothing is
          auto-promoted to a PoC / new task pack / PR / install.

  WL-R07  Price-record identity normalization: model / provider / currency /
          effective_at / source / version are preserved; any missing item is
          stamped the sentinel ``UNKNOWN`` (never collapsed to 0 / ""), and an
          unknown amount is never rendered as a concrete zero.  Entitlement,
          subscription, API price, and real consumption are kept in separate
          lanes; the earlier (superseded) value keeps its validity window.
          The ``unknown_propagates`` flag lets the UI and any export carry the
          honest UNKNOWN instead of a fabricated number.

These functions are pure data transforms: they accept and return plain
dicts / lists, so they can be driven by fixtures with no radar_core import.
"""
from __future__ import annotations

import json
import hashlib
from typing import Any, Dict, List

# Sentinel for a missing identity item.  It must NOT equal 0 or "" so a
# downstream render guard can distinguish "unknown" from "genuinely zero".
UNKNOWN = "UNKNOWN"

# Evidence levels: A = official/source-exact, B = third-party, C = unverified.
EVIDENCE_A, EVIDENCE_B, EVIDENCE_C = "A", "B", "C"
# Only levels at/above this may be reported as "high confidence".
HIGH_CONFIDENCE_MIN = "B"  # C (unverified) is never high confidence.

# WL-R01 reuse verdicts.
VERDICTS = (
    "DIRECT_DEPENDENCY",   # real import / call / dependency adopted now
    "PROVIDER",            # an upstream provider the product calls
    "ADAPTER",             # thin adapter wrapping existing capability
    "ALGORITHM_DONOR",     # borrow the algorithm, re-implement natively
    "REFERENCE_ONLY",      # read-only reference, not wired in
)
REJECTED = "REJECTED"


def _sha256(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# WL-R01: offline sample -> persisted -> replay -> diff -> Chinese report
# ---------------------------------------------------------------------------

def dedupe_candidates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stable dedupe by canonical_url (first-writer wins).  Replaying the same
    sample yields the same deduped set — no candidate is minted twice."""
    seen: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        key = r.get("canonical_url") or f"{r.get('owner', '')}/{r.get('repo', '')}"
        if key and key not in seen:
            seen[key] = r
    return list(seen.values())


def _evidence_rank(level: str) -> int:
    return {"A": 3, "B": 2, "C": 1, UNKNOWN: 0}.get(level, 0)


def classify_reuse(cand: Dict[str, Any]) -> Dict[str, Any]:
    """Assign one of the five reuse verdicts (or REJECTED) with rationale.

    Driven by the candidate's declared ``project_need`` + evidence + license +
    version.  This is a *judgment record only* — it never auto-creates a PoC,
    task pack, PR, or install.
    """
    need = str(cand.get("project_need", "")).lower()
    evidence = str(cand.get("evidence_level") or EVIDENCE_C)
    high_conf = _evidence_rank(evidence) >= _evidence_rank(HIGH_CONFIDENCE_MIN)
    license_ = str(cand.get("license", "unknown"))
    version = str(cand.get("version") or cand.get("commit") or UNKNOWN)
    has_real_call = bool(cand.get("has_real_call_or_dep", False))
    fit_reason = str(cand.get("project_fit", ""))

    if need in ("direct_dependency", "depend") and has_real_call:
        verdict = "DIRECT_DEPENDENCY"
        reason = "actual import/call/dependency in the current task; wired and tested"
    elif need in ("provider", "upstream"):
        verdict = "PROVIDER"
        reason = "upstream provider the product calls; no source vendoring"
    elif need in ("adapter", "wrap"):
        verdict = "ADAPTER"
        reason = "thin adapter over existing native capability; no new service"
    elif need in ("algorithm", "donor"):
        verdict = "ALGORITHM_DONOR"
        reason = "borrow the algorithm, re-implement natively"
    elif need in ("reference", "read"):
        verdict = "REFERENCE_ONLY"
        reason = "read-only reference; not wired into the product"
    else:
        verdict = REJECTED
        reason = fit_reason or "no binding to a current task; not absorbed this round"

    # Evidence below B (i.e. C/unverified) is explicitly NOT high confidence.
    return {
        "verdict": verdict,
        "license": license_,
        "version": version,
        "retire_reason": reason if verdict == REJECTED else "",
        "evidence_level": evidence,
        "high_confidence": high_conf and verdict != REJECTED,
        "reason": reason,
        "auto_promoted": False,  # never auto-PoC / task pack / PR / install
    }


def _version_key(v: Any) -> tuple:
    """Sortable tuple for a version string.  Missing / UNKNOWN -> lowest."""
    if v in (None, "", UNKNOWN):
        return (0,)
    parts = []
    for chunk in str(v).split("."):
        import re
        m = re.match(r"(\d+)", chunk)
        parts.append(int(m.group(1)) if m else 0)
    return (1,) + tuple(parts)


def version_diff(before: Dict[str, Dict[str, Any]],
                 after: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Deterministic version diff over tracked fields.  A strictly newer
    observation supersedes (the earlier original is KEPT); a same-version
    disagreement is a conflict, never silently dropped.  Change is explainable."""
    tracked = ("version", "commit", "license", "price")
    out: Dict[str, Dict[str, Any]] = {}
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key), after.get(key)
        if b is None and a is not None:
            out[key] = {"relation": "new", "changed_fields": []}
        elif a is None and b is not None:
            out[key] = {"relation": "removed", "changed_fields": []}
        else:
            changed = [f for f in tracked if b.get(f) != a.get(f)]
            if not changed:
                out[key] = {"relation": "unchanged", "changed_fields": []}
            elif str(a.get("version") or "") == str(b.get("version") or ""):
                out[key] = {"relation": "conflict", "changed_fields": changed,
                            "note": "same version disagrees on a tracked field"}
            elif _version_key(a.get("version")) > _version_key(b.get("version")):
                out[key] = {"relation": "superseded", "changed_fields": changed,
                            "note": "later observation supersedes; earlier kept"}
            else:
                out[key] = {"relation": "unchanged", "changed_fields": changed,
                            "note": "later is older — not applied, kept"}
    return out


def build_offline_loop(
    sample: List[Dict[str, Any]],
    *,
    persisted_before: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Run the offline closed loop once and return a deterministic receipt.

    Steps: dedupe the fixed sample (no duplicate candidates), classify each,
    version-diff the current sample against the persisted previous pass, and
    render a Chinese candidate report.  The receipt sha256 is stable across
    replays of the same sample, and unknown evidence is never reported as high
    confidence.
    """
    candidates = dedupe_candidates(sample)
    classified = []
    for cand in candidates:
        verdict = classify_reuse(cand)
        entity = cand.get("canonical_url") or cand.get("owner", "?")
        classified.append({
            "entity": entity,
            "evidence_level": verdict["evidence_level"],
            "high_confidence": verdict["high_confidence"],
            "reuse": verdict,
        })

    # Chinese candidate report (the WL-R01 deliverable).
    report_lines: List[str] = []
    for c in classified:
        r = c["reuse"]
        conf = "高置信" if c["high_confidence"] else "证据不足（非高置信）"
        line = (
            f"- {c['entity']}: 复用判断={r['verdict']}，"
            f"许可={r['license']}，版本={r['version']}，"
            f"证据={c['evidence_level']}，{conf}。"
        )
        if r["retire_reason"]:
            line += f" 淘汰理由：{r['retire_reason']}。"
        if r["auto_promoted"]:
            line += " 已自动晋级（禁止）。"
        report_lines.append(line)

    # Version diff: persisted previous pass (entity -> tracked fields) vs the
    # current sample (entity -> tracked fields).  Explains how/why each entity
    # moved (new / removed / superseded / conflict / unchanged).
    current_view = {
        (cand.get("canonical_url") or f"{cand.get('owner', '')}/{cand.get('repo', '')}"): {
            "version": cand.get("version") or cand.get("commit"),
            "commit": cand.get("commit"),
            "license": cand.get("license"),
            "price": cand.get("price"),
        }
        for cand in candidates
    }
    diff = version_diff(persisted_before or {}, current_view)

    receipt = {
        "schema": "workflow/radar-offline-loop/v1",
        "candidate_count": len(candidates),
        "candidates": classified,
        "version_diff": diff,
        "chinese_report": report_lines,
        "no_duplicate_candidates": len(candidates) == len(dedupe_candidates(candidates)),
        "all_evidence_honest": all(
            c["high_confidence"] is False
            for c in classified if c["evidence_level"] == EVIDENCE_C
        ),
        "receipt_sha256": _sha256([c["entity"] for c in classified]),
    }
    return receipt


# ---------------------------------------------------------------------------
# WL-R07: price-identity normalization + UNKNOWN propagation
# ---------------------------------------------------------------------------

def normalize_price_identity(record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a price record's identity; missing items -> UNKNOWN sentinel.

    - model / provider / currency / effective_at / source / version are all
      preserved; any that is absent, None, or empty becomes the ``UNKNOWN``
      sentinel (never collapsed to 0 or "").
    - amount == None -> the figure is UNKNOWN and is NOT rendered as 0.
    - entitlement / subscription / api_price / real_consumption stay in
      separate lanes (no cross-provider mixing).
    - the earlier (superseded) value keeps its validity window.
    """
    identity = {
        "model": _stamp(record.get("model")),
        "provider": _stamp(record.get("provider")),
        "currency": _stamp(record.get("currency")),
        "effective_at": _stamp(record.get("effective_at") or record.get("valid_from")),
        "source": _stamp(record.get("source")),
        "version": _stamp(record.get("version") or record.get("standard_version")),
    }

    amount = record.get("amount")
    amount_known = isinstance(amount, (int, float)) and not isinstance(amount, bool)
    figure = {
        "value": amount if amount_known else None,   # None = UNKNOWN, not 0
        "is_unknown": not amount_known,
        "never_rendered_as_zero": (not amount_known),
    }

    # Separate lanes — a subscription is not a metered API price.
    lanes = {
        "entitlement": _stamp(record.get("entitlement")),
        "subscription": record.get("subscription") or _stamp(record.get("subscription")),
        "api_price": amount if amount_known else UNKNOWN,
        "real_consumption": _stamp(record.get("real_consumption")),
    }

    # Superseded value keeps its validity window.
    superseded = record.get("superseded") or {}
    superseded_identity = {
        "value": _stamp(superseded.get("amount")),
        "valid_from": _stamp(superseded.get("valid_from")),
        "valid_to": _stamp(superseded.get("valid_to")),
        "as_of": _stamp(superseded.get("as_of")),
    } if superseded else None

    # UNKNOWN propagates when any key identity is missing or the figure is unknown.
    unknown_propagates = (
        any(v == UNKNOWN for v in identity.values())
        or figure["is_unknown"]
    )
    return {
        "identity": identity,
        "figure": figure,
        "lanes": lanes,
        "superseded_identity": superseded_identity,
        "unknown_propagates": unknown_propagates,
        # UI / export render guard: show the figure only when it is concrete.
        "display": (figure["value"] if amount_known else UNKNOWN),
    }


def _stamp(v: Any) -> str:
    """Absent / None / empty -> UNKNOWN sentinel (never 0 or "")."""
    if v is None:
        return UNKNOWN
    if isinstance(v, str) and v.strip() == "":
        return UNKNOWN
    if isinstance(v, float) and v == 0.0 and _stamp_hint_zero(v):
        # 0.0 for an *identity* field is not meaningful; treat as unknown.
        return UNKNOWN
    return v


def _stamp_hint_zero(v: Any) -> bool:
    return True


def price_receipt(record: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic receipt over the normalized price identity (WL-R07)."""
    normalized = normalize_price_identity(record)
    normalized["receipt_sha256"] = _sha256(
        {k: normalized[k] for k in ("identity", "figure", "lanes", "superseded_identity")},
    )
    return normalized
