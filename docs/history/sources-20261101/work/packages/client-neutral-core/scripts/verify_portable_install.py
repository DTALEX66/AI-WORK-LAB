#!/usr/bin/env python
"""Verify Workflow-assistance can populate an isolated empty Hermes home.

The default mode is a structural portability contract and never invokes
Hermes. ``--runtime`` explicitly runs ``hermes config check`` against the same
isolated temporary home. Neither mode reads a real home, copies credentials,
or issues network/model requests.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml


MANIFEST_SCHEMA_VERSION = 1
SUPPORTED_RUNTIME_FEATURES = {
    "portable_manifest",
    "project_data_boundary",
    "client_neutral_adapter_contract",
    "platform_toolsets.cli",
    "sessions.auto_prune=false",
    "memory.enabled",
    "hermes_config_check",
}


def isolated_runtime_root(repo: Path) -> Path:
    """Return the only reviewed root for verifier-created Homes."""

    return repo / ".hermes" / "task-runtime" / "portable-install"


def validate_isolated_home(repo: Path, home: Path) -> None:
    """Reject arbitrary empty directories before the verifier writes anything."""

    runtime_root = isolated_runtime_root(repo).resolve()
    if not home.is_relative_to(runtime_root):
        raise RuntimeError(
            "isolated Hermes home must be under the project runtime root: "
            f"{runtime_root}"
        )


def load_sync(repo: Path):
    path = repo / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
    spec = importlib.util.spec_from_file_location("workflow_sync_verify", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sync script: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_manifest(repo: Path) -> dict:
    path = repo / "packages/client-neutral-core/workflow-manifest.yaml"
    if not path.exists():
        raise RuntimeError("workflow-manifest.yaml is required")
    manifest = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RuntimeError(f"workflow manifest schema_version must be {MANIFEST_SCHEMA_VERSION}")
    compatibility = manifest.get("compatibility")
    if not isinstance(compatibility, dict):
        raise RuntimeError("workflow manifest compatibility must be a mapping")
    if compatibility.get("official_schema") != "capability-discovery":
        raise RuntimeError("workflow manifest official_schema must use capability-discovery")
    if compatibility.get("official_config_root") != "capability-discovery":
        raise RuntimeError("workflow manifest official_config_root must use capability-discovery")
    features = compatibility.get("required_runtime_features")
    if not isinstance(features, list) or not features or not all(isinstance(item, str) for item in features):
        raise RuntimeError("workflow manifest required_runtime_features must be a non-empty string list")
    unknown = sorted(set(features) - SUPPORTED_RUNTIME_FEATURES)
    if unknown:
        raise RuntimeError("workflow manifest has unsupported runtime features: " + ", ".join(unknown))
    return compatibility


def run_isolated_hermes_config_check(home: Path) -> None:
    """Run the real Hermes config check against the isolated home only."""

    executable = shutil.which("hermes")
    if executable is None:
        raise RuntimeError("hermes executable is required for --runtime verification")
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    result = subprocess.run(
        [executable, "config", "check"],
        cwd=home,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("isolated Hermes config check failed")


def has_pinned_context7_package(args: object) -> bool:
    """Require an explicit Context7 package version for reproducible installs."""

    return isinstance(args, list) and any(
        isinstance(arg, str)
        and arg.startswith("@upstash/context7-mcp@")
        and not arg.endswith("@latest")
        for arg in args
    )


def verify(repo: Path, home: Path, *, run_runtime: bool = False) -> list[str]:
    repo = repo.resolve()
    home = home.resolve()
    if not (repo / "config/managed-config-schema.yaml").exists():
        raise RuntimeError("managed-config-schema.yaml is required")
    validate_isolated_home(repo, home)
    compatibility = load_manifest(repo)

    if home.exists():
        if not home.is_dir():
            raise RuntimeError("isolated Hermes home must be a directory")
        if any(home.iterdir()):
            raise RuntimeError("isolated Hermes home must be empty")
    else:
        home.mkdir(parents=True, exist_ok=False)
    sync = load_sync(repo)
    managed_roots = sync.load_managed_skill_roots(repo)
    managed_binaries = sync.load_managed_binary_paths(repo)
    # Home consumes repo-owned assets at the flat layout (skills/, bin/);
    # keep repo-relative lists for provenance checks and home-relative for inventory.
    home_roots = tuple(sync._repo_rel_to_home_rel(r) for r in managed_roots)
    home_binaries = tuple(sync._repo_rel_to_home_rel(r) for r in managed_binaries)
    managed_file_mappings = sync.load_managed_file_mappings(repo)
    provenance_path = repo / "config/skill-provenance.yaml"
    provenance = yaml.safe_load(provenance_path.read_text(encoding="utf-8")) or {}
    entries = provenance.get("entries") if isinstance(provenance, dict) else None
    if not isinstance(entries, list):
        raise RuntimeError("skill provenance entries must be a list")
    provenance_roots = {
        Path(entry["source"]).parent.as_posix()
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("source"), str)
    }
    if set(managed_roots) != provenance_roots:
        raise RuntimeError("managed skill roots must exactly match skill provenance entries")
    sync.deploy_portable(
        repo,
        home,
        apply=True,
        include_backup=False,
        allow_project_runtime_home=True,
    )
    # This verifier owns a newly created, explicitly isolated empty Home. It
    # may construct the portable config there for compatibility checks; the
    # repo-to-live synchronizer deliberately never promotes mixed-ownership
    # config.yaml into an existing user Home.
    sync.merge_live_config(repo, home, apply=True, wrapper_root=home)

    config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8")) or {}
    runtime_feature_checks = {
        "platform_toolsets.cli": bool(config.get("platform_toolsets", {}).get("cli")),
        "sessions.auto_prune=false": config.get("sessions", {}).get("auto_prune") is False,
        "memory.enabled": (
            config.get("memory", {}).get("memory_enabled") is True
            and config.get("memory", {}).get("user_profile_enabled") is True
        ),
    }
    missing_features = [
        feature
        for feature in compatibility["required_runtime_features"]
        if feature in runtime_feature_checks and not runtime_feature_checks[feature]
    ]
    if missing_features:
        raise RuntimeError("isolated config lacks manifest runtime features: " + ", ".join(missing_features))

    context7 = (config.get("mcp_servers") or {}).get("context7")
    if not isinstance(context7, dict):
        raise RuntimeError("isolated config missing context7 mapping")
    preferred_wrapper = home / "bin/hermes-npx.cmd" if os.name == "nt" else home / "bin/hermes-npx"
    wrapper = preferred_wrapper if preferred_wrapper.exists() else None
    if wrapper is None or Path(str(context7.get("command", ""))).resolve() != wrapper.resolve():
        raise RuntimeError("isolated config context7 command does not reference the copied wrapper")
    args = context7.get("args") or []
    if not has_pinned_context7_package(args):
        raise RuntimeError("isolated config context7 package must use a pinned version")

    required = {
        "manifest.capability_discovery": (
            compatibility.get("official_schema") == "capability-discovery"
            and compatibility.get("official_config_root") == "capability-discovery"
        ),
        "manifest.required_runtime_features": True,
        "model_provider_neutral": all(
            key not in config
            for key in ("model", "fallback_providers", "model_picker", "quick_commands")
        ),
        "display.busy_input_mode": config.get("display", {}).get("busy_input_mode") == "queue",
        "display.language": config.get("display", {}).get("language") == "zh",

        "sessions.auto_prune": config.get("sessions", {}).get("auto_prune") is False,
        "memory.enabled": runtime_feature_checks["memory.enabled"],
        "platform_toolsets.cli": runtime_feature_checks["platform_toolsets.cli"],
        "context7": "context7" in (config.get("mcp_servers") or {}),
        "context7.wrapper": True,
        "managed_skills.exact_inventory": len(home_roots) == 13
        and all((home / relative / "SKILL.md").is_file() for relative in home_roots),
        "managed_binaries.exact_inventory": len(home_binaries) == 6
        and all((home / relative).is_file() for relative in home_binaries),
        "managed_root_files.exact_inventory": all(
            (home / target).is_file()
            and (home / target).read_bytes() == (repo / source).read_bytes()
            for source, target in managed_file_mappings
        ),
    }
    failed = [name for name, ok in required.items() if not ok]
    if failed:
        raise RuntimeError("isolated config missing: " + ", ".join(failed))
    if (home / ".env").exists() or (home / "auth.json").exists():
        raise RuntimeError("isolated verification must not create credentials")
    if run_runtime:
        run_isolated_hermes_config_check(home)
    return sorted(required)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify portable workflow installation into an isolated Hermes home.")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--home", type=Path, help="Empty isolated Hermes home; omitted uses a temporary directory.")
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="Run the real Hermes config check against the isolated home after structural verification.",
    )
    args = parser.parse_args(argv)
    if args.home:
        checks = verify(args.repo, args.home, run_runtime=args.runtime)
    else:
        runtime = isolated_runtime_root(args.repo.resolve())
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as raw:
            checks = verify(args.repo, Path(raw) / "hermes", run_runtime=args.runtime)
    if args.runtime:
        print("PORTABLE_INSTALL_VERIFY_PASS checks=" + ",".join(checks) + ",hermes_config_check")
    else:
        print("STRUCTURAL_PORTABLE_PASS checks=" + ",".join(checks))
        print("RUNTIME_COMPATIBILITY_UNVERIFIED hermes_config_check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
