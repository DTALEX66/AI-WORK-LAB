# SPDX-License-Identifier: MIT
"""Read-only projection of the committed Domain Packs (ODA4-0204, Spec V2).

Domain packs are repository-committed records, not per-project or machine-local
state, so this reads them from the package's own repository root -- the same root
`design-lab/scripts/verify_domain_pack_v2.py` is run against in CI. It installs,
generates, validates-by-hand and adjudicates nothing: it lists what is on disk and
reports the repo's own checker verdict per pack.

Measured in this checkout on 2026-10-08, before this module existed:

* ``design-lab/domain-packs/`` holds 13 pack directories;
* 12 of them pass ``design-lab/scripts/verify_domain_pack_v2.py``;
* ``minigame-design/manifest.json`` declares ``workflow/domain-pack/v1`` and that
  checker rejects it (11 errors; the first is ``'domain' is a required property``,
  because the v1 manifest has no ``domain``/``files`` at all).

The Workbench's ``#/domains`` slot therefore claimed "13 个域包" while the repo's
checker accepts 12. This projection does not settle which number a reader wants; it
reports the directory count, the per-pack verdict and the checker's reasons, all
derived in the call, so no page can carry a hand-typed number again.

Three rules the tests pin, because they are this project's recurring failure modes:

1. the verdict comes from the repo's own checker module, so a pack this route
   presents as VALIDATES cannot be one the checker would reject;
2. a pack that cannot be read, or that the checker could not be run for, gets an
   explicit state (``UNREADABLE`` / ``NOT_CHECKED``) -- it is never omitted from the
   list and never folded into ``VALIDATES``;
3. a manifest field the pack does not declare is ``null``, never a defaulted string,
   so a v1 pack does not start reporting the v2 identity it never claimed.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

SCHEMA_VERSION = "design-lab/domain-pack-readback/v1"
PACK_ROOT_REL = Path("design-lab") / "domain-packs"
CHECKER_REL = Path("design-lab") / "scripts" / "verify_domain_pack_v2.py"
SCHEMA_REL = Path("design-lab") / "schemas" / "domain-pack.schema.json"

#: Domain packs are committed next to this file in a source checkout. They are NOT
#: in the wheel's force-include list (pyproject ships workbench + capability-library
#: inputs only), so an installed wheel reports rootState MISSING rather than
#: pretending the catalog is empty. Closing that is a packaging change, not a UI one.
REPO_ROOT = Path(__file__).resolve().parents[2]


def packaged_root():
    """The repository root a read should use: packaged resources first, checkout second.

    D09/D10 (batch 22): ``REPO_ROOT`` is ``parents[2]`` of this module, which is the
    checkout in a source tree but ``site-packages`` once installed, so an installed
    wheel reported ``rootState MISSING`` -- a truthful but useless answer, since the
    packs themselves ship with the wheel. The wheel copy wins when it carries the pack
    root; otherwise this checkout is used and may still report MISSING for real.
    """
    from importlib.resources import files
    # absolute: `design_lab` is a namespace package, so a `..relative` import from
    # here raises "attempted relative import beyond top-level package".
    from design_lab.runtime.state_resources import repo_resource
    try:
        candidate = files('design_lab').joinpath('resources', 'repo')
        if (candidate / 'design-lab' / 'domain-packs').is_dir():
            return candidate
        # one probe, so a half-populated wheel says which half is missing
        repo_resource('domain-packs')
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        pass
    return REPO_ROOT

VALIDATES = "VALIDATES"
INVALID = "INVALID"
UNREADABLE = "UNREADABLE"
NOT_CHECKED = "NOT_CHECKED"
#: The whole vocabulary this emitter produces. Nothing else may appear in `validation`.
VALIDATION_STATES = (VALIDATES, INVALID, UNREADABLE, NOT_CHECKED)

ROOT_PRESENT = "PRESENT"
ROOT_MISSING = "MISSING"
ROOT_UNREADABLE = "UNREADABLE"

#: A rejected pack can carry a full JSON Schema dump as its first error (the checker
#: prints jsonschema's own message). Bounded so one malformed manifest cannot turn a
#: metadata read into a payload the page has to scroll through; the true total always
#: travels as `validationErrorCount`, so a cut is never mistaken for completeness.
MAX_ERRORS = 12
MAX_ERROR_CHARS = 200


def _describe(error: object) -> str:
    """One line per checker error: jsonschema puts the schema dump after the reason."""
    first = str(error).strip().splitlines()[0] if str(error).strip() else "unspecified"
    return first[:MAX_ERROR_CHARS]


def _load_checker(root: Path) -> tuple[ModuleType | None, str | None]:
    """The repo's own validator, imported by path. Reused rather than reimplemented:
    a read path with its own copy of the rules is a second authority that can disagree
    with CI, which is exactly the shape of the claim this route exists to correct."""
    script = root / CHECKER_REL
    if not script.is_file():
        return None, f"checker not found at {CHECKER_REL.as_posix()}"
    try:
        spec = importlib.util.spec_from_file_location("design_lab_domain_pack_checker",
                                                      script)
        if spec is None or spec.loader is None:
            return None, "checker module could not be loaded"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - a broken checker must not fail the route
        return None, f"checker failed to load: {type(exc).__name__}"
    if not callable(getattr(module, "validate", None)):
        return None, "checker exposes no validate() to reuse"
    return module, None


def _read_manifest(pack: Path) -> tuple[dict | None, str | None]:
    """The manifest as bytes, or the reason it could not be read.

    Absent, unreadable and unparsable all land here together because the reader needs
    the same thing from each: to know this pack has no declared identity to read.
    """
    manifest = pack / "manifest.json"
    if not manifest.is_file():
        return None, "manifest.json is absent"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")), None
    except UnicodeDecodeError:
        return None, "manifest.json is not valid UTF-8"
    except OSError as exc:
        return None, f"manifest.json could not be read ({exc.strerror or exc})"
    except ValueError:
        return None, "manifest.json is not valid JSON"


def _pack_entry(pack: Path, checker: ModuleType | None, checker_note: str | None) -> dict:
    entry = {
        "directory": pack.name,
        "packId": None,
        "version": None,
        "displayName": None,
        "domain": None,
        "manifestSchemaVersion": None,
        "dependencies": None,
        "validation": NOT_CHECKED,
        "validationErrors": [],
        "validationErrorCount": 0,
        "note": None,
    }
    if pack.is_symlink():
        # Following it could leave the repository tree, and silently dropping it would
        # make the list look complete when it is not.
        entry["note"] = ("pack directory is a symbolic link; the read path does not "
                         "follow it, so no verdict is claimed for it")
        return entry
    manifest, read_error = _read_manifest(pack)
    if manifest is None:
        entry["validation"] = UNREADABLE
        entry["validationErrors"] = [read_error]
        entry["validationErrorCount"] = 1
        entry["note"] = "no readable manifest, so this pack declares no identity"
        return entry
    # Identity fields come from the manifest exactly as declared. A v1 manifest simply
    # has no `domain`; defaulting it would be the projection inventing a claim.
    for key, field in (("packId", "pack_id"), ("version", "version"),
                       ("displayName", "display_name"), ("domain", "domain"),
                       ("manifestSchemaVersion", "schema_version")):
        value = manifest.get(field)
        entry[key] = value if isinstance(value, str) and value else None
    dependencies = manifest.get("dependencies")
    if isinstance(dependencies, list):
        entry["dependencies"] = [str(item) for item in dependencies]
    if checker is None:
        entry["note"] = f"no verdict is claimed because the checker was not run: {checker_note}"
        return entry
    # The checker's own verdict and reasons, unaltered. It re-reads the manifest from
    # disk, so a manifest that parsed here can still be rejected there -- both are
    # reported rather than reconciled by a local opinion.
    try:
        ok, errors = checker.validate(pack)
    except Exception as exc:  # noqa: BLE001 - a checker crash is a finding, not a verdict
        entry["validation"] = NOT_CHECKED
        entry["note"] = f"the checker raised {type(exc).__name__} for this pack; no verdict"
        return entry
    entry["validation"] = VALIDATES if ok else INVALID
    entry["validationErrors"] = [_describe(error) for error in errors[:MAX_ERRORS]]
    entry["validationErrorCount"] = len(errors)
    if len(errors) > MAX_ERRORS:
        entry["note"] = (f"{len(errors)} checker errors, first {MAX_ERRORS} reported "
                         "and one line each")
    return entry


def build(root: Path | None = None) -> dict:
    """Return the domain-pack readback for one repository root."""
    root = packaged_root() if root is None else Path(root)
    pack_root = root / PACK_ROOT_REL
    checker, checker_note = _load_checker(root)
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "root": PACK_ROOT_REL.as_posix(),
        "rootState": ROOT_PRESENT,
        "meaning": ("Read-only projection of the committed Domain Pack directories and "
                    "the verdicts design-lab/scripts/verify_domain_pack_v2.py gives them. "
                    "VALIDATES is a STRUCTURAL (E1) statement about files in this "
                    "repository: it is not a host run, not a design verdict and not an "
                    "accepted domain capability."),
        "unmeasuredMeans": ("null = the manifest does not declare that field, or the pack "
                            "could not be read. It is not 0, not empty and not 'none'. "
                            "validation NOT_CHECKED = no checker verdict was produced, "
                            "which is not a pass and not a failure."),
        "validationVocabulary": list(VALIDATION_STATES),
        "checker": {
            "path": CHECKER_REL.as_posix(),
            "state": "LOADED" if checker else "UNAVAILABLE",
            "note": checker_note,
        },
        "sources": {"packRoot": PACK_ROOT_REL.as_posix(),
                    "schema": SCHEMA_REL.as_posix(),
                    "checker": CHECKER_REL.as_posix()},
        "counts": {"packs": 0, "byValidation": {}},
        "packs": [],
    }
    if not pack_root.exists():
        payload["rootState"] = ROOT_MISSING
        return payload
    if not pack_root.is_dir():
        payload["rootState"] = ROOT_UNREADABLE
        payload["checker"]["note"] = None
        return payload
    try:
        directories = sorted((item for item in pack_root.iterdir() if item.is_dir()),
                             key=lambda item: item.name)
    except OSError as exc:
        payload["rootState"] = ROOT_UNREADABLE
        payload["meaning"] = (f"the pack root could not be listed: {exc.strerror or exc}. "
                             "No pack verdict is claimed.")
        return payload
    packs = [_pack_entry(item, checker, checker_note) for item in directories]
    counts: dict[str, int] = {state: 0 for state in VALIDATION_STATES}
    for pack in packs:
        counts[pack["validation"]] += 1
    payload["packs"] = packs
    payload["counts"] = {"packs": len(packs),
                         "byValidation": {key: counts[key] for key in VALIDATION_STATES}}
    return payload


if __name__ == "__main__":  # pragma: no cover - operator probe, not a product path
    json.dump(build(), sys.stdout, ensure_ascii=False, indent=2)
    print()
