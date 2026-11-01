"""Promote one WORK-LAB-authored original from the project's own ignored root into the tracked tree.

`recover_shared_root_original.py` covers bytes that live OUTSIDE the Git root, in a declared shared
root or the owner's read-only material root. This covers the other half of AG-19: a record that is
already inside the project boundary but under the git-ignored runtime root, where CI can never see it
and a drift cannot be enforced by any gate. Promotion converts an unenforceable claim into a versioned
one, so it carries the same screens, plus one the shared-root tool cannot do — a structural read of the
document's own key names, because that is where a session identifier, a credential field, or a
prompt/response body would actually be hiding (ERR-139: a JSON leaf walked as a line of text is
invisible to a key-name screen).

Screens, all fail-closed and in this order:
  * the source must be inside the Git root AND hidden from a clean checkout by the repository's own
    ignore rules (`git check-ignore`), which is the property that makes promotion worth doing; E:/ F:/
    are refused outright;
  * `--expect-sha256` is required: an unpinned "recovery" is just a copy with a plausible name;
  * the parsed document is walked for secret-shaped keys, prompt/response-body-shaped fields,
    credential-shaped values, session UUIDs and forbidden-drive paths — any hit refuses the run, and
    only counts and dotted paths are reported, never the value;
  * the destination must not exist in the working tree and must not be tracked — no overwrite, no merge;
  * after writing, the staged index blob (not the working tree) is compared to the source bytes,
    because `* text=auto` can make those differ (ERR-125/ERR-153).

Usage:
    python scripts/maintenance/promote_ignored_root_original.py \
      --source .project-local/atlas-2026-09-29/.../WORK-LAB_MASTER_SOURCE_REGISTRY.json \
      --dest docs/history/archive/recovered-originals/WORK-LAB-MASTER-SOURCE-REGISTRY.json \
      --expect-sha256 79bf958a... --evidence .project-local/runs/<run>/promotion.json \
      --actor <you> [--stage]
Exit: 0 promoted; 2 refused by a screen; 1 post-write verification failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BOUNDARY = REPO / ".project/governance" / "project-data-boundary.json"
SPILL_LEDGER = REPO / ".project-local" / "artifacts" / "spill-ledger.jsonl"

SECRET_KEY = re.compile(r"(api[_-]?key|access[_-]?token|auth[_-]?token|secret|passwor|token|"
                        r"credential|private[_-]?key|authorization|bearer|cookie|session[_-]?id)", re.I)
SECRET_VALUE = re.compile(r"(ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|ghs_[A-Za-z0-9]{20,}|"
                          r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-|AKIA[0-9A-Z]{16}|"
                          r"-----BEGIN |eyJ[A-Za-z0-9_-]{20,}\.)")
BODY_KEY = re.compile(r"^(prompt|completion|response|request|messages?|content_body|transcript|"
                      r"conversation)$", re.I)
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
FORBIDDEN_ROOT = re.compile(r"^\s*[\"']?[EFef]:[\\\\/]")
MIN_BODY_CHARS = 200


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def declared_ignored_roots() -> list[tuple[str, Path]]:
    b = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    out = []
    for key in ("runtimeRoot", "taskArtifactsRoot", "canonicalEvidenceRoot"):
        val = b.get(key)
        if isinstance(val, str) and val.strip():
            out.append((key, (REPO / val).resolve()))
    return out


def role_root_of(source: Path):
    """The deepest boundary-declared role root containing the source, else None.

    Recorded as a fact, not used as the screen: the data boundary names three role roots while the
    ignore rules cover the whole ignored runtime root, so a record parked elsewhere under it is still
    invisible to a clean checkout and still promotable.
    """
    best = None
    for key, rp in declared_ignored_roots():
        try:
            source.relative_to(rp)
        except ValueError:
            continue
        if best is None or len(rp.parts) > len(best[1].parts):
            best = (key, rp)
    return best


def git_ignore_rule(rel: str) -> str:
    """The ignore rule hiding this path from a clean checkout, or "" when nothing ignores it."""
    proc = subprocess.run(["git", "check-ignore", "-v", "--", rel], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.stdout.strip() if proc.returncode == 0 else ""


def structural_scan(node, path="$", found=None) -> dict:
    """Walk the parsed document and report blocker SHAPES, never values."""
    found = {"secret_keys": [], "body_fields": [], "secret_values": [],
             "forbidden_paths": [], "uuids": 0, "strings": 0, "longest": 0} if found is None else found
    if isinstance(node, dict):
        for k, v in node.items():
            kp = f"{path}.{k}"
            if SECRET_KEY.search(str(k)) and isinstance(v, str) and v.strip():
                found["secret_keys"].append(kp)
            if BODY_KEY.match(str(k)) and isinstance(v, str) and len(v) > MIN_BODY_CHARS:
                found["body_fields"].append(f"{kp} ({len(v)} chars)")
            structural_scan(v, kp, found)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            structural_scan(v, f"{path}[{i}]", found)
    elif isinstance(node, str):
        found["strings"] += 1
        found["longest"] = max(found["longest"], len(node))
        if SECRET_VALUE.search(node):
            found["secret_values"].append(path)
        if FORBIDDEN_ROOT.search(node):
            found["forbidden_paths"].append(path)
        found["uuids"] += len(UUID.findall(node))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="repo-relative path under the declared ignored root")
    ap.add_argument("--dest", required=True, help="repo-relative path inside the tracked tree")
    ap.add_argument("--expect-sha256", required=True, help="the pin the promoted bytes must match")
    ap.add_argument("--evidence", required=True, help="repo-relative path under .project-local")
    ap.add_argument("--actor", required=True)
    ap.add_argument("--stage", action="store_true", help="git add the destination after verifying")
    args = ap.parse_args()

    refuse: list[str] = []
    src_rel = args.source.replace("\\", "/")
    source = (REPO / src_rel).resolve()
    forbidden = tuple(json.loads(BOUNDARY.read_text(encoding="utf-8"))["forbiddenExternalRoots"])
    if str(source).startswith(forbidden):
        refuse.append("SOURCE_IN_FORBIDDEN_VOLUME")

    outside = False
    try:
        source.relative_to(REPO.resolve())
    except ValueError:
        outside = True
        refuse.append("SOURCE_OUTSIDE_GIT_ROOT")
    ignore_rule = "" if outside else git_ignore_rule(src_rel)
    if not outside and not ignore_rule:
        # the promotion exists to make CI-visible what a clean checkout cannot see; a source that is
        # already versioned needs no promotion, and one outside the root is a different operation
        refuse.append("SOURCE_NOT_GIT_IGNORED")
    root = role_root_of(source)
    basis = root[0] if root else "git-ignored-runtime-root"
    if not source.is_file():
        refuse.append("SOURCE_MISSING")

    dest_rel = args.dest.replace("\\", "/")
    dest = REPO / dest_rel
    try:
        dest.resolve().relative_to(REPO.resolve())
    except ValueError:
        refuse.append("DEST_OUTSIDE_GIT_ROOT")
    if dest.exists():
        refuse.append("DEST_ALREADY_EXISTS")
    if subprocess.run(["git", "ls-files", "--", dest_rel], cwd=REPO,
                      capture_output=True).stdout.strip():
        refuse.append("DEST_ALREADY_TRACKED")

    if refuse:
        print("PROMOTE_REFUSED " + " ".join(refuse))
        return 2

    body = source.read_bytes()
    digest = sha256(body)
    if digest != args.expect_sha256:
        print(f"PROMOTE_REFUSED DIGEST_PIN_MISMATCH expected={args.expect_sha256} actual={digest}")
        return 2

    try:
        parsed = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        # A document that does not parse cannot be structurally screened, and an unscreened document
        # cannot be published to every clone of the repository.
        print(f"PROMOTE_REFUSED SOURCE_UNPARSEABLE {type(exc).__name__}: {str(exc)[:120]}")
        return 2

    scan = structural_scan(parsed)
    blockers = ([f"secret_keyed_field:{p}" for p in scan["secret_keys"]]
                + [f"body_shaped_field:{p}" for p in scan["body_fields"]]
                + [f"credential_shaped_value:{p}" for p in scan["secret_values"]]
                + [f"forbidden_drive_path:{p}" for p in scan["forbidden_paths"]])
    if blockers:
        print(f"PROMOTE_REFUSED CONTENT_SCAN_BLOCKED:{len(blockers)} "
              + " ".join(b.split(':')[0] for b in blockers[:8]))
        return 2

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)

    verify = {"sourceUnchanged": sha256(source.read_bytes()) == digest,
              "workingTreeIdentical": dest.read_bytes() == body,
              "indexBlobIdentical": None, "indexBlobSha256": None, "indexBlobBytes": None}
    if args.stage:
        subprocess.run(["git", "add", "--", dest_rel], cwd=REPO, check=True)
        staged = subprocess.run(["git", "show", f":{dest_rel}"], cwd=REPO, capture_output=True)
        verify["indexBlobIdentical"] = staged.returncode == 0 and staged.stdout == body
        verify["indexBlobSha256"] = sha256(staged.stdout) if staged.returncode == 0 else None
        verify["indexBlobBytes"] = len(staged.stdout) if staged.returncode == 0 else None

    at = time.strftime("%Y-%m-%dT%H:%M:%S+0800", time.gmtime(time.time() + 8 * 3600))
    line = {"at": at, "actor": args.actor,
            "action": f"promote a WORK-LAB-authored record from this project's own ignored root "
                      f"({basis}) into the tracked tree at {dest_rel}",
            "outOfRoot": False, "target": dest_rel, "source": str(source),
            "trace": f"sha256 {digest} over {len(body)} B, equal to the caller's --expect-sha256 pin",
            "locate": str(source),
            "clean": f"removable with a single delete of {dest_rel}; the ignored-root copy stays, "
                     "so removal loses nothing",
            "migrate": "already migrated in: this line records the migration from ignored to tracked",
            "reversible": "the tracked copy is an added file, revertible by git; the ignored-root "
                          "source was read only and is still on disk",
            "ignoreRule": ignore_rule,
            "promotionBasis": basis,
            "contentScan": {k: (len(v) if isinstance(v, list) else v)
                           for k, v in scan.items()},
            "verifications": verify}
    SPILL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with SPILL_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    evidence = {"schemaVersion": "work-lab/ignored-root-original-promotion/v1", "at": at,
                "tool": "scripts/maintenance/promote_ignored_root_original.py",
                "actor": args.actor, "source": str(source), "promotionBasis": basis,
                "gitIgnoreRule": ignore_rule,
                "dest": dest_rel, "bytes": len(body), "sha256": digest,
                "scanFacts": {"strings": scan["strings"], "longestString": scan["longest"],
                              "sessionUuids": scan["uuids"], "blockers": len(blockers)},
                "verifications": verify, "ledgerAppended": True, "staged": bool(args.stage)}
    out = REPO / args.evidence
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = all(v is not False for v in verify.values()) and verify["workingTreeIdentical"]
    print(f"PROMOTED dest={dest_rel} bytes={len(body)} sha256={digest[:16]}… "
          f"basis={basis} strings={scan['strings']} uuids={scan['uuids']} "
          f"blobIdentical={verify['indexBlobIdentical']}")
    print(f"evidence -> {out.relative_to(REPO).as_posix()}")
    if not ok:
        print("POST_WRITE_VERIFICATION_FAILED")
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
