"""AG-05g: recompute the model registry's byte claims against the declared weight root.

`verify_model_registry_integrity.py` can only check the *shape* of a digest claim:
the CI runner has no weight root, so a full-file sha256 cannot be recomputed there.
This tool is the other half — it runs on the machine that owns the library and turns
each claim into a recomputed fact. It is deliberately not wired into the aggregate
gate: a required job that can only skip on the runner would fail the gate by AGENTS.md
own rule, and a silently-skipped check is the hazard this whole path exists to remove.

Fail-closed by design: a missing root exits 2, a digest that does not match exits 1,
and a claim whose path was written with an ellipsis is reported as unresolvable rather
than as absent, because "I cannot find it with this string" is not "it is not there".

Usage:
    python scripts/audit/model_library_readback.py [--root PATH] [--receipt PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / ".project" / "governance" / "model-registry.json"
CHUNK = 1 << 24
PREFIX_BYTES = 1 << 20
OLLAMA_BLOB_DIRS = ("ollama/blobs",)


def sha256_file(path: Path) -> tuple[str, str]:
    """Return (full digest, digest of the first 1 MiB)."""
    full = hashlib.sha256()
    prefix = hashlib.sha256()
    read = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            full.update(block)
            if read < PREFIX_BYTES:
                take = min(len(block), PREFIX_BYTES - read)
                prefix.update(block[:take])
                read += take
    return full.hexdigest(), prefix.hexdigest()


def entry_path(root: Path, entry_file: dict) -> tuple[Path | None, str]:
    for key, kind in (("relative_path", "file"), ("physical_path", "file"),
                      ("physical_dir", "directory")):
        value = entry_file.get(key)
        if isinstance(value, str) and value:
            candidate = Path(value) if os.path.isabs(value) else root / value.replace("\\", os.sep)
            return candidate, kind
    return None, "logical_ref_only"


def manifest_tags(root: Path, digest: str) -> list[str]:
    """Ollama model tags whose manifest references this blob digest."""
    tags: list[str] = []
    manifests = root / "ollama" / "manifests"
    if not digest or not manifests.is_dir():
        return tags
    for path in manifests.rglob("*"):
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - an unreadable manifest is not our failure
            continue
        tag = f"{path.parent.relative_to(manifests).as_posix()}/{path.name}"
        layers = [str(layer.get("digest", "")) for layer in (doc.get("layers") or [])]
        config = str((doc.get("config") or {}).get("digest", ""))
        if any(digest in value for value in layers + [config]):
            tags.append(tag)
    return tags


def store_total_masquerading_as_model(rows: list[dict]) -> list[str]:
    """A model's byte figure must be its own; the shared blob store's total is not one.

    Two different models once printed the identical 29,751,357,111 B because their path resolved to the
    whole ollama store, so the tool reported the store's size as each model's size and no reader could
    tell the difference. A row that names a store directory must therefore carry a different number as
    its own size.
    """
    return [f"{row['id']}: bytes_observed equals the whole blob store "
            f"{row['store_dir_bytes']} - that is the store's size, not the model's"
            for row in rows
            if row.get("store_dir") and row.get("bytes_observed") == row.get("store_dir_bytes")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="weight root; defaults to the registry's own field")
    parser.add_argument("--receipt", type=Path,
                        default=REPO / ".project-local" / "artifacts" / "model-library-readback.json")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    root = args.root or Path(str(data.get("sharedPhysicalRoot") or ""))
    if not str(root) or not root.is_dir():
        print(f"MODEL_LIBRARY_ROOT_MISSING {root}")
        return 2

    checked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows, failures = [], []

    for model in data["models"]:
        entry_file = model.get("file") or {}
        stated = str(model.get("sha256") or "")
        path, kind = entry_path(root, entry_file)
        row = {"id": model["id"], "status": model.get("status"), "resolved_via": kind,
               "path": str(path) if path else None, "stated_sha256": stated or None,
               "stated_bytes": entry_file.get("bytes")}
        if path and path.is_file():
            actual, prefix = sha256_file(path)
            row.update(presence="VERIFIED_FILE", bytes_observed=path.stat().st_size,
                       bytesBasis="file",
                       sha256_recomputed=actual, prefix_1miB_sha256=prefix,
                       digest_matches=bool(stated) and actual == stated)
            if row["stated_bytes"] not in (None, path.stat().st_size):
                failures.append(f"{model['id']}: stated_bytes={row['stated_bytes']} "
                                f"but the file is {path.stat().st_size} B")
            if stated and not row["digest_matches"]:
                failures.append(f"{model['id']}: recorded sha256 is not the digest of the file "
                                f"on disk (recomputed {actual})")
        elif path and path.is_dir():
            files = sorted(p for p in path.rglob("*") if p.is_file())
            blob = path / "blobs" / f"sha256-{stated}" if stated else None
            if blob is None:
                blob = next((root / d / f"sha256-{stated}" for d in OLLAMA_BLOB_DIRS
                             if stated and (root / d / f"sha256-{stated}").is_file()), None)
            # A model whose path resolves to the shared ollama store must not report the store's total as
            # its own size: two different models produced the identical 29,751,357,111 B, which reads as
            # a per-model byte claim and is not one. The directory total is kept, but under a name that
            # says whose bytes they are, and the model's own size comes from the blob it points at.
            dir_total = sum(p.stat().st_size for p in files)
            store_dir = (path / "blobs").is_dir() or path.name in OLLAMA_BLOB_DIRS
            row.update(presence="VERIFIED_DIR", file_count=len(files))
            if store_dir:
                row["store_dir"] = str(path.relative_to(root)).replace("\\", "/")
                row["store_dir_bytes"] = dir_total
                row["bytes_observed"] = blob.stat().st_size if blob and blob.is_file() else None
                row["bytesBasis"] = "blob" if blob and blob.is_file() else "unknown"
            else:
                row["bytes_observed"] = dir_total
                row["bytesBasis"] = "directory"
            total = dir_total
            if not stated and total <= (1 << 31):
                # A small asset directory is replaced by a per-file manifest, so a
                # multi-file model stops being one truncated prose claim.
                row["directory_manifest"] = [
                    {"relative_path": str(f.relative_to(path)).replace("\\", "/"),
                     "bytes": f.stat().st_size, "sha256": sha256_file(f)[0]} for f in files]
            if stated:
                blob_path = root / "ollama" / "blobs" / f"sha256-{stated}"
                if blob_path.is_file():
                    actual, _ = sha256_file(blob_path)
                    row.update(presence="VERIFIED_BLOB_CONTENT_ADDRESS",
                               blob_path=str(blob_path.relative_to(root)).replace("\\", "/"),
                               blob_bytes=blob_path.stat().st_size,
                               sha256_recomputed=actual, digest_matches=actual == stated,
                               manifest_tags=manifest_tags(root, stated))
                    if actual != stated:
                        failures.append(f"{model['id']}: ollama blob content does not hash to "
                                        f"its own file name")
                else:
                    row.update(presence="ABSENT_BLOB", digest_matches=False)
                    failures.append(f"{model['id']}: no blob named sha256-{stated[:16]}… in the store")
            if model.get("status") in ("RETIRED_PENDING_DECISION", "RETIRED"):
                row["retained_bytes"] = row.get("blob_bytes") or row.get("bytes_observed")
        else:
            row.update(presence="UNRESOLVED", digest_matches=None)
            failures.append(f"{model['id']}: neither a file nor a directory resolves: {row['path']}")
        rows.append(row)
        print(f"{model['id']:<38} {row['presence']:<28} bytes={row.get('bytes_observed')} "
              f"digest_match={row.get('digest_matches')}", flush=True)

    orphans = []
    for orphan in data.get("candidateOrphans", []) or []:
        claimed = str(orphan.get("path") or "")
        entry = {"claimed_path": claimed, "claimed_bytes": orphan.get("bytes")}
        if "…" in claimed or "(" in claimed:
            entry.update(recheck="UNRESOLVABLE_AS_WRITTEN",
                         note="the path field is prose, so no tool can locate it")
        else:
            target = root / Path(claimed)
            if target.is_file():
                actual, prefix = sha256_file(target)
                claimed_prefix = str((orphan.get("assetDigest") or {}).get("prefix") or "")
                same_as = next((m["id"] for m in data["models"]
                                if str(m.get("sha256") or "") == actual), None)
                # `assetDigest.prefix` in this registry is the leading characters of the
                # FULL file digest (measured 2026-10-07 on the reranker orphan), so that is
                # what a re-check must compare. The 1 MiB prefix digest is recorded too, as
                # the cheap form a future run can compare without reading the whole file.
                entry.update(recheck="PRESENT", bytes_observed=target.stat().st_size,
                             sha256_recomputed=actual, prefix_1miB_sha256=prefix,
                             prefix_claim_matches=bool(claimed_prefix)
                             and actual.startswith(claimed_prefix),
                             prefix_claim_length=len(claimed_prefix),
                             byte_duplicate_of=same_as)
            else:
                entry.update(recheck="ABSENT_NOW")
        orphans.append(entry)
        print(f"orphan {claimed[:52]:<54} {entry['recheck']}", flush=True)

    registered_digests = {str(m.get("sha256") or "") for m in data["models"]}
    unregistered = []
    blobs = root / "ollama" / "blobs"
    if blobs.is_dir():
        for blob in sorted(p for p in blobs.iterdir() if p.is_file() and p.stat().st_size > 0):
            digest = blob.name.removeprefix("sha256-")
            if digest not in registered_digests:
                unregistered.append({"path": str(blob.relative_to(root)).replace("\\", "/"),
                                     "bytes": blob.stat().st_size, "digest": digest,
                                     "manifest_tags": manifest_tags(root, digest)})
    large_unregistered = [u for u in unregistered if u["bytes"] > (1 << 30)]

    # The defect this check exists to keep out: a model whose "size" was the size of the whole shared
    # store, so two different models printed the same 29,751,357,111 B and it read as a per-model fact.
    failures.extend(store_total_masquerading_as_model(rows))
    shared = {}
    for r in rows:
        value = r.get("bytes_observed")
        if value and r.get("bytesBasis") == "blob":
            shared.setdefault(value, []).append(r["id"])
    same_blob = {str(k): v for k, v in shared.items() if len(v) > 1}

    receipt = {"schemaVersion": "work-lab/model-library-readback/v1",
               "checkedAt": checked_at, "root": str(root),
               "hashBasis": "sha256 over the full bytes of each file as it sits on this machine",
               "bytesBasisLegend": {"file": "the resolved file's own size",
                                    "directory": "sum of files under the model's own directory",
                                    "blob": "the single ollama blob the model points at; store totals "
                                            "are reported separately as store_dir_bytes"},
               "modelsSharingOneBlob": same_blob,
               "models": rows, "orphans_rechecked": orphans,
               "unregistered_blobs": unregistered,
               "large_unregistered_blobs": large_unregistered,
               "failures": failures}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"models={len(rows)} orphan_checks={len(orphans)} "
          f"large_unregistered={[ (u['bytes'], u['manifest_tags']) for u in large_unregistered ]}")
    if failures:
        print("MODEL_LIBRARY_READBACK_FAIL")
        for failure in failures:
            print("  ! " + failure)
        print(f"receipt={args.receipt}")
        return 1
    print(f"MODEL_LIBRARY_READBACK_PASS models={len(rows)} receipt={args.receipt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
