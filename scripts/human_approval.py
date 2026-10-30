# SPDX-License-Identifier: MIT
"""Mint one named-human professional acceptance at a local terminal gate (F08).

This is the only way a live-origin approval enters the ledger, and it is
deliberately not reachable over HTTP: a client that can already send a verdict
string could otherwise approve itself. The person types their name and a
statement here; the row binds the exact result id and the stored content digest,
so it cannot be reused for different bytes or a different result.

    .venv/Scripts/python.exe scripts/human_approval.py \
        --store workspace/.project-local/ai-work-lab/unified.sqlite3 \
        --ledger workspace/.project-local/ai-work-lab/human-approvals.json \
        --result-id <32 hex>

Identity is attested, not verified — see backend/core/human_gate.py's
IDENTITY_LIMITS. ``--allow-non-interactive`` exists so the contract is testable,
and it stamps the row ``data_origin=test``: a fixture approval can never satisfy
real professional acceptance.

Writes only the ledger file. Never touches the store it reads.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
for entry in (str(TARGET_ROOT), str(TARGET_ROOT / "domains" / "design")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backend.core.human_gate import ApprovalError, ApprovalLedger, mint_interactively  # noqa: E402
from backend.core.unified_store import UnifiedStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    # The prompts and the receipt lines carry Chinese; a Windows console defaults
    # to cp936 and a caller reading this output as UTF-8 (a test, an audit script)
    # would fail to decode it rather than see a refusal.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", required=True, type=Path,
                        help="unified store to read the result's digest from (opened read-only)")
    parser.add_argument("--ledger", required=True, type=Path,
                        help="human-approval ledger file to append")
    parser.add_argument("--result-id", required=True, help="the result this approval accepts")
    parser.add_argument("--allow-non-interactive", action="store_true",
                        help="test fixture only: records data_origin=test and reads stdin once")
    parser.add_argument("--verifier", help="with --allow-non-interactive: human:<name>")
    parser.add_argument("--statement", help="with --allow-non-interactive: what was accepted")
    args = parser.parse_args(argv)

    if not args.store.is_file():
        print("STORE_MISSING " + str(args.store), file=sys.stderr)
        return 2
    store = UnifiedStore.open_readonly(args.store)
    try:
        result = store.get_result(args.result_id)
    finally:
        store.close()
    if result is None:
        print("RESULT_NOT_FOUND " + repr(args.result_id)
              + " — approve a result the store actually carries", file=sys.stderr)
        return 2
    if not result["verifications"]:
        print("RESULT_NOT_VERIFIED " + repr(args.result_id)
              + " — a professional approval is given over an imported result", file=sys.stderr)
        return 2
    ledger = ApprovalLedger(args.ledger)
    reader = None
    if args.allow_non_interactive and args.verifier and args.statement:
        lines = iter((args.verifier, args.statement))
        reader = lambda _prompt: next(lines)  # noqa: E731 - fixed two-field fixture input
    try:
        row = mint_interactively(ledger, result_id=result["result_id"],
                                 subject_fingerprint=result["content_sha256"],
                                 prompt_reader=reader,
                                 require_tty=not args.allow_non_interactive)
    except (ApprovalError, StopIteration) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("APPROVAL_MINTED " + row["approval_id"])
    print("RESULT_ID       " + row["result_id"])
    print("FINGERPRINT     " + row["subject_fingerprint"])
    print("VERIFIER        " + row["verifier_ref"])
    print("DATA_ORIGIN     " + row["data_origin"])
    print("IDENTITY_STATE  " + row["identity_state"])
    print("Now submit the verdict with POST /api/v1/results/<id>/verifications "
          "{axis: professional, professional_verdict: PASS, approval_ref: "
          + row["approval_id"] + "}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
