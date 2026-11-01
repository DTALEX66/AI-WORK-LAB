"""Agent claims — path-level ownership (advisory, WLR parallel framework).

Replaces global single-writer with path-level claims: agents claim paths before
writing; different paths run in parallel, only true overlap queues. Claims are
advisory (trust model), recorded in .workflow/claims.json.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

CLAIMS_FILE = ".workflow/claims.json"
DEFAULT_TTL = 3600  # 1h claim lease


def _read(root: Path) -> dict:
    f = root / CLAIMS_FILE
    if not f.exists():
        return {"claims": {}}
    return json.loads(f.read_text(encoding="utf-8"))


def _write(root: Path, data: dict) -> None:
    f = root / CLAIMS_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=1), encoding="utf-8")


def claim(root: Path, path: str, owner: str, ttl: int = DEFAULT_TTL) -> dict:
    """Claim a path for an owner. Returns blocked=False if free, True if held."""
    data = _read(root)
    now = time.time()
    existing = data["claims"].get(path)
    if existing and existing["expiresAt"] > now and existing["owner"] != owner:
        return {"claimed": False, "blocked": True, "heldBy": existing["owner"], "expiresAt": existing["expiresAt"]}
    data["claims"][path] = {"owner": owner, "claimedAt": now, "expiresAt": now + ttl}
    _write(root, data)
    return {"claimed": True, "blocked": False, "path": path, "owner": owner, "expiresAt": now + ttl}


def release(root: Path, path: str, owner: str) -> dict:
    data = _read(root)
    c = data["claims"].get(path)
    if c and c["owner"] == owner:
        del data["claims"][path]
        _write(root, data)
        return {"released": True}
    return {"released": False}


def status(root: Path) -> dict:
    data = _read(root)
    now = time.time()
    active = {p: c for p, c in data["claims"].items() if c["expiresAt"] > now}
    return {"activeClaims": active, "count": len(active)}


if __name__ == "__main__":
    import sys
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(status(root), indent=1))
