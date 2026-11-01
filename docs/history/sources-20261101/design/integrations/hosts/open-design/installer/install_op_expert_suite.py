#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""Install the OP personal expert suite through Open Design's supported surfaces.

Open Design 0.19+ owns both the user-skill files and their Personal Workspace
binding. This installer therefore calls ``POST /api/skills/install`` with a
local source folder. Plugins and bundles are registered through
``POST /api/plugins/install`` from an upgrade-stable mirror under the active
namespace's ``data/local-plugin-sources`` directory. It never edits app.sqlite.

The installer maintains editable user design systems and user skills. The
default is content-aware and idempotent: matching skills are left untouched,
while changed skills are refreshed through the official delete/install routes.
Pass ``--refresh`` to force reinstalling every existing managed skill.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


# DL-DIR-MIG-R1: open-design host tree now lives at repo-root integrations/
# (installer is 4 levels deep: installer -> open-design -> hosts -> integrations -> repo).
REPO_ROOT = Path(__file__).resolve().parents[4]
HOST_ROOT = REPO_ROOT / "integrations" / "hosts" / "open-design"
SUITE_SRC = HOST_ROOT / "expert-suite" / "skills"
DESIGN_SYSTEMS_ROOT = REPO_ROOT / "design-lab" / "design-systems"
PLUGINS_ROOT = REPO_ROOT / "packages" / "capabilities" / "plugins"
BUNDLES_ROOT = REPO_ROOT / "packages" / "capabilities" / "bundles"
ATOMS_ROOT = REPO_ROOT / "packages" / "capabilities" / "atoms"
SCENARIOS_ROOT = REPO_ROOT / "packages" / "capabilities" / "scenarios"
EXPERT_RESOURCE_SOURCES = (
    *(('plugins', name) for name in (
        'anomaly-monitor-hud',
        'brand-visual-director',
        'design-qa-critic',
        'graphic-design-director',
        'minigame-ui-director',
        'spatial-exhibition-director',
        'uiux-layout-director',
    )),
    *(('bundles', name) for name in (
        'commercial-design-core',
        'production-handoff',
        'visual-quality-core',
    )),
    *(('scenarios', name) for name in (
        'commercial-design-router',
        'brand-campaign-360',
    )),
)
DESIGN_SYSTEM_SOURCES = (
    {
        "slug": "uiux-commercial-light",
        "title": "UIUX Commercial Light",
        "category": "UI/UX & Commercial",
        "surface": "web",
        "summary": "五类黄金案例共享的商业 UI/UX、组件、响应式与无障碍个人设计体系。",
    },
    {
        "slug": "anomaly-monitor-dark",
        "title": "Anomaly Monitor Dark",
        "category": "Game UI & HUD",
        "surface": "web",
        "summary": "可选的 CCTV、异常叙事、监控 HUD 与控制台视觉专精；不是通用小游戏的默认主题。",
    },
    {
        "slug": "personal-design-intelligence",
        "title": "Personal Design Intelligence",
        "category": "Design Intelligence",
        "surface": "web",
        "summary": "大师方法、风格谱系、来源治理、视觉质检和生产交付组成的个人设计智能体系。",
    },
)
URL_RE = re.compile(r"http://127\.0\.0\.1:\d+")
DESIGN_SYSTEM_MANAGED_PREFIX = "Managed by DESIGN-LAB; slug="


class ApiError(RuntimeError):
    """An Open Design API request failed."""


