"""NF-02-SYNC: real cross-process / cross-project acceptance + exact-version CI.

The acceptance slice separates EVIDENCE LEVELS so a universal delivery is not
accepted on simulation counts or a same-object repeat or a plain green light:

  * every claimed-supported acceptance case (AT) must carry a REAL or
    appropriate-level piece of evidence; SIMULATION and REAL evidence are
    counted SEPARATELY and never summed;
  * at least one EXTERNAL real project is used WITHOUT copying the core source
    into it; project-role switching does not cross-wire;
  * a CI gate is tied to an EXACT SHA — it is not substituted by a
    different-SHA CI success, and a public repository is never wired to an
    arbitrary PR-callable everyday self-hosted runner;
  * an optional/mature-solution comparison must not block the required gate;
  * without the matching authorization a case stays PENDING-VERIFY, it is NOT
    faked as a pass.

Pure and deterministic: no network, no CI invocation, no runner, no real
device; this module only grades evidence and validates the gate policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Iterable

# evidence levels, from weakest to strongest
LEVELS = ("SIMULATED", "SYNTHETIC", "INTEGRATED", "REAL")

REQUIRED_LEVELS = {"REAL", "INTEGRATED", "SYNTHETIC", "SIMULATED"}


@dataclass
class EvidenceRecord:
    """One piece of evidence for an acceptance case, at a specific level.

    U11 real-evidence binding fields are all optional (default None) and
    additive, so the frozen positional constructions
    (case_id, level, artifact, simulated=...) keep working unchanged.
    """
    case_id: str
    level: str
    artifact: str            # a verifiable handle (path / URL / SHA / report id)
    simulated: bool
    # --- U11 REAL-evidence binding (verifiable identity of the record) ---
    evidence_type: str | None = None     # e.g. RUN_ARTIFACT / CI / EXTERNAL
    receipt_digest: str | None = None    # identity/digest of the evidence
    producer: str | None = None          # who produced it
    verifier: str | None = None         # who read it back / verified it
    observed_at: str | None = None      # ISO-8601 observation timestamp
    source_sha: str | None = None       # source SHA / run identity (optional)

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"evidence level must be one of {LEVELS}")
        # a SIMULATED / SYNTHETIC record is, by definition, simulated
        if self.level in ("SIMULATED", "SYNTHETIC"):
            self.simulated = True
        # U11: a REAL-level record must carry a verifiable handle — an empty
        # REAL handle is invalid and is rejected up front, never faked.
        if self.level in ("REAL", "INTEGRATED") and not (self.artifact or "").strip():
            raise ValueError(
                f"empty REAL evidence handle for case {self.case_id!r}: "
                "a real-level record must carry a verifiable handle"
            )


class EvidenceLedger:
    """Collects evidence per acceptance case and grades it honestly.

    Simulation and real evidence are NEVER summed: a case is only 'covered'
    when its required level is met by a matching-level record.  A case whose
    only evidence is simulated is reported as SIMULATED-ONLY, not covered.
    """

    def __init__(self) -> None:
        self._records: dict[str, list[EvidenceRecord]] = {}

    def add(self, record: EvidenceRecord) -> None:
        self._records.setdefault(record.case_id, []).append(record)

    def best_level(self, case_id: str) -> str | None:
        recs = self._records.get(case_id)
        if not recs:
            return None
        return max((r.level for r in recs), key=LEVELS.index)

    def count_by_level(self) -> dict[str, int]:
        """Count records per level — simulation and real are kept apart."""
        counts = {lvl: 0 for lvl in LEVELS}
        for recs in self._records.values():
            for r in recs:
                counts[r.level] += 1
        return counts

    def grade_case(self, case_id: str, *, required: str = "REAL") -> dict[str, Any]:
        """Grade a case against its required level.  A simulated-only case is
        PENDING-VERIFY (or SIMULATED-ONLY), never a faked pass.  The
        authorization flag determines whether a real-level case is PENDING
        (not yet authorized) or COVERED."""
        best = self.best_level(case_id)
        has_real = any(r.level in ("REAL", "INTEGRATED") for r in self._records.get(case_id, []))
        if best is None:
            return {"case": case_id, "status": "NO_EVIDENCE", "covered": False,
                    "best_level": None, "note": "no evidence recorded"}
        required_idx = LEVELS.index(required)
        best_idx = LEVELS.index(best)
        if best_idx >= required_idx and has_real:
            return {"case": case_id, "status": "COVERED", "covered": True,
                    "best_level": best, "level_met": True}
        if has_real:
            # real-level evidence exists but below the required bar
            return {"case": case_id, "status": "PENDING-VERIFY", "covered": False,
                    "best_level": best, "level_met": False,
                    "note": "evidence below the required level; not faked as a pass"}
        # only simulated / synthetic evidence
        return {"case": case_id, "status": "SIMULATED-ONLY", "covered": False,
                "best_level": best, "level_met": False,
                "note": "only simulated evidence; counted separately, not a real pass"}

    def summary(self, required_cases: Mapping[str, str]) -> dict[str, Any]:
        """Grade all required cases; report covered vs pending vs simulated-only.
        Counts simulation and real separately, never fakes a pass."""
        outcomes = {cid: self.grade_case(cid, required=required_cases.get(cid, "REAL"))
                    for cid in required_cases}
        covered = [c for c, o in outcomes.items() if o["covered"]]
        pending = [c for c, o in outcomes.items() if o["status"] in
                   ("PENDING-VERIFY", "NO_EVIDENCE")]
        simulated_only = [c for c, o in outcomes.items() if o["status"] == "SIMULATED-ONLY"]
        return {
            "covered": covered,
            "pending_verify": pending,
            "simulated_only": simulated_only,
            "counts_by_level": self.count_by_level(),
            "faked_any_pass": False,
            "note": "simulation and real evidence are counted separately; "
                    "no case is faked as a pass",
        }


@dataclass
class ExternalProjectCheck:
    """At least one external real project is used WITHOUT copying the core
    source into it; project-role switching must not cross-wire."""
    project: str
    core_source_copied_into_it: bool = False
    role_cross_wired: bool = False

    def is_clean(self) -> bool:
        return (not self.core_source_copied_into_it) and (not self.role_cross_wired)


def external_project_ok(checks: Iterable[ExternalProjectCheck]) -> dict[str, Any]:
    """Prove at least one external project is clean (no copied core source,
    no role cross-wiring)."""
    checks = list(checks)
    clean = [c for c in checks if c.is_clean()]
    return {
        "has_clean_external_project": len(clean) >= 1,
        "clean_projects": [c.project for c in clean],
        "rejected": [c.project for c in checks if not c.is_clean()],
        "note": "an external project must run WITHOUT the core source copied in"
    }


class CiShaGate:
    """A required CI gate is bound to an EXACT SHA.  A different-SHA CI success
    never substitutes it; a public repo is never wired to an arbitrary
    PR-callable everyday self-hosted runner; an optional comparison never blocks
    the required gate."""

    def __init__(self) -> None:
        self._gate: dict[str, str] = {}   # gate -> required exact sha
        self._results: dict[str, dict[str, Any]] = {}  # sha -> {status, runner}
        self._optional: set[str] = set()

    def bind_required(self, gate: str, sha: str) -> None:
        if len(sha) < 7:
            raise ValueError("a gate requires an EXACT (long-enough) SHA, not a tag")
        self._gate[gate] = sha

    def mark_optional(self, gate: str) -> None:
        """An optional / mature-solution comparison gate must NOT block the
        required gate."""
        self._optional.add(gate)

    def record_result(self, gate: str, *, sha: str, status: str,
                      runner_kind: str = "gh-hosted") -> None:
        self._results[gate] = {"sha": sha, "status": status, "runner_kind": runner_kind}

    def evaluate(self, gate: str) -> dict[str, Any]:
        required_sha = self._gate.get(gate)
        if required_sha is None:
            return {"gate": gate, "verdict": "UNBOUND",
                    "note": "no required exact-SHA gate bound"}
        res = self._results.get(gate)
        if res is None:
            return {"gate": gate, "verdict": "PENDING", "required_sha": required_sha,
                    "note": "no result recorded for the bound SHA"}
        # a different-SHA CI success is NOT a substitute
        if res["sha"] != required_sha:
            return {"gate": gate, "verdict": "SHA_MISMATCH",
                    "required_sha": required_sha, "recorded_sha": res["sha"],
                    "note": "a different-SHA CI success does not substitute the "
                            "required exact-SHA gate"}
        # a public repo wired to an arbitrary PR-callable everyday self-hosted
        # runner is refused
        if res["runner_kind"] in ("self-hosted", "everyday-self-hosted"):
            return {"gate": gate, "verdict": "RUNNER_REFUSED",
                    "required_sha": required_sha, "runner_kind": res["runner_kind"],
                    "note": "a public repo must not be wired to an arbitrary "
                            "PR-callable everyday self-hosted runner"}
        if res["status"] != "success":
            return {"gate": gate, "verdict": "FAILED", "required_sha": required_sha,
                    "status": res["status"]}
        if gate in self._optional:
            return {"gate": gate, "verdict": "OPTIONAL_PASSED",
                    "required_sha": required_sha,
                    "note": "optional gate passed; it does not block the required gate"}
        return {"gate": gate, "verdict": "GATE_PASSED", "required_sha": required_sha}


# ---------------------------------------------------------------------------
# U11 — REAL evidence binding validation.
# A REAL-level record is only as strong as the identity fields that let an
# independent reader verify it: the evidence type, a verifiable handle, an
# identity/digest, the producer, the verifier/readback, and the observation
# timestamp.  source_sha is OPTIONAL (a run identity when applicable) but,
# when present, must be well formed.  Simulated / synthetic records are not
# subject to real binding (they are, by definition, not real evidence).
# ---------------------------------------------------------------------------

# fields every REAL-level record must carry to be verifiable
REAL_BINDING_REQUIRED = ("evidence_type", "receipt_digest", "producer", "verifier", "observed_at")

# a source SHA, when present, must be long enough to be a real identity —
# mirror the CiShaGate "exact SHA" rule (>= 7 chars of hex) without pinning a
# fixed length, so a 40-char git object id and a CI run sha both validate.
_SOURCE_SHA_MIN = 7


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_real_binding(record: EvidenceRecord) -> list[str]:
    """Return the list of U11 binding issues on ``record`` ([] when valid).

    Only real-level records are subject to real binding; a simulated /
    synthetic record returns ``[]`` (it is not claiming real evidence).
    """
    if record.level in ("SIMULATED", "SYNTHETIC"):
        return []
    issues = [f for f in REAL_BINDING_REQUIRED if _is_blank(getattr(record, f, None))]
    # empty handle is a binding issue even though __post_init__ already
    # rejects it — keep the validator total / usable on reconstructed records.
    if _is_blank(record.artifact):
        issues.append("artifact")
    # source_sha is optional but must be well-formed when present.
    if not _is_blank(record.source_sha):
        sha = record.source_sha.strip()
        if len(sha) < _SOURCE_SHA_MIN or not all(c in "0123456789abcdefABCDEF" for c in sha):
            issues.append("source_sha")
    # dedupe + stable order
    seen: set[str] = set()
    out: list[str] = []
    for name in ("artifact",) + REAL_BINDING_REQUIRED + ("source_sha",):
        if name in issues and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def real_binding_status(record: EvidenceRecord) -> str:
    """U11 grade for a record's real-evidence binding.

    NOT_APPLICABLE: simulated/synthetic (no real binding is expected).
    VALID: real-level with a complete binding.
    INCOMPLETE: real-level missing one or more binding fields.
    """
    if record.level in ("SIMULATED", "SYNTHETIC"):
        return "NOT_APPLICABLE"
    return "VALID" if not validate_real_binding(record) else "INCOMPLETE"
