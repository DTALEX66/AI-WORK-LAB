"""Round-trip AG-16's missing middle link: a real planning end returns a plan, and the real contract
judges it.

AG-16's own row says the contract is implemented and tested but "**no structured handback has actually
been round-tripped**", so this exercises that link once against the running local model server recorded
in `.project/governance/runtime-registry.json`, and records what actually came back.

Two cases, and both are the point:
  1. the bare model return, fed straight into `build_candidate` — which must REFUSE, because the
     contract will not infer `baseline`/`contextDigest`/`planningSoftware`/`workUnitId`/`taskRevision`;
  2. the same model content inside a real envelope, where every factual field is supplied by this
     harness from the repository and the running server with its source named, while the cognitive
     fields (`changes`, `verification`, `assumptions`, `openQuestions`, `unresolved`,
     `targetCapability`, `authorizationRef`) remain the model's own bytes.

Deliberately NOT claimed, and the gate that reads this output enforces it:
  - nothing executed: every case carries `executionStatus=NOT_EXECUTED` and `executorSelected=null`;
  - a model-produced plan is never AUTHORIZED, because there is no real grant in the trusted record;
    any AUTHORIZED verdict comes from a fixture case whose `grantSource` says "fixture";
  - the automatic cross-client connection stays the owner decision in AG-17 (OD02).

Privacy: prompt and response bodies are never copied into the evidence — digests, lengths, key names
and verdicts only (AGENTS.md: no prompt bodies or response bodies in produced artefacts).

Usage: python scripts/audit/ag16_handback_roundtrip.py [--out PATH] [--model ID]
Exit: 0 when the round-trip produced a complete evidence file, 2 when the planning end is unreachable.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "packages" / "client-neutral-core" / "scripts"
CONTEXT_REL = "docs/current/workflow-assistance/workflow/error-governance.md"
BASE = "http://localhost:1234/v1"
WORK_UNIT = "AG16-HANDBACK-20261007"
FAKE_GRANT = "grant-that-does-not-exist"

PROMPT = (
    "You are a planning end returning a structured plan over a context capsule. "
    "Task: re-point the remaining stale file-path references in this repository's live "
    "documentation. Reply with ONLY a JSON object with these keys and no others: "
    "changes (array of strings, each one concrete edit), "
    "verification (array of strings, each a check that would prove the edit worked), "
    "assumptions (array of strings), openQuestions (array of strings), "
    "unresolved (array of strings, empty if none), "
    "targetCapability (exactly one of read/publish/execute/status/observe/review/store), "
    "authorizationRef (string, MUST be empty unless a human has granted it). "
    "Do not invent an authorization, and do not claim approval.")

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {"type": "array", "items": {"type": "string"}},
        "verification": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "openQuestions": {"type": "array", "items": {"type": "string"}},
        "unresolved": {"type": "array", "items": {"type": "string"}},
        "targetCapability": {"type": "string"},
        "authorizationRef": {"type": "string"},
    },
    "required": ["changes", "verification", "assumptions", "openQuestions", "unresolved",
                 "targetCapability", "authorizationRef"],
    "additionalProperties": False,
}


def load_modules():
    """Import client-neutral-core scripts the way the repo's own tests do.

    A bare importlib.util load leaves the module out of sys.modules, and @dataclass processing then
    dies inside dataclasses._is_type when it looks the defining module up.
    """
    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    return importlib.import_module("plan_candidate"), importlib.import_module("capability_roles")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request(path: str, payload: dict | None, timeout: int = 300) -> tuple[dict, float]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"} if data else {},
                                 method="POST" if data else "GET")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8")), time.time() - t0


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".project-local/artifacts/ag16-handback/evidence.json")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    pc, cr = load_modules()
    runtime = json.loads((REPO / ".project/governance/runtime-registry.json")
                         .read_text(encoding="utf-8"))
    lm = next((r for r in runtime["runtimes"] if r.get("id") == "lmstudio"), None)
    if lm is None:
        print("LMSTUDIO_NOT_IN_REGISTRY")
        return 2

    served = sorted(m["id"] for m in request("/models", None)[0].get("data", []))
    chat = args.model or next((m for m in served if "instruct" in m or "vl" in m), None)
    if chat is None:
        print(f"NO_CHAT_MODEL_SERVED served={served}")
        return 2

    caps = sorted(lm.get("capabilities") or [])
    registry = cr.CapabilityRoleRegistry()
    registry.register_software("lmstudio", adapter_id="openai-compat", roles=["executor"],
                              probed_capabilities=caps)

    body = {"model": chat, "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0.0, "stream": False}
    # LM Studio accepts response_format.type in {json_schema, text}; `json_object`, which plain OpenAI
    # clients send, is refused with HTTP 400. Try constrained, fall back to text, record which served.
    try:
        raw, secs = request("/chat/completions", dict(
            body, response_format={"type": "json_schema", "json_schema": {
                "name": "planning_draft", "strict": True, "schema": DRAFT_SCHEMA}}))
        mode = "json_schema"
    except urllib.error.HTTPError as exc:
        note = exc.read().decode("utf-8", "replace")[:180]
        print(f"json_schema refused ({exc.code}) -> text mode. {note}")
        raw, secs = request("/chat/completions", dict(body, response_format={"type": "text"}))
        mode = "text"

    text = (((raw.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    parse_error = None
    draft = None
    try:
        draft = json.loads(text)
    except ValueError as exc:
        parse_error = f"{type(exc).__name__}: {exc}"

    steps = []
    if isinstance(draft, dict):
        try:
            pc.build_candidate(draft)
            steps.append({"case": "model-return-without-envelope", "origin": "MODEL",
                          "verdictStatus": "UNEXPECTED_PASS", "executionStatus": "NOT_EXECUTED",
                          "executorSelected": None})
        except ValueError as exc:
            steps.append({"case": "model-return-without-envelope", "origin": "MODEL",
                          "verdictStatus": "REFUSED_MISSING_ENVELOPE",
                          "refusalReason": str(exc)[:300],
                          "keysReturnedByModel": sorted(draft),
                          "executionStatus": "NOT_EXECUTED", "executorSelected": None})

        head = git("rev-parse", "HEAD")
        blob = subprocess.run(["git", "show", f"HEAD:{CONTEXT_REL}"], cwd=REPO,
                              capture_output=True).stdout
        context_digest = hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest()
        envelope = {"planningSoftware": f"lmstudio:{chat}", "workUnitId": WORK_UNIT,
                    "taskRevision": 1, "baseline": {"commit": head, "description": "HEAD at round H"},
                    "contextRef": CONTEXT_REL, "contextDigest": context_digest,
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        merged = {**draft, **envelope}
        candidate = pc.build_candidate(merged)
        verdict = pc.check_candidate(candidate, capability_registry=registry)
        needed = candidate.get("targetCapability") or ""
        replay = pc.check_candidate(
            pc.build_candidate({**merged, "candidateId": "fresh-id-replay"}),
            capability_registry=registry, already_seen_digests=[candidate["contentDigest"]])
        steps.append({
            "case": "model-content-in-real-envelope", "origin": "MODEL+HARNESS_ENVELOPE",
            "envelopeSources": {
                "planningSoftware": "GET /v1/models on the registered lmstudio runtime",
                "baseline.commit": "git rev-parse HEAD",
                "contextRef": CONTEXT_REL,
                "contextDigest": "sha256 of that tracked file's blob at HEAD, CRLF normalised",
                "workUnitId": "harness id for this round-trip",
                "taskRevision": "first revision of this work unit"},
            "modelSuppliedKeys": sorted(k for k in draft if k not in envelope),
            "contentDigest": candidate.get("contentDigest"),
            "verdictStatus": verdict["status"], "verdictReason": verdict["reason"],
            "ignoredSelfClaims": verdict.get("ignoredSelfClaims", []),
            "blockingItems": verdict.get("blockingItems", []),
            "targetCapability": needed,
            "registryAdvertisesCapability": bool(registry.roles_with_capability(needed)),
            "replaySameContentFreshId": replay["status"],
            "executionStatus": "NOT_EXECUTED", "executorSelected": None})
    else:
        steps.append({"case": "model-content-in-real-envelope", "origin": "MODEL",
                      "verdictStatus": "DRAFT_INVALID", "parseError": parse_error,
                      "executionStatus": "NOT_EXECUTED", "executorSelected": None})

    def fixture(name, cand, grants):
        v = pc.check_candidate(cand, capability_registry=registry, trusted_grants=grants)
        steps.append({"case": name, "origin": "FIXTURE", "contentDigest": v.get("contentDigest"),
                      "verdictStatus": v["status"], "verdictReason": v["reason"],
                      "grantSource": "fixture" if grants else "none",
                      "trustedGrants": sorted(grants),
                      "blockingItems": v.get("blockingItems", []),
                      "ignoredSelfClaims": v.get("ignoredSelfClaims", []),
                      "executionStatus": "NOT_EXECUTED", "executorSelected": None})

    base_draft = {"changes": ["re-point live-doc paths"],
                  "verification": ["scan reports zero unresolved"], "unresolved": [],
                  "assumptions": [], "openQuestions": [], "references": [],
                  "targetCapability": caps[0] if caps else "read",
                  "authorizationRef": FAKE_GRANT, "planningSoftware": "fixture",
                  "workUnitId": WORK_UNIT + "-FIXTURE", "taskRevision": 1,
                  "baseline": {"commit": git("rev-parse", "HEAD")},
                  "contextRef": CONTEXT_REL, "contextDigest": "b" * 64}
    clean = pc.build_candidate(base_draft)
    fixture("fixture-clean-no-grant", clean, {})
    fixture("fixture-clean-with-fixture-grant", clean, {FAKE_GRANT: "read-only-doc-edit"})
    fixture("fixture-blocking-despite-grant",
            pc.build_candidate({**base_draft, "candidateId": "",
                                "unresolved": ["who authorizes this?"]}),
            {FAKE_GRANT: "read-only-doc-edit"})
    fixture("fixture-unknown-capability",
            pc.build_candidate({**base_draft, "candidateId": "",
                                "targetCapability": "capability-nobody-advertises"}),
            {FAKE_GRANT: "read-only-doc-edit"})
    fixture("fixture-self-grant-ignored",
            pc.build_candidate({**base_draft, "candidateId": "", "approved": True,
                                "scope": "write-everything"}), {})

    doc = {
        "schemaVersion": "work-lab/ag16-handback-roundtrip/v1",
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": "scripts/audit/ag16_handback_roundtrip.py",
        "objective": "exercise the planning -> handback -> contract link once with a real returning "
                     "end, which AG-16 recorded as never having been round-tripped",
        "planningEnd": {"runtime": "lmstudio", "endpoint": BASE + "/chat/completions",
                        "modelRequested": chat, "servedModels": served,
                        "registryCapabilities": caps, "responseFormatMode": mode,
                        "responseSeconds": round(secs, 2)},
        "returnShape": {"jsonParseOk": isinstance(draft, dict), "parseError": parse_error,
                        "responseChars": len(text), "responseSha256": sha(text),
                        "topLevelKeys": sorted(draft) if isinstance(draft, dict) else [],
                        "note": "prompt and response bodies are not copied here by design"},
        "requestPromptSha256": sha(PROMPT), "requestPromptChars": len(PROMPT),
        "contextUsedForPlanning": {"path": CONTEXT_REL,
                                   "basis": "the tracked blob at HEAD, CRLF normalised"},
        "cases": steps,
        "counts": {"cases": len(steps),
                   "modelOrigin": sum(1 for s in steps if s["origin"].startswith("MODEL")),
                   # the contract spells an authorization "AUTHORIZED_NOT_EXECUTED"; matching the
                   # exact word here is what hid one authorized case from the count (and the gate
                   # would have passed a vacuous 0 == 0)
                   "authorized": sum(1 for s in steps
                                     if s["verdictStatus"].startswith("AUTHORIZED")),
                   "authorizedWithoutFixtureGrant": sum(
                       1 for s in steps if s["verdictStatus"].startswith("AUTHORIZED")
                       and s.get("grantSource") != "fixture"),
                   "executed": sum(1 for s in steps if s["executionStatus"] != "NOT_EXECUTED")},
        "notClaimed": ["no executor was selected and nothing executed",
                       "no real authorization exists; any AUTHORIZED verdict carries "
                       "grantSource=fixture",
                       "the automatic cross-client connection remains AG-17 / OD02 (owner decision)",
                       "one planning return, one model, temperature 0.0 — a round-trip, not a "
                       "quality measurement"],
    }
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"planningEnd={chat} mode={mode} served={len(served)} "
          f"responseSeconds={round(secs, 2)} jsonOk={doc['returnShape']['jsonParseOk']}")
    for s in steps:
        extra = f"  replay={s['replaySameContentFreshId']}" if "replaySameContentFreshId" in s else ""
        print(f"  {s['origin']:24s} {s['case']:34s} -> {s['verdictStatus']}{extra}")
    print(f"RESULT cases={doc['counts']['cases']} authorized={doc['counts']['authorized']} "
          f"authorizedWithoutFixtureGrant={doc['counts']['authorizedWithoutFixtureGrant']} "
          f"executed={doc['counts']['executed']}")
    print(f"evidence -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
