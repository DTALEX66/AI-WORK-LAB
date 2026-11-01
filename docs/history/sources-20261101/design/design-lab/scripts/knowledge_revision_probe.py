#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-KB-05 over real HTTP: append a revision, refuse a stale write, keep latest != recommended.

A2 says a correction must append (the parent's digest stays put) and a write prepared against a
stale revision must be refused with the revision that exists. The separation clause says the newest
revision is not automatically the recommended one. Both are already unit-tested against the store;
this probe asks the same questions through the service a UI calls, and then restarts the service on
the same project root to check the revision chain reads back the same -- "restart" is what an
in-memory-only revision list would fail.

Exit 0 only if every printed reading is the one the deliverable claims.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

SOURCE = {"sourceId": "owner-note", "origin": "UNKNOWN", "author": "owner",
          "license": "UNKNOWN", "licenseStatus": "unknown", "allowedUsage": "UNKNOWN",
          "citationScope": "UNKNOWN", "version": "1", "observedAt": "2026-10-24T00:00:00Z",
          "contentHash": "UNKNOWN", "verification": "UNVERIFIED"}


def body(**overrides) -> dict:
    value = {
        "entry_type": "METHOD",
        "title": "分镜拆解三步法",
        "summary": "把一段脚本拆成镜头表：先定节拍，再定景别，最后定转场。",
        "domain_tags": ["film"],
        "task_tags": ["storyboard"],
        "target_tools": ["storyboarder"],
        "body": "第一步按段落切节拍。第二步给每个节拍选景别。第三步只标必要的转场。",
        "applicability": "适合 30-90 秒短片的分镜前置。",
        "limits": "不适用于需要精确口型对位的动画。",
        "source": dict(SOURCE),
        "related_capability_ids": [],
        "recommended": True,
        "created_by": "PROBE",
        "supersedes": None,
    }
    value.update(overrides)
    return value


def revision_body(**overrides) -> dict:
    """The revise route's exact key set: create's contract minus `supersedes`, plus the guard."""
    value = body(**overrides)
    value.pop("supersedes")
    return value


def _call(base: str, token: str, method: str, path: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"authorization": "Bearer " + token, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(request) as answer:
            return answer.status, json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def _serve(root: Path, token: str):
    from design_lab.http_service import make_server
    from design_lab.service import ProjectService
    service = ProjectService(str(root))
    server = make_server(service, token, port=0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    return server, worker, f"http://127.0.0.1:{server.server_address[1]}"


def _stop(server, worker) -> None:
    server.shutdown()
    worker.join()
    server.server_close()


def run(base: str, token: str) -> int:
    failures: list[str] = []
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO), check=True,
                            capture_output=True, text=True).stdout.strip()
    print(f"KB_REVISION_PROBE_COMMIT={commit}")

    status, created = _call(base, token, "POST", "/api/knowledge-entries", body())
    if status != 201:
        print("KB_REVISION_CREATE_REFUSED", status, json.dumps(created, ensure_ascii=False))
        return 1
    entry = created["entry"]
    entry_id = entry["knowledge_entry_id"]
    parent_sha = entry["content_sha256"]
    print("KB_REVISION_CREATED " + json.dumps({
        "entry_id": entry_id, "revision": entry["revision"], "content_sha256": parent_sha,
        "recommended": entry["recommended"]}, ensure_ascii=False))

    status, revised = _call(base, token, "POST", f"/api/knowledge-entries/{entry_id}/revisions",
                            revision_body(title="分镜拆解三步法（修订）", recommended=False,
                                          expected_revision=1))
    if status != 201:
        print("KB_REVISION_APPEND_REFUSED", status, json.dumps(revised, ensure_ascii=False))
        return 1
    print("KB_REVISION_APPENDED " + json.dumps({
        "revision": revised["entry"]["revision"],
        "content_sha256": revised["entry"]["content_sha256"],
        "recommended": revised["entry"]["recommended"]}, ensure_ascii=False))

    status, detail = _call(base, token, "GET", f"/api/knowledge-entries/{entry_id}")
    if status != 200:
        print("KB_REVISION_DETAIL_REFUSED", status)
        return 1
    first_read = {
        "latest_revision": detail["latest_revision"],
        "recommended_revision": detail["recommended_revision"],
        "current_title": detail["current"]["title"],
        "recommended_title": (detail.get("recommended") or {}).get("title"),
        "revisions": [row["revision"] for row in detail["revisions"]],
        "parent_sha": detail["revisions"][0]["content_sha256"],
        "child_sha": detail["revisions"][1]["content_sha256"],
    }
    print("KB_REVISION_DETAIL " + json.dumps(first_read, ensure_ascii=False))
    if detail["latest_revision"] != 2:
        failures.append("最新修订不是 2")
    if detail["recommended_revision"] != 1:
        failures.append("推荐版本被最新版覆盖：latest 与 recommended 没有分开")
    if detail["current"]["title"] != "分镜拆解三步法（修订）":
        failures.append("current 不是最新修订的正文")
    if (detail.get("recommended") or {}).get("title") != "分镜拆解三步法":
        failures.append("recommended 没有指向旧修订的正文")
    if first_read["parent_sha"] != parent_sha:
        failures.append("追加修订后父版本摘要改变")

    status, conflict = _call(base, token, "POST", f"/api/knowledge-entries/{entry_id}/revisions",
                             revision_body(title="并发覆盖尝试", expected_revision=1))
    print("KB_REVISION_CONFLICT " + json.dumps({"status": status, **conflict}, ensure_ascii=False))
    if status != 409 or conflict.get("error") != "KNOWLEDGE_ENTRY_REVISION_CONFLICT":
        failures.append("并发覆盖没有被拒绝为 KNOWLEDGE_ENTRY_REVISION_CONFLICT")
    if "revision 2" not in str(conflict.get("detail") or ""):
        failures.append("冲突提示没有给出实际存在的修订号")

    status, detail = _call(base, token, "GET", f"/api/knowledge-entries/{entry_id}")
    if status != 200 or detail["latest_revision"] != 2:
        failures.append("被拒绝的并发写入改变了修订链")
    print("KB_REVISION_AFTER_CONFLICT " + json.dumps({
        "status": status, "latest_revision": detail.get("latest_revision"),
        "revisions": [row["revision"] for row in detail.get("revisions", [])]},
        ensure_ascii=False))
    return failures, entry_id, first_read


def main() -> int:
    token = secrets.token_hex(32)
    runtime = REPO / ".project-local" / "task-runtime" / "revision-probe"
    runtime.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=runtime) as tmp:
        root = Path(tmp)
        (root / "AGENTS.md").write_text("# synthetic revision probe project", encoding="utf-8")
        with patch.dict(os.environ, {"PROJECT_LOCAL_ROOT": str(root / ".project-local")}):
            server, worker, base = _serve(root, token)
            try:
                result = run(base, token)
            finally:
                _stop(server, worker)
            if isinstance(result, int):
                return result
            failures, entry_id, first_read = result
            server, worker, base = _serve(root, token)
            try:
                status, detail = _call(base, token, "GET", f"/api/knowledge-entries/{entry_id}")
            finally:
                _stop(server, worker)
    if status != 200:
        failures.append("重启后条目读不回来")
    else:
        second_read = {
            "latest_revision": detail["latest_revision"],
            "recommended_revision": detail["recommended_revision"],
            "revisions": [row["revision"] for row in detail["revisions"]],
            "parent_sha": detail["revisions"][0]["content_sha256"],
            "child_sha": detail["revisions"][1]["content_sha256"],
        }
        print("KB_REVISION_RESTART_READBACK " + json.dumps(second_read, ensure_ascii=False))
        if second_read != {key: first_read[key] for key in second_read}:
            failures.append("重启后修订链读回与重启前不一致")
    for failure in failures:
        print("KB_REVISION_FAILED " + failure)
    print("KB_REVISION_OK" if not failures else "KB_REVISION_NOT_OK")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