def active_namespace_root() -> Path:
    """Select the namespace with the newest readable Web sidecar log."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise ApiError("APPDATA is unavailable")
    namespaces = Path(appdata) / "Open Design" / "namespaces"
    candidates = []
    for log in namespaces.glob("*/logs/web/latest.log"):
        try:
            matches = URL_RE.findall(log.read_text(encoding="utf-8", errors="ignore"))
            if matches:
                candidates.append((log.stat().st_mtime_ns, log, matches[-1]))
        except OSError:
            continue
    if not candidates:
        raise ApiError("no active Open Design namespace Web log was discovered")
    candidates.sort(key=lambda item: item[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise ApiError("multiple Open Design namespace Web logs have the same freshness")
    return candidates[0][1].parents[2]


def default_app_url() -> str:
    """Read the current Open Design Web sidecar URL from its official log."""
    try:
        log = active_namespace_root() / "logs" / "web" / "latest.log"
        matches = URL_RE.findall(log.read_text(encoding="utf-8", errors="ignore"))
    except (ApiError, OSError):
        return ""
    return matches[-1] if matches else ""


def namespace_data_root(app_url: str) -> Path:
    """Bind an explicit sidecar URL to exactly one namespace data root."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise ApiError("APPDATA is unavailable")
    expected = app_url.rstrip("/")
    matches = []
    namespaces = Path(appdata) / "Open Design" / "namespaces"
    for log in namespaces.glob("*/logs/web/latest.log"):
        try:
            urls = {url.rstrip("/") for url in URL_RE.findall(
                log.read_text(encoding="utf-8", errors="ignore")
            )}
        except OSError:
            continue
        if expected in urls:
            matches.append(log.parents[2])
    if len(matches) != 1:
        raise ApiError(
            f"sidecar URL {expected} maps to {len(matches)} Open Design namespaces"
        )
    return matches[0] / "data"


def verify_sidecar_health(app_url: str) -> None:
    """Confirm the explicit sidecar is live before selecting any write target."""
    status, data = api_request(app_url, "/api/health", timeout=10)
    if status != 200 or data.get("ok") is not True:
        raise ApiError(f"Open Design sidecar health check failed: HTTP {status}")


