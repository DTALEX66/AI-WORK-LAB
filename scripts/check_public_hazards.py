"""Public-surface credential check, run by the pre-push guard and by CI-equivalent gates.

Two defects in the throwaway version this replaces, both of which produced a confident "0 live-shaped"
while GitHub was alerting on four:

* the AWS family list carried only ``AKIA``. Temporary session keys are ``ASIA``, and CloudFront key pair
  ids are ``APKA`` -- so the whole alert class was outside the population being scanned. A family list is a
  claim about coverage, and this one was wrong.
* a CRC "is this a well-formed AWS key id" test was used to *downgrade* findings. My implementation had no
  positive control against a key AWS actually issued, and GitHub alerts on format alone. A check that can
  talk itself out of a finding is worse than no check, because it reports green.

So: every AWS-prefixed identifier is a finding, full stop. Structure (checksum) is reported as extra
information and never waives anything. A finding is waived only by an entry in
``config/secret-scan-adjudications.json`` that still matches the file's current digest -- if the file changes,
the adjudication stops applying and the check goes red again rather than inheriting an old decision.
"""
import argparse
import base64
import binascii
import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "config/secret-scan-adjudications.json"
LONG = chr(92) * 2 + chr(63) + chr(92)
AWS_PREFIXES = ("AKIA", "ASIA", "ABIA", "ACCA", "AGPA", "AIDA", "AROA", "ANPA", "ANVA", "APKA",
                "ASCA", "ASPA", "AVTA")
FAMILIES = {
    # Detection alphabet stays the broad [0-9A-Z] GitHub matches: narrowing to base32 here would silently
    # drop any key containing 0/1/8/9, which is the same population mistake that hid the ASIA alerts.
    "aws-key-id": re.compile(r"(?<![A-Za-z0-9])(" + "|".join(AWS_PREFIXES) + r")([0-9A-Z]{16})(?![A-Za-z0-9])"),
    "github-classic-token": re.compile(r"(?<![A-Za-z0-9])ghp_([A-Za-z0-9]{36})(?![A-Za-z0-9])"),
    "github-fine-grained-token": re.compile(r"(?<![A-Za-z0-9])github_pat_([A-Za-z0-9_]{22,})(?![A-Za-z0-9])"),
    "slack-token": re.compile(r"(?<![A-Za-z0-9])xox[baprs]-([A-Za-z0-9-]{10,})(?![A-Za-z0-9])"),
    "private-key-body": re.compile(r"BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY(?:"
                                   r"[\r\n][A-Za-z0-9+/=]{" + "20," + r"})"),
    "connection-string-auth": re.compile(r"(?i)\b(?:mongodb|mysql|postgres(?:ql)?|redis|amqp)://"
                                         r"([^\s:/@]{1,64}):([^\s@]{4,})@"),
    "secret-assignment": re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|"
                                    r"refresh[_-]?token|client[_-]?secret)\b\s*[:=]\s*"
                                    r"[\"']([A-Za-z0-9_\-\.]{16,})[\"']"),
    "authorization-bearer": re.compile(r"(?i)authorization\s*[:=]?\s*[\"']?bearer\s+"
                                        r"([A-Za-z0-9_\-\.=]{16,})"),
}
# Narrow on purpose: only a value that is *obviously* an example is waived here. Anything else has to be
# adjudicated in the ledger, by name, with a reason and a file digest that still matches.
CANONICAL_EXAMPLES = {"AKIAIOSFODNN7EXAMPLE", "AKIAABCDEFGHIJKLMNOP", "ASIAIOSFODNN7EXAMPLE",
                      "ASIAABCDEFGHIJKLMNOP"}
SHORTHAND = re.compile(r"^(?:([A-Za-z0-9])\1{5,}|x{6,}|X{6,}|0{6,})$")
#: Only shapes that cannot be a real key in any alphabet. Anything random-looking has to be adjudicated
#: by name, with a reason -- which is why this list is short and literal rather than fuzzy.
EXAMPLE_LITERAL = re.compile(r"(?i)^(?:your|example|sample|placeholder|synthetic|dummy|fake|"
                             r"notreal|not_real|redacted|masked)[a-z0-9_\-]*$")


