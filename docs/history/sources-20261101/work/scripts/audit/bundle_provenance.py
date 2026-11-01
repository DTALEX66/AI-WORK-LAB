#!/usr/bin/env python
"""Name the exact bytes a rendered measurement looked at.

A CDP receipt says what the DOM did; nothing in it says WHICH bundle produced that DOM. That gap is not
academic -- on 2026-10-10 the Observer `dist` was rebuilt after every screenshot and geometry receipt had
already been written, so a whole set of "measured" claims described bytes that no longer existed, and the
receipts could not tell the difference. `GATE_HEAD` binds a gate report to a commit; this binds a render
report to the files the browser actually fetched.

The identity covers every file the built page can load -- `index.html` plus everything under `dist/assets`
-- because the entry chunk pulls two more chunks dynamically (`window-*.js`, `webview-*.js`) that
`index.html` never mentions. Hashing only what the HTML references would leave a change to those two
invisible, and the point of a binding is that it moves when the bytes the browser ran move.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(root: Path) -> dict:
    """{files:[{path,sha256,bytes}], bundleDigest} for the built Observer front end."""
    dist = root / "apps" / "observer" / "frontend" / "dist"
    index = dist / "index.html"
    assets = dist / "assets"
    if not index.is_file() or not assets.is_dir():
        raise SystemExit(f"BUNDLE_PROVENANCE_NOT_RUN no {index} or {assets} -- build the front end first")
    files = [{"path": "index.html", "sha256": file_sha256(index), "bytes": index.stat().st_size}]
    files += [{"path": p.relative_to(dist).as_posix(), "sha256": file_sha256(p), "bytes": p.stat().st_size}
              for p in sorted(assets.rglob("*")) if p.is_file()]
    digest = hashlib.sha256("\n".join(f"{f['path']}:{f['sha256']}" for f in files).encode("utf-8")).hexdigest()
    return {"files": files, "bundleDigest": digest}


if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    print(json.dumps(describe(Path(__file__).resolve().parents[2]), ensure_ascii=False, indent=2))
