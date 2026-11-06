"""Turn a reviewer's own output into a tracked record, without typing any of its facts by hand.

A00#1 says the register must record *which SHA* was independently reviewed and what the reviewer
concluded. Both halves used to be impossible: the closure column was a constant, so the only value
it could ever hold was ``NOT_RUN``. This is the input side of that fix -- it reads the reviewer's
stdout, takes the verdict block from the reviewer's own words, verifies the SHA it claims against
this repository, and appends a record.

What it deliberately does not do: invent which audit items were covered. That comes from
``--items``, and the caller is expected to list only the ones the report shows evidence for. The
verdict, the SHA, the counts and the tool version all come from the artifact or from git.

Run:  .venv/Scripts/python.exe -B -X utf8 scripts/build_independent_review_record.py \
          --report .project-local/audit/20261106-independent/REVIEW-raw.txt \
          --artifact .project-local/audit/20261106-independent/REVIEW-raw.txt \
          --items F03,F04 --note "逐项表见报告正文"
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "config" / "independent-reviews.json"
VERDICTS = ("PASS", "PASS_WITH_FINDINGS", "FAIL")
FIELDS = {"verdict": "INDEPENDENT_REVIEW_VERDICT", "reviewed_sha": "reviewed_sha",
          "blocking_findings": "blocking_findings", "non_blocking_findings": "non_blocking_findings",
          "checks_actually_run": "checks_actually_run", "unverified_claims": "unverified_claims"}


def parse_report(text: str) -> dict:
    """The reviewer's own machine-readable block, last occurrence wins."""
    found = {}
    for line in text.splitlines():
        for key, label in FIELDS.items():
            match = re.match(r"^\s*%s:\s*(\S.*?)\s*$" % re.escape(label), line)
            if match:
                found[key] = match.group(1)
    missing = [label for key, label in FIELDS.items() if key not in found]
    if missing:
        raise SystemExit("REVIEW_REPORT_INCOMPLETE missing=" + ",".join(missing))
    if found["verdict"] not in VERDICTS:
        raise SystemExit("REVIEW_REPORT_VERDICT_UNKNOWN " + found["verdict"])
    for counter in ("blocking_findings", "non_blocking_findings", "checks_actually_run",
                    "unverified_claims"):
        if not re.fullmatch(r"\d+", found[counter]):
            raise SystemExit("REVIEW_REPORT_COUNTER_NOT_INTEGER %s=%s" % (counter, found[counter]))
    return found


def git(*args: str) -> str:
    done = subprocess.run(["git"] + list(args), cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise SystemExit("GIT_QUERY_FAILED " + " ".join(args) + ": " + done.stderr.strip()[:200])
    return done.stdout.strip()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", required=True, help="reviewer stdout to read the verdict from")
    parser.add_argument("--artifact", required=True, help="path recorded in the register cell")
    parser.add_argument("--items", default="", help="comma-separated closure IDs the report covers")
    parser.add_argument("--note", default="")
    parser.add_argument("--reviewer", default=None,
                        help="override the reviewer identity (default: the CLI's own --version)")
    parser.add_argument("--check", action="store_true", help="report what would be added, write nothing")
    args = parser.parse_args(argv[1:])

    report = pathlib.Path(args.report).read_text(encoding="utf-8", errors="replace")
    parsed = parse_report(report)
    claimed = parsed["reviewed_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", claimed):
        raise SystemExit("REVIEW_REPORT_SHA_NOT_A_FULL_COMMIT " + claimed[:20])
    head = git("rev-parse", "HEAD")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", claimed, "HEAD"],
                              cwd=str(ROOT), capture_output=True)
    if ancestor.returncode != 0:
        raise SystemExit("REVIEWED_SHA_NOT_IN_THIS_CHECKOUT %s (HEAD %s)" % (claimed[:12], head[:12]))

    reviewer = args.reviewer
    if reviewer is None:
        raise SystemExit("REVIEWER_IDENTITY_REQUIRED -- a record without a named reviewer is a "
                         "claim of independence, not evidence of it")
    record = dict(verdict=parsed["verdict"], reviewed_sha=claimed, reviewer=reviewer,
                  reviewed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  artifact=args.artifact, note=args.note,
                  verified_items=sorted({i.strip() for i in args.items.split(",") if i.strip()}),
                  blocking_findings=int(parsed["blocking_findings"]),
                  non_blocking_findings=int(parsed["non_blocking_findings"]),
                  checks_actually_run=int(parsed["checks_actually_run"]),
                  unverified_claims=int(parsed["unverified_claims"]),
                  review_state_at_record="CLEAN" if not git("status", "--porcelain=v1") else "DIRTY")
    known = set(csv_ids())
    unknown = sorted(set(record["verified_items"]) - known)
    if unknown:
        raise SystemExit("REVIEW_ITEM_NOT_IN_CLOSURE_REGISTER " + ",".join(unknown))

    document = (json.loads(OUT.read_text(encoding="utf-8-sig")) if OUT.is_file()
                else dict(schema_version="awl/independent-reviews/v1",
                          rule="复审结论一律取自复审者自己的输出块；被审 SHA 由 git 现读核验，"
                               "verified_items 只列报告里真的留下了读数的项",
                          records=[]))
    if args.check:
        print(json.dumps(dict(would_append=record, records=len(document["records"])),
                         ensure_ascii=False))
        return 0
    document["records"].append(record)
    OUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps(dict(written=str(OUT), records=len(document["records"]),
                          verdict=record["verdict"], reviewed_sha=record["reviewed_sha"][:12],
                          verified_items=record["verified_items"]), ensure_ascii=False))
    return 0


def csv_ids() -> list[str]:
    path = ROOT / "migration" / "audit-item-closure.csv"
    if not path.is_file():
        return []
    import csv as _csv
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row["ID"] for row in _csv.DictReader(handle)]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