def api_request(
    app_url: str,
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> tuple[int, dict[str, Any]]:
    """Call the local Open Design API without routing localhost via a proxy."""
    body = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"{app_url.rstrip('/')}{path}",
        data=body,
        headers=request_headers,
        method=method,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            data = {"error": raw.strip() or exc.reason}
        return exc.code, data
    except urllib.error.URLError as exc:
        raise ApiError(f"Open Design is unreachable at {app_url}: {exc.reason}") from exc


def select_workspace(app_url: str) -> dict[str, str]:
    """Select the active Personal Workspace from Open Design's directory API."""
    status, data = api_request(app_url, "/api/workspace/directory")
    if status != 200:
        raise ApiError(f"workspace directory failed: HTTP {status} {data}")
    items = [
        item
        for item in data.get("items", [])
        if item.get("memberStatus") == "active"
        and item.get("lifecycleState") == "active"
    ]
    personal = [item for item in items if item.get("workspaceType") == "personal"]
    active_id = data.get("activeWorkspaceId")
    selected = next(
        (item for item in personal if item.get("workspaceId") == active_id), None
    )
    if selected is None and len(personal) == 1:
        selected = personal[0]
    if selected is None:
        raise ApiError("could not select exactly one active Personal Workspace")
    workspace_id = str(selected.get("workspaceId", "")).strip()
    member_id = str(selected.get("workspaceMemberId", "")).strip()
    role = str(selected.get("role", "")).strip()
    member_status = str(selected.get("memberStatus", "")).strip()
    lifecycle_state = str(selected.get("lifecycleState", "")).strip()
    if not all((workspace_id, member_id, role, member_status, lifecycle_state)):
        raise ApiError("selected Personal Workspace has incomplete authority")
    return {
        "x-od-workspace-id": workspace_id,
        "x-od-workspace-member-id": member_id,
        "x-od-workspace-type": "personal",
        "x-od-workspace-role": role,
        "x-od-workspace-member-status": member_status,
        "x-od-workspace-lifecycle-state": lifecycle_state,
    }


def read_app_config(app_url: str, headers: dict[str, str]) -> dict[str, Any]:
    """Read the complete config for an in-memory preservation check; never print it."""
    status, data = api_request(app_url, "/api/app-config", headers=headers)
    if status != 200 or not isinstance(data, dict):
        raise ApiError(f"app-config readback failed: HTTP {status}")
    return data


def copy_expert_resource_sources(destination: Path) -> None:
    """Copy managed resources and their complete local asset closure."""
    shutil.copytree(ATOMS_ROOT, destination / "atoms")
    resource_roots = (
        ("plugins", PLUGINS_ROOT),
        ("bundles", BUNDLES_ROOT),
        ("scenarios", SCENARIOS_ROOT),
    )
    for kind, root in resource_roots:
        for source_kind, name in EXPERT_RESOURCE_SOURCES:
            if source_kind == kind:
                shutil.copytree(root / name, destination / kind / name)
    # Manifest assets are paths relative to the resource directory (e.g.
    # ../../atoms/<id>/SKILL.md).  After DL-DIR-MIG-R1 the catalogs live under
    # packages/capabilities/<kind> (plugins/bundles/scenarios/atoms share the
    # packages/capabilities parent), while research/ stays under design-lab/.
    # Sources are resolved from the real anchors; the mirror keeps the resource
    # directories so each manifest asset reference resolves inside the mirror.
    # DL-DIR-MIG-R1 layout: catalogs moved from design-lab/<kind> to
    # packages/capabilities/<kind>, so the ../../<shared> asset references in
    # manifests resolve against the new anchor; research/ assets that shared the
    # design-lab/ root with the old bundles are resolved from the legacy anchor.
    resource_anchors = {
        "plugins": PLUGINS_ROOT,
        "bundles": BUNDLES_ROOT,
        "scenarios": SCENARIOS_ROOT,
    }
    mirror_root = destination.resolve()
    for kind, name in EXPERT_RESOURCE_SOURCES:
        manifest_path = destination / kind / name / "open-design.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative in manifest.get("od", {}).get("context", {}).get("assets", []):
            anchor = resource_anchors.get(kind)
            if anchor is None:
                raise ApiError(f"unknown resource kind: {kind}")
            source = (anchor / name / relative).resolve()
            if not source.is_file():
                legacy = REPO_ROOT / "design-lab" / kind / name / relative
                source = legacy.resolve()
            if not source.is_file():
                raise ApiError(f"missing expert resource asset: {relative}")
            # mirror target mirrors the manifest's own relative reference so the
            # copied tree stays self-consistent (manifest_path.parent / relative)
            target = (manifest_path.parent / relative).resolve()
            try:
                target.relative_to(mirror_root)
            except ValueError as exc:
                raise ApiError(f"asset escapes mirror root: {relative}") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(source, target)


class StableSourceUpdate:
    """A pending stable-source swap retained until runtime readback succeeds."""

    def __init__(self, target: Path, previous: Path | None):
        self.target = target
        self.previous = previous
        self.finished = False

    def commit(self) -> None:
        if self.finished:
            return
        if self.previous and self.previous.exists():
            shutil.rmtree(self.previous)
        self.finished = True

    def rollback(self) -> None:
        if self.finished:
            return
        if self.target.exists():
            shutil.rmtree(self.target)
        if self.previous and self.previous.exists():
            self.previous.replace(self.target)
        self.finished = True


def begin_stable_resource_source_update(app_url: str) -> StableSourceUpdate:
    """Swap in a new mirror while retaining the old tree for later rollback."""
    target = namespace_data_root(app_url) / "local-plugin-sources" / "design-lab"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".design-lab-", dir=target.parent))
    previous = target.with_name(f".{target.name}.previous")
    try:
        copy_expert_resource_sources(temp)
        if previous.exists():
            raise ApiError(f"stale source rollback tree exists: {previous}")
        retained: Path | None = None
        if target.exists():
            target.replace(previous)
            retained = previous
        temp.replace(target)
        return StableSourceUpdate(target, retained)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        if previous.exists() and not target.exists():
            previous.replace(target)
        raise


