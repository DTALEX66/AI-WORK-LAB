#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-AST-001: asset governance gate (strict, fail-closed).

Replaces the size+sidecar-only gate. Real verification for every tracked
binary outside inert prefixes:
- repository total budget (hard 256 MiB; warning at 220 MiB);
- per-file cap (5 MiB);
- .license sidecar must exist AND be structured asset-sidecar v1;
- sidecar sha256 must match the actual file hash;
- author / license must be recorded;
- redistributable / modelInputAllowed / commercialUse must be booleans;
- sourceId must resolve in SOURCE_REGISTRY (v3, active/reference-only) OR the
  sidecar must carry a human-approved exception with a non-expired expiresAt;
- new binaries without a complete sidecar are rejected by default.

Legacy SPDX-text sidecars are a hard violation (they cannot prove hash/rights),
which forces the one-time upgrade path (upgrade_asset_sidecars.py, DL-AST-001).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOTAL_BUDGET_MIB = 256
WARN_BUDGET_MIB = 220
SINGLE_FILE_MIB = 5
SIDECAR_V1 = "design-lab/asset-sidecar/v1"
REGISTRY = REPO / "design-lab/research/global-absorption/SOURCE_REGISTRY.json"
QUARANTINE = REPO / "design-lab/research/global-absorption/QUARANTINE_REGISTRY.json"

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".wav", ".mp3", ".mp4",
    ".pdf", ".zip", ".gz", ".7z", ".ttf", ".otf", ".woff", ".woff2",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".model", ".onnx", ".pb",
    ".apk", ".aab",
}
SKIPPED_PREFIXES = (
    "design-lab/research/quarantine/",
    "docs/history/",
    "reports/history/",
    "fixtures/domains/game-visual/assets/generated/",
)


