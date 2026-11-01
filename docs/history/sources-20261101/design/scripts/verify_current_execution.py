# SPDX-License-Identifier: MIT
"""Read-only current task partition, source, dependency and frozen-history check."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.governance.reporting import Reader, validate_ledger_contract
from design_lab.governance.current_execution import projection

if __name__ == '__main__':
    try:
        validate_ledger_contract(ROOT)
        ledger = json.loads((ROOT / 'design-lab/config/task-ledger-r3.json').read_text(encoding='utf-8'))
        p = projection(Reader(ROOT), ledger)
        print(f'CURRENT_EXECUTION=PASS tasks={len(p["tasks"])} mobile={p["mobile"]} '
              f'counts={p["counts"]} product_evidence=NO_EVIDENCE_UNLESS_BOUND')
    except (ValueError, KeyError, OSError) as exc:
        print('CURRENT_EXECUTION=FAIL ' + str(exc))
        raise SystemExit(1)
