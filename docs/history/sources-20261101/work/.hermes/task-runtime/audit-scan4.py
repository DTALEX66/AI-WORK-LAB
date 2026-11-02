import subprocess, os, json, re, datetime
repo = "D:/All projects/WORK-LAB"
out = open("D:/All projects/WORK-LAB/.project-local/runs/audit-scan4.out.txt","w",encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")
def sh(args, t=120):
    r = subprocess.run([str(x) for x in args], cwd=repo, capture_output=True, text=True, timeout=t)
    return r.stdout.strip()

# ===== 1) TAG CENSUS (62) =====
P("=== 1) TAG CENSUS ===")
tags = sh(["git","tag","-l"]).splitlines()
P(f"total tags: {len(tags)}")
wl_retire = [t for t in tags if t.startswith("wl-retire-20260917/")]
other_tags = [t for t in tags if not t.startswith("wl-retire-20260917/")]
P(f"wl-retire-20260917/* = {len(wl_retire)} (branch-convergence retirement evidence, intentional per BRANCH-RETIREMENT-LEDGER)")
P("non-wl-retire tags:")
for t in other_tags:
    P(f"  {t}")

# ===== 2) LOCAL BRANCH DISPOSITION =====
P()
P("=== 2) LOCAL BRANCH DISPOSITION ===")
for b in sh(["git","branch","--format","%(refname:short)"]).splitlines():
    tip = sh(["git","rev-parse","--short",b])
    behind_main = sh(["git","rev-list","--count",f"{b}..origin/main"])
    ahead_main = sh(["git","rev-list","--count",f"origin/main..{b}"])
    has_pr = "yes" if b in ("chore/readme-v2-sync","dsh/err088-governance-20260924") else "no"
    P(f"  {b:38s} tip={tip} ahead_main={ahead_main} behind_main={behind_main} openPR={has_pr}")

# ===== 3) OPEN-TASK-REGISTER: rows NOT closed =====
P()
P("=== 3) OPEN-TASK-REGISTER — rows not ACCEPTED/closed ===")
reg = open("taskpacks/current/OPEN-TASK-REGISTER.md",encoding="utf-8").read()
for line in reg.splitlines():
    m = re.match(r"^\|\s*([A-ZU][\w-]+)\s*\|\s*(P\d|ENV|USER AUTH|OPTIONAL)\s*\|\s*([^|]+)\|", line)
    if m:
        rid, prio, status = m.group(1), m.group(2), m.group(3).strip()
        # flag anything not fully closed
        if not re.search(r"ACCEPTED|CLOSED|CONVERGED|RECORDED|MAPPED", status):
            P(f"  {rid:5s} {prio:10s} {status[:70]}")
P("  (rows flagged = still open per register status text)")

# ===== 4) authority chain — are the referenced files current? =====
P()
P("=== 4) authority index referenced-file validity ===")
pidx = json.load(open(".project/governance/project-authority-index.json"))
tidx = json.load(open(".project/governance/taskpack-authority-index.json"))
P(f"topHumanAuthority={pidx.get('topHumanAuthority')} exists={os.path.exists(pidx.get('topHumanAuthority',''))}")
P(f"currentTaskpack={tidx.get('currentTaskpack')}")
P(f"  exists={os.path.exists('taskpacks/current/'+tidx.get('currentTaskpack',''))}")
P(f"currentOpenTaskRegister={pidx.get('currentOpenTaskRegister')} exists={os.path.exists(pidx.get('currentOpenTaskRegister',''))}")
# baselineRevalidation freshness
br = tidx.get("baselineRevalidation",{})
P(f"baselineRevalidation.main_ref={br.get('main_ref')} (frozen 09-23)")
P(f"  actual origin/main={sh(['git','rev-parse','--short','origin/main'])}  -> revalidation anchor is HISTORICAL, trunk moved on (by design)")

# ===== 5) SPILL / boundary recheck =====
P()
P("=== 5) data-boundary / spill state ===")
bd = json.load(open(".project/governance/project-data-boundary.json"))
P(f"forbiddenExternalRoots={bd.get('forbiddenExternalRoots')}")
P(f"cacheRoot={bd.get('cacheRoot')} runtimeRoot={bd.get('runtimeRoot')}")
P("C-drive .dsh artifacts:")
P("  C:/Users/ALEX/.dsh :", os.path.exists("C:/Users/ALEX/.dsh"))
P("  C:/Users/ALEX/.dsh-skeleton-backup-20260924 :", os.path.exists("C:/Users/ALEX/.dsh-skeleton-backup-20260924"))
P("D-drive DSH migration archive (intended landing):")
mig = "D:/All projects/DSH/.migration/20260924/c-dsh-skeleton-backup-20260924"
P("  ", mig, "exists:", os.path.exists(mig))

# ===== 6) 9-month planning audit: which P0-P3 items from GOAL doc remain =====
P()
P("=== 6) GOAL §34 completion-criteria vs current tree (read-only) ===")
for f, label in [
  ("docs/decisions/PROJECT_POSITIONING.md","P0-03 PROJECT_POSITIONING"),
  ("docs/decisions/instruction-precedence.md","P0-06 precedence"),
  ("docs/current/workflow-assistance/workflow/active-authority-index.md","P0-03 active-authority-index (still 2nd top authority?)"),
  (".project/governance/projects.yaml","P0-04 projects.yaml (parallel module model vs projects.json)"),
  (".project/governance/data-ownership.yaml","P0-05 data-ownership.yaml (E-only vs boundary.json E+F)"),
  ("apps/control-surface","P1-06 control-surface dir (exists?)"),
  ("docs/current/product/future-candidate-registry.md","E future-candidate-registry"),
]:
    P(f"  {label:46s} -> {'PRESENT' if os.path.exists(f) else 'absent'} {f}")

out.close(); print("AUDIT_SCAN4_DONE")
