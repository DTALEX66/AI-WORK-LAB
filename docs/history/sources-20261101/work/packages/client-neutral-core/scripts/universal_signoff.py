"""NF-14-SYNC: layered delivery, the universal goal must be genuinely signed
off.

Deliver a single usable single-link result FIRST, then complete the universal
proof; intermediate results carry a distinct name and never silently become
the final goal.  The final label ``UNIVERSAL_WORKFLOW_VERIFIED`` is used ONLY
when the universal validation matrix is met by real evidence.  When a real
external project or a second executor is missing, the delivery may report a
STAGE COMPLETE — it must NOT be claimed as a full completion.  An uninstalled
software is never given a fake LIVE PASS; a condition-study / unrelated
maintenance gap is preserved, but it does not drag an in-scope delivery into
an unbounded re-audit loop.

Reuses the evidence-level vocabulary from NF-02 (``acceptance_evidence``) —
simulation and real evidence are graded separately, never summed.

Pure and deterministic: no publish / merge / deploy (those are independent
side effects, blocked here), no fake LIVE PASS, no infinite audit loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Iterable

# evidence levels (shared with NF-02); a SIMULATED / NO_EVIDENCE level can
# never count as a real proof for a required matrix cell
LEVELS = ("NO_EVIDENCE", "SIMULATED", "SYNTHETIC", "INTEGRATED", "REAL")

# the checks that must be met by REAL evidence for the universal goal
UNIVERSAL_CHECKS = (
    "shared_rule_effect",          # 共同规则在真实软件原生载体生效
    "project_isolation",           # 项目隔离
    "official_native_choice",      # 官方原生选择保持
    "zero_manual_body_copy",       # 0 人工正文复制
    "receipt_readback",            # 回执回读
    "revision_cancel_real_restart",# 修订/取消与真实重启
)

FULL_LABEL = "UNIVERSAL_WORKFLOW_VERIFIED"
STAGE_LABEL = "STAGE_COMPLETE"
PENDING_LABEL = "PENDING_VERIFY"

# a condition-study / unrelated-maintenance gap that must NOT unblock an
# in-scope delivery but whose gap is preserved
HOLD_GAPS = ("condition_study", "unrelated_maintenance")


@dataclass
class MatrixCell:
    """One project x software x capability x environment evidence cell."""
    project: str
    software: str
    capability: str
    environment: str
    level: str = LEVELS[0]
    handle: str = ""            # a verifiable artifact / run / SHA / URL

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"evidence level must be one of {LEVELS}")

    @property
    def is_real(self) -> bool:
        # only REAL or INTEGRATED evidence counts as real proof
        return self.level in ("REAL", "INTEGRATED")


class UniversalDeliverySignoff:
    """Builds the universal validation matrix and decides the honest label.

    A matrix cell is *met* only when it carries REAL evidence (or INTEGRATED,
    when explicitly acceptable for that cell).  The universal label is granted
    ONLY when every required check is met by real evidence AND the two
    structural preconditions hold (a real external project + a second
    executor).  Anything short of that is a stage completion, not a full one.
    """

    def __init__(self) -> None:
        self._cells: dict[str, MatrixCell] = {}
        self._checks: dict[str, str] = {}          # check -> evidence level
        self._holds: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # matrix
    # ------------------------------------------------------------------
    def add_cell(self, cell: MatrixCell) -> None:
        key = f"{cell.project}|{cell.software}|{cell.capability}|{cell.environment}"
        # the strongest evidence for the same cell wins, never downgraded
        prev = self._cells.get(key)
        if prev is None or LEVELS.index(cell.level) > LEVELS.index(prev.level):
            self._cells[key] = cell

    def matrix_cells(self) -> list[MatrixCell]:
        return sorted(self._cells.values(), key=lambda c: (
            c.project, c.software, c.capability, c.environment))

    def external_projects_with_real_evidence(self) -> list[str]:
        return sorted({c.project for c in self._cells.values()
                       if c.is_real and c.project != "work-lab"})

    def second_executor_present(self, primary: str = "hermes") -> bool:
        """A second executor is present when a non-primary software carries
        REAL execution evidence in some environment."""
        for c in self._cells.values():
            if c.software != primary and c.is_real and \
                    c.capability in ("execute", "task_execution"):
                return True
        return False

    def _check_level(self, check: str) -> str:
        return self._checks.get(check, LEVELS[0])

    # ------------------------------------------------------------------
    # sign-off
    # ------------------------------------------------------------------
    def sign_off(self, *, real_external_required: bool = True,
                 second_executor_required: bool = True) -> dict[str, Any]:
        """Return the honest delivery label.  The universal label is ONLY
        returned when the matrix is genuinely met; otherwise it is a stage
        completion or pending, never a fake full completion."""
        check_levels = {c: self._check_level(c) for c in UNIVERSAL_CHECKS}
        checks_met = all(LEVELS.index(check_levels[c]) >= LEVELS.index("REAL")
                          for c in UNIVERSAL_CHECKS)
        real_external = bool(self.external_projects_with_real_evidence())
        second_exec = self.second_executor_present()

        preconditions_ok = (
            (not real_external_required or real_external)
            and (not second_executor_required or second_exec)
        )

        unmet_checks = [c for c in UNIVERSAL_CHECKS
                        if LEVELS.index(check_levels[c]) < LEVELS.index("REAL")]

        if checks_met and preconditions_ok:
            label = FULL_LABEL
        elif any(LEVELS.index(check_levels[c]) >= LEVELS.index("INTEGRATED")
                 for c in UNIVERSAL_CHECKS) or real_external or second_exec:
            # some real work happened -> a stage is complete, but it is NOT the
            # full universal goal
            label = STAGE_LABEL
        else:
            label = PENDING_LABEL

        return {
            "label": label,
            "full_completion_claimed": label == FULL_LABEL,
            "is_stage_only": label != FULL_LABEL,
            "checks": check_levels,
            "checks_met": checks_met,
            "unmet_checks": unmet_checks,
            "real_external_project": real_external,
            "second_executor": second_exec,
            "preconditions_ok": preconditions_ok,
            "held_gaps": list(self._holds),
            "note": ("every universal check is met by real evidence AND a real "
                     "external project + a second executor exist; the universal "
                     "label is granted"
                     if label == FULL_LABEL else
                     "at least one precondition or check is not met by real "
                     "evidence; only a stage completion is claimed, not a full "
                     "completion"),
        }

    # ------------------------------------------------------------------
    # checks + holds
    # ------------------------------------------------------------------
    def record_check(self, check: str, level: str, handle: str = "") -> None:
        if check not in UNIVERSAL_CHECKS:
            raise ValueError(f"unknown universal check {check!r}")
        if level not in LEVELS:
            raise ValueError(f"evidence level must be one of {LEVELS}")
        # a check level can only improve, not downgrade
        cur = self._checks.get(check, LEVELS[0])
        if LEVELS.index(level) > LEVELS.index(cur):
            self._checks[check] = level

    def hold_gap(self, kind: str, description: str) -> None:
        """A condition-study / unrelated-maintenance gap is PRESERVED (so it
        is not lost) but it does NOT push the in-scope delivery into an
        unbounded re-audit loop."""
        if kind not in HOLD_GAPS:
            raise ValueError(f"hold kind must be one of {HOLD_GAPS}")
        self._holds[kind] = {"kind": kind, "description": description,
                              "blocks_in_scope_delivery": False,
                              "note": "gap preserved; it does not create an "
                                      "infinite re-audit loop for an in-scope "
                                      "delivery"}

    def no_infinite_reaudit(self) -> bool:
        """Honest invariant: a held gap never escalates the in-scope delivery
        into an unbounded 'audit one more round' loop."""
        return all(not h["blocks_in_scope_delivery"] for h in self._holds.values())

    # ------------------------------------------------------------------
    # layered delivery naming
    # ------------------------------------------------------------------
    def layer_names(self) -> dict[str, str]:
        """Layered results carry DISTINCT names; the single-link result is not
        renamed into the universal goal and vice versa."""
        return {
            "single_link_result": "SINGLE_LINK_USABLE",
            "stage_result": "STAGE_COMPLETE",
            "universal_result": FULL_LABEL,
            "note": "intermediate results keep their own name; the final goal "
                    "is not silently substituted",
        }

    def no_fake_live_pass_for_uninstalled(self, software: str,
                                           installed: bool) -> dict[str, Any]:
        """A LIVE PASS is only claimed for software that is actually installed
        and running; an uninstalled one is marked, never faked."""
        if installed:
            return {"software": software, "live_pass": True, "installed": True}
        return {"software": software, "live_pass": False, "installed": False,
                "label": "NOT_INSTALLED",
                "note": "an uninstalled software is not given a fake LIVE PASS"}
