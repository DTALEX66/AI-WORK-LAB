#!/usr/bin/env python3
"""Validate repository skill metadata, references, and optional live-profile parity.

This checker is intentionally secret-free: it reads only SKILL.md metadata and
content hashes. It never loads Hermes configuration, auth stores, plugins, or
provider credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Any

import yaml

KNOWN_PROFILE_SKILLS = {
    "agent-workflow-fortress",
    "codex",
    "github-pr-workflow",
    "hermes-agent",
    "plan",
    "project-gap-analysis",
    "project-data-boundary",
    "sleep-mode",
    "systematic-debugging",
    "test-driven-development",
}
def sha256(path: Path) -> str:
    """Hash canonical UTF-8 text so Windows CRLF and Linux LF agree."""

    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing YAML frontmatter: {path}")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError(f"unterminated YAML frontmatter: {path}")
    data = yaml.safe_load(text[4:end]) or {}
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter must be a mapping: {path}")
    return data


def discover(root: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    result: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(root.rglob("SKILL.md")):
        data = frontmatter(path)
        name = data.get("name")
        version = data.get("version")
        metadata = data.get("metadata")
        hermes = metadata.get("hermes") if isinstance(metadata, dict) else None
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"skill name is missing: {path}")
        if not isinstance(version, (str, int, float)):
            raise ValueError(f"skill version is missing: {path}")
        if not isinstance(hermes, dict):
            raise ValueError(f"metadata.hermes is missing: {path}")
        if name in result:
            raise ValueError(f"duplicate skill name {name!r}: {path}")
        result[name] = (path, data)
    return result


def related_names(data: dict[str, Any]) -> list[str]:
    metadata = data.get("metadata") or {}
    hermes = metadata.get("hermes") if isinstance(metadata, dict) else {}
    values = hermes.get("related_skills", []) if isinstance(hermes, dict) else []
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise ValueError("metadata.hermes.related_skills must be a string list")
    return values


def load_source_roots(repo_root: Path, manifest: dict) -> list[Path]:
    """Resolve the skill roots DECLARED by the manifest instead of guessing one.

    The earlier implementation hard-coded ``repo_root / "skills"``, a path that
    does not exist in this repository. Discovery therefore always found zero
    skills ("skills=0") and the coverage check could never fail, which made a
    passing gate meaningless for source-skill coverage.
    """

    declared = manifest.get("source_roots") if isinstance(manifest, dict) else None
    if not isinstance(declared, list) or not declared:
        raise ValueError("skill provenance manifest must declare a non-empty source_roots list")
    if not all(isinstance(item, str) and item.strip() for item in declared):
        raise ValueError("skill provenance manifest source_roots must be non-empty strings")
    root = repo_root.resolve()
    resolved: list[Path] = []
    for relative in declared:
        path = (repo_root / relative).resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"declared source root escapes the repository: {relative}")
        if not path.is_dir():
            raise ValueError(f"declared source root does not exist: {relative}")
        resolved.append(path)
    return resolved


def discover_roots(roots: list[Path]) -> dict[str, tuple[Path, dict[str, Any]]]:
    """Discover SKILL.md across every declared root, rejecting cross-root duplicates."""

    combined: dict[str, tuple[Path, dict[str, Any]]] = {}
    for root in roots:
        for name, item in discover(root).items():
            if name in combined:
                raise ValueError(f"duplicate skill name across source roots: {name} ({item[0]})")
            combined[name] = item
    return combined


def validate(repo_root: Path, manifest_path: Path, live_root: Path | None = None) -> int:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("skill provenance manifest schema_version must be 1")
    source = discover_roots(load_source_roots(repo_root, manifest))
    if not source:
        raise ValueError("zero source skills discovered under the declared source_roots; expected a non-empty set")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("skill provenance manifest entries must be a list")

    for name, (_, data) in source.items():
        missing = sorted(set(related_names(data)) - (set(source) | KNOWN_PROFILE_SKILLS))
        if missing:
            raise ValueError(f"{name} references unknown source skills: {', '.join(missing)}")

    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("provenance entry must be a mapping")
        name = entry.get("name")
        source_rel = entry.get("source")
        if not isinstance(name, str) or not isinstance(source_rel, str):
            raise ValueError("provenance entry requires name and source")
        if name in seen:
            raise ValueError(f"duplicate provenance entry: {name}")
        seen.add(name)
        if source_rel.startswith("profile-live-only/"):
            source_path = None
        else:
            source_path = (repo_root / source_rel).resolve()
            if not source_path.is_file():
                raise ValueError(f"provenance source does not exist: {source_rel}")
            data = frontmatter(source_path)
            if data.get("name") != name:
                raise ValueError(f"provenance name mismatch: {source_rel}")
            expected_sha = entry.get("source_sha256")
            if expected_sha != sha256(source_path):
                raise ValueError(f"source SHA drift: {name}")
        if not entry.get("trust") or not entry.get("permission") or "enabled" not in entry:
            raise ValueError(f"provenance trust/permission/enabled missing: {name}")
        # Offline self-consistency (added AG-08b, 2026-10-01). `live_sha256` is
        # only checked against a real deployment root when --live-root is passed,
        # and the canonical CI gate does NOT pass it (it prints
        # live_checked=False). So a stale live_sha256 could sit in the manifest
        # undetected: model-switch carried a digest that differed from its own
        # source file for an unknown period.
        #
        # Where `live` equals `source` (all entries today, because the live field
        # holds a repo-relative path rather than a deployment target), the two
        # digests describe the SAME file and must therefore agree. source_sha256
        # is already validated against disk above, so this comparison needs no
        # external root and closes the silent-drift hole offline.
        if entry.get("live") == source_rel:
            if entry.get("live_sha256") != entry.get("source_sha256"):
                raise ValueError(
                    f"live/source self-inconsistency: {name} records live==source but "
                    "live_sha256 != source_sha256 (the two digests describe the same file)"
                )
        # AG-06o (audit F04): content that exists only in the deployed copy is
        # destroyed by the next single-direction publish, silently, because the
        # repository source does not contain it. A verification that only compares
        # digests cannot see that; it needs the divergence named. When an entry
        # declares it, the declaration must be complete enough to act on.
        divergence = entry.get("live_content_divergence")
        if isinstance(divergence, dict) and divergence.get("live_ahead_of_source"):
            if not divergence.get("live_only_lessons") and not divergence.get(
                "live_only_references"
            ):
                raise ValueError(
                    f"live divergence without content: {name} claims the deployed copy is "
                    "ahead of the source but names no lesson or reference that only the "
                    "deployed copy has"
                )
            if not divergence.get("remediation_path"):
                raise ValueError(
                    f"live divergence without remediation: {name} records content that a "
                    "redeploy would destroy but names no path to land it"
                )
            if not divergence.get("effect_if_redeployed_without_review"):
                raise ValueError(
                    f"live divergence without impact: {name} does not state what a "
                    "redeploy would lose"
                )
        if live_root is not None:
            live_rel = entry.get("live")
            if not isinstance(live_rel, str):
                raise ValueError(f"live path missing: {name}")
            live_path = (live_root / live_rel).resolve()
            if not live_path.is_file():
                raise ValueError(f"live skill missing: {name}: {live_path}")
            live_sha = sha256(live_path)
            if entry.get("live_sha256") != live_sha:
                raise ValueError(f"live SHA drift: {name}")
    if not set(source).issubset(seen):
        missing = sorted(set(source) - seen)
        raise ValueError("manifest does not cover all repository skills: " + ", ".join(missing))
    print(f"SKILL_PROVENANCE_PASS skills={len(source)} live_checked={live_root is not None}")
    return 0


def build_manifest(
    repo_root: Path,
    manifest_path: Path,
    live_root: Path | None = None,
    *,
    allow_shrink: bool = False,
) -> dict[str, Any]:
    """Rebuild the manifest, refusing the destructive cases.

    Refuses when the declared roots are missing/empty, when discovery yields zero
    skills, or when the entry count would drop, so `--write` can never silently
    empty the inventory.

    A refresh recomputes HASHES ONLY. An earlier revision also reset
    ``trust``/``enabled``/``permission``/``profile_scope`` to defaults and rewrote
    ``live`` to the source path, which silently promoted a quarantined entry to
    enabled and broke a genuine live mapping (independent-review R3). Existing
    human decisions and real ``live`` targets are therefore carried across
    verbatim, and a newly discovered skill enters as pending review instead of
    being enabled.
    """

    existing: dict[str, Any] = {}
    if manifest_path.is_file():
        existing = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if not isinstance(existing, dict) or existing.get("schema_version") != 1:
            raise ValueError("refusing to rewrite a manifest whose schema_version is not 1")
    roots = load_source_roots(repo_root, existing)
    source = discover_roots(roots)
    if not source:
        raise ValueError("refusing to write a manifest with zero discovered skills")
    previous_entries = [item for item in (existing.get("entries") or []) if isinstance(item, dict)]
    previous = len(previous_entries)
    if previous and len(source) < previous and not allow_shrink:
        raise ValueError(
            f"refusing to shrink the manifest: {previous} -> {len(source)} entries (pass --allow-shrink to override)"
        )

    # Carried across verbatim: everything that records a human decision or a real
    # deployment target. Only hashes and the version string are refreshed.
    carried_fields = ("trust", "enabled", "permission", "profile_scope", "live", "live_sha256")
    carried: dict[str, dict[str, Any]] = {}
    for item in previous_entries:
        name = item.get("name")
        if isinstance(name, str):
            carried[name] = {key: item[key] for key in carried_fields if key in item}

    root_rel = repo_root / "skills"
    entries: list[dict[str, Any]] = []
    for name, (path, data) in sorted(source.items()):
        rel = path.relative_to(repo_root).as_posix()
        previous_entry = carried.get(name)
        if previous_entry is None:
            # Newly discovered: pending review, NOT enabled.
            try:
                home_relative = "skills/" + path.relative_to(roots[0]).as_posix()
            except ValueError:  # pragma: no cover - defensive
                home_relative = rel
            entry: dict[str, Any] = {
                "name": name,
                "source": rel,
                "live": home_relative,
                "source_sha256": sha256(path),
                "version": str(data["version"]),
                "trust": "pending-review",
                "enabled": False,
                "permission": "observe-only",
                "profile_scope": "default",
            }
        else:
            entry = {
                "name": name,
                "source": rel,
                "source_sha256": sha256(path),
                "version": str(data["version"]),
            }
            for key, value in previous_entry.items():
                entry[key] = value
        if live_root is not None:
            live_rel = str(entry.get("live") or "")
            live_path = live_root / live_rel
            if not live_path.is_file():
                raise ValueError(f"cannot build manifest: live skill missing: {live_path}")
            entry["live_sha256"] = sha256(live_path)
        entries.append(entry)
    declared_roots = [str(item) for item in existing.get("source_roots") or []]
    return {
        "schema_version": 1,
        "profile_scope": str(existing.get("profile_scope") or "default"),
        "source_roots": declared_roots,
        "entries": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--live-root", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--allow-shrink",
        action="store_true",
        help="permit a manifest rewrite that drops entries (refused by default)",
    )
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    live = args.live_root.resolve() if args.live_root else None
    if args.write:
        built = build_manifest(repo, args.manifest, live, allow_shrink=args.allow_shrink)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        # Validate the COMPLETE candidate before touching the real manifest: an
        # earlier revision wrote first and validated afterwards, so a failing
        # validation could leave a changed artifact behind (R3).
        staging = args.manifest.with_name(args.manifest.name + ".candidate")
        try:
            staging.write_text(yaml.safe_dump(built, allow_unicode=True, sort_keys=False), encoding="utf-8")
            validate(repo, staging, live)
        except BaseException:
            staging.unlink(missing_ok=True)
            raise
        os.replace(staging, args.manifest)
    return validate(repo, args.manifest, live)


if __name__ == "__main__":
    raise SystemExit(main())