def git(args: list[str]) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def git_paths(args: list[str]) -> list[str]:
    """List paths from git through NUL-separated porcelain.

    Plain `git ls-files` quotes any non-ASCII path (core.quotePath), so splitting
    its stdout by lines hands the caller a literal "\"docs/\\345\\225\\206…\"" token.
    Pathlib then stats a filename that never existed and every such tracked file is
    reported missing. -z is the only porcelain that is never quoted, so path lists
    must be taken from it. Same reason scripts/classify_repo.py uses -z.
    """
    r = subprocess.run(["git", *args, "-z"], cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -z: {r.stderr.strip()}")
    return [p for p in r.stdout.split("\0") if p]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()



def sidecar_findings(rel: str, binary: Path, sidecar: Path) -> list[str]:
    """DL-AST-001 per-binary gate findings (fail-closed).

    Returns [] when the binary is fully governed.
    """
    errs: list[str] = []
    if not sidecar.exists():
        return [f"binary without .license sidecar (DL-AST-001): {rel}"]
    try:
        sc = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [f"binary sidecar not valid JSON (must be asset-sidecar v1): {rel}"]
    if sc.get("schemaVersion") != SIDECAR_V1:
        return [f"binary sidecar not structured v1 (legacy SPDX text is a violation): {rel}"]
    if sc.get("file") != rel:
        errs.append(f"sidecar file mismatch: {rel} (sidecar says {sc.get('file')!r})")
    if sc.get("sha256") != sha256_of(binary):
        errs.append(f"sidecar sha256 mismatch: {rel}")
    if not sc.get("license"):
        errs.append(f"sidecar missing license: {rel}")
    if not sc.get("author"):
        errs.append(f"sidecar missing author/rights holder: {rel}")
    for flag in ("redistributable", "modelInputAllowed", "commercialUse"):
        if not isinstance(sc.get(flag), bool):
            errs.append(f"sidecar {flag} must be boolean: {rel}")
    source_id = sc.get("sourceId")
    if source_id:
        try:
            reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
            known = any(e.get("source", {}).get("sourceId") == source_id for e in reg.get("entries", []))
            qreg = json.loads(QUARANTINE.read_text(encoding="utf-8"))
            quarantined = any(e.get("sourceId") == source_id for e in qreg.get("entries", []))
        except (OSError, json.JSONDecodeError) as exc:
            errs.append(f"cannot read source registries for {rel}: {exc}")
            known = quarantined = False
        if quarantined:
            errs.append(f"binary references quarantined sourceId {source_id} (not allowed): {rel}")
        elif not known:
            errs.append(f"binary sourceId not in SOURCE_REGISTRY: {rel} ({source_id})")
    else:
        exc_info = sc.get("exception")
        if not isinstance(exc_info, dict) or not exc_info.get("approvedBy") or not exc_info.get("expiresAt"):
            errs.append(f"binary without sourceId needs approved exception with expiry: {rel}")
        else:
            try:
                if date.fromisoformat(exc_info["expiresAt"]) < date.today():
                    errs.append(f"binary exception expired {exc_info['expiresAt']}: {rel}")
            except ValueError:
                errs.append(f"binary exception expiresAt invalid: {rel} ({exc_info.get('expiresAt')!r})")
    return errs


def tracked_blob_sizes() -> dict[str, int]:
    """Byte size of every tracked path, straight from the index and object store.

    Deliberately NOT `Path.stat()`: a tracked path can point at bytes that are
    absent in a given checkout (absorbed or gitignored locations), and a missing
    file would then measure 0 bytes and silently pass every size budget.
    """
    sha_by_path: dict[str, str] = {}
    for rec in git_paths(["ls-files", "-s"]):
        meta, _, path = rec.partition("\t")
        parts = meta.split()
        if path and len(parts) >= 2:
            sha_by_path[path] = parts[1]
    shas = sorted(set(sha_by_path.values()))
    sizes: dict[str, int] = {}
    for i in range(0, len(shas), 2000):
        chunk = shas[i:i + 2000]
        probe = subprocess.run(["git", "cat-file", "--batch-check"], input="\n".join(chunk),
                               capture_output=True, text=True, cwd=str(REPO),
                               encoding="utf-8", errors="replace")
        for line in probe.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "blob" and parts[2].isdigit():
                sizes[parts[0]] = int(parts[2])
    missing = sorted(p for p, s in sha_by_path.items() if s not in sizes)
    if missing:
        raise RuntimeError(f"{len(missing)} tracked blobs unreadable, e.g. {missing[:3]}")
    return {path: sizes[sha] for path, sha in sha_by_path.items()}


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    binary_count = 0

    # 1. total repo budget (pack size) + 220 MiB warning line
    try:
        size_out = git(["count-objects", "-vH"])
        pack_line = next(l for l in size_out.splitlines() if l.startswith("size-pack:"))
        pack_mib = float(pack_line.split(":")[1].strip().split()[0])
    except (StopIteration, ValueError) as e:
        errors.append(f"cannot read pack size: {e}")
        pack_mib = 0.0
    if pack_mib > TOTAL_BUDGET_MIB:
        errors.append(f"repo pack {pack_mib:.1f} MiB exceeds hard budget {TOTAL_BUDGET_MIB} MiB")
    elif pack_mib > WARN_BUDGET_MIB:
        warnings.append(f"repo pack {pack_mib:.1f} MiB above {WARN_BUDGET_MIB} MiB warning line")

    # 2. per-file cap + 3. binary gate on tracked files
    tracked = git_paths(["ls-files"])
    quarantine_bytes = 0

    # Large-asset declarations. The pack has already grown past its warning line,
    # and ~179 MiB of it is history that cannot be reclaimed without destroying
    # archive-evidence tags. The only cheap lever left is refusing NEW unbound
    # large binaries, so each >=256 KiB file must sit inside a budgeted,
    # reason-carrying bundle in design-lab/config/large-assets.json.
    #
    # Sizes come from git's own index mode blob, not from the filesystem: a
    # tracked path may be a pointer into a gitignored / absorbed location that has
    # no bytes on disk in some checkouts, and a missing file must not silently
    # read as a zero-byte pass.
    try:
        large = json.loads((REPO / 'design-lab' / 'config' / 'large-assets.json')
                           .read_text(encoding='utf-8'))
        assert large['schemaVersion'] == 'design-lab/large-assets/v1'
        assert large['bundles']
    except (OSError, KeyError, AssertionError, json.JSONDecodeError) as exc:
        errors.append(f'large-assets declaration unreadable: {exc}')
        large = {'declareAboveKiB': 256, 'bundles': [], 'workingTreeBudgetMib': 0}
    large_total = 0
    per_bundle: dict[str, int] = {}
    try:
        blob_sizes = tracked_blob_sizes()
    except RuntimeError as exc:
        errors.append(f"cannot measure tracked blobs: {exc}")
        blob_sizes = {}
    # The working-tree budget covers every tracked path: text files are cheap per
    # byte but unbounded in count, and this repository's pack is already past its
    # warning line.
    working_tree_mib = sum(
        size for rel, size in blob_sizes.items() if not rel.startswith(SKIPPED_PREFIXES)
    ) / 1048576
    if working_tree_mib > large['workingTreeBudgetMib']:
        errors.append(f"working tree {working_tree_mib:.1f} MiB exceeds "
                      f"{large['workingTreeBudgetMib']} MiB budget")
    declare_above = large['declareAboveKiB'] * 1024

    for rel in tracked:
        if rel.startswith(SKIPPED_PREFIXES):
            if rel.startswith("design-lab/research/quarantine/"):
                try:
                    quarantine_bytes += (REPO / rel).stat().st_size
                except OSError as exc:
                    errors.append(f"cannot stat quarantine file: {rel} ({exc})")
            continue
        p = REPO / rel
        try:
            size = p.stat().st_size
        except OSError as exc:
            errors.append(f"cannot stat tracked file: {rel} ({exc})")
            continue
        if size > SINGLE_FILE_MIB * 1024 * 1024:
            errors.append(f"file exceeds {SINGLE_FILE_MIB} MiB cap: {rel} ({size/1048576:.1f} MiB)")

        suffix = Path(rel).suffix.lower()
        if suffix not in BINARY_SUFFIXES:
            continue
        binary_count += 1
        # Declaration applies to binaries only: a 340 KiB JSON ledger is normal
        # working material and must not need a review-time opt-in every edit.
        blob = blob_sizes.get(rel, size)
        if blob >= declare_above:
            large_total += blob
            declared = next((b for b in large['bundles'] if rel.startswith(b['prefix'])), None)
            if declared is None:
                errors.append(
                    f'large binary outside a declared bundle: {rel} '
                    f'({blob/1024:.0f} KiB) — extend design-lab/config/large-assets.json '
                    f'with a reason in review before committing it')
            else:
                per_bundle[declared['prefix']] = per_bundle.get(declared['prefix'], 0) + blob
        sidecar = Path(str(p) + ".license")
        if not sidecar.exists():
            errors.append(f"binary without .license sidecar (DL-AST-001): {rel}")
            continue
        try:
            sc = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append(f"binary sidecar not valid JSON (must be asset-sidecar v1): {rel}")
            continue
        if sc.get("schemaVersion") != SIDECAR_V1:
            errors.append(f"binary sidecar not structured v1 (legacy SPDX text is a violation): {rel}")
            continue
        if sc.get("file") != rel:
            errors.append(f"sidecar file mismatch: {rel} (sidecar says {sc.get('file')!r})")
        actual = sha256_of(p)
        if sc.get("sha256") != actual:
            errors.append(f"sidecar sha256 mismatch: {rel}")
        if not sc.get("license"):
            errors.append(f"sidecar missing license: {rel}")
        if not sc.get("author"):
            errors.append(f"sidecar missing author/rights holder: {rel}")
        for flag in ("redistributable", "modelInputAllowed", "commercialUse"):
            if not isinstance(sc.get(flag), bool):
                errors.append(f"sidecar {flag} must be boolean: {rel}")
        source_id = sc.get("sourceId")
        if source_id:
            try:
                reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
                known = any(e.get("source", {}).get("sourceId") == source_id for e in reg.get("entries", []))
                qreg = json.loads(QUARANTINE.read_text(encoding="utf-8"))
                quarantined = any(e.get("sourceId") == source_id for e in qreg.get("entries", []))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"cannot read source registries for {rel}: {exc}")
                known = quarantined = False
            if quarantined:
                errors.append(f"binary references quarantined sourceId {source_id} (not allowed): {rel}")
            elif not known:
                errors.append(f"binary sourceId not in SOURCE_REGISTRY: {rel} ({source_id})")
        else:
            exc_info = sc.get("exception")
            if not isinstance(exc_info, dict) or not exc_info.get("approvedBy") or not exc_info.get("expiresAt"):
                errors.append(f"binary without sourceId needs approved exception with expiry: {rel}")
            else:
                try:
                    if date.fromisoformat(exc_info["expiresAt"]) < date.today():
                        errors.append(f"binary exception expired {exc_info['expiresAt']}: {rel}")
                except ValueError:
                    errors.append(f"binary exception expiresAt invalid: {rel} ({exc_info.get('expiresAt')!r})")

    for bundle in large['bundles']:
        actual = per_bundle.get(bundle['prefix'], 0)
        if actual > bundle['budgetMib'] * 1048576:
            errors.append(f"bundle over budget: {bundle['prefix']} "
                          f"{actual/1048576:.2f} MiB > {bundle['budgetMib']} MiB")
    print(f"LARGE_ASSETS declared_bundles={len(large['bundles'])} "
          f"large_mib={large_total/1048576:.2f} working_tree_mib={working_tree_mib:.2f} "
          f"working_tree_budget_mib={large['workingTreeBudgetMib']}")

    print(f"ASSET_GOVERNANCE={'FAIL' if errors else 'OK'}")
    print(f"pack_mib={pack_mib:.1f} hard_budget_mib={TOTAL_BUDGET_MIB} warn_mib={WARN_BUDGET_MIB} "
          f"files={len(tracked)} binaries={binary_count} quarantine_bytes={quarantine_bytes/1048576:.1f}MiB")
    for w in warnings:
        print("WARN :", w)
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
