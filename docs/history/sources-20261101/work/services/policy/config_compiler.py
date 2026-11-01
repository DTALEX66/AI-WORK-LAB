#!/usr/bin/env python3
"""Canonical Config Compiler (WLR-040).

Pipeline: canonical intent → client projection → plan diff → approval → apply → readback

Usage:
  config_compiler.py create  --client <client> --type <type> --target <target> [--value <json>]
  config_compiler.py plan    --intent <intent.json>
  config_compiler.py approve --intent <intent.json>
  config_compiler.py apply   --intent <intent.json>
  config_compiler.py readback --intent <intent.json>
"""
import argparse, json, sys, hashlib, uuid
from pathlib import Path
from datetime import datetime

CONTRACT_PATH = (Path(__file__).resolve().parents[2] / "packages" / "contracts"
                 / "schemas" / "workflow" / "canonical-config-intent.schema.json")
APPROVAL_DIR = Path(__file__).parent.parent.parent / "config" / "pending-approvals"


def contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def off_contract_reasons(doc, client, intent_type, target):
    """The registered schema is the authority, so its enums are read from it, never restated here."""
    props = doc["properties"]
    clients = sorted(set(props["client"]["enum"]))
    types = sorted(set(props["intent"]["properties"]["type"]["enum"]))
    reasons = []
    if client not in clients:
        reasons.append(f"--client {client!r} is not one of the contract clients {clients}")
    if intent_type not in types:
        reasons.append(f"--type {intent_type!r} is not one of the contract types {types}")
    if not target:
        reasons.append("--target is empty; the contract requires a non-empty target")
    return reasons


def new_intent_id():
    return f"intent-{uuid.uuid4().hex[:12]}"

def create_intent(args):
    """Create a new canonical config intent."""
    doc = contract()
    reasons = off_contract_reasons(doc, args.client, args.type, args.target)
    if reasons:
        for reason in reasons:
            print(f"REFUSED_BY_CONTRACT: {reason}")
        sys.exit(2)
    value = json.loads(args.value) if args.value else None
    intent = {
        "schema_version": doc["properties"]["schema_version"]["const"],
        "intentId": new_intent_id(),
        "client": args.client,
        "intent": {"type": args.type, "target": args.target, "value": value, "reason": args.reason or ""},
        "plan": {"diff": [], "approval_required": True, "idempotency_key": uuid.uuid4().hex},
        "status": "draft",
    }
    out = Path(args.output) if args.output else APPROVAL_DIR / f"{intent['intentId']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(intent, indent=2), encoding="utf-8")
    print(f"OK: intent {intent['intentId']} -> {out}")

def plan_intent(args):
    """Generate plan diff from intent (stub — real projection needs adapter)."""
    cap = json.loads(Path(args.intent).read_text(encoding="utf-8"))
    client = cap["client"]
    intent = cap["intent"]
    diff_entry = {
        "path": f"{client}:{intent['target']}",
        "operation": "modify",
        "proposed_value": intent.get("value"),
        "file": f"({client} adapter projection)",
    }
    cap["plan"]["diff"] = [diff_entry]
    cap["status"] = "pending_approval"
    Path(args.intent).write_text(json.dumps(cap, indent=2), encoding="utf-8")
    print(f"OK: plan generated ({len(cap['plan']['diff'])} diff entries), status=pending_approval")

def approve_intent(args):
    """Approve a pending intent."""
    cap = json.loads(Path(args.intent).read_text(encoding="utf-8"))
    if cap["status"] != "pending_approval":
        print(f"FAIL: status is {cap['status']}, expected pending_approval"); sys.exit(1)
    cap["status"] = "approved"
    Path(args.intent).write_text(json.dumps(cap, indent=2), encoding="utf-8")
    print(f"OK: intent {cap['intentId']} approved")

def apply_intent(args):
    """Apply an approved intent.

    NF-04: without a reviewed adapter apply_fn there is no native write
    surface, so apply must NOT report success. The old stub set
    status=applied unconditionally — a fabricated success (audit A02).
    The real transaction path is services/policy/config_control_plane.py
    `transaction(approved=True, apply_fn=..., readback_fn=...)`, which
    requires an adapter-supplied apply function.
    """
    cap = json.loads(Path(args.intent).read_text(encoding="utf-8"))
    if cap["status"] != "approved":
        print(f"FAIL: status is {cap['status']}, expected approved"); sys.exit(1)
    print(
        f"UNSUPPORTED_APPLY: intent {cap['intentId']} has no adapter apply_fn. "
        "Use services/policy/config_control_plane.py transaction() with a "
        "reviewed adapter apply_fn + readback_fn; this CLI cannot fabricate "
        "an applied state."
    )
    sys.exit(3)

def readback_intent(args):
    """Readback current state after apply.

    NF-04: reports the intent file's own status honestly. This is NOT a
    native config readback — it cannot verify the target software; use the
    control-plane transaction readback_fn for that.
    """
    cap = json.loads(Path(args.intent).read_text(encoding="utf-8"))
    status = cap["status"]
    if status == "applied":
        # legacy intents written by the retired stub apply carry a fabricated
        # status; surface that instead of echoing success
        print(json.dumps({
            "intentId": cap["intentId"],
            "client": cap["client"],
            "status": "APPLIED_UNVERIFIED_LEGACY",
            "note": "status=applied was written by the retired stub apply without any native readback; treat as unverified",
            "diff_count": len(cap.get("plan", {}).get("diff", [])),
        }, indent=2))
        return
    print(json.dumps({
        "intentId": cap["intentId"],
        "client": cap["client"],
        "status": status,
        "applied_at": cap.get("applied_at"),
        "diff_count": len(cap.get("plan", {}).get("diff", [])),
    }, indent=2))

def main():
    p = argparse.ArgumentParser(description="Canonical Config Compiler (WLR-040)")
    sub = p.add_subparsers(dest="cmd")

    cr = sub.add_parser("create")
    cr.add_argument("--client", required=True)
    cr.add_argument("--type", required=True)
    cr.add_argument("--target", required=True)
    cr.add_argument("--value", default=None)
    cr.add_argument("--reason", default=None)
    cr.add_argument("--output", default=None)

    pl = sub.add_parser("plan")
    pl.add_argument("--intent", required=True)

    ap = sub.add_parser("approve")
    ap.add_argument("--intent", required=True)

    au = sub.add_parser("apply")
    au.add_argument("--intent", required=True)

    rb = sub.add_parser("readback")
    rb.add_argument("--intent", required=True)

    args = p.parse_args()
    if args.cmd == "create": create_intent(args)
    elif args.cmd == "plan": plan_intent(args)
    elif args.cmd == "approve": approve_intent(args)
    elif args.cmd == "apply": apply_intent(args)
    elif args.cmd == "readback": readback_intent(args)
    else: p.print_help()

if __name__ == "__main__":
    main()
