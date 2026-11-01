"""Bring one WORK-LAB-authored original held in a DECLARED shared root back inside the Git root.

The spill rule in `.project/governance/project-data-boundary.json` says a write outside the Git root
must be traceable, locatable, cleanable and *migratable* — relocatable back inside the project
boundary. Mirroring in is that last property exercised: this reads one file from a root the project
already declares in `.project/governance/external-libraries-index.json`, writes a byte copy inside the
repository, and appends the per-write ledger line. The outside original is left exactly where it is —
this tool never deletes, moves or rewrites anything outside the Git root, so running it cannot cost
the owner data that this project does not own.

Fail-closed screens, in order:
  * E:/ and F:/ are refused outright (forbidden data volumes, reads included).
  * the source must sit inside a declared shared root, otherwise this is a cross-project read;
  * content is classified through the existing artifact-flow policy
    (`packages/client-neutral-core/scripts/artifact_flow_policy.py`), so a private-session,
    conversation-log, telemetry-body, credential, account-key or browser-data document cannot be
    mirrored in even with the flag set; a secret-shaped line also stops the run. Only the count and
    the dotted path are reported, never the value.
  * the destination must not already exist in the working tree or in git — no overwrite, no merge.

Usage:
    python scripts/maintenance/recover_shared_root_original.py \
      --source "D:/All projects/OS External Configuration/docs/X.md" \
      --dest docs/history/archive/recovered-originals/X.md \
      --evidence .project-local/runs/<run>/recovery.json [--stage]
Exit: 0 mirrored; 2 refused by a screen; 1 post-write verification failed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXTERNAL_INDEX = REPO / ".project/governance" / "external-libraries-index.json"
BOUNDARY = REPO / ".project/governance" / "project-data-boundary.json"
SPILL_LEDGER = REPO / ".project-local" / "artifacts" / "spill-ledger.jsonl"
LEDGER_FIELDS = ("at", "actor", "action", "outOfRoot", "target", "source", "trace", "locate",
                 "clean", "migrate", "reversible")


def load_policy():
    """Load the tracked artifact-flow policy module rather than restating its rules."""
    path = REPO / "packages" / "client-neutral-core" / "scripts" / "artifact_flow_policy.py"
    spec = importlib.util.spec_from_file_location("artifact_flow_policy", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def declared_root_of(source: Path):
    """(rootId, rootPath, basis) when the source sits under a declared root, else (None, None, None).

    Two kinds of root are consulted and they are NOT the same thing. A `sharedRoot` from
    `.project/governance/external-libraries-index.json` is a root this project co-owns for toolchain
    and library purposes. A `readOnlyInboundRoots` entry from the data boundary is owner material that
    may only be read — recovering from it needs the caller's explicit `--allow-owner-material`, and
    the basis is recorded on the ledger line so a later reader can see which kind of root the bytes
    came from.
    """
    candidates = []
    for rid, rpath in json.loads(EXTERNAL_INDEX.read_text(encoding="utf-8")).get("sharedRoots", {}).items():
        candidates.append((rid, Path(rpath).resolve(), "shared-root"))
    for entry in json.loads(BOUNDARY.read_text(encoding="utf-8")).get("readOnlyInboundRoots", []):
        candidates.append((entry["id"], Path(entry["path"]).resolve(), "owner-material-read-only"))
    best = None
    for rid, rp, basis in candidates:
        try:
            source.relative_to(rp)
        except ValueError:
            continue
        if best is None or len(rp.parts) > len(best[1].parts):
            best = (rid, rp, basis)
    if best is None:
        return None, None, None
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None, help="loose file under a declared root")
    ap.add_argument("--dest", required=True, help="repo-relative path inside the Git root")
    ap.add_argument("--evidence", required=True, help="repo-relative path under .project-local")
    ap.add_argument("--actor", required=True)
    ap.add_argument("--kind", default="user_published_audit")
    ap.add_argument("--stage", action="store_true", help="git add the destination after verifying")
    ap.add_argument("--source-archive", default=None,
                    help="recover ONE member out of a zip under a declared root, instead of a loose file")
    ap.add_argument("--member", default=None, help="archive member path, exact as listed by infolist()")
    ap.add_argument("--expect-sha256", default=None,
                    help="required with --source-archive: the digest the member must match")
    ap.add_argument("--allow-owner-material", action="store_true",
                    help="explicit opt-in when the root is read-only inbound owner material")
    args = ap.parse_args()

    source = Path(args.source) if args.source else (Path(args.source_archive) if args.source_archive else None)
    dest_rel = args.dest.replace("\\", "/")
    refuse = []
    archive_info = None

    if source is None:
        print("RECOVER_REFUSED NO_SOURCE_NAMED pass --source or --source-archive")
        return 2

    if args.source_archive:
        if not args.member:
            refuse.append("ARCHIVE_SOURCE_WITHOUT_MEMBER")
        if not args.expect_sha256:
            # Without a pin, "recover the original" degrades into "copy any file with a plausible
            # name out of a 15 GB archive". The pin is the whole claim.
            refuse.append("ARCHIVE_SOURCE_WITHOUT_DIGEST_PIN")
        source = Path(args.source_archive)

    if str(source).startswith(tuple(json.loads(BOUNDARY.read_text(encoding="utf-8"))
                                    ["forbiddenExternalRoots"])):
        refuse.append("SOURCE_IN_FORBIDDEN_VOLUME")
    root_id, root_path, basis = declared_root_of(source)
    if root_id is None:
        refuse.append("SOURCE_NOT_UNDER_DECLARED_SHARED_ROOT")
    elif basis == "owner-material-read-only" and not args.allow_owner_material:
        refuse.append("OWNER_MATERIAL_OPT_IN_MISSING")
    if not source.is_file():
        refuse.append("SOURCE_MISSING")

    dest = REPO / dest_rel
    try:
        dest.resolve().relative_to(REPO.resolve())
    except ValueError:
        refuse.append("DEST_OUTSIDE_GIT_ROOT")
    if dest.exists():
        refuse.append("DEST_ALREADY_EXISTS")
    tracked = subprocess.run(["git", "ls-files", "--", dest_rel], cwd=REPO, capture_output=True)
    if tracked.stdout.strip():
        refuse.append("DEST_ALREADY_TRACKED")

    def read_source_bytes() -> bytes:
        """The bytes named by the source, whether a loose file or one member of an archive."""
        if args.source_archive:
            with zipfile.ZipFile(source) as zf:
                return zf.read(args.member)
        return source.read_bytes()

    if args.source_archive:
        try:
            with zipfile.ZipFile(source) as zf:
                info = zf.getinfo(args.member)
                archive_info = {"archive": str(source), "member": args.member,
                                "memberSize": info.file_size,
                                "memberCrc32": format(info.CRC, "08x"),
                                "archiveBytes": source.stat().st_size,
                                "archiveSha256": sha256(source.read_bytes())}
                body = zf.read(args.member)
        except (KeyError, zipfile.BadZipFile) as exc:
            print(f"RECOVER_REFUSED ARCHIVE_MEMBER_UNREADABLE {exc!r}")
            return 2
    else:
        body = source.read_bytes() if source.is_file() else b""
    if args.expect_sha256 and sha256(body) != args.expect_sha256:
        # The pin is the claim; a member that does not match it is a different document.
        print(f"RECOVER_REFUSED DIGEST_PIN_MISMATCH expected={args.expect_sha256} "
              f"actual={sha256(body)}")
        return 2
    policy = load_policy()
    relative = (str(source.relative_to(root_path)) if root_path is not None else str(source))
    if args.member:
        relative = f"{relative}!/{args.member}"
    # the policy reads `artifact_kind`, not `kind` — passing the wrong key name made it take the
    # unknown-kind branch and report PENDING_AUTHORIZATION for a document it had never classified
    #
    # lines are keyed ({"L1": ...}) rather than listed because `artifact_flow_policy._walk_keys`
    # only descends into dicts and lists of containers: a bare string inside a list is never yielded,
    # so a token on its own line would be invisible to `find_nested_secrets` (ERR-139)
    lines = {f"L{i}": text for i, text in enumerate(body.decode("utf-8", errors="replace").splitlines())}
    artifact = {"artifact_kind": args.kind, "path": f"{root_id}/{relative}" if root_id else relative,
                "content": lines}
    decision = policy.classify_flow(artifact, authorized=True)
    secret_paths = policy.find_nested_secrets(artifact)
    if decision.get("decision") != "ALLOW":
        # fail closed on anything the sanctioned policy does not affirmatively allow, including
        # PENDING_AUTHORIZATION: an unclassified kind is not evidence that the content is safe
        refuse.append(f"ARTIFACT_FLOW_NOT_ALLOWED:{decision.get('decision')}")
    if secret_paths:
        # report paths and count only — the matched value is never printed or copied anywhere
        refuse.append(f"SECRET_SHAPED_LINES:{len(secret_paths)}")

    if refuse:
        print("RECOVER_REFUSED " + " ".join(refuse))
        return 2

    before = {"bytes": len(body), "sha256": sha256(body),
              "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(source.stat().st_mtime))}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)

    after_src = read_source_bytes()
    mirrored = dest.read_bytes()
    verify = {
        "originalUntouched": sha256(after_src) == before["sha256"] and len(after_src) == before["bytes"],
        "workingTreeIdentical": mirrored == body,
        "gitBlobIdentical": None,
        "differOnlyByLineEndings": (mirrored.replace(b"\r\n", b"\n")
                                    == body.replace(b"\r\n", b"\n")),
    }
    if args.stage:
        subprocess.run(["git", "add", "--", dest_rel], cwd=REPO, check=True)
        staged = subprocess.run(["git", "show", f":{dest_rel}"], cwd=REPO, capture_output=True)
        verify["gitBlobIdentical"] = (staged.returncode == 0 and staged.stdout == body)
        verify["gitBlobSha256"] = sha256(staged.stdout) if staged.returncode == 0 else None
        verify["gitBlobBytes"] = len(staged.stdout) if staged.returncode == 0 else None

    at = time.strftime("%Y-%m-%dT%H:%M:%S+0800",
                       time.gmtime(time.time() + 8 * 3600)).replace("+0800", "+0800")
    line = {"at": at, "actor": args.actor,
            "action": f"mirror-in recovery of a WORK-LAB-authored original from declared root "
                      f"{root_id} into {dest_rel}",
            "outOfRoot": False,
            "target": dest_rel,
            "source": str(source),
            "trace": f"sha256 {before['sha256']} over {before['bytes']} B read from the source at "
                     f"mtime {before['mtime']}",
            "locate": str(source),
            "clean": f"removable with a single delete of {dest_rel}; the outside original was not "
                     "modified, moved or deleted, so removal loses nothing",
            "migrate": f"already migrated in: this line records the migration",
            "reversible": "the outside copy remains the authoritative original; the repo copy is an "
                          "added file, revertible by git without touching anything outside the root",
            "artifactKind": args.kind,
            "flowDecision": decision.get("decision"),
            "declaredRoot": root_id,
            "rootBasis": basis,
            "archiveMember": archive_info,
            "verifications": verify}
    SPILL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with SPILL_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    evidence = {"schemaVersion": "work-lab/shared-root-original-recovery/v1", "at": at,
                "tool": "scripts/maintenance/recover_shared_root_original.py",
                "actor": args.actor, "source": str(source), "declaredRoot": root_id,
                "declaredRootPath": str(root_path), "dest": dest_rel,
                "originalMeasure": before, "flowDecision": decision,
                "secretShapedLines": len(secret_paths), "verifications": verify,
                "ledgerAppended": True, "staged": bool(args.stage)}
    out = REPO / args.evidence
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = all(v is not False for v in verify.values()) and verify["workingTreeIdentical"]
    print(f"RECOVERED dest={dest_rel} bytes={before['bytes']} sha256={before['sha256'][:16]}… "
          f"root={root_id} flow={decision.get('decision')} "
          f"untouched={verify['originalUntouched']} identical={verify['workingTreeIdentical']} "
          f"blobIdentical={verify['gitBlobIdentical']} lineEndingsOnly={verify['differOnlyByLineEndings']}")
    print(f"evidence -> {out.relative_to(REPO).as_posix()}")
    if not ok:
        print("POST_WRITE_VERIFICATION_FAILED")
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
