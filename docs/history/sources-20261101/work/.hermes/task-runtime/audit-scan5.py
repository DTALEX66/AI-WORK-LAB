import subprocess, os, json, re
repo = "D:/All projects/WORK-LAB"
out = open("D:/All projects/WORK-LAB/.project-local/runs/audit-scan5.out.txt","w",encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")
def sh(args, t=120):
    r = subprocess.run([str(x) for x in args], cwd=repo, capture_output=True, text=True, timeout=t)
    return r.stdout.strip()

# 1) taskpack existence — why did os.path.exists fail?
p = "taskpacks/current/WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918.md"
P("1) taskpack file direct check:")
P("   os.path.exists:", os.path.exists(p), "| abs:", os.path.abspath(p))
P("   git ls-files:", sh(["git","ls-files","--","taskpacks/current","-z"]).count(p))
P("   on-disk listing of taskpacks/current (UPC):", [f for f in os.listdir("taskpacks/current") if "UNIFIED" in f or "UPC" in f] or "NONE")

# 2) pre-commit hook target dir reality
P()
P("2) pre-commit hook target paths:")
P("   00-governance/ exists:", os.path.exists("00-governance"))
P("   .project/governance/generated/ exists:", os.path.exists(".project/governance/generated"))
P("   .project/governance/generated tracked files:", sh(["git","ls-files","--",".project/governance/generated"]))

# 3) generate_current_state.py — which dir does it write?
g = open("scripts/ci/generate_current_state.py",encoding="utf-8").read()
P("   generator writes to:", re.findall(r"[\"']([.a-z-]*generated[.a-z-]*)[\"']", g)[:5])

# 4) knowledge-staging nature
P()
P("3) knowledge-staging/:")
ks = sh(["git","ls-files","--","knowledge-staging"]).splitlines()
P("   tracked:", len(ks))
for f in ks[:6]: P("   ", f)
# what references it?
P("   consumers (grep):", (sh(["git","grep","-l","knowledge-staging","--","scripts","services","tests","packages",".github",".project"]) or "(none)").splitlines()[:8])

# 5) E:/F: footprint check (metadata only, no listing)
P()
P("4) E:/F: metadata only (no enumeration):")
for d in ["E:/","F:/"]:
    ex = os.path.exists(d)
    P(f"   {d} exists={ex} accessible-metadata={'(skipped - protected)' if ex else 'n/a'}")
# quarantine DSH removal detail
q1 = "D:/All projects/WORK-LAB/.project-local/quarantine/dsh-011-removed-20260824"
P("   quarantine dsh-011-removed-20260824 top entries:", (os.listdir(q1) if os.path.isdir(q1) else "absent")[:8])

# 6) CI re-run state for #132
P()
P("5) #132 CI — re-run check (any runs after 16:45:38Z failure?):")
full = "54add198d4d90eb2d96245bffecb713294697783"
o = sh(["gh","api", f"repos/DTALEX66/WORK-LAB/actions/runs?head_sha={full}&per_page=10"])
try:
    for run in json.loads(o).get("workflow_runs",[]):
        P(f"   {run['created_at']} wf={run['name']:24s} {run['status']}/{run.get('conclusion')} event={run.get('event')}")
except Exception as e:
    P("   parse err:", e)

out.close(); print("AUDIT_SCAN5_DONE")
