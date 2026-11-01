"""Offline validation layer for the price-record chain (WL-R07 / audit §7).

The 2026-09-15 workbook audit concluded the price calculator sheet is "人工
情景试算可保留；边界输入需要加固；不直接转为预算执行引擎".  Before any
price record can ever drive a budget engine, four boundary defects the audit
reproduced in-memory must be rejected up front:

  * fractional call counts          -> invalid (call counts are whole units)
  * zero billing denominator        -> explicit error, never a propagated #DIV/0!
  * negative duration (voice, etc.) -> rejected
  * unknown cost filled as 0        -> must stay UNKNOWN, never rendered as 0

This module is a pure, offline, no-dispatch validator: it takes synthetic
inputs (no real billing data, no provider, no payment) and returns a typed
result so the price chain fails CLOSED on bad inputs instead of emitting a
plausible-looking number.  It pairs with radar_observations.PriceRecord but
does not mutate it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class Verdict:
    OK = "ok"
    REJECTED = "rejected"


@dataclass
class ValidationResult:
    verdict: str
    errors: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    value: Optional[float] = None  # concrete computed figure when verdict == ok

    def to_dict(self) -> Dict[str, Any]:
        return {"verdict": self.verdict, "errors": self.errors,
                "reasons": self.reasons, "value": self.value}

    @property
    def ok(self) -> bool:
        return self.verdict == Verdict.OK and not self.errors


def _is_unknown(x: Any) -> bool:
    return x is None


def validate_call_count(count: Any) -> ValidationResult:
    """Call counts are whole, non-negative units.  0 is a legitimate
    'nothing called yet' (but see pass_rate: 0 attempts -> no task price)."""
    if _is_unknown(count):
        return ValidationResult(Verdict.REJECTED,
                                errors=["call_count is unknown (None)"],
                                reasons=["refuse to fabricate a call count"])
    if isinstance(count, bool):
        return ValidationResult(Verdict.REJECTED,
                                errors=["call_count is a bool, not a count"])
    if not isinstance(count, int):
        # 0.5 -> reject; 2.0 (a float that is whole) is also a data error
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"call_count must be int, got {type(count).__name__}={count}"],
                                reasons=["fractional/typed call counts are not valid units"])
    if count < 0:
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"call_count is negative ({count})"])
    return ValidationResult(Verdict.OK)


def validate_pass_rate(rate: Any) -> ValidationResult:
    """Pass rate is a 0..1 ratio (audit: 0-1 通过率验证)."""
    if _is_unknown(rate):
        return ValidationResult(Verdict.REJECTED,
                                errors=["pass_rate is unknown (None)"])
    if not isinstance(rate, (int, float)) or isinstance(rate, bool):
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"pass_rate must be a number, got {type(rate).__name__}"])
    if rate < 0.0 or rate > 1.0:
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"pass_rate out of [0,1] ({rate})"])
    return ValidationResult(Verdict.OK)


def validate_duration(seconds: Any, kind: str = "voice") -> ValidationResult:
    """Durations must be non-negative (audit: 语音负时长必须拒绝)."""
    if _is_unknown(seconds):
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"{kind} duration is unknown (None)"])
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"{kind} duration must be a number, got {type(seconds).__name__}"])
    if seconds < 0:
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"{kind} duration is negative ({seconds})"],
                                reasons=["negative duration is not physically valid"])
    return ValidationResult(Verdict.OK)


def validate_price(amount: Optional[float], *, currency: str = "") -> ValidationResult:
    """A price that is UNKNOWN (None) must stay UNKNOWN, never be rendered as
    0.  A concrete price must be non-negative and currency-qualified."""
    if _is_unknown(amount):
        # Not an error — unknown is a valid, HONEST state.  We only assert it
        # is not secretly coerced to 0 by the caller (that is checked by the
        # render guard, not here).
        return ValidationResult(Verdict.OK,
                                reasons=["amount is UNKNOWN (None) and must be kept as such, never 0"])
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"price must be a number or None, got {type(amount).__name__}"])
    if amount < 0:
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"price is negative ({amount})"])
    if amount != 0 and not currency:
        # a concrete non-zero price with no currency is an incomplete record
        return ValidationResult(Verdict.REJECTED,
                                errors=["a concrete price requires a currency"],
                                reasons=["no currency -> cannot be a usable cost figure"])
    return ValidationResult(Verdict.OK)


def compute_price(unit: Optional[float], denominator: float,
                  currency: str = "") -> ValidationResult:
    """The #DIV/0! guard: a zero (or otherwise invalid) billing denominator
    must return an explicit REJECTED with a reason, never a zero/nan that
    silently propagates (audit: 分母误改为零必须给明确错误而非传播 #DIV/0!)."""
    if _is_unknown(unit):
        return ValidationResult(Verdict.OK,
                                reasons=["unit price UNKNOWN -> result UNKNOWN, not fabricated"])
    if isinstance(unit, bool) or not isinstance(unit, (int, float)):
        return ValidationResult(Verdict.REJECTED,
                                errors=[f"unit price must be a number or None, got {type(unit).__name__}"])
    if isinstance(denominator, bool) or not isinstance(denominator, (int, float)):
        return ValidationResult(Verdict.REJECTED,
                                errors=["denominator must be a number"])
    if denominator == 0:
        return ValidationResult(Verdict.REJECTED,
                                errors=["billing denominator is zero"],
                                reasons=["#DIV/0! is forbidden; reject with an explicit error instead of a number"])
    if unit < 0:
        return ValidationResult(Verdict.REJECTED,
                                errors=["unit price is negative"])
    # valid concrete result
    result = unit / denominator
    return ValidationResult(Verdict.OK,
                            reasons=[f"{unit} / {denominator} = {result:.6g} {currency}".strip()],
                            value=result)


def validate_price_record(rec: Dict[str, Any]) -> ValidationResult:
    """Validate a whole (dict-shaped) price record against all boundary rules
    at once.  Collects every violation so the record is one-shot, not
    whack-a-mole."""
    errs: List[str] = []
    reas: List[str] = []

    for field_name in ("calls",):
        v = validate_call_count(rec.get("calls"))
        errs += v.errors; reas += v.reasons
    # pass_rate is OPTIONAL (models/papers needn't report one) — validate only when present
    if "pass_rate" in rec:
        v = validate_pass_rate(rec.get("pass_rate"))
        errs += v.errors; reas += v.reasons
    if "duration_seconds" in rec:
        v = validate_duration(rec.get("duration_seconds"))
        errs += v.errors; reas += v.reasons

    # price / unknown-cost-not-0
    v = validate_price(rec.get("amount"), currency=rec.get("currency", ""))
    errs += v.errors; reas += v.reasons

    verdict = Verdict.REJECTED if errs else Verdict.OK
    return ValidationResult(verdict, errs, reas)