def install_expert_resource(
    app_url: str,
    headers: dict[str, str],
    kind: str,
    resource_id: str,
) -> None:
    """Install and bind a local resource through OP's official SSE endpoint."""
    source = f"./../data/local-plugin-sources/design-lab/{kind}/{resource_id}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(1, 4):
        req = urllib.request.Request(
            f"{app_url.rstrip('/')}/api/plugins/install",
            data=json.dumps({"source": source}).encode("utf-8"),
            headers={
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
                "Origin": app_url,
                **headers,
            },
            method="POST",
        )
        try:
            with opener.open(req, timeout=180) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code == 400 and not raw.strip() and attempt < 3:
                time.sleep(attempt)
                continue
            raise ApiError(
                f"install resource {resource_id} failed: HTTP {exc.code} {raw}"
            ) from exc
        if "event: success" not in raw:
            raise ApiError(
                f"install resource {resource_id} returned no success event: {raw}"
            )
        return


def verify_expert_resources(app_url: str, headers: dict[str, str]) -> None:
    """Read back all managed IDs and their upgrade-stable local sources."""
    status = 0
    data: dict[str, Any] = {}
    for attempt in range(1, 6):
        status, data = api_request(app_url, "/api/plugins", headers=headers)
        if status == 200:
            break
        if status == 400 and not data and attempt < 5:
            time.sleep(attempt)
            continue
        break
    if status != 200:
        raise ApiError(f"plugin catalog readback failed: HTTP {status} {data}")
    plugins = {
        str(item.get("id")): item
        for item in data.get("plugins", [])
        if isinstance(item, dict) and item.get("id")
    }
    missing = []
    unstable = []
    for kind, resource_id in EXPERT_RESOURCE_SOURCES:
        item = plugins.get(resource_id)
        if item is None:
            missing.append(resource_id)
            continue
        expected = (
            "./../data/local-plugin-sources/"
            f"design-lab/{kind}/{resource_id}"
        )
        if item.get("sourceKind") != "local" or item.get("source") != expected:
            unstable.append(resource_id)
    if missing or unstable:
        raise ApiError(
            f"expert resource readback failed: missing={missing}, unstable={unstable}"
        )


