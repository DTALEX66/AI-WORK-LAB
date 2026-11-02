# SPDX-License-Identifier: MIT
"""V27: audit item L21 closed -- the adapter contract has an owner, and a PASS needs a source.

L21 (``本地契约可先验证``) stayed PARTIAL with a named hole: three places described adapter
capability and nothing compared them.

* ``config/adapter-registry.json`` declared per-adapter operations;
* ``config/capability-conformance.json`` declared PROTOCOL conformance and the file each claim
  rests on -- and it asserted ``STATIC_PASS`` for ``acp`` and ``skills`` while the only entries
  backing those claims cited ``integrations/executors/codex/acp_adapter.py`` and
  ``config/skill-provenance.yaml``, neither of which exists in this candidate. The claim was
  therefore unverifiable here, by construction;
* the projection copied that status straight onto every adapter card, so a status nobody could
  re-read reached the surfaces.

This round migrated the protocol harness (``adapter_conformance.py``, byte-identical to its
source) so the verb vocabulary has one executable owner, added
``scripts/check_adapter_conformance.py`` as the reconciliation, and downgraded the two
unsupported claims to ``STATIC_UNVERIFIED`` -- the honest direction, since restoring a PASS
requires vendoring the evidence, which this batch decided not to do.

The guard below is not a description of that story: it re-runs the reconciliation and refuses
if the published verdict, the data, and the projection disagree. The last two tests plant the
failures the rule is meant to catch -- an unsupported PASS and an invented verb -- because a
check that can only ever pass is not evidence.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

TARGET_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TARGET_ROOT / "scripts"))
import source_roots  # noqa: E402  the one place roots outside this checkout are resolved
CHECKER = TARGET_ROOT / "scripts" / "check_adapter_conformance.py"
VERDICT = TARGET_ROOT / "config" / "adapter-conformance-verdict.json"
HARNESS = TARGET_ROOT / "domains" / "work" / "workflow_core" / "adapter_conformance.py"
REGISTRY = TARGET_ROOT / "config" / "adapter-registry.json"
CONFORMANCE = TARGET_ROOT / "config" / "capability-conformance.json"
WORK_SOURCE = source_roots.work_root() / "packages/client-neutral-core/scripts" / \
              "adapter_conformance.py"


def _checker():
    sys.path.insert(0, str(TARGET_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("adapter_conformance_checker", CHECKER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["adapter_conformance_checker"] = module
    spec.loader.exec_module(module)
    return module


def _json(path: pathlib.Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def test_the_migrated_harness_is_byte_identical_to_the_source_it_came_from():
    """A migration claim is a digest comparison, not a filename match."""
    assert HARNESS.is_file(), "契约夹具没在仓里，动词表就仍然没有归属"
    if not WORK_SOURCE.is_file():
        pytest.skip("the read-only WORK-LAB checkout is not on this machine; the in-repo "
                    "harness is still checked by every test below")
    assert HARNESS.read_bytes() == WORK_SOURCE.read_bytes(), (
        "迁入的 adapter_conformance.py 与来源不再逐字节相同：要么是被就地改过（应改为声明 patch），"
        "要么是来源动了而这里没跟上")


def test_the_verb_vocabulary_has_exactly_one_owner():
    module = _checker()
    document = module.reconcile()
    harness = module._module(HARNESS, "harness_for_verbs")
    assert document["verb_vocabulary"] == list(harness.OPERATIONS)
    conformance = _json(CONFORMANCE)
    interface = [entry for protocol in ("acp", "skills", "mcp")
                 for entry in (conformance.get(protocol) or {}).get("entries") or []
                 if entry.get("id") == "adapter-interface"]
    assert len(interface) == 1, interface
    assert sorted(interface[0]["capabilities"]) == sorted(document["verb_vocabulary"]), (
        "conformance 文件与契约夹具的动词表不一致")
    registry = _json(REGISTRY)
    for entry in registry["entries"]:
        unknown = sorted(set(entry.get("operations") or []) - set(document["verb_vocabulary"]))
        assert unknown == [], (entry["id"], "登记声明了契约里没有的动词：" + str(unknown))


def test_the_reconciliation_passes_and_the_published_verdict_is_a_reread_of_it():
    module = _checker()
    document = module.reconcile()
    assert document["problems"] == [], document["problems"]
    assert document["verdict"] == "PASS"
    assert VERDICT.is_file(), "对账结果必须进仓，而不是只留在脚本输出里"
    published = _json(VERDICT)
    published.pop("generated_at")
    fresh = dict(document)
    fresh.pop("generated_at")
    assert published == fresh, (
        "跟踪的判定文件与本机现读不一致：它没有被 --write 重新生成过，或数据已改动")


def test_no_protocol_claims_a_pass_whose_evidence_is_not_readable_here():
    module = _checker()
    document = _json(VERDICT)
    conformance = _json(CONFORMANCE)
    for protocol in ("acp", "skills", "mcp"):
        status = (conformance.get(protocol) or {}).get("status")
        entries = (conformance.get(protocol) or {}).get("entries") or []
        readable = sum(1 for entry in entries
                       if module.PATHLIKE.search(str(entry.get("source") or ""))
                       and (TARGET_ROOT / str(entry.get("source") or "")).is_file())
        if status == "STATIC_PASS":
            assert entries and readable == len(entries), (protocol, status, entries)
    # and the two downgraded claims are still on the record as disclosures, not erased
    assert document["protocol_status"] == {"acp": "STATIC_UNVERIFIED",
                                           "skills": "STATIC_UNVERIFIED",
                                           "mcp": "STATIC_UNVERIFIED"}, document
    assert [item["rule"] for item in document["disclosed"]] == ["SOURCE_ABSENT", "SOURCE_ABSENT"], (
        "降级不等于遗忘：不可读的来源必须以披露的形式留在判定里")
    assert document["contract_run"]["grants"] == "CONTRACT_ONLY"
    assert document["contract_run"]["evidence_state"] == "ISOLATED_PASS"


def test_the_projection_shows_the_same_status_the_data_holds():
    module = _checker()
    harness = module._module(HARNESS, "harness_for_projection")
    verdict = _json(VERDICT)
    cards = module._module(TARGET_ROOT / "domains" / "work" / "orchestration"
                           / "adapter_capability_projection.py",
                           "projection_for_v27").project_adapter_capabilities(
        registry=_json(REGISTRY), conformance=_json(CONFORMANCE),
        matrix=_json(TARGET_ROOT / "config" / "capability-matrix.json"))
    assert sorted(str(card["clientId"]) for card in cards) == verdict["adapters"]
    for card in cards:
        for protocol, value in card["protocolConformance"].items():
            assert value == verdict["protocol_status"][protocol], (card["clientId"], protocol)
        for layer in card["layers"]:
            # nothing a synthetic contract run proves may be read as a host qualification
            assert not (str(layer["state"]) in ("MET", "VERIFIED")
                        and str(layer.get("source") or "").startswith("conformance:")), layer
    # the protocol is a runtime-checkable shape, so an object that cannot answer the seven
    # verbs is not an adapter -- and the fixture that passes is not thereby qualified
    assert isinstance(harness.FakeAdapter(adapter_id="x"), harness.AdapterProtocol)
    assert not isinstance(object(), harness.AdapterProtocol), (
        "AdapterProtocol 如果对任何人都成立，它就没有断言任何东西")


def test_an_unsupported_pass_is_refused_by_the_same_rules(tmp_path, monkeypatch):
    """Falsification: put the old claim back and the checker must go red.

    Without this the reconciliation could only ever agree with itself: the data and the check
    were written in the same minute, so a rule that silently matched nothing would look
    identical to a rule that is holding.
    """
    module = _checker()
    forged = json.loads(CONFORMANCE.read_bytes().decode("utf-8-sig"))
    forged["skills"]["status"] = "STATIC_PASS"
    copy = tmp_path / "capability-conformance.json"
    copy.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8", newline="\n")
    original = module.CONFORMANCE
    try:
        module.CONFORMANCE = copy
        document = module.reconcile()
    finally:
        module.CONFORMANCE = original
    rules = {problem["rule"] for problem in document["problems"]}
    assert "UNSUPPORTED_PASS" in rules, document["problems"]
    assert "SOURCE_ABSENT" in rules, "把 PASS 加回去时，缺证据的来源也必须一起变红"
    assert document["verdict"] == "FAIL"


def test_an_invented_verb_is_refused(tmp_path, monkeypatch):
    """Falsification the other way: a registry that claims a verb the contract has never heard of."""
    module = _checker()
    forged = json.loads(REGISTRY.read_bytes().decode("utf-8-sig"))
    forged["entries"][0]["operations"] = list(forged["entries"][0]["operations"]) + ["teleport"]
    copy = tmp_path / "adapter-registry.json"
    copy.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8", newline="\n")
    original = module.REGISTRY
    try:
        module.REGISTRY = copy
        document = module.reconcile()
    finally:
        module.REGISTRY = original
    assert any(problem["rule"] == "VOCABULARY" and "teleport" in problem["detail"]
               for problem in document["problems"]), document["problems"]


def test_the_checker_writes_the_tracked_verdict_and_refuses_loudly_on_failure(tmp_path):
    before = VERDICT.read_bytes()
    finished = subprocess.run([sys.executable, "-B", "-X", "utf8", str(CHECKER)],
                              cwd=str(TARGET_ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    assert finished.returncode == 0, (finished.stdout[-600:], finished.stderr[-600:])
    assert json.loads(finished.stdout)["verdict"] == "PASS"
    assert VERDICT.read_bytes() == before, "不带 --write 的运行不得改写跟踪文件"
    out = tmp_path / "verdict.json"
    finished = subprocess.run([sys.executable, "-B", "-X", "utf8", str(CHECKER),
                               "--json-out", str(out)], cwd=str(TARGET_ROOT),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert finished.returncode == 0
    assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == "PASS"