def structure_note(prefix, body):
    """Informational only: never used to decide whether something is a finding."""
    try:
        decoded = base64.b32decode(body)
    except Exception:
        return "undecodable-base32"
    if len(decoded) != 10:
        return "not-10-bytes"
    crc = struct.pack(">I", binascii.crc32(decoded[:8]) & 0xFFFFFFFF)[2:4]
    return "crc-matches" if decoded[8:10] == crc else "crc-mismatch"


def tracked_files():
    raw = subprocess.run(["git", "ls-files", "-z"], capture_output=True, cwd=str(ROOT)).stdout
    return [p.decode("utf-8") for p in raw.split(b"\0") if p]


def masked(value):
    return value[:6] + "…" + str(len(value))


def load_ledger():
    if not LEDGER.is_file():
        return {"entries": []}
    return json.loads(LEDGER.read_text(encoding="utf-8-sig"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="same verdict, machine-readable")
    parser.add_argument("--emit", type=pathlib.Path,
                        help="write the current findings as ledger entries (still needs a reason per entry)")
    args = parser.parse_args(argv)

    ledger = load_ledger()
    waived_index = {}
    stale = []
    for entry in ledger.get("entries", []):
        waived_index[(entry["file"], entry["family"], entry["value_sha256"])] = entry
    findings = []
    for rel in tracked_files():
        try:
            text = open(LONG + str((ROOT / rel).resolve(strict=False)), "rb").read().decode(
                "utf-8", errors="replace")
        except OSError:
            continue
        if "\x00" in text[:4096]:
            continue
        file_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        for family, pattern in FAMILIES.items():
            for match in pattern.finditer(text):
                value = match.group(0)
                line = text[:match.start()].count("\n") + 1
                material = match.group(match.lastindex) if match.lastindex else value
                note = ""
                if family == "aws-key-id":
                    value = match.group(1) + match.group(2)
                    material = value
                    note = structure_note(match.group(1), match.group(2))
                if (value.upper() in CANONICAL_EXAMPLES or SHORTHAND.match(material)
                        or EXAMPLE_LITERAL.match(material)):
                    status = "example-literal"
                elif (rel, family, hashlib.sha256(value.encode()).hexdigest()) in waived_index:
                    kept = waived_index[(rel, family, hashlib.sha256(value.encode()).hexdigest())]
                    if kept.get("file_sha256") != file_digest:
                        status = "adjudication-stale"
                        stale.append((rel, family, masked(value), kept.get("decided_at", "?")))
                    else:
                        status = "adjudicated"
                else:
                    status = "unadjudicated"
                findings.append({"file": rel, "line": line, "family": family, "value": masked(value),
                                 "value_sha256": hashlib.sha256(value.encode()).hexdigest(),
                                 "structure": note, "status": status, "file_sha256": file_digest})
    blocking = [f for f in findings if f["status"] in ("unadjudicated", "adjudication-stale")]
    if args.emit:
        args.emit.write_text(json.dumps(findings, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8", newline="\n")
    print(json.dumps({"scanned_files": len(tracked_files()), "findings": len(findings),
                      "by_status": {key: sum(1 for f in findings if f["status"] == key)
                                    for key in ("unadjudicated", "adjudication-stale", "adjudicated",
                                                "example-literal")},
                      "blocking": len(blocking)}, ensure_ascii=False))
    for item in blocking[:20]:
        print("  %-24s %-10s %s:%d" % (item["family"], item["status"], item["file"][-64:],
                                       item["line"]))
    if stale:
        print("  裁决因文件变更失效：" + "; ".join("%s %s" % (s[0][-40:], s[1]) for s in stale[:6]))
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