def list_plugin_catalog(
    app_url: str, headers: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """Read a stable projection of this suite's managed catalog entries."""
    status, data = api_request(app_url, "/api/plugins", headers=headers)
    if status != 200:
        raise ApiError(f"plugin catalog snapshot failed: HTTP {status} {data}")
    managed_ids = {resource_id for _kind, resource_id in EXPERT_RESOURCE_SOURCES}
    return {
        str(item["id"]): {
            key: item.get(key)
            for key in ("id", "version", "source", "sourceKind", "trust", "status")
        }
        for item in data.get("plugins", [])
        if isinstance(item, dict) and item.get("id") in managed_ids
    }


def describe_catalog_delta(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> str:
    """Describe catalog mutations without exposing unrelated catalog content."""
    before_ids = set(before)
    after_ids = set(after)
    changed = sorted(key for key in before_ids & after_ids if before[key] != after[key])
    return (
        f"added={sorted(after_ids - before_ids)}, "
        f"removed={sorted(before_ids - after_ids)}, changed={changed}"
    )


def install_expert_resources_transactionally(
    app_url: str,
    headers: dict[str, str],
    *,
    before_commit: Callable[[], None] | None = None,
) -> int:
    """Install resources; restore the mirror and report any catalog mutation."""
    catalog_before = list_plugin_catalog(app_url, headers)
    source_update = begin_stable_resource_source_update(app_url)
    installed_count = 0
    try:
        for kind, name in EXPERT_RESOURCE_SOURCES:
            install_expert_resource(app_url, headers, kind, name)
            print(f"  install  {kind}/{name} (personal + active)")
            installed_count += 1
        verify_expert_resources(app_url, headers)
        if before_commit is not None:
            before_commit()
    except Exception as install_error:
        source_update.rollback()
        try:
            catalog_after = list_plugin_catalog(app_url, headers)
        except Exception as snapshot_error:
            raise ApiError(
                "expert resource installation failed; mirror restored, but catalog "
                f"state is unknown: install={install_error}; snapshot={snapshot_error}"
            ) from snapshot_error
        if catalog_after != catalog_before:
            raise ApiError(
                "expert resource installation failed; mirror restored with partial "
                f"catalog mutation: {describe_catalog_delta(catalog_before, catalog_after)}; "
                f"install={install_error}"
            ) from install_error
        raise ApiError(
            "expert resource installation failed; mirror restored and catalog "
            f"snapshot is unchanged: {install_error}"
        ) from install_error
    source_update.commit()
    return installed_count


def list_installed_skills(
    app_url: str, headers: dict[str, str]
) -> dict[str, dict[str, Any]]:
    status, data = api_request(app_url, "/api/skills", headers=headers)
    if status != 200:
        raise ApiError(f"skill catalog failed: HTTP {status} {data}")
    return {
        str(skill.get("id")): skill
        for skill in data.get("skills", [])
        if skill.get("source") == "user" and skill.get("id")
    }


def read_skill(app_url: str, headers: dict[str, str], skill_id: str) -> dict[str, Any]:
    """Read one user skill, including its body, through the official API."""
    status, data = api_request(
        app_url,
        f"/api/skills/{urllib.parse.quote(skill_id, safe='')}",
        headers=headers,
    )
    if status != 200 or not isinstance(data, dict):
        raise ApiError(f"skill readback {skill_id} failed: HTTP {status} {data}")
    return data


def parse_skill_source(source_dir: Path) -> dict[str, Any]:
    """Parse the controlled frontmatter subset used by this personal suite."""
    text = (source_dir / "SKILL.md").read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ApiError(f"skill source has no YAML frontmatter: {source_dir}")
    frontmatter, body = parts[1], parts[2].lstrip("\r\n")
    lines = frontmatter.strip().splitlines()
    result: dict[str, Any] = {"triggers": [], "body": body.rstrip()}
    section = ""
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if stripped == "triggers:":
            section = "triggers"
            index += 1
            continue
        if stripped == "od:":
            section = "od"
            index += 1
            continue
        if section == "triggers" and stripped.startswith("- "):
            result["triggers"].append(stripped[2:].strip().strip('"\''))
            index += 1
            continue
        if stripped == "description: |":
            block: list[str] = []
            index += 1
            while index < len(lines) and (
                lines[index].startswith("  ") or not lines[index].strip()
            ):
                block.append(lines[index][2:] if lines[index].startswith("  ") else "")
                index += 1
            result["description"] = "\n".join(block).strip()
            section = ""
            continue
        match = re.match(r"^(name|description):\s*(.+)$", stripped)
        if match:
            result[match.group(1)] = match.group(2).strip().strip('"\'')
            section = ""
            index += 1
            continue
        if section == "od":
            match = re.match(r"^(mode|category|upstream):\s*(.+)$", stripped)
            if match:
                result[match.group(1)] = match.group(2).strip().strip('"\'')
        index += 1
    required = {"name", "description", "triggers", "mode", "category", "body"}
    missing = sorted(required - result.keys())
    if missing:
        raise ApiError(f"skill source fields missing for {source_dir.name}: {missing}")
    return result


def skill_matches_source(current: dict[str, Any], source_dir: Path) -> bool:
    expected = parse_skill_source(source_dir)
    current_body = str(current.get("body", "")).replace("\r\n", "\n").strip("\n")
    expected_body = str(expected["body"]).replace("\r\n", "\n").strip("\n")
    return current_body == expected_body


def require_managed_skill(current: dict[str, Any], source_dir: Path) -> None:
    """Refuse to refresh a same-ID user skill not owned by this repository."""
    expected = parse_skill_source(source_dir)
    expected_upstream = str(expected.get("upstream", "")).strip()
    current_upstream = str(current.get("upstream", "")).strip()
    if not expected_upstream or current_upstream != expected_upstream:
        raise ApiError(
            f"unmanaged skill has reserved id {current.get('id')!r}; "
            "refusing to overwrite user-owned content"
        )


def list_user_design_systems(
    app_url: str, headers: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """Return editable user design systems keyed by title."""
    status, data = api_request(app_url, "/api/design-systems", headers=headers)
    if status != 200:
        raise ApiError(f"design-system catalog failed: HTTP {status} {data}")
    systems: dict[str, dict[str, Any]] = {}
    for system in data.get("designSystems", []):
        if not isinstance(system, dict):
            continue
        if (
            system.get("source") != "user"
            or system.get("isEditable") is not True
            or not system.get("title")
        ):
            continue
        title = str(system["title"])
        if title in systems:
            raise ApiError(
                f"multiple editable user design systems share title {title!r}"
            )
        systems[title] = system
    return systems


def read_design_system(
    app_url: str, headers: dict[str, str], system_id: str
) -> dict[str, Any]:
    """Read one editable design system for managed-identity verification."""
    status, data = api_request(
        app_url,
        f"/api/design-systems/{urllib.parse.quote(system_id, safe='')}",
        headers=headers,
    )
    if status != 200 or not isinstance(data, dict):
        raise ApiError(f"design-system readback {system_id} failed: HTTP {status}")
    result = data.get("designSystem", data)
    if not isinstance(result, dict):
        raise ApiError(f"design-system readback {system_id} returned invalid data")
    return result


def sync_design_systems(
    app_url: str,
    headers: dict[str, str],
    workspace_id: str,
    *,
    dry_run: bool,
) -> tuple[int, int]:
    """Create or update repo design systems through official OP routes."""
    existing = list_user_design_systems(app_url, headers)
    created_count = 0
    updated_count = 0
    for spec in DESIGN_SYSTEM_SOURCES:
        source_dir = DESIGN_SYSTEMS_ROOT / spec["slug"]
        body = (source_dir / "DESIGN.md").read_text(encoding="utf-8")
        payload = {
            "title": spec["title"],
            "category": spec["category"],
            "surface": spec["surface"],
            "status": "published",
            "summary": spec["summary"],
            "sourceNotes": (
                f"{DESIGN_SYSTEM_MANAGED_PREFIX}{spec['slug']}; "
                "canonical repository resource."
            ),
            "body": body,
            "workspaceId": workspace_id,
        }
        current = existing.get(spec["title"])
        if current:
            source_notes = str(current.get("sourceNotes", ""))
            managed = (
                source_notes.startswith(
                    f"{DESIGN_SYSTEM_MANAGED_PREFIX}{spec['slug']};"
                )
                or "maintained by DESIGN-LAB" in source_notes
            )
            if not managed:
                system_id = str(current.get("id", "")).strip()
                if not system_id:
                    raise ApiError(
                        f"unmanaged design system {spec['title']!r} has no readable id"
                    )
                detail = read_design_system(app_url, headers, system_id)
                current_body = str(detail.get("body", "")).replace(
                    "\r\n", "\n"
                ).strip("\n")
                expected_body = body.replace("\r\n", "\n").strip("\n")
                managed = current_body == expected_body
            if not managed:
                raise ApiError(
                    f"unmanaged design system has reserved title {spec['title']!r}; "
                    "refusing to overwrite user-owned content"
                )
        action = "update" if current else "create"
        if dry_run:
            print(f"  [dry-run] {action} design-system {spec['slug']}")
            continue
        if current:
            system_id = str(current.get("id", ""))
            status, data = api_request(
                app_url,
                f"/api/design-systems/{urllib.parse.quote(system_id, safe='')}",
                method="PATCH",
                headers={"Origin": app_url, **headers},
                payload=payload,
            )
            expected_status = 200
            updated_count += 1
        else:
            status, data = api_request(
                app_url,
                "/api/design-systems",
                method="POST",
                headers={"Origin": app_url, **headers},
                payload=payload,
            )
            expected_status = 201
            created_count += 1
        if status != expected_status:
            raise ApiError(
                f"{action} design-system {spec['slug']} failed: HTTP {status} {data}"
            )
        result = data.get("designSystem") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            result = data
        if not isinstance(result, dict) or result.get("source") != "user":
            raise ApiError(
                f"{action} design-system {spec['slug']} returned an unexpected response: {data}"
            )
        print(
            f"  {action:<8} design-system {spec['slug']} "
            f"(id={result.get('id')}, status={result.get('status')})"
        )
    return created_count, updated_count


def delete_skill(app_url: str, headers: dict[str, str], skill_id: str) -> None:
    status, data = api_request(
        app_url,
        f"/api/skills/{urllib.parse.quote(skill_id)}",
        method="DELETE",
        headers={"Origin": app_url, **headers},
    )
    if status not in (200, 404):
        raise ApiError(f"delete {skill_id} failed: HTTP {status} {data}")


def install_skill(
    app_url: str, headers: dict[str, str], skill_id: str, source_dir: Path
) -> dict[str, Any]:
    status, data = api_request(
        app_url,
        "/api/skills/install",
        method="POST",
        headers={"Origin": app_url, **headers},
        payload={"source": "local", "path": str(source_dir.resolve())},
    )
    if status != 200:
        raise ApiError(f"install {skill_id} failed: HTTP {status} {data}")
    skill = data.get("skill")
    if not isinstance(skill, dict) or skill.get("id") != skill_id:
        raise ApiError(f"install {skill_id} returned an unexpected response: {data}")
    return skill


def write_skill_snapshot(skill: dict[str, Any], destination: Path) -> None:
    """Materialize an API-read skill only for official-route rollback."""
    required = ("name", "description", "triggers", "mode", "category", "body")
    missing = [field for field in required if field not in skill]
    if missing:
        raise ApiError(f"cannot snapshot skill {skill.get('id')}: missing {missing}")
    triggers = skill.get("triggers")
    if not isinstance(triggers, list) or not all(isinstance(item, str) for item in triggers):
        raise ApiError(f"cannot snapshot skill {skill.get('id')}: invalid triggers")
    lines = [
        "---",
        f"name: {json.dumps(str(skill['name']), ensure_ascii=False)}",
        f"description: {json.dumps(str(skill['description']), ensure_ascii=False)}",
        "triggers:",
        *(f"  - {json.dumps(item, ensure_ascii=False)}" for item in triggers),
        "od:",
        f"  mode: {json.dumps(str(skill['mode']), ensure_ascii=False)}",
        f"  category: {json.dumps(str(skill['category']), ensure_ascii=False)}",
    ]
    if skill.get("upstream"):
        lines.append(f"  upstream: {json.dumps(str(skill['upstream']), ensure_ascii=False)}")
    lines.extend(("---", "", str(skill["body"]).strip("\r\n"), ""))
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


def refresh_skill_safely(
    app_url: str,
    headers: dict[str, str],
    skill_id: str,
    source_dir: Path,
    current: dict[str, Any],
) -> dict[str, Any]:
    """Refresh one skill and restore its API snapshot if installation fails."""
    delete_skill(app_url, headers, skill_id)
    try:
        return install_skill(app_url, headers, skill_id, source_dir)
    except ApiError as install_error:
        try:
            rollback_root = REPO_ROOT / ".project-local" / "task-runtime" / "tmp"
            rollback_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix="skill-rollback-", dir=rollback_root
            ) as temp:
                restore_dir = Path(temp) / skill_id
                write_skill_snapshot(current, restore_dir)
                install_skill(app_url, headers, skill_id, restore_dir)
        except Exception as restore_error:
            raise ApiError(
                f"refresh {skill_id} failed and previous skill restore failed: "
                f"install={install_error}; restore={restore_error}"
            ) from restore_error
        raise ApiError(
            f"refresh {skill_id} failed; restored previous skill: {install_error}"
        ) from install_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app-url",
        default=default_app_url(),
        help="Open Design Web sidecar URL (default: auto-discovered from web/latest.log)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="force official delete/reinstall for all existing managed skills",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show the official API actions only"
    )
    args = parser.parse_args()

    if not SUITE_SRC.is_dir():
        print(f"ERROR: suite source not found: {SUITE_SRC}")
        return 1
    if not args.app_url:
        print("ERROR: Open Design Web URL was not discovered; start OP or pass --app-url")
        return 1

    names = sorted(path.name for path in SUITE_SRC.iterdir() if path.is_dir())
    try:
        verify_sidecar_health(args.app_url)
        workspace_headers = select_workspace(args.app_url)
        installed = list_installed_skills(args.app_url, workspace_headers)
        workspace_id = workspace_headers["x-od-workspace-id"]
        print(f"Open Design: {args.app_url}")
        print(f"Personal Workspace: {workspace_id}")
        print(f"personal design systems: {len(DESIGN_SYSTEM_SOURCES)}")
        print(f"suite skills: {len(names)}")
        print(f"personal expert resources: {len(EXPERT_RESOURCE_SOURCES)}")
        config_before = read_app_config(args.app_url, workspace_headers)

        created_systems, updated_systems = sync_design_systems(
            args.app_url,
            workspace_headers,
            workspace_id,
            dry_run=args.dry_run,
        )

        installed_count = 0
        skipped_count = 0
        for name in names:
            exists = name in installed
            if exists and not args.refresh:
                current = read_skill(args.app_url, workspace_headers, name)
                if skill_matches_source(current, SUITE_SRC / name):
                    print(f"  skip     {name} (content matches)")
                    skipped_count += 1
                    continue
            action = "refresh" if exists else "install"
            if args.dry_run:
                print(f"  [dry-run] {action} {name}")
                continue
            if exists:
                current = read_skill(args.app_url, workspace_headers, name)
                require_managed_skill(current, SUITE_SRC / name)
                skill = refresh_skill_safely(
                    args.app_url,
                    workspace_headers,
                    name,
                    SUITE_SRC / name,
                    current,
                )
            else:
                skill = install_skill(
                    args.app_url, workspace_headers, name, SUITE_SRC / name
                )
            print(
                f"  {action:<8} {name} "
                f"(source={skill.get('source')}, hasBody={skill.get('hasBody')})"
            )
            installed_count += 1

        resource_count = 0
        if args.dry_run:
            for kind, name in EXPERT_RESOURCE_SOURCES:
                print(f"  [dry-run] install/bind {kind}/{name}")
        else:
            def verify_config_preserved() -> None:
                config_after = read_app_config(args.app_url, workspace_headers)
                if config_after != config_before:
                    raise ApiError(
                        "Open Design app-config changed during resource installation; "
                        "refusing to claim user-config preservation"
                    )

            resource_count = install_expert_resources_transactionally(
                args.app_url,
                workspace_headers,
                before_commit=verify_config_preserved,
            )

        state = "DRY-RUN" if args.dry_run else "OK"
        print(
            "design systems created: "
            f"{created_systems}; updated: {updated_systems}"
        )
        print(f"installed: {installed_count}; skipped: {skipped_count}")
        print(f"expert resources installed/bound: {resource_count}")
        if not args.dry_run:
            print("EXPERT_RESOURCE_READBACK=PASS")
            print("USER_CONFIG_PRESERVED=PASS")
        print(f"OP_EXPERT_SUITE_INSTALL={state}")
        return 0
    except (ApiError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())