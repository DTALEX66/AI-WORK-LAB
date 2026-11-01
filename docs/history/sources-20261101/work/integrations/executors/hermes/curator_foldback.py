"""Curator fold-back: converge live skill drift back into the repository.

The problem this solves
-----------------------
Hermes ships a native curator that rewrites skills on its own. It writes into
`HERMES_HOME/skills/**`, which WORK-LAB declares as a managed unit deployed with
whole-tree replacement semantics. So the two writers share one directory: the
curator adds knowledge, and the managed-asset guard then refuses to publish
because the live tree no longer matches anything it published. The deploy path
blocks until a human reconciles it, and the curator keeps writing, so it recurs.

The policy decided for this repository is "always fold back": curator output is
preserved by folding it into the repository, which stays the single authority,
and live is then republished from that authority until the two match again.

Safety shape
------------
Automation may only ever ADD. For every file the classification is:

  ADDED            present in live, absent in repo                 -> auto-fold
  EXTENDED         live keeps every repo line and adds to them      -> auto-fold
  LINE_ENDINGS     identical after normalising CRLF/LF             -> auto-fold
  REMOVED          present in repo, absent in live                  -> NEEDS_REVIEW
  TRIMMED          live deleted lines that the repo still has       -> NEEDS_REVIEW
  REWRITTEN        live changed lines the repo still has            -> NEEDS_REVIEW

A target is FOLDABLE only when nothing was removed, trimmed or rewritten. Anything
else is reported for a human, because that is a curator edit that would destroy
repository content - exactly the case the guard exists to catch. The tool never
writes to Hermes Home; publishing is the sync's job and stays behind --publish.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO_DEFAULT = Path(__file__).resolve().parents[2]

# Extensions whose worktree bytes must stay LF, per .gitattributes eol=lf.
LF_EXTENSIONS = (".json", ".yaml", ".yml", ".md", ".sh")

ADDED = "ADDED"
EXTENDED = "EXTENDED"
LINE_ENDINGS = "LINE_ENDINGS"
REMOVED = "REMOVED"
TRIMMED = "TRIMMED"
REWRITTEN = "REWRITTEN"
UNCHANGED = "UNCHANGED"

FOLDABLE = "FOLDABLE"
NEEDS_REVIEW = "NEEDS_REVIEW"
IDENTICAL = "IDENTICAL"

AUTO_FOLDABLE_KINDS = {ADDED, EXTENDED, LINE_ENDINGS}
BLOCKING_KINDS = {REMOVED, TRIMMED, REWRITTEN}


# --------------------------------------------------------------------------- #
# pure policy
# --------------------------------------------------------------------------- #
def _reads(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _is_subsequence(small: list[str], large: list[str]) -> bool:
    """True when every line of *small* appears in *large* in the same order."""

    iterator = iter(large)
    return all(any(candidate == wanted for candidate in iterator) for wanted in small)


def _lines(data: bytes) -> list[str]:
    return data.replace(b"\r\n", b"\n").decode("utf-8", errors="replace").split("\n")


def classify_file(repo_bytes: bytes | None, live_bytes: bytes | None) -> str:
    """Classify one file. Pure: no I/O, so the rules are unit-testable."""

    if repo_bytes is None and live_bytes is None:
        return UNCHANGED
    if repo_bytes is None:
        return ADDED
    if live_bytes is None:
        return REMOVED
    repo_lines = _lines(repo_bytes)
    live_lines = _lines(live_bytes)
    if repo_lines == live_lines:
        return UNCHANGED if repo_bytes == live_bytes else LINE_ENDINGS
    if _is_subsequence(repo_lines, live_lines):
        return EXTENDED
    if _is_subsequence(live_lines, repo_lines):
        return TRIMMED
    return REWRITTEN


def classify_tree(repo_files: dict[str, bytes], live_files: dict[str, bytes]) -> dict:
    """Classify a whole target tree and return a verdict plus per-file detail."""

    verdicts: dict[str, str] = {}
    for rel in sorted(set(repo_files) | set(live_files)):
        verdicts[rel] = classify_file(repo_files.get(rel), live_files.get(rel))

    blocking = {rel: kind for rel, kind in verdicts.items() if kind in BLOCKING_KINDS}
    folding = {rel: kind for rel, kind in verdicts.items() if kind in AUTO_FOLDABLE_KINDS}
    if blocking:
        verdict = NEEDS_REVIEW
    elif folding:
        verdict = FOLDABLE
    else:
        verdict = IDENTICAL
    return {"verdict": verdict, "files": verdicts, "auto_fold": sorted(folding), "blocking": sorted(blocking)}


def read_tree(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = _reads(path)
            if data is not None:
                out[path.relative_to(root).as_posix()] = data
    return out


def read_target(path: Path) -> dict[str, bytes]:
    """Read a managed target as a one-entry tree when it is a single file.

    Not every managed target is a directory: `.env.template` and `SOUL.md` are files.
    Treating them as trees keeps one classification and one fold path for both shapes.
    """

    if path.is_file():
        data = _reads(path)
        return {path.name: data} if data is not None else {}
    if path.is_dir():
        return read_tree(path)
    return {}


def normalized_bytes(rel: str, data: bytes) -> bytes:
    """Normalise to LF for the extensions .gitattributes pins to eol=lf."""

    if rel.lower().endswith(LF_EXTENSIONS):
        return data.replace(b"\r\n", b"\n")
    return data


def fold_target(live_path: Path, repo_path: Path) -> list[str]:
    """Write the live content into the repository. Only for FOLDABLE targets.

    Callers must have classified the target first; this function does not decide.
    Entries absent from live are left alone on purpose - deleting repository content
    is never an automatic outcome here. Handles both directory trees and single-file
    targets, because the managed set contains both.
    """

    live = read_target(live_path)
    existing = read_target(repo_path)
    written: list[str] = []
    if live_path.is_file():
        rel = live_path.name
        payload = normalized_bytes(rel, live[rel])
        if existing.get(rel) != payload:
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            repo_path.write_bytes(payload)
            written.append(rel)
        return written
    for rel, data in live.items():
        payload = normalized_bytes(rel, data)
        target = repo_path / rel
        if existing.get(rel) == payload:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        written.append(rel)
    return written


def refresh_provenance(repo: Path, skill_rel: str) -> dict | None:
    """Refresh skill-provenance hashes for one skill, if it is tracked there.

    The standard requires the manifest's live hashes to move in the same change as
    the skill content, so folding without this would leave a stale manifest.
    """

    manifest = repo / "config" / "skill-provenance.yaml"
    if not manifest.is_file():
        return None
    import yaml  # dependency of the gate environment, not of this module's policy

    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return None
    skill_md = repo / "packages" / "client-neutral-core" / "skills" / skill_rel / "SKILL.md"
    if not skill_md.is_file():
        return None
    digest = hashlib.sha256(skill_md.read_bytes()).hexdigest()
    name = skill_rel.split("/")[-1]
    changed = []
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict) or entry.get("name") != name:
            continue
        if entry.get("source_sha256") != digest or entry.get("live_sha256") != digest:
            entry["source_sha256"] = digest
            entry["live_sha256"] = digest
            changed.append(name)
    if not changed:
        return None
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120)
    manifest.write_text(text, encoding="utf-8", newline="\n")
    return {"skill": name, "sha256": digest, "entries_updated": changed}


# --------------------------------------------------------------------------- #
# integration with the sanctioned sync
# --------------------------------------------------------------------------- #
def load_sync(repo: Path):
    path = repo / "integrations" / "executors" / "hermes" / "sync_hermes_workflow_assets.py"
    spec = importlib.util.spec_from_file_location("sync_for_foldback", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repo_tree_for(repo: Path, target: str) -> Path:
    """Map a managed target to its repository source.

    Most targets live under packages/client-neutral-core/, but the sync maps two of
    them explicitly from config/ (APPROVED_MANAGED_FILE_MAPPINGS plus .env.template).
    Guessing a single root silently mis-resolved those two, so the mapping is
    consulted in the same order the sync uses.
    """

    direct = repo / "packages" / "client-neutral-core" / target
    if direct.exists():
        return direct
    from_config = repo / "config" / target
    if from_config.exists():
        return from_config
    return direct


def live_tree_for(home: Path, target: str) -> Path:
    return home / target


def drifted_targets(sync, repo: Path, home: Path) -> list[dict]:
    """Every managed target whose live tree differs from the repository candidate."""

    inputs = sync.managed_guard_inputs(repo, home)
    out = []
    for target, info in sorted(inputs.items()):
        if info["live_sha256"] == info["candidate_sha256"] and info["live_exists"]:
            continue
        out.append({
            "target": target,
            "live_sha256": info["live_sha256"],
            "candidate_sha256": info["candidate_sha256"],
            "live_exists": info["live_exists"],
        })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(REPO_DEFAULT))
    parser.add_argument("--home", required=True, help="HERMES_HOME (read only unless --publish)")
    parser.add_argument("--check", action="store_true", help="report drift and classification only (default)")
    parser.add_argument("--apply", action="store_true", help="fold FOLDABLE targets into the repository")
    parser.add_argument("--publish", action="store_true", help="after folding, adopt + publish through the sync")
    parser.add_argument("--evidence-dir", default=None, help="where to write the review artifact")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    home = Path(args.home).resolve()
    sync = load_sync(repo)
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else repo / ".project-local" / "artifacts" / "curator-foldback"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    drift = drifted_targets(sync, repo, home)
    print(f"drifted managed targets: {len(drift)}")
    report: dict = {"targets": [], "folded": [], "provenance": [], "published": []}

    for item in drift:
        target = item["target"]
        repo_tree = repo_tree_for(repo, target)
        live_tree = live_tree_for(home, target)
        if not (live_tree.is_dir() or live_tree.is_file()):
            print(f"  {target}: live tree missing -> NEEDS_REVIEW (never recreate from nothing)")
            report["targets"].append({**item, "verdict": NEEDS_REVIEW, "reason": "live tree missing"})
            continue
        result = classify_tree(read_target(repo_tree), read_target(live_tree))
        print(f"  {target}: {result['verdict']}")
        for rel in result["auto_fold"]:
            print(f"      auto-fold  {result['files'][rel]:<12} {rel}")
        for rel in result["blocking"]:
            print(f"      REVIEW     {result['files'][rel]:<12} {rel}")
        report["targets"].append({**item, "verdict": result["verdict"], "files": result["files"]})

        # a reviewable diff always goes to disk, folded or not
        diff_path = evidence_dir / f"{target.replace('/', '__')}.diff"
        lines = []
        for rel, kind in result["files"].items():
            if kind == UNCHANGED:
                continue
            lines.append(f"### {kind}: {rel}")
            repo_data = read_target(repo_tree).get(rel, b"")
            live_data = read_target(live_tree).get(rel, b"")
            import difflib
            lines.extend(difflib.unified_diff(
                _lines(repo_data), _lines(live_data), lineterm="", n=2,
                fromfile=f"repo/{rel}", tofile=f"live/{rel}",
            ))
        diff_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"      diff -> {diff_path}")

        if args.apply and result["verdict"] == FOLDABLE:
            written = fold_target(live_tree, repo_tree)
            report["folded"].append({"target": target, "files": written})
            print(f"      folded {len(written)} file(s) into the repository")
            provenance = refresh_provenance(repo, target.split("skills/", 1)[1])
            if provenance:
                report["provenance"].append(provenance)
                print(f"      provenance refreshed: {provenance['skill']}")

        if args.publish and result["verdict"] == FOLDABLE:
            # Adopt first: it records the reviewed live digest as the baseline and
            # writes no asset bytes, which is what turns the guard's refusal into a
            # CLEAN_UPDATE. Publishing is then the sync's own job, invoked through its
            # documented flags rather than reimplemented here.
            adopted = sync.adopt_baselines(
                repo, home,
                reviewed={target: item["live_sha256"]},
                operator="curator_foldback (operator-reviewed live digest)",
            )
            print(f"      adopt recorded: {adopted}")
            import subprocess
            completed = subprocess.run(
                [
                    sys.executable,
                    str(repo / "integrations" / "executors" / "hermes" / "sync_hermes_workflow_assets.py"),
                    "--repo", str(repo), "--home", str(home), "--apply", "--approved",
                ],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(repo),
            )
            verdict = "PASS" if "ACTION_PLAN_READBACK_PASS" in (completed.stdout or "") else "FAIL"
            print(f"      publish through the sync: {verdict} (exit {completed.returncode})")
            report["published"].append({
                "target": target, "adopted": adopted,
                "publish_verdict": verdict, "publish_exit": completed.returncode,
            })

    (evidence_dir / "curator-foldback-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(f"\nreport -> {evidence_dir / 'curator-foldback-report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
