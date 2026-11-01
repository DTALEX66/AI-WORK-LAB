#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail closed when the single mutable ledger breaks its own R5 contract.

`generate_current_reports.py --check` additionally compares generated output
against a generation-time git snapshot, so it cannot run on a clean checkout.
This gate validates exactly the part that can, and it is the check that would
have caught the 1acbfa1 ledger break instead of letting it sit invisible for
six days with `reports/current/**` frozen behind a crashing generator.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab.governance.reporting import validate_ledger_contract


def main() -> int:
    try:
        validate_ledger_contract(REPO)
    except Exception as exc:  # a contract break is a report line, not a traceback
        print(f'TASK_LEDGER_CONTRACT=FAIL {type(exc).__name__}: {exc}')
        return 1
    print('TASK_LEDGER_CONTRACT=OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
