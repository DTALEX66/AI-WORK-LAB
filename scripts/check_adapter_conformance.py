# SPDX-License-Identifier: MIT
"""Reconcile the three places adapter capability is claimed, and refuse a PASS with no source.

Audit item L21 (「本地契约可先验证」) stayed PARTIAL because nothing compared these three:

* ``config/adapter-registry.json``     -- what each adapter declares it can do,
* ``config/capability-conformance.json`` -- what a PROTOCOL is claimed to conform to, and the
  file each claim rests on,
* ``domains/work/orchestration/adapter_capability_projection.py`` -- what the surfaces show,
  including ``protocolConformance`` copied straight out of the second file.

Before this script the second file asserted ``STATIC_PASS`` for ``acp`` and ``skills`` while
the only entries backing those claims cited ``integrations/executors/codex/acp_adapter.py``
and ``config/skill-provenance.yaml`` -- neither of which exists in this candidate (both are
WORK-LAB paths that were adjudicated as not vendored). The projection therefore published a
conformance status that nothing in this repository could disagree with, and the protocol
harness that could have produced one (``adapter_conformance.py``) was recorded as RETAIN,
i.e. never migrated. Both halves are fixed here: the harness is in-tree and byte-identical
to its source, and the check below decides what may be claimed.

The rules, all mechanically enforced:

1. **Verb vocabulary has one owner.** The harness's ``OPERATIONS`` must equal the
   ``adapter-interface`` entry's capability list, and every registry entry's operations must
   be a subset. Drift here means the surfaces and the contract disagree about what ``apply``
   even is.
2. **A PASS needs a readable source.** An entry whose ``source`` looks like a path must
   resolve to a file in this candidate. ``STATIC_PASS`` is allowed for a protocol only when
   *every* one of its entries resolves; a declaration token (``transport: external`` with no
   path) can never carry a PASS, because there is nothing here to re-read.
3. **The projection must agree with the data it reads.** Every card's
   ``protocolConformance`` must equal the protocol status in the conformance file, and the
   card set must be exactly the registry's adapter ids -- no invented adapter, none dropped.
4. **Running the contract grants only the contract.** ``run_conformance(FakeAdapter())``
   produces ``ISOLATED_PASS``; that is recorded as ``CONTRACT_ONLY`` and must never appear as
   a real qualification. A synthetic pass is evidence about shape, not about a host.

Exit code 0 with ``verdict: PASS`` only when no problem is found; each problem is printed
with the file and field that caused it.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "adapter-registry.json"
CONFORMANCE = ROOT / "config" / "capability-conformance.json"
HARNESS = ROOT / "domains/work/workflow_core/adapter_conformance.py"
OUT = ROOT / "config" / "adapter-conformance-verdict.json"
PROTOCOLS = ("acp", "skills", "mcp")
PASSING = ("STATIC_PASS", "PASS")
PATHLIKE = re.compile(r"[/\\]|\.(py|json|yaml|yml|toml|md)$")


def _module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # @dataclass resolves cls.__module__ through sys.modules while the class is being built,
    # so a module loaded by exec_module without being registered dies at its first decorator
    sys.modules[name] = module
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "domains" / "design"))
    spec.loader.exec_module(module)
    return module


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def reconcile() -> dict:
    problems: list[dict] = []
    harness = _module(HARNESS, "adapter_conformance_migrated")
    registry = _load(REGISTRY)
    conformance = _load(CONFORMANCE)

    operations = list(harness.OPERATIONS)
    interface = next((entry for protocol in PROTOCOLS
                      for entry in (conformance.get(protocol) or {}).get("entries") or []
                      if entry.get("id") == "adapter-interface"), None)
    if interface is None:
        problems.append(dict(rule="VOCABULARY", detail="capability-conformance.json 里没有 "
                                                       "adapter-interface 条目，动词表没有归属"))
    elif sorted(interface.get("capabilities") or []) != sorted(operations):
        problems.append(dict(rule="VOCABULARY", detail=(
            "harness OPERATIONS 与 adapter-interface 声明的动词表不一致："
            + repr(sorted(set(operations) ^ set(interface.get("capabilities") or []))))))

    declared = set(operations)
    for entry in registry.get("entries") or []:
        adapter = str(entry.get("id") or "")
        missing = sorted(set(entry.get("operations") or []) - declared)
        if missing:
            problems.append(dict(rule="VOCABULARY",
                                 detail="登记 %s 声明了契约里没有的动词 %s" % (adapter, missing)))

    protocol_status: dict[str, str] = {}
    entry_facts: list[dict] = []
    disclosed: list[dict] = []
    for protocol in PROTOCOLS:
        block = conformance.get(protocol) or {}
        entries = block.get("entries") or []
        status = str(block.get("status") or "")
        passes = any(word in status.upper() for word in PASSING)
        resolvable = 0
        for entry in entries:
            source = str(entry.get("source") or "")
            is_path = bool(PATHLIKE.search(source))
            exists = is_path and (ROOT / source).is_file()
            if exists:
                resolvable += 1
            fact = dict(protocol=protocol, id=entry.get("id"), source=source,
                        source_is_path=is_path, source_resolves=exists,
                        transport=entry.get("transport"),
                        declared=entry.get("capabilities") or [])
            entry_facts.append(fact)
            if is_path and not exists:
                # An unreadable source is only a defect when something claims a PASS from it.
                # With the protocol honestly unverified, the same fact is a disclosure: a
                # not-vendored dependency cannot over-claim, and a typo in its path can only
                # ever under-claim -- which the entry below still reports.
                if passes:
                    problems.append(dict(rule="SOURCE_ABSENT", detail=(
                        "%s/%s 声称依据 %s，但该文件不在本候选里（WORK-LAB 侧路径未随迁）"
                        % (protocol, entry.get("id"), source))))
                else:
                    disclosed.append(dict(rule="SOURCE_ABSENT", detail=(
                        "%s/%s 的依据 %s 不在本候选（未随迁）；该协议状态为 %s，"
                        "因此这是一条披露而不是一个 PASS"
                        % (protocol, entry.get("id"), source, status))))
        if passes and entries and resolvable != len(entries):
            problems.append(dict(rule="UNSUPPORTED_PASS", detail=(
                "%s 的状态是 %s，但它 %d 个条目里只有 %d 个的来源能在本候选读到；"
                "没有可读来源的协议不得声明 PASS"
                % (protocol, status, len(entries), resolvable))))
        protocol_status[protocol] = status

    projection = _module(ROOT / "domains/work/orchestration/adapter_capability_projection.py",
                         "adapter_capability_projection_under_check")
    cards = projection.project_adapter_capabilities(registry=registry, conformance=conformance,
                                                    matrix=_load(ROOT / "config" /
                                                                 "capability-matrix.json"))
    card_ids = sorted(str(card["clientId"]) for card in cards)
    registry_ids = sorted(str(entry.get("id")) for entry in registry.get("entries") or [])
    if card_ids != registry_ids:
        problems.append(dict(rule="PROJECTION_POPULATION", detail=(
            "投影卡片与登记不一致：卡片 %s，登记 %s" % (card_ids, registry_ids))))
    for card in cards:
        for protocol, value in (card.get("protocolConformance") or {}).items():
            if value != protocol_status.get(protocol):
                problems.append(dict(rule="PROJECTION_STATUS", detail=(
                    "%s 卡片的 %s 是 %s，与 conformance 文件里的 %s 不同"
                    % (card["clientId"], protocol, value, protocol_status.get(protocol)))))

    verdict = harness.run_conformance(harness.FakeAdapter(adapter_id="conformance-fixture"))
    evidence_state = str(verdict.get("evidence_state") or "")
    grants = "CONTRACT_ONLY" if verdict.get("passed") else "NOTHING"
    if verdict.get("passed") and evidence_state != "ISOLATED_PASS":
        problems.append(dict(rule="EVIDENCE_STATE", detail=(
            "契约跑通了但 evidence_state 不是 ISOLATED_PASS：" + evidence_state)))
    # a contract run must not be able to bless a real adapter
    for card in cards:
        for layer in card.get("layers") or []:
            if str(layer.get("state")) in ("MET", "VERIFIED") and \
               str(layer.get("source") or "").startswith("conformance:"):
                problems.append(dict(rule="CONTRACT_GRANTS_QUALIFICATION", detail=(
                    "%s 的层 %s 由契约运行升格为 %s" % (card["clientId"], layer.get("layer"),
                                                       layer.get("state")))))

    return dict(
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        schema="ai-work-lab/adapter-conformance-verdict/v1",
        verdict="FAIL" if problems else "PASS",
        rules=["VOCABULARY", "SOURCE_ABSENT", "UNSUPPORTED_PASS", "PROJECTION_POPULATION",
               "PROJECTION_STATUS", "EVIDENCE_STATE", "CONTRACT_GRANTS_QUALIFICATION"],
        verb_vocabulary=operations,
        verb_vocabulary_owner="domains/work/workflow_core/adapter_conformance.py",
        harness_sha256=hashlib.sha256(HARNESS.read_bytes()).hexdigest(),
        protocol_status=protocol_status,
        entries=entry_facts,
        adapters=card_ids,
        disclosed=disclosed,
        contract_run=dict(evidence_state=evidence_state, passed=bool(verdict.get("passed")),
                          grants=grants,
                          note="合成夹具证明的是契约形状，不是宿主能力；不授予 VERIFIED"),
        problems=problems)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true",
                        help="publish config/adapter-conformance-verdict.json (a tracked file)")
    parser.add_argument("--json-out", help="write the verdict to a path outside the repo")
    args = parser.parse_args((argv or sys.argv)[1:])

    document = reconcile()
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        pathlib.Path(args.json_out).write_text(payload, encoding="utf-8", newline="\n")
    if args.write:
        OUT.write_text(payload, encoding="utf-8", newline="\n")
    print(json.dumps(dict(verdict=document["verdict"], problems=len(document["problems"]),
                          protocol_status=document["protocol_status"],
                          adapters=len(document["adapters"]),
                          written=bool(args.write)), ensure_ascii=True))
    for problem in document["problems"]:
        print("PROBLEM %s %s" % (problem["rule"], problem["detail"]), file=sys.stderr)
    return 1 if document["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
