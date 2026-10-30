# SPDX-License-Identifier: MIT
"""DL-P1-111: Penpot adapter contract, ``.penpot`` file boundary and import plan.

What this module is
-------------------
A *declaration*, a *structural validator* and a *plan*, nothing more. It states how
DESIGN-LAB would talk to a locally running Penpot, what a ``.penpot`` file is and
how a future importer would treat it, and then stops. It performs no import, no
export, no live API call, no host read, no process launch and no network access:

* ``ADAPTER`` conforms to the repository's existing
  ``design-lab/schemas/adapter-contract.schema.json`` with ``status: "structural"``
  and ``mode: "external-local-api"``; every capability is ``supported: false``.
  Penpot being installed on this machine is user-provided existence information,
  not a verified host run.
* ``file_boundary()`` describes the ``.penpot`` container and the read policy.
* ``validate_penpot_archive(data)`` checks the *structure* of a ``.penpot`` archive
  the caller already has the bytes of -- it does not merely ask "is this a ZIP".
  A Penpot v3 export is a ZIP holding ``manifest.json`` at its root, JSON metadata
  and binary assets, so the validator reads the central directory (names and sizes)
  and ``manifest.json``, and then checks the archive's internal references: path
  traversal, duplicate entries, declared files that are absent or declared twice,
  declared sizes that disagree with the ZIP metadata, and undeclared payload
  entries outside a documented allow-list. It extracts nothing, writes nothing and
  never opens Penpot. Passing it is **not** evidence that Penpot can open the file:
  no live Penpot run happened (``live_run: NOT_EXECUTED``).
* ``validate_adapter(adapter)`` applies that schema plus the extra rule that a
  ``structural`` adapter may not claim a capability that needs a live host run.
* ``import_plan(path)`` returns a read-only step plan that ends with the exact
  terminator ``requires a live Penpot run: NOT_EXECUTED``.

Evidence is E1 (STRUCTURAL) only: a schema-valid declaration, offline structural
checks over caller-supplied bytes and unit tests against a synthetic archive.
No live Penpot import or export ran, and this module never reads a user's
personal libraries.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path, PureWindowsPath

from ..runtime.paths import PROJECT_ROOT
from . import InteropError, load_schema, resource_registry, schema_errors

TASK_ID = "DL-P1-111"
SCHEMA_VERSION = "design-lab/interop-penpot-adapter/v1"
ADAPTER_SCHEMA_PATH = PROJECT_ROOT / "design-lab/schemas/adapter-contract.schema.json"
SCHEMA_PATH = PROJECT_ROOT / "design-lab/schemas/interop-penpot-adapter.schema.json"

PENPOT_EXTENSION = ".penpot"

#: The ``.penpot`` index entry; a Penpot v3 export keeps it at the archive root.
MANIFEST_ENTRY = "manifest.json"
#: Keys ``manifest.json`` may carry the declared file list under (first present wins).
DECLARED_FILE_KEYS = ("files", "entries")
#: Name keys inside one declared file record.
DECLARED_FILE_NAME_KEYS = ("name", "path")
#: Size keys inside one declared file record.
DECLARED_FILE_SIZE_KEYS = ("size", "bytes")
#: Undeclared entries that are allowed: JSON metadata, ...
ALLOWLISTED_UNDECLARED_SUFFIXES = (".json",)
#: ... and preview/thumbnail images.
ALLOWLISTED_UNDECLARED_IMAGE_NAMES = ("preview", "thumbnail", "thumb")
ALLOWLISTED_UNDECLARED_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")
#: Cap on the manifest this validator will read, so a hostile archive cannot
#: exhaust memory through ``manifest.json`` alone.
MAX_MANIFEST_BYTES = 8 * 1024 * 1024


#: Marker a structural adapter must carry in ``evidence.note``.
LIVE_RUN_MARKER = "live_run=NOT_EXECUTED"
TERMINATOR = "requires a live Penpot run: NOT_EXECUTED"

#: Capabilities that are verifiable without a live host run. A ``structural``
#: adapter may only declare ``supported: true`` for these.
STRUCTURAL_SAFE_CAPABILITIES = frozenset({"tokens.dtcg.map", "schema.validate",
                                          "file.boundary.describe"})
#: Capabilities that require a live Penpot and therefore can never be
#: ``supported: true`` while the adapter status is ``structural``.
LIVE_HOST_CAPABILITIES = frozenset({
    "penpot.import", "penpot.export", "penpot.file.read", "penpot.file.write",
    "penpot.render", "penpot.library.read",
})

#: The adapter declaration DESIGN-LAB owns for a local Penpot. No host run backs it.
ADAPTER = {
    "adapter_id": "adapter-penpot-local",
    "tool": "Penpot",
    "capabilities": [
        {
            "name": "penpot.file.read",
            "supported": False,
            "note": "no importer exists and no Penpot read ran; the archive can only be checked "
                    "structurally (validate_penpot_archive) on bytes the caller already has, which "
                    "is not a Penpot read",
        },
        {
            "name": "penpot.import",
            "supported": False,
            "note": "requires a live Penpot run: NOT_EXECUTED",
        },
        {
            "name": "penpot.export",
            "supported": False,
            "note": "requires a live Penpot run: NOT_EXECUTED",
        },
        {
            "name": "tokens.dtcg.map",
            "supported": False,
            "note": "DTCG mapping is structural (DL-P0-110) and is declared unsupported here "
                    "because no Penpot round trip has verified it",
        },
    ],
    "status": "structural",
    "mode": "external-local-api",
    "license": "MPL-2.0",
    "fallback": "user-exported DTCG tokens and SVGs; no adapter execution",
    "evidence": {
        "level": "E1",
        "runtime_version": None,
        "task_ids": [TASK_ID],
        "artifact_paths": [
            "src/design_lab/interop/penpot.py",
            "design-lab/schemas/interop-penpot-adapter.schema.json",
        ],
        "note": "structural contract only (E1): the adapter declaration validates against "
                "adapter-contract.schema.json and the .penpot boundary is described, but no live "
                "Penpot import or export ran. live_run=NOT_EXECUTED",
    },
    "rollback": "the adapter performs no host mutation and no host call: revert the contract change "
                "in git and delete the mapping report under .project-local",
}


def _fail(message: str) -> "InteropError":
    return InteropError(message)


def adapter() -> dict:
    """A deep copy of the Penpot adapter declaration (callers cannot mutate the constant)."""
    return json.loads(json.dumps(ADAPTER))


def file_boundary() -> dict:
    """Describe the ``.penpot`` import/export boundary.

    A ``.penpot`` file is a ZIP container whose ``manifest.json`` indexes the file's
    pages and objects. That internal schema is owned and versioned by Penpot, not by
    DESIGN-LAB, and is not a public stable contract. DESIGN-LAB therefore treats a
    ``.penpot`` file as an opaque read-only *external asset*: it is never written,
    never rewritten in place, and never inspected without a documented importer and
    the owner's consent. A user's personal Penpot libraries and profile data are
    never read. This function returns a static description and reads nothing.
    """
    return {
        "task_id": TASK_ID,
        "asset_kind": "penpot-file",
        "extension": PENPOT_EXTENSION,
        "container": {
            "format": "zip",
            "index_entry": "manifest.json",
            "index_is_json": True,
            "schema_owner": "Penpot",
            "stability": "Penpot's internal file schema is not a public stable contract; it is "
                         "verified against a live Penpot version only, which has not happened here",
        },
        "access": {
            "read_policy": "opaque-read-only-external-asset",
            "write_policy": "never",
            "copy_policy": "a copy may only be written under .project-local when a documented "
                           "importer exists and the owner approved the copy",
            "user_personal_libraries": "NEVER_READ",
        },
        "state": {
            "importer": "NOT_IMPLEMENTED",
            "exporter": "NOT_IMPLEMENTED",
            "live_run": "NOT_EXECUTED",
            "evidence_level": "E1",
        },
        "validation": {
            "entry_point": "validate_penpot_archive",
            "scope": "structure of the container and the references inside it, never its meaning",
            "reads": [
                "the ZIP central directory (entry names and recorded sizes)",
                "manifest.json inside the archive",
            ],
            "extraction": "NEVER",
            "declared_file_list_keys": list(DECLARED_FILE_KEYS),
            "undeclared_allow_list": [
                MANIFEST_ENTRY,
                "*.json (JSON metadata)",
                "preview/thumbnail images named preview/thumbnail/thumb with an image suffix "
                "(" + ", ".join(ALLOWLISTED_UNDECLARED_IMAGE_SUFFIXES) + ")",
            ],
            "rejects": [
                "path traversal: a '..' or '.' segment, an absolute or drive path, a backslash",
                "duplicate entry names in the central directory",
                "a declared file that is absent, declared twice, or whose declared size disagrees "
                "with the ZIP metadata",
                "an undeclared payload entry outside the allow-list",
                "a missing, non-JSON or file-list-less manifest.json",
            ],
            "live_run": "NOT_EXECUTED",
            "evidence_level": "E1",
            "note": "a valid archive is structural evidence about the container only; it is not a "
                    "Penpot import, not a Penpot readback and not proof that a Penpot version can "
                    "open the file",
        },
        "prohibited": [
            "writing into a .penpot file or rewriting it in place",
            "reading a user's personal libraries, profile or account data",
            "opening a Penpot API session from DESIGN-LAB test or validation code",
            "presenting an unverified Penpot version, capability or import result as verified",
        ],
        "notes": [
            "DESIGN-LAB never owns Penpot's private database or a user's asset library (AGENTS.md).",
            "Token interchange with Penpot goes through DTCG (DL-P0-110), not through this adapter.",
        ],
    }


# --------------------------------------------------------------------------- #
# .penpot archive structure
# --------------------------------------------------------------------------- #

def _check_entry_name(name, where: str) -> str:
    """Lexically validate one archive entry name. Never touches the filesystem."""
    if not isinstance(name, str) or not name.strip():
        raise _fail(f"{where} must be a nonempty entry name")
    if "\x00" in name:
        raise _fail(f"{where} {name!r} contains a NUL character")
    if "\\" in name:
        raise _fail(
            f"{where} {name!r} uses a backslash; .penpot entries are named with forward slashes"
        )
    if name.startswith("/"):
        raise _fail(
            f"{where} {name!r} is an absolute path; every .penpot entry must be relative to the "
            "archive root"
        )
    if PureWindowsPath(name).drive:
        raise _fail(
            f"{where} {name!r} names a drive; every .penpot entry must be relative to the archive root"
        )
    stripped = name[:-1] if name.endswith("/") else name
    if not stripped:
        raise _fail(f"{where} {name!r} has no file name")
    for segment in stripped.split("/"):
        if segment == "..":
            raise _fail(f"{where} {name!r} escapes the archive root: it contains a '..' segment")
        if segment in ("", "."):
            raise _fail(f"{where} {name!r} contains an empty or '.' path segment")
    return name


def _allowlisted_undeclared(name: str) -> bool:
    """Documented allow-list: entries that may exist without being declared."""
    if name == MANIFEST_ENTRY:
        return True
    lowered = name.lower()
    if lowered.endswith(ALLOWLISTED_UNDECLARED_SUFFIXES):
        return True
    stem, dot, suffix = lowered.rpartition(".")
    if not dot:
        return False
    basename = stem.rsplit("/", 1)[-1]
    return (f".{suffix}" in ALLOWLISTED_UNDECLARED_IMAGE_SUFFIXES
            and basename in ALLOWLISTED_UNDECLARED_IMAGE_NAMES)


def _declared_files(manifest):
    """Read the declared file list out of a parsed ``manifest.json``."""
    if not isinstance(manifest, dict):
        raise _fail(f"{MANIFEST_ENTRY} must be a JSON object; found {type(manifest).__name__}")
    key = next((candidate for candidate in DECLARED_FILE_KEYS if candidate in manifest), None)
    if key is None:
        raise _fail(
            f"{MANIFEST_ENTRY} declares no file list under "
            + " or ".join(repr(candidate) for candidate in DECLARED_FILE_KEYS)
            + "; a Penpot v3 export lists the JSON metadata and binary assets it indexes"
        )
    entries = manifest[key]
    if not isinstance(entries, list) or not entries:
        raise _fail(f"{MANIFEST_ENTRY} {key!r} must be a nonempty array of file records")
    declared: dict[str, int | None] = {}
    for index, entry in enumerate(entries):
        where = f"{MANIFEST_ENTRY} {key}[{index}]"
        size = None
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            name = next((entry[item] for item in DECLARED_FILE_NAME_KEYS if item in entry), None)
            if name is None:
                raise _fail(
                    f"{where} must name a file with "
                    + " or ".join(repr(item) for item in DECLARED_FILE_NAME_KEYS)
                )
            size = next((entry[item] for item in DECLARED_FILE_SIZE_KEYS if item in entry), None)
        else:
            raise _fail(f"{where} must be a file name or an object naming one")
        _check_entry_name(name, where)
        if name in declared:
            raise _fail(
                f"{where} declares {name!r} a second time; every archive entry must be declared once"
            )
        if size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 0):
            raise _fail(
                f"{where} size for {name!r} must be a non-negative integer number of bytes; "
                f"found {size!r}"
            )
        declared[name] = size
    return declared, key


def validate_penpot_archive(data: bytes) -> dict:
    """Validate the structure of a ``.penpot`` archive given as bytes.

    A Penpot v3 export is a ZIP container with ``manifest.json`` at its root, JSON
    metadata and binary assets. This function checks the container and the
    references *inside* it -- not merely "it is a ZIP" -- by reading the central
    directory (entry names and recorded sizes) through :mod:`zipfile` on an
    in-memory :class:`io.BytesIO`, plus ``manifest.json``. Nothing is extracted,
    nothing is written and Penpot is never opened.

    Fails closed (naming the offending entry) when:

    * the bytes are not a well-formed ZIP, or the central directory is empty;
    * an entry name is empty, NUL-bearing, backslash-separated, absolute or a drive
      path, or contains ``..`` / ``.`` / empty segments (path traversal);
    * the same entry name appears twice;
    * ``manifest.json`` is missing from the root, is not UTF-8 JSON, is not an
      object, or declares no file list under ``files``/``entries``;
    * a declared file is absent, is declared twice, or declares a size that
      disagrees with the byte size in the ZIP metadata;
    * an entry that is not declared is outside the documented allow-list
      (:data:`MANIFEST_ENTRY`, other ``*.json`` metadata, ``preview``/``thumbnail``
      images) -- an undeclared payload file is rejected rather than ignored.

    The returned report is structural (E1). It states that the container is
    internally consistent; it is **not** a Penpot import, not a readback and not
    evidence that a Penpot version can open the file: ``live_run`` is
    ``NOT_EXECUTED`` here and no live Penpot run happened anywhere in this module.
    """
    if isinstance(data, memoryview):
        data = data.tobytes()
    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise _fail(
            "a .penpot archive must be passed as bytes; this validator reads no file from disk"
        )
    if not data:
        raise _fail("the .penpot archive is empty; a Penpot export is a ZIP container")

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = archive.namelist()
            if not infos:
                raise _fail(
                    "the .penpot central directory is empty; the archive declares no entries"
                )
            seen: set[str] = set()
            for name in names:
                _check_entry_name(name, "archive entry")
                if name in seen:
                    raise _fail(
                        f"the .penpot archive lists the entry {name!r} more than once; duplicate "
                        "entries make the archive ambiguous"
                    )
                seen.add(name)
            if MANIFEST_ENTRY not in seen:
                raise _fail(
                    f"the .penpot archive has no {MANIFEST_ENTRY} at its root; a Penpot v3 export "
                    "indexes its JSON metadata and binary assets from that manifest"
                )
            manifest_info = archive.getinfo(MANIFEST_ENTRY)
            if manifest_info.file_size > MAX_MANIFEST_BYTES:
                raise _fail(
                    f"{MANIFEST_ENTRY} records {manifest_info.file_size} bytes, above the "
                    f"{MAX_MANIFEST_BYTES}-byte limit this validator reads"
                )
            try:
                raw = archive.read(MANIFEST_ENTRY)
            except RuntimeError as exc:  # encrypted or otherwise unreadable entry
                raise InteropError(f"{MANIFEST_ENTRY} cannot be read: {exc}") from exc
            try:
                manifest = json.loads(raw.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise InteropError(f"{MANIFEST_ENTRY} is not UTF-8 text: {exc}") from exc
            except json.JSONDecodeError as exc:
                raise InteropError(f"{MANIFEST_ENTRY} is not valid JSON: {exc}") from exc
    except zipfile.BadZipFile as exc:
        raise InteropError(
            f"the .penpot container is not a well-formed ZIP archive: {exc}"
        ) from exc
    except NotImplementedError as exc:
        raise InteropError(
            f"the .penpot ZIP uses a feature this validator cannot read: {exc}"
        ) from exc

    info_by_name = {info.filename: info for info in infos}
    file_names = [name for name in names if not name.endswith("/")]
    directory_names = [name for name in names if name.endswith("/")]

    declared, declared_key = _declared_files(manifest)
    for name, size in declared.items():
        info = info_by_name.get(name)
        if info is None:
            raise _fail(
                f"{MANIFEST_ENTRY} declares {name!r} but the archive contains no such entry"
            )
        if info.is_dir():
            raise _fail(
                f"{MANIFEST_ENTRY} declares {name!r} as a file but the archive records it as a "
                "directory entry"
            )
        if size is not None and size != info.file_size:
            raise _fail(
                f"{MANIFEST_ENTRY} declares {size} byte(s) for entry {name!r} but the ZIP central "
                f"directory records {info.file_size} byte(s)"
            )

    allowlisted: list[str] = []
    for name in file_names:
        if name in declared or name == MANIFEST_ENTRY:
            # The index entry itself is required, not an undeclared payload file.
            continue
        if _allowlisted_undeclared(name):
            allowlisted.append(name)
            continue
        raise _fail(
            f"archive entry {name!r} is not declared by {MANIFEST_ENTRY} and is not on the "
            "documented allow-list of undeclared entries (JSON metadata, preview/thumbnail "
            "images); an undeclared payload file is rejected rather than ignored"
        )

    return {
        "task_id": TASK_ID,
        "boundary": "penpot-archive-structural",
        "manifest_entry": MANIFEST_ENTRY,
        "manifest_declared_key": declared_key,
        "manifest_version": manifest.get("version"),
        "entry_count": len(names),
        "file_count": len(file_names),
        "directory_count": len(directory_names),
        "declared_file_count": len(declared),
        "declared_files": sorted(declared),
        "undeclared_allowlisted": sorted(allowlisted),
        "total_file_bytes": sum(info_by_name[name].file_size for name in file_names),
        "extraction_performed": False,
        "write_performed": False,
        "live_run": "NOT_EXECUTED",
        "evidence_level": "E1",
    }


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def _adapter_schema_errors(adapter) -> list[str]:
    return schema_errors(load_schema(ADAPTER_SCHEMA_PATH), adapter)


def validate_adapter(adapter) -> dict:
    """Validate an adapter declaration: the repository schema plus the honesty rule.

    Structural rules come from ``design-lab/schemas/adapter-contract.schema.json``.
    The extra rule enforced here: a ``structural`` adapter may not declare any
    capability that requires a live host run -- it may only claim the capabilities
    listed in :data:`STRUCTURAL_SAFE_CAPABILITIES` -- and its evidence block must be
    E1 and carry the ``live_run=NOT_EXECUTED`` marker.

    The repository's own ``integrations/adapter-registry.json`` is validated by
    ``design-lab/tests/test_oda4_0206_adapters.py`` and is not re-validated here;
    the marker convention belongs to this interop package.
    """
    problems = _adapter_schema_errors(adapter)
    if problems:
        raise InteropError(
            f"adapter declaration violates {ADAPTER_SCHEMA_PATH.name}: " + "; ".join(problems)
        )
    status = adapter["status"]
    evidence = adapter["evidence"]
    if status == "structural":
        for index, capability in enumerate(adapter["capabilities"]):
            if not capability["supported"]:
                continue
            name = capability["name"]
            if name not in STRUCTURAL_SAFE_CAPABILITIES or name in LIVE_HOST_CAPABILITIES:
                raise _fail(
                    f"capabilities[{index}] {name!r} is supported=true on a structural adapter; a "
                    "capability that needs a live host run cannot be claimed without an E2+ run. "
                    "Capabilities verifiable without a host run: "
                    + ", ".join(sorted(STRUCTURAL_SAFE_CAPABILITIES))
                )
        if evidence["level"] != "E1":
            raise _fail(
                f"a structural adapter must carry E1 evidence; found {evidence['level']!r}. Only a "
                "real host run may raise the level above E1"
            )
        if LIVE_RUN_MARKER not in evidence["note"]:
            raise _fail(
                f"a structural adapter must state that no live run happened: evidence.note must "
                f"contain {LIVE_RUN_MARKER!r}"
            )
    return {
        "adapter_id": adapter["adapter_id"],
        "tool": adapter["tool"],
        "status": status,
        "mode": adapter["mode"],
        "evidence_level": evidence["level"],
        "supported_capabilities": sorted(capability["name"] for capability in adapter["capabilities"]
                                         if capability["supported"]),
        "capability_count": len(adapter["capabilities"]),
        "live_run": "NOT_EXECUTED" if LIVE_RUN_MARKER in evidence["note"] else "UNKNOWN",
        "task_ids": sorted(evidence["task_ids"]),
    }


def validate_declaration(document) -> dict:
    """Validate the full Penpot declaration package against its schema.

    The ``adapter_contract`` member is resolved through an offline registry built
    from ``design-lab/schemas/adapter-contract.schema.json``, so the shared contract
    has exactly one definition and nothing is fetched over the network.
    """
    wrapper_schema = load_schema(SCHEMA_PATH)
    contract_schema = load_schema(ADAPTER_SCHEMA_PATH)
    reference = wrapper_schema["properties"]["adapter_contract"]["$ref"]
    registry = resource_registry({reference: contract_schema})
    problems = schema_errors(wrapper_schema, document, registry=registry)
    if problems:
        raise InteropError(
            f"penpot declaration violates {SCHEMA_PATH.name}: " + "; ".join(problems)
        )
    report = validate_adapter(document["adapter_contract"])
    report["schemaVersion"] = document["schemaVersion"]
    report["import_plan_status"] = (None if document["import_plan"] is None
                                    else document["import_plan"]["status"])
    report["read_performed"] = False
    return report


# --------------------------------------------------------------------------- #
# import plan
# --------------------------------------------------------------------------- #

def _checked_target(path) -> tuple[str, str]:
    """Validate an import target lexically. Never touches the filesystem."""
    if not isinstance(path, str) or not path.strip() or path != path.strip():
        raise _fail("import target must be a nonempty path string")
    if any(character in path for character in ("\x00", "%", "$", "~")):
        raise _fail("import target must not contain shell-expansion or NUL characters")
    normalized = path.replace("\\", "/")
    if normalized.startswith("//"):
        raise _fail("import target must not be a network/UNC path")
    windows = PureWindowsPath(normalized)
    if windows.drive and windows.drive.rstrip(":").upper() == "E":
        raise _fail("the E: drive is protected and may not be read or named as an import target")
    target = Path(normalized)
    if target.suffix.lower() != PENPOT_EXTENSION:
        raise _fail(
            f"import target must be a {PENPOT_EXTENSION} file; got {path!r}. A .penpot file is the "
            "only Penpot artifact DESIGN-LAB has a boundary for"
        )
    if target.name in ("", ".", ".."):
        raise _fail(f"import target {path!r} has no file name")
    try:
        inside = target.is_relative_to(PROJECT_ROOT)
    except (OSError, ValueError):
        inside = False
    return normalized, "inside-repository" if inside else "outside-repository"


def import_plan(path) -> dict:
    """Return a read-only plan for a future Penpot importer, ending in the terminator.

    The plan is a description, not an execution: this call reads no file, opens no
    container, starts no process and performs no API call (``source_probed`` is
    ``NOT_EXECUTED`` and ``read_performed`` is ``false``). The final step is exactly
    ``requires a live Penpot run: NOT_EXECUTED``: everything after the structural
    mapping needs a live Penpot and has not been run.
    """
    normalized, location = _checked_target(path)
    return {
        "task_id": TASK_ID,
        "mode": "read-only-plan",
        "target": {
            "path": normalized,
            "extension": PENPOT_EXTENSION,
            "location": location,
            "source_probed": "NOT_EXECUTED",
            "read_performed": False,
        },
        "steps": [
            {
                "step": 1,
                "action": "declare the import target, its owner consent and its rights status; "
                          "refuse to continue without both",
                "reads": [],
                "writes": [],
                "gate": "HUMAN_GATE_RIGHTS",
            },
            {
                "step": 2,
                "action": "treat the .penpot file as an opaque ZIP container and list its entries "
                          "without extracting anything",
                "reads": ["zip central directory of the declared target"],
                "writes": [],
                "gate": "NONE",
            },
            {
                "step": 3,
                "action": "read manifest.json and record the Penpot file schema and version fields "
                          "verbatim, without interpreting them",
                "reads": ["manifest.json inside the declared target"],
                "writes": [],
                "gate": "NONE",
            },
            {
                "step": 4,
                "action": "copy the target into .project-local before any parsing, so the external "
                          "asset is never written back",
                "reads": [],
                "writes": [".project-local/task-runtime/penpot-import/<run-id>/"],
                "gate": "HUMAN_GATE_PRODUCTION",
            },
            {
                "step": 5,
                "action": "map Penpot pages and objects onto Design IR candidates, recording every "
                          "unmapped node type instead of guessing it",
                "reads": [],
                "writes": [],
                "gate": "NONE",
            },
            {
                "step": 6,
                "action": "validate the mapping structurally and run the interop unit tests; the "
                          "result stays E1 evidence",
                "reads": [],
                "writes": [],
                "gate": "NONE",
            },
            {
                "step": 7,
                "action": "verify that the import round-trips through a live Penpot (open the "
                          "imported file, read it back) before any capability is declared supported",
                "reads": [],
                "writes": [],
                "gate": "REQUIRES_LIVE_HOST",
            },
            {
                "step": 8,
                "action": TERMINATOR,
                "reads": [],
                "writes": [],
                "gate": "REQUIRES_LIVE_HOST",
            },
        ],
        "terminates_with": TERMINATOR,
        "status": "PLAN_ONLY_NOT_EXECUTED",
        "evidence_level": "E1",
    }


def declaration(*, import_target=None) -> dict:
    """The complete DL-P1-111 declaration package (adapter + boundary + optional plan).

    The result validates against ``interop-penpot-adapter.schema.json``; nothing in
    it claims a Penpot run.
    """
    return {
        "schemaVersion": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "adapter_contract": adapter(),
        "file_boundary": file_boundary(),
        "import_plan": None if import_target is None else import_plan(import_target),
    }
