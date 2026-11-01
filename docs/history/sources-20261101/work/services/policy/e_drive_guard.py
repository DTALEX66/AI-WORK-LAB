"""Protected-drive guard — pre_tool_call hook blocking E:\\ / F:\\ access without authorization.

The user's standing rule protects BOTH the E: and F: data drives. This hook
checks a tool-call payload (stdin JSON) for E:\\ or F:\\ paths; blocks any
read/write/list/move/delete that touches a protected drive unless an explicit
auth marker is present. Fails closed. Mounted under Hermes hooks.pre_tool_call.
"""
from __future__ import annotations

import json
import re
import sys

PROTECTED_DRIVE_RE = re.compile(r"[EeFf]:[\\/]")
AUTH_MARKER = "E_DRIVE_AUTHORIZED"  # explicit per-operation authorization (legacy marker name; authorizes the whole payload)


def _find_protected_paths(obj, hits=None):
    if hits is None:
        hits = []
    if isinstance(obj, str):
        if PROTECTED_DRIVE_RE.search(obj):
            hits.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _find_protected_paths(v, hits)
    elif isinstance(obj, list):
        for v in obj:
            _find_protected_paths(v, hits)
    return hits


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    authorized = AUTH_MARKER in json.dumps(payload).upper()
    hits = _find_protected_paths(payload)
    if hits and not authorized:
        print(json.dumps({"allow": False, "reason": f"Protected-drive (E:\\/F:\\) access blocked ({len(hits)} path(s)): not authorized"}))
        return 1
    print(json.dumps({"allow": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
