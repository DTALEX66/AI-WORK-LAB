import subprocess, os
repo = "D:/All projects/WORK-LAB"
out = open("D:/All projects/WORK-LAB/.project-local/runs/audit-scan2.out.txt","w",encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")
def sh(args, t=120):
    r = subprocess.run(args, cwd=repo, capture_output=True, text=True, timeout=t)
    return r.stdout.strip()

# 1) authority §4 canonical surfaces vs actual tracked top-level dirs
P("=== 1) WORK-LAB-AUTHORITY.md §4 declared active surfaces ===")
auth = open("WORK-LAB-AUTHORITY.md",encoding="utf-8").read()
import re
m = re.search(r"## 4\..*?```text\n(.*?)```", auth, re.S)
if m:
    for l in m.group(1).splitlines():
        P("  declared:", l.strip())
P("actual tracked top-level dirs not in §4:")
declared = set()
if m:
    for l in m.group(1).splitlines():
        s=l.strip().rstrip("/")
        if s: declared.add(s)
for d in ["knowledge-staging","projections","reports"]:
    n = len([x for x in sh(["git","ls-files","--",d]).splitlines() if x.strip()])
    P(f"  {d:18s} tracked_files={n}  in_authority_S4={d in declared}")

P()
P("=== 2) .githooks/pre-commit — does it still reference legacy 00-governance? ===")
hook = open(".githooks/pre-commit",encoding="utf-8").read()
for pat in ["00-governance/generated",".project/governance/generated","generate_current_state.py"]:
    P(f"  hook mentions '{pat}':", pat in hook)
P("  (00-governance/ on disk?)", os.path.exists("00-governance"), " | .project/governance/generated on disk:", os.path.exists(".project/governance/generated"))

P()
P("=== 3) refs/codex/* — local only or pushed? ===")
rc = sh(["git","for-each-ref","--format","%(refname)","refs/codex/"])
P(rc or "(none)")
P("remote has codex refs:", sh(["git","ls-remote","origin","refs/codex/*"]) or "(NONE pushed)")

P()
P("=== 4) LANGUAGE CENSUS (project language discipline) ===")
exts = {}
for l in sh(["git","ls-files"]).splitlines():
    if not l.strip(): continue
    base = l.split("/")[-1]
    for e in [".py",".ts",".tsx",".rs",".js",".sh",".ps1",".yaml",".yml",".json",".md"]:
        if base.endswith(e):
            exts[e] = exts.get(e,0)+1; break
# count by top-level owner
P("extension census (tracked):")
for k,v in sorted(exts.items(), key=lambda x:-x[1]): P(f"  {k:6s} {v}")
P()
P("Rust files location (should be native/desktop boundary only):")
P(sh(["git","ls-files","*.rs"])[:800] or "(no .rs)")
P()
P("PowerShell .ps1 files (bootstrap-only per §8):")
P(sh(["git","ls-files","*.ps1"])[:600] or "(no .ps1)")
P()
P("=== 5) projections/ + reports/ contents ===")
P("projections/:", sh(["git","ls-files","--","projections"]))
P("reports/:", sh(["git","ls-files","--","reports"]))

P()
P("=== 6) quarantine breakdown (spill, deferred) ===")
q = os.path.join(repo,".project-local","quarantine")
if os.path.isdir(q):
    tot=0; bytop={}
    for root,_,fs in os.walk(q):
        rel = os.path.relpath(root,q)
        top = rel.split(os.sep)[0] if rel!="." else "(root)"
        for f in fs:
            try: s=os.path.getsize(os.path.join(root,f))
            except OSError: s=0
            bytop[top] = bytop.get(top,0)+s
            tot+=s
    P(f"quarantine total {tot/1073741824:.2f} GB; by top entry:")
    for k,v in sorted(bytop.items(), key=lambda x:-x[1])[:8]:
        P(f"  {k:40s} {v/1048576:9.1f} MB")

P()
P("=== 7) untracked .bak/.orig anywhere (D2 re-check) ===")
P(sh(["git","ls-files","--others","--exclude-standard","-i","--","*.bak","*.orig","*.backup"]) or "(none untracked)")
P("tracked .bak/.orig:", sh(["git","ls-files","-i","--","*.bak","*.orig","*.backup"]) or "(none tracked)")

out.close(); print("AUDIT_SCAN2_DONE")
