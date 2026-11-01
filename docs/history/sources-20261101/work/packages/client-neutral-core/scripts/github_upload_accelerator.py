"""Optional, explicit-scope GitHub delivery helper. No worktree mutation in diagnosis mode."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github_common import MANAGED_REPOS, git, local_path, request, redact

CONVENTIONAL = ("feat", "fix", "docs", "chore", "refactor", "test", "perf", "build", "ci", "revert")


def _prefix(message: str) -> str:
    if any(message.startswith(p + ":") for p in CONVENTIONAL):
        return message
    low = message.lower()
    for words, prefix in ((("fix", "修复", "bug", "error"), "fix"),
                          (("docs", "文档", "readme"), "docs"),
                          (("feat", "feature", "add", "new", "新增", "增强"), "feat")):
        if any(word in low for word in words):
            return f"{prefix}: {message}"
    return "chore: " + message


def _sanitize(message: str) -> str:
    return message.replace("\r", "").replace("\n", " ").strip()[:120]


def _repo_identity(repo_local: str) -> str:
    return next(e["repo"] for e in MANAGED_REPOS if e["local"] == repo_local)


def upload(repo_local: str, message: str | None = None, *, files: list[str] | None = None,
           repo_root: str | None = None, push: bool = False, create_pr: bool = False,
           target: str = "main") -> dict:
    result = {"repo": repo_local, "steps": []}
    try:
        d = local_path({"local": repo_local, "root": repo_root})
        branch = git(d, "symbolic-ref", "--quiet", "--short", "HEAD")
        result["branch"] = branch
        status = git(d, "status", "--porcelain=v1", "--untracked-files=all")
        result["dirty_count"] = len(status.splitlines())
        staged = git(d, "diff", "--cached", "--name-only", "-z")
        if staged:
            result.update(status="BLOCKED_STAGED", error="existing staged content must be resolved separately")
            return result
        try:
            upstream = git(d, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        except RuntimeError:
            upstream = None
        result["upstream"] = upstream
        if upstream:
            ahead = int(git(d, "rev-list", "--count", f"{upstream}..HEAD"))
            result["ahead"] = ahead
        else:
            result["ahead"] = None
        if not message:
            result["status"] = ("DIRTY_NO_ACTION" if status else
                                "NO_UPSTREAM" if not upstream else
                                "UNPUSHED_COMMITS" if ahead else "CLEAN_LOCAL_REMOTE_UNVERIFIED")
            return result
        if branch == target or branch in ("main", "master"):
            result.update(status="BLOCKED_BRANCH", error="refusing to write on the protected branch")
            return result
        if create_pr and not push:
            result.update(status="BLOCKED_PR", error="--create-pr requires --push")
            return result
        if push and upstream and ahead:
            result.update(status="BLOCKED_UNPUSHED", error="existing unpushed commits need separate review")
            return result
        if push and not upstream:
            try:
                base_head = git(d, "rev-parse", "refs/remotes/origin/main")
            except RuntimeError:
                result.update(status="REMOTE_UNKNOWN", error="origin/main is unavailable; fetch and review first")
                return result
            if git(d, "rev-parse", "HEAD") != base_head:
                result.update(status="BLOCKED_UNPUSHED", error="branch has commits without an upstream; review them separately")
                return result
        paths = files or []
        if not paths:
            result.update(status="BLOCKED_SCOPE", error="explicit --file scope is required")
            return result
        for path in paths:
            p = Path(path)
            if p.is_absolute() or ".." in p.parts or path.startswith("-"):
                raise ValueError("file scope must contain repository-relative paths")
        # Git pathspec magic and directory scopes can silently widen the write-set.
        if any(any(ch in path for ch in "*?[]:") or (d / path).is_dir() for path in paths):
            raise ValueError("file scope must use literal file paths")
        git(d, "add", "--", *paths)
        selected = set(filter(None, git(d, "diff", "--cached", "--name-only").splitlines()))
        if not selected or selected != set(paths):
            raise ValueError("staged files differ from explicit file scope; inspect index before retry")
        result["steps"].append("staged explicit files")
        commit_msg = _prefix(_sanitize(message))
        git(d, "commit", "-m", commit_msg)
        result["commit"] = git(d, "rev-parse", "HEAD")
        result["steps"].append("committed")
        if push:
            git(d, "push", "-u", "origin", branch)
            result["steps"].append("pushed")
        if create_pr:
            repo = _repo_identity(repo_local)
            pr = request("POST", "/pulls", {"title": commit_msg, "head": branch,
                                              "base": target, "body": f"Delivery of {', '.join(paths)}"}, repo=repo)
            url = pr.get("html_url")
            if not url or not url.startswith(f"https://github.com/{repo}/pull/"):
                raise RuntimeError("PR creation returned no verifiable URL")
            result["pr_url"] = url
        result["status"] = "DONE_LOCAL" if not push else "DONE_PUSHED"
    except (RuntimeError, ValueError, KeyError) as exc:
        result.update(status="ERROR", error=redact(str(exc)))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Optional GitHub delivery helper")
    parser.add_argument("--repo", required=True, help="registered local repository name")
    parser.add_argument("--repo-root", help="explicit path to the repository checkout")
    parser.add_argument("--message", "-m", help="commit message; omit for read-only diagnosis")
    parser.add_argument("--file", action="append", default=[], help="literal task-owned file, repeatable")
    parser.add_argument("--push", action="store_true", help="explicitly push the current feature branch")
    parser.add_argument("--create-pr", action="store_true", help="create PR after explicit push")
    parser.add_argument("--target", default="main")
    args = parser.parse_args(argv)
    result = upload(args.repo, args.message, files=args.file, repo_root=args.repo_root,
                    push=args.push, create_pr=args.create_pr, target=args.target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"DONE_LOCAL", "DONE_PUSHED", "DIRTY_NO_ACTION",
                                      "CLEAN_LOCAL_REMOTE_UNVERIFIED", "UNPUSHED_COMMITS"} else 1


if __name__ == "__main__":
    sys.exit(main())
