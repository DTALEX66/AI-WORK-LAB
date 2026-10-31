# SPDX-License-Identifier: MIT
"""V28: a refusal that describes the deployment is not a server failure.

``GET /api/evidence-projection`` recomputes the evidence link of *the checkout the service
runs from* and refuses, by name, when that checkout has no task ledger. Refusing is correct:
the projection's own contract says an empty ``receipts`` list never means "the evidence is
fine", so answering 200 with an empty readback would be a manufactured green. What was wrong
was the status class -- 503 tells an operator that the store is broken, and the surface
probe therefore registered the route as 缺陷 (``migration/route-surface.csv``, the only
defect among 164 endpoints).

In this fusion the absence is the normal shape: DESIGN-LAB's ledger ships as packaged
source material under ``domains/design/design_lab/resources/repo/``, and reading it as this
checkout's ledger would describe another repository's task state under this repository's
commit. That is a fact about the deployment, so it is answered as 409 with a sentence, and
every other refusal keeps its class -- which is what the last two tests pin, because a
change that turned all refusals into benign 4xx would hide a real outage just as well as the
503 hid the deployment shape.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
for _entry in (str(TARGET_ROOT), str(TARGET_ROOT / "domains" / "design")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from design_lab import http_service  # noqa: E402
from design_lab.governance import evidence_readback  # noqa: E402

#: Refusals that mean "this deployment lacks the artifact" -- answered 4xx.
DEPLOYMENT_SHAPED = {"EVIDENCE_LEDGER_ABSENT"}
#: Refusals that mean "the artifact is here and unreadable / code and contract diverged".
ENVIRONMENT_BROKEN = {"EVIDENCE_CONTRACT_ABSENT", "EVIDENCE_SUBJECT_UNRESOLVABLE"}
CODE_BROKEN = {"EVIDENCE_LEDGER_REJECTED", "EVIDENCE_CONTRACT_UNLOADABLE",
               "EVIDENCE_CONTRACT_VIOLATION", "EVIDENCE_PROJECTION_OVERFLOW"}


def test_the_refusal_classes_are_kept_apart_in_the_table():
    table = http_service.EVIDENCE_READBACK_STATUS
    assert set(table) == DEPLOYMENT_SHAPED | ENVIRONMENT_BROKEN | CODE_BROKEN, (
        "a new refusal code must be placed in a class here, not default to 500")
    for code in DEPLOYMENT_SHAPED:
        assert table[code] == 409, code
    for code in ENVIRONMENT_BROKEN:
        assert table[code] == 503, "%s is an environment the operator can repair" % code
    for code in CODE_BROKEN:
        assert table[code] == 500, "%s means code and contract diverged" % code
    assert "EVIDENCE_LEDGER_ABSENT" in http_service.EVIDENCE_REFUSAL_MEANING, (
        "the one refusal a reader is most likely to misread as 'all good' must carry a sentence")


def test_the_route_answers_409_with_a_name_and_never_with_an_empty_readback(server):
    status, body = server.client.get("/api/evidence-projection")
    if status == 200:
        pytest.skip("this checkout carries a task ledger, so the readback is real; the "
                    "absence branch is exercised by the planted-refusal test below")
    assert status == 409, (status, body)
    assert body["error"] == "EVIDENCE_LEDGER_ABSENT", body
    assert "meaning" in body and "全部通过" in body["meaning"], body
    # the point of refusing instead of answering 200: no empty projection to misread
    assert "receipts" not in body and "totals" not in body, body
    assert body.get("detail"), "the refusal must say what it looked for"


def test_a_planted_refusal_of_another_class_keeps_its_own_status(server, monkeypatch):
    """Falsification: the change must not have become a blanket downgrade of all refusals."""
    def refuse(code):
        def _inner(*_args, **_kwargs):
            raise evidence_readback.EvidenceReadbackError(code, ["planted for the test"])
        return _inner

    for code, expected in (("EVIDENCE_CONTRACT_ABSENT", 503),
                           ("EVIDENCE_CONTRACT_VIOLATION", 500),
                           ("EVIDENCE_LEDGER_ABSENT", 409)):
        monkeypatch.setattr(http_service, "evidence_projection", refuse(code))
        status, body = server.client.get("/api/evidence-projection")
        assert status == expected, (code, status, body)
        assert body["error"] == code, body


def test_the_absence_is_a_fact_about_this_checkout_not_about_a_broken_store():
    """The packaged ledger exists; the route must not silently start reading it as ours."""
    packaged = (TARGET_ROOT / "domains/design/design_lab/resources/repo"
                / evidence_readback.reporting.LEDGER)
    own = TARGET_ROOT / evidence_readback.reporting.LEDGER
    assert packaged.is_file(), "DESIGN-LAB 的账本应作为包内来源材料留在仓内"
    assert not own.exists(), (
        "若本检出哪天放进了自己的账本，这条测试要连同路由的判定一起更新，而不是让它悄悄绿")
    with pytest.raises(evidence_readback.EvidenceReadbackError) as raised:
        evidence_readback.projection()
    assert raised.value.code == "EVIDENCE_LEDGER_ABSENT", raised.value.code
    assert any(evidence_readback.reporting.LEDGER in str(item)
               for item in raised.value.details), raised.value.details
