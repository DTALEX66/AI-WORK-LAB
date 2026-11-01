"""AG-19: test the owner's material root against the atlas pins for the missing originals.

Round C proved the timeline original absent by size and digest over the project tree, git objects and
60 archives — all inside this repository. Row AG-19b had only enumerated `D:\\All projects\\Record` BY
FILENAME, and that root is 15 GB / 114 files / 39 archives of multi-project material which no pin
test had covered. This is that coverage, and it is the stronger test: an exact-copy recovery must
match the pinned byte count (identical bytes imply identical size), so every file in scope is size-
filtered first and hashed only when its size equals a pin, and every archive is read by its central
directory so 31,382 members are compared without inflating them.

Two of the five atlas items (the 2026-09-28 startup prompt and the final execution document) carry no
`expected_sha256` at all. For those a hash-level negative proof is IMPOSSIBLE by construction: the
record labels them unpinned and the verdict cannot claim more than "no exact name hit attributed to
WORK-LAB". Naming that limit is the point of the instrument, not a caveat to smooth over.

CI-stability: the pin list is read from the promoted copy under `docs/history/archive/recovered-originals`
first, so a fresh runner has the real pins instead of a published echo of them (the atlas under
`.project-local` is only the fallback, and it is not on a runner). The Record root is not on a runner
either, so a run without it present reports `SCOPE_NOT_AVAILABLE_ON_THIS_MACHINE` and makes no absence
claim about the originals. Reads are read-only outside the Git root; the only writes are the tracked
record and the ignored detail file.

Usage: python scripts/audit/ag19_record_root_pin_test.py [--json-out PATH]
Exit: 0 measured (recovered or negatively proven in scope); 1 a recovery was found and needs landing;
      2 the pin source was unreadable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRACKED_ATLAS = (REPO / "docs/history/archive/recovered-originals"
                 / "WORK-LAB_MASTER_SOURCE_REGISTRY.json")
ATLAS = (REPO / ".project-local/atlas-2026-09-29/WORK-LAB_MASTER_ATLAS_2026-09-29"
         / "WORK-LAB_MASTER_SOURCE_REGISTRY.json")
RECORD_ROOT = Path(r"D:\All projects\Record")
TRACKED_RECORD = REPO / "docs" / "audits" / "AG19_RECORD_ROOT_PIN_TEST_2026-10-07.json"
DETAIL_DEFAULT = ".project-local/runs/convergence-20261007-j/ag19_detail.json"

# the name tokens the atlas items are searched by; WORK-LAB attribution is what separates an actual
# candidate from another project's identically-shaped launch prompt
NAME_TOKENS = ("时间线汇报", "完整项目对话", "启动提示词", "最终执行", "NEW-CHAT-HANDOFF", "WORK-LAB-SUMMARY")
OTHER_PROJECT = re.compile(r"(AAOS|ArcheAxis|DESIGN-LAB|ARCHIUM|三项目)", re.I)
WORKLAB = re.compile(r"(WORK[-_ ]?LAB|wl3)", re.I)


def attribute(name: str) -> str:
    """Who does a matching filename belong to? Other-project material must never count as a hit."""
    if OTHER_PROJECT.search(name):
        return "otherProject"
    if WORKLAB.search(name):
        return "worklab"
    return "unattributed"


def load_targets() -> tuple[list[dict], str]:
    """The five atlas pins, from the first source this machine (or a runner) can actually read."""
    for path, source in ((TRACKED_ATLAS, "tracked-promoted-copy"), (ATLAS, "atlas-machine-local")):
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))["missing_or_recovered_pins"]
            return ([{"pinId": p.get("id"), "name": p.get("name"), "status": p.get("status"),
                      "expectedBytes": p.get("expected_bytes"),
                      "expectedSha256": p.get("expected_sha256"),
                      "pinned": bool(p.get("expected_sha256"))} for p in data], source)
    if TRACKED_RECORD.is_file():
        published = json.loads(TRACKED_RECORD.read_text(encoding="utf-8"))
        return published["targets"], "tracked-record-published-list"
    return [], "NO_PIN_SOURCE"


def normalize(name: str) -> str:
    """Filename stem with the export de-duplication suffix and extension dropped.

    The atlas pins `WORK-LAB-NEW-CHAT-HANDOFF-2026-09-03(1).md` while the archive member is
    `WORK-LAB-NEW-CHAT-HANDOFF-2026-09-03.md`; without this the only real candidate in scope would be
    missed by an exact-name test. The normalization is stated as the match basis, never hidden.
    """
    stem = re.sub(r"\.(md|txt|docx|json|html|zip)$", "", name, flags=re.I)
    return re.sub(r"\(\d+\)$", "", stem).strip()


def scan(root: Path, sizes: set[int], digests: dict[str, dict],
         by_name: dict[str, dict], extract_to: Path | None) -> dict:
    files = members = 0
    size_hits, digest_hits, name_hits = [], [], []
    unreadable = []

    def check_content(data: bytes, where: dict, basis: str) -> None:
        digest = hashlib.sha256(data).hexdigest()
        pin = digests.get(digest)
        entry = dict(where, sha256=digest, bytes=len(data), matchBasis=basis,
                     pinMatches=pin["pinId"] if pin else None)
        size_hits.append(entry)
        if pin:
            digest_hits.append(dict(pinId=pin["pinId"], basis=basis, **{k: where[k] for k in where}))

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            unreadable.append({"name": path.name, "why": type(exc).__name__})
            continue
        files += 1
        rel = path.relative_to(root).as_posix()
        if any(tok in path.name for tok in NAME_TOKENS):
            name_hits.append({"kind": "file", "relative": rel, "bytes": size,
                              "attribution": attribute(path.name)})
        # a digest-pinned target with no pinned size can only be found by name, so name is the
        # second legitimate entry into the hash test — the size filter is not the whole method
        if size in sizes or normalize(path.name) in by_name:
            basis = "expected_bytes" if size in sizes else "normalized_filename"
            check_content(path.read_bytes(), {"kind": "file", "relative": rel}, basis)
    for archive in sorted(root.rglob("*.zip")):
        try:
            zf = zipfile.ZipFile(archive)
        except (OSError, zipfile.BadZipFile) as exc:
            unreadable.append({"name": archive.name, "why": type(exc).__name__})
            continue
        with zf:
            for info in zf.infolist():
                members += 1
                base = info.filename.rsplit("/", 1)[-1]
                if any(tok in base for tok in NAME_TOKENS):
                    name_hits.append({"kind": "zip-member", "archive": archive.name,
                                      "member": info.filename, "bytes": info.file_size,
                                      "crc": format(info.CRC, "08x"),
                                      "attribution": attribute(base)})
                if info.file_size in sizes:
                    # bytes are not inflated on a size lead alone: it is reported, not hashed
                    size_hits.append({"kind": "zip-member", "archive": archive.name,
                                      "member": info.filename, "bytes": info.file_size,
                                      "crc": format(info.CRC, "08x"), "sha256": None,
                                      "matchBasis": "expected_bytes",
                                      "pinMatches": "SIZE_ONLY_MEMBER_NOT_HASHED"})
                elif normalize(base) in by_name and extract_to is not None:
                    target = extract_to / f"{archive.name[:40]}__{base}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as fh, target.open("wb") as out:
                        out.write(fh.read())
                    rel_out = (target.relative_to(REPO).as_posix() if REPO in target.parents
                               else str(target))
                    check_content(target.read_bytes(),
                                  {"kind": "extracted-member", "archive": archive.name,
                                   "member": info.filename, "extractedTo": rel_out,
                                   "crc": format(info.CRC, "08x")}, "normalized_filename")
    return {"files": files, "zipMembers": members, "sizeHits": size_hits,
            "digestHits": digest_hits, "nameHits": name_hits, "unreadable": unreadable}


def _basis_counts(hits: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for h in hits:
        key = str(h.get("matchBasis"))
        out[key] = out.get(key, 0) + 1
    return out


def recovered_in_repo(digest: str) -> dict | None:
    """Is this pinned digest already held by the repository, verifiable from a clean checkout?

    A recovery only counts when the bytes can be read out of git rather than off this disk — that is
    the difference between the registry claiming a file is machine-local (ERR-142's complaint about
    evidence nobody else can re-measure) and claiming it is tracked. `git show HEAD:<path>` is what
    proves it, so the answer cannot be inflated by a leftover scratch copy.
    """
    registry = REPO / ".project" / "governance" / "recovered-source-registry.json"
    if not registry.is_file():
        return None
    try:
        doc = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for entry in doc.get("entries", []):
        if entry.get("sha256") != digest or entry.get("location") != "tracked":
            continue
        tracked_path = entry.get("trackedPath")
        if not tracked_path:
            continue
        proc = subprocess.run(["git", "show", f"HEAD:{tracked_path}"], cwd=REPO,
                              capture_output=True)
        if proc.returncode != 0:
            continue
        blob = hashlib.sha256(proc.stdout).hexdigest()
        if blob == digest:
            return {"trackedPath": tracked_path, "blobSha256": blob, "blobBytes": len(proc.stdout),
                    "recoveryBasis": entry.get("recoveryBasis")}
    return None


def verdict_for(targets: list[dict], present: bool, measured: dict) -> str:
    """What the data can actually support — the label that cannot be inflated."""
    if not present:
        return "SCOPE_NOT_AVAILABLE_ON_THIS_MACHINE"
    if measured["digestHits"]:
        by_pin = {t["pinId"]: t for t in targets}
        recovered = []
        for hit in measured["digestHits"]:
            pin = by_pin.get(hit.get("pinId")) or {}
            recovered.append((hit, recovered_in_repo(pin.get("expectedSha256") or "")))
        measured["recoveryState"] = [
            {"pinId": hit.get("pinId"), "expectedSha256": (by_pin.get(hit.get("pinId")) or {}).get("expectedSha256"),
             "recovered": state} for hit, state in recovered]
        if all(state for _, state in recovered):
            return "PIN_MATCH_FOUND_AND_RECOVERED_TRACKED"
        return "PIN_MATCH_FOUND_EXTRACTION_OWED"
    pinned = [t for t in targets if t["pinned"]]
    unpinned = [t for t in targets if not t["pinned"]]
    worklab_name_hits = [h for h in measured["nameHits"] if h["attribution"] == "worklab"]
    if len(pinned) == len(targets):
        return "NEGATIVELY_PROVEN_ALL_TARGETS_PINNED_IN_SCOPE"
    if not worklab_name_hits:
        return ("NEGATIVELY_PROVEN_FOR_PINNED_TARGETS_ONLY_UNPINNED_HAVE_NO_HASH_PROOF"
                if unpinned else "IN_SCOPE_NEGATIVE_PROOF")
    return "WORKLAB_NAME_HITS_REQUIRE_EXTRACTION_AND_HASH"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(RECORD_ROOT))
    ap.add_argument("--json-out", default=DETAIL_DEFAULT)
    ap.add_argument("--record", default=str(TRACKED_RECORD))
    args = ap.parse_args()

    targets, pin_source = load_targets()
    if pin_source == "NO_PIN_SOURCE":
        print("AG19_PIN_SOURCE_MISSING — no atlas on this machine and no published record to fall back on")
        return 2
    sizes = {int(t["expectedBytes"]) for t in targets if t.get("expectedBytes")}
    digests = {str(t["expectedSha256"]): t for t in targets if t.get("expectedSha256")}
    root = Path(args.root)
    present = root.is_dir()
    by_name = {normalize(str(t_["name"])): t_ for t_ in targets
               if t_.get("expectedSha256") and not t_.get("expectedBytes")}
    detail = REPO / args.json_out
    extract_to = detail.parent / "ag19_extraction"
    measured = (scan(root, sizes, digests, by_name, extract_to) if present else
                {"files": 0, "zipMembers": 0, "sizeHits": [], "digestHits": [], "nameHits": [],
                 "unreadable": []})
    verdict = verdict_for(targets, present, measured)
    attributions: dict[str, int] = {}
    for hit in measured["nameHits"]:
        attributions[hit["attribution"]] = attributions.get(hit["attribution"], 0) + 1

    record = {"schemaVersion": "work-lab/ag19-record-root-pin-test/v1",
              "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "tool": "scripts/audit/ag19_record_root_pin_test.py",
              "pinSource": pin_source,
              "scope": {"root": str(root), "rootPresent": present,
                        "filesEnumerated": measured["files"],
                        "zipMembersEnumerated": measured["zipMembers"],
                        "method": ("two entry points into the hash test: a file whose size equals a "
                                   "pin's expected_bytes is hashed, and a file or archive member whose "
                                   "normalized filename equals a digest-pinned target that carries no "
                                   "pinned size is hashed (members extracted into the ignored run "
                                   "directory first); archive members are otherwise compared by the "
                                   "central directory only (name+size+CRC, bytes not inflated); nested "
                                   "zips listed but not entered"),
                        "namePinnedTargets": sorted(by_name)},
              "targets": targets,
              "counts": {"pinnedTargets": sum(1 for t in targets if t["pinned"]),
                         "unpinnedTargets": sum(1 for t in targets if not t["pinned"]),
                         "contentHits": len(measured["sizeHits"]),
                         "contentHitsByBasis": _basis_counts(measured["sizeHits"]),
                         "digestHits": len(measured["digestHits"]),
                         "nameHits": len(measured["nameHits"]),
                         "nameHitsByAttribution": attributions,
                         "unreadable": len(measured["unreadable"])},
              "contentHits": measured["sizeHits"], "digestHits": measured["digestHits"],
              "nameHits": measured["nameHits"], "unreadable": measured["unreadable"],
              "verdict": verdict,
              "whatThisDoesNotProve": [
                  "an unpinned target (no expected_sha256 in the atlas) cannot be disproved by hash at "
                  "all; for those this instrument can only report that no WORK-LAB-attributed exact "
                  "name hit exists in the enumerated scope",
                  "a zip member matched on SIZE alone is a lead, not a recovery: its bytes are only "
                  "compared after extraction, and this sweep extracts only members whose normalized "
                  "filename matches a digest-pinned target that has no pinned size",
                  "nested zips (a .zip inside a .zip) were listed but not opened",
                  "absence in this root says nothing about the source platform, which this repository "
                  "cannot reach, and 'not found' is not 'deleted'",
                  "on a machine without the root the verdict is SCOPE_NOT_AVAILABLE_ON_THIS_MACHINE and "
                  "no absence claim is made at all"]}
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text(json.dumps({"record": record, "rawTargets": targets}, ensure_ascii=False,
                                 indent=2), encoding="utf-8")
    Path(args.record).write_bytes(json.dumps(record, ensure_ascii=False, indent=2)
                                  .replace("\n", "\r\n").encode())
    print(f"pinSource={pin_source} targets={len(targets)} "
          f"pinned={record['counts']['pinnedTargets']} unpinned={record['counts']['unpinnedTargets']}")
    print(f"rootPresent={present} files={measured['files']} zipMembers={measured['zipMembers']} "
          f"contentHits={len(measured['sizeHits'])} digestHits={len(measured['digestHits'])} "
          f"nameHits={len(measured['nameHits'])} byAttribution={attributions} "
          f"unreadable={len(measured['unreadable'])}")
    print(f"VERDICT {verdict}")
    print(f"record -> {Path(args.record).relative_to(REPO).as_posix()}")
    print(f"detail -> {detail.relative_to(REPO).as_posix()}")
    owed = [h for h in (measured.get("recoveryState") or []) if not h["recovered"]]
    return 1 if measured["digestHits"] and owed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
