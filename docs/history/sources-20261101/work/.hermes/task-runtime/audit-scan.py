import subprocess, os, json, re, time, sys
repo = "D:/All projects/WORK-LAB"
out = open("D:/All projects/WORK-LAB/.project-local/runs/audit-scan.out.txt","w",encoding="utf-8")
def P(*a):
    out.write(" ".join(str(x) for x in a) + "\n")

def sh(args, t=90):
    r = subprocess.run(args, cwd=repo, capture_output=True, text=True, timeout=t)
    return r.stdout.strip()

# ===== A. REF CLASSIFICATION =====
P("=== A. REF CLASSIFICATION ===")
out_ref = sh(["git","for-each-ref","--format","%(refname) %(objectname:short)"])
local, tags, remote, other = [], [], [], []
for l in out_ref.splitlines():
    parts = l.split(" ",1)
    ref, sha = parts[0], parts[1] if len(parts)>1 else "?"
    if ref.startswith("refs/heads/"): local.append((ref[11:], sha))
    elif ref.startswith("refs/tags/"): tags.append((ref[8:], sha))
    elif ref.startswith("refs/remotes/origin/"): remote.append((ref[16:], sha))
    else: other.append(l)
P(f"local branches: {len(local)}")
for n,s in local: P(f"  HEAD: {n:45s} {s}")
P(f"tags: {len(tags)}")
P(f"remote origin branches: {len(remote)}")
for n,s in remote: P(f"  OBR: {n:45s} {s}")
P(f"other refs: {len(other)}")
for l in other: P("  ", l[:100])

# which remote branches are NOT in main history (i.e. have unique commits)?
P()
P("=== remote branches ahead of origin/main ===")
for n,s in remote:
    ahead = sh(["git","rev-list","--count",f"origin/main..origin/{n}"])
    if ahead != "0":
        P(f"  origin/{n}: ahead {ahead} commits")

# ===== B. SPILL SCAN (E/F + C-drive) =====
P()
P("=== B. SPILL / OUT-OF-PROJECT DATA ===")
P("E: drive exists:", os.path.exists("E:/"), "| F: exists:", os.path.exists("F:/"))
# .hermes/task-runtime + task-artifacts sizes
for d in [".hermes/task-runtime",".hermes/task-artifacts",".project-local/runs",".project-local/artifacts",".project-local/quarantine"]:
    p = os.path.join(repo,d)
    if os.path.isdir(p):
        total=0; files=0
        for root,_,fs in os.walk(p):
            for f in fs:
                try:
                    total += os.path.getsize(os.path.join(root,f)); files+=1
                except OSError: pass
        P(f"  {d:32s} {total/1048576:10.2f} MB ({files} files)")
    else:
        P(f"  {d:32s} (absent)")
# C-drive .dsh artifacts (from ERR-088)
P("C:\\Users\\ALEX\\.dsh exists:", os.path.exists("C:/Users/ALEX/.dsh"))
P("C:\\Users\\ALEX\\.dsh-skeleton-backup-20260924 exists:", os.path.exists("C:/Users/ALEX/.dsh-skeleton-backup-20260924"))
# junctions inside project (data-boundary concern)
P()
P("=== C. TRACKED FILE INVENTORY (repo conventions) ===")
counts = {}
for l in sh(["git","ls-files"]).splitlines():
    if not l.strip(): continue
    top = l.split("/")[0]
    counts[top] = counts.get(top,0)+1
for k,v in sorted(counts.items(), key=lambda x:-x[1]):
    P(f"  {k:36s} {v}")
P(f"total tracked: {sum(counts.values())}")

# ===== D. UNTRACKED/UNCOMMITTED =====
P()
P("=== D. WORKTREE STATE ===")
P("git status --short:", sh(["git","status","--short"]) or "(clean)")
P("branch:", sh(["git","branch","--show-current"]))
P("untracked top-level dirs:")
for l in sh(["git","ls-files","--others","--exclude-standard"]).splitlines():
    if not l.strip(): continue
    P("  ", l.split("/")[0])

out.close()
print("AUDIT_SCAN_DONE")
