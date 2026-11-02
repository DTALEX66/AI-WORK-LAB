import subprocess, json, os
repo = "D:/All projects/WORK-LAB"
out = open("D:/All projects/WORK-LAB/.project-local/runs/audit-scan3.out.txt","w",encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")

def gh(args):
    r = subprocess.run(["gh"]+args, cwd=repo, capture_output=True, text=True, timeout=60)
    return r.stdout.strip()

for pr, head in [("131","c26b636"),("132","54add19")]:
    P(f"=== PR#{pr} head={head} — work-lab-gate runs (newest first) ===")
    r = subprocess.run(["gh","api",f"repos/DTALEX66/WORK-LAB/actions/runs?head_sha={head}&per_page=5"],
                       cwd=repo, capture_output=True, text=True, timeout=60)
    try:
        runs = json.loads(r.stdout).get("workflow_runs", [])
    except Exception:
        runs = []
    for run in runs:
        P(f"  {run.get('created_at','')} wf={run.get('name',''):24s} {run.get('status','')}/{run.get('conclusion','')} "
          f"url={run.get('html_url','')}")
    P()

# failing jobs detail for #132 (latest run)
r = subprocess.run(["gh","api","repos/DTALEX66/WORK-LAB/actions/runs?head_sha=54add19&per_page=5"],
                   cwd=repo, capture_output=True, text=True, timeout=60)
try:
    runs = json.loads(r.stdout).get("workflow_runs", [])
    if runs:
        rid = runs[0]["id"]
        jr = subprocess.run(["gh","api",f"repos/DTALEX66/WORK-LAB/actions/runs/{rid}/jobs?per_page=20"],
                            cwd=repo, capture_output=True, text=True, timeout=60)
        jobs = json.loads(jr.stdout).get("jobs", [])
        P("latest #132 run jobs:")
        for j in jobs:
            P(f"  {j.get('name',''):24s} {j.get('status','')}/{j.get('conclusion','')}")
except Exception as e:
    P(f"job detail failed: {e}")

out.close(); print("AUDIT_SCAN3_DONE")
