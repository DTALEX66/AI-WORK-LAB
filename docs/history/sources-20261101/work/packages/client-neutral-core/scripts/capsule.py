#!/usr/bin/env python3
"""Context Continuity Protocol CLI (WLR-030).

Usage:
  capsule.py export  --client <client> --input <path> --output <capsule.json>
  capsule.py import  --capsule <capsule.json> --target <path>
  capsule.py verify  --capsule <capsule.json>
  capsule.py migrate --capsule <capsule.json> --to v1
  capsule.py redact  --capsule <capsule.json> --output <redacted.json>
"""
import argparse, hashlib, json, sys, os
from pathlib import Path

SCHEMA_VERSION = "work-lab/context-capsule/v1"
REDACTED_PATTERNS = ["api_key", "token", "password", "secret", "cookie", "private_key", "prompt_body", "response_body"]

def capsule_field(cap, name):
    """Read a capsule field accepting the canonical snake_case name, with
    legacy camelCase fallback (WL-DIR-110 schema_version unification)."""
    if name in cap:
        return cap[name]
    legacy = "".join(word.capitalize() if i else word for i, word in enumerate(name.split("_")))
    if legacy in cap:
        return cap[legacy]
    return None

def sha256_of(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def cmd_export(args):
    """Export a source file into a context capsule."""
    src = Path(args.input)
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr); sys.exit(1)
    body = src.read_text(encoding="utf-8")
    capsule = {
        "schema_version": SCHEMA_VERSION,
        "capsuleId": f"capsule-{src.stem}",
        "source": {
            "client": args.client,
            "format": src.suffix.lstrip(".") or "text",
            "exportedAt": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "originalPath": str(src),
        },
        "content": {"type": "session", "body": body, "summary": f"Exported from {src.name}"},
        "integrity": {"contentHash": sha256_of(body), "algorithm": "sha256"},
        "metadata": {},
    }
    Path(args.output).write_text(json.dumps(capsule, indent=2), encoding="utf-8")
    print(f"OK: exported {len(body)} chars -> {args.output}")

def cmd_verify(args):
    """Verify capsule integrity."""
    cap = json.loads(Path(args.capsule).read_text(encoding="utf-8"))
    version = capsule_field(cap, "schema_version")
    if version != SCHEMA_VERSION:
        print(f"FAIL: schema version mismatch: {version!r} != {SCHEMA_VERSION!r}"); sys.exit(1)
    body = cap["content"]["body"]
    actual = sha256_of(body if isinstance(body, str) else json.dumps(body, sort_keys=True))
    expected = cap["integrity"]["contentHash"]
    if actual != expected:
        print(f"FAIL: hash mismatch actual={actual[:16]} expected={expected[:16]}"); sys.exit(1)
    print("OK: capsule integrity verified")

def cmd_redact(args):
    """Redact sensitive fields from capsule content."""
    cap = json.loads(Path(args.capsule).read_text(encoding="utf-8"))
    body = cap["content"]["body"]
    if isinstance(body, str):
        # string bodies carry inline key=value pairs or bearer tokens; mask them
        import re as _re
        for pattern in REDACTED_PATTERNS:
            body = _re.sub(
                _re.compile(rf"(?i)([\"']?{pattern}[\"']?\s*[:=]\s*)([^,;\s\"'\}}]+)"),
                lambda m: m.group(1) + "[REDACTED]",
                body,
            )
        cap["content"]["body"] = body
    elif isinstance(body, dict):
        for k in list(body.keys()):
            if any(p in k.lower() for p in REDACTED_PATTERNS):
                body[k] = "[REDACTED]"
    else:
        print("FAIL: capsule content.body has unsupported type for redaction"); sys.exit(1)
    cap["integrity"]["contentHash"] = sha256_of(body if isinstance(body, str) else json.dumps(body, sort_keys=True))
    cap["metadata"]["redacted"] = True
    Path(args.output).write_text(json.dumps(cap, indent=2), encoding="utf-8")
    print(f"OK: redacted capsule -> {args.output}")

def cmd_import(args):
    """Import capsule content into target path."""
    cap = json.loads(Path(args.capsule).read_text(encoding="utf-8"))
    if cap.get("metadata", {}).get("expiresAt"):
        exp = __import__("datetime").datetime.fromisoformat(cap["metadata"]["expiresAt"].rstrip("Z"))
        if __import__("datetime").datetime.utcnow() > exp:
            print("FAIL: capsule expired", file=sys.stderr); sys.exit(1)
    body = cap["content"]["body"]
    target = Path(args.target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body if isinstance(body, str) else json.dumps(body, indent=2), encoding="utf-8")
    print(f"OK: imported {target}")

def cmd_migrate(args):
    """Migrate capsule to target schema version (stub — v1 is current)."""
    print("OK: capsule already at v1 (no migration needed)")

def main():
    p = argparse.ArgumentParser(description="Context Continuity Protocol CLI")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("verify").add_argument("--capsule", required=True)
    sub.add_parser("migrate").add_argument("--capsule", required=True)

    ex = sub.add_parser("export")
    ex.add_argument("--client", required=True)
    ex.add_argument("--input", required=True)
    ex.add_argument("--output", required=True)

    im = sub.add_parser("import")
    im.add_argument("--capsule", required=True)
    im.add_argument("--target", required=True)

    rd = sub.add_parser("redact")
    rd.add_argument("--capsule", required=True)
    rd.add_argument("--output", required=True)

    args = p.parse_args()
    if args.cmd == "export": cmd_export(args)
    elif args.cmd == "verify": cmd_verify(args)
    elif args.cmd == "import": cmd_import(args)
    elif args.cmd == "redact": cmd_redact(args)
    elif args.cmd == "migrate": cmd_migrate(args)
    else: p.print_help()

if __name__ == "__main__":
    main()
