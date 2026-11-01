"""Global workflow deployment readback: repo source vs live native targets (read-only)."""
import os, json, pathlib, hashlib, datetime

REPO = pathlib.Path(r"D:\All projects\WORK-LAB")
HOME = pathlib.Path(os.environ["USERPROFILE"])
LA = pathlib.Path(os.environ["LOCALAPPDATA"])
HERMES = LA / "hermes"
CODEX = HOME / ".codex"

def sha(p):
    h = hashlib.sha256()
    with open(str(p), "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

res = {"generated_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "policy": "Read-only hash comparison between repo-managed skills and live native targets."}

# 1. Hermes managed skills: repo source vs live Hermes skills tree
src_root = REPO / "packages" / "client-neutral-core" / "skills"
live_root = HERMES / "skills"
rows = []
for skill_md in sorted(src_root.rglob("SKILL.md")):
    rel = skill_md.relative_to(src_root)
    live = live_root / rel
    row = {"skill": str(rel).replace("\\", "/"), "repo_sha16": sha(skill_md)[:16]}
    if live.exists():
        row["live_sha16"] = sha(live)[:16]
        row["state"] = "MATCH" if row["live_sha16"] == row["repo_sha16"] else "DIFFERS"
        row["live_bytes"] = live.stat().st_size
    else:
        row["state"] = "MISSING_LIVE"
        # try to find by name anywhere (moved group dir?)
        cands = list(live_root.rglob(f"{rel.parent.name}/SKILL.md"))
        row["candidates"] = [str(c.relative_to(live_root)).replace("\\", "/") for c in cands[:3]]
    rows.append(row)
res["hermes_managed_skills"] = {
    "count": len(rows),
    "match": sum(1 for r in rows if r["state"] == "MATCH"),
    "differs": sum(1 for r in rows if r["state"] == "DIFFERS"),
    "missing_live": sum(1 for r in rows if r["state"] == "MISSING_LIVE"),
    "rows": rows,
}

# 2. Codex native targets from the extension
codex_targets = {
    "AGENTS.md": CODEX / "AGENTS.md",
    "config.toml": CODEX / "config.toml",
    "rules/workflow-assistance.rules": CODEX / "rules" / "workflow-assistance.rules",
    "rules/ dir exists": CODEX / "rules",
    "skills/ dir exists": CODEX / "skills",
}
cx = {}
for label, p in codex_targets.items():
    if p.exists() and p.is_file():
        txt = p.read_text(encoding="utf-8", errors="replace") if p.suffix in (".md", ".toml", ".rules") else ""
        cx[label] = {"exists": True, "bytes": p.stat().st_size, "sha256": sha(p)[:16],
                     "has_managed_marker": ("WORKFLOW-ASSISTANCE MANAGED" in txt),
                     "has_worklab_text": ("WORK-LAB" in txt)}
    else:
        cx[label] = {"exists": bool(p.exists())}
# count workflow-assistance skills live in codex
sk = CODEX / "skills"
cx["workflow_assistance_skill_dirs_live"] = sorted([d.name for d in sk.iterdir() if d.is_dir() and "workflow" in d.name.lower()]) if sk.exists() else []
res["codex_native_targets"] = cx

# 3. Hermes SOUL + bin matrix
res["hermes_other_targets"] = {
    "repo config/SOUL.md sha16": sha(REPO / "config" / "SOUL.md")[:16],
    "live SOUL.md sha16": sha(HERMES / "SOUL.md")[:16] if (HERMES / "SOUL.md").exists() else None,
    "repo bin/": sorted([p.name for p in (REPO / "bin").iterdir()]) if (REPO / "bin").exists() else [],
    "live hermes bin/": sorted([p.name for p in (HERMES / "bin").iterdir()])[:20] if (HERMES / "bin").exists() else [],
}
res["hermes_other_targets"]["soul_match"] = (
    res["hermes_other_targets"]["repo config/SOUL.md sha16"] == res["hermes_other_targets"]["live SOUL.md sha16"])

dest = REPO / "reports" / "audit-evidence" / "assets-20260930" / "global-deployment-readback.json"
dest.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("wrote", dest.name, dest.stat().st_size)
h = res["hermes_managed_skills"]
print(f"HERMES managed skills: {h['count']} -> MATCH={h['match']} DIFFERS={h['differs']} MISSING_LIVE={h['missing_live']}")
for r in h["rows"]:
    if r["state"] != "MATCH":
        print("   ", r["state"], r["skill"], r.get("candidates"))
print("SOUL match:", res["hermes_other_targets"]["soul_match"])
print("CODEX targets:")
for k, v in cx.items():
    print("   ", k, v)
