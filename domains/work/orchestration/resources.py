"""Resource location API for the migrated WORK orchestration package.

Every path here is anchored to this file's own position in the repository and never
to the current working directory. The migrated modules read registry and contract
files at call time; a read that depended on `cwd` would report "no such file" for
every launcher that starts the sidecar from a different directory (which is exactly
how `platform_collector.py` was written against WORK-LAB: `parents[3] / "config"`,
a depth that only holds for `packages/client-neutral-core/scripts/`).

Placement decision (F01 change class c): the migrated registry files live in this
repository's root `config/` directory, because every already-migrated consumer in
this repository resolves `config/...` against the repository root and reads the
contract schema from `packages/contracts/...`, also relative to the repository root:

- `domains/work/control/composition_root.py:65`   -> `_ROOT / "config" / "software-registry.json"`
- `domains/work/control/composition_root.py:535`  -> `parents[..] / "config" / "adapter-registry.json"`
- `domains/work/control/snapshot_validator.py:97` -> `_contract_verb_vocabulary(_REPO_ROOT)`, which reads
  `config/capability-matrix.json` AND `packages/contracts/schemas/workflow/client-adapter.schema.json`
- `domains/work/workflow_core/repair_pack_projection.py:711` -> `root / "config" / "adapter-registry.json"`

A second copy under `domains/work/resources/` would have forced one of those four
call sites to disagree with the other three, so the root is the single location and
this module is the only place that spells it out.
"""
from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
DOMAIN_ROOT = PACKAGE_ROOT.parent
REPO_ROOT = PACKAGE_ROOT.parents[2]
CONFIG_DIR = REPO_ROOT / "config"

SOFTWARE_REGISTRY = "software-registry.json"
ADAPTER_REGISTRY = "adapter-registry.json"
PROJECT_PLATFORM_MAP = "project-platform-map.json"
CAPABILITY_MATRIX = "capability-matrix.json"
CAPABILITY_CONFORMANCE = "capability-conformance.json"

# The registry files migrated for F01, by file name. `migrated_config_names()` is what the
# migration register and the preflight check compare the on-disk directory against.
MIGRATED_CONFIG_FILES = (
    SOFTWARE_REGISTRY,
    ADAPTER_REGISTRY,
    PROJECT_PLATFORM_MAP,
    CAPABILITY_MATRIX,
    CAPABILITY_CONFORMANCE,
)


def repo_root() -> Path:
    """This repository's root, derived from this file (never from `cwd`)."""
    return REPO_ROOT


def config_dir() -> Path:
    """The directory holding the migrated registry files."""
    return CONFIG_DIR


def config_path(name: str) -> Path:
    """Location of one registry file. Does not stat it: absence is the caller's to report."""
    return CONFIG_DIR / name


def software_registry_path() -> Path:
    return config_path(SOFTWARE_REGISTRY)


def adapter_registry_path() -> Path:
    return config_path(ADAPTER_REGISTRY)


def project_platform_map_path() -> Path:
    return config_path(PROJECT_PLATFORM_MAP)


def missing_config_files() -> tuple[str, ...]:
    """Names of the migrated registry files that are not on disk — an honest gap list."""
    return tuple(name for name in MIGRATED_CONFIG_FILES if not config_path(name).is_file())
