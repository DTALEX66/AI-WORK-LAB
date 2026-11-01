# SPDX-License-Identifier: MIT
"""The files the toolchain anchors on must be LF in the working tree.

The incident: a scratch tool rewrote `apps/workbench/shell.ts` with `Path.write_text()`, which
on Windows translates every "\\n" to "\\r\\n". Nine tracked files became CRLF, and the first
thing that noticed was three falsifier scripts whose anchors contain "\\n" reporting
`count=0` -- guards that had silently stopped guarding while still exiting 0 on their other
plants.

Two designs were tried and rejected on measurement, not on taste:

* **diff-based ending-churn detection** is impossible here. With `core.autocrlf=true` git
  normalizes on comparison, so a pure CRLF conversion produces an EMPTY patch -- verified:
  converting `README.md` to CRLF yields zero bytes from both `git diff -- README.md` and
  `git diff --ignore-cr-at-eol -- README.md`. Nothing in git's view sees it.
* **whole-repo bytes-vs-attribute** flags 2,729 tracked files that are already CRLF on this
  machine and have been for a long time, including `.gitattributes` itself. A gate that is red
  on arrival gets narrowed into vacuity by the next person who runs it.

So the check names the files that actually matter: the ones whose bytes are matched by string
anchors in scripts and tests. Those must be pure LF. The last test plants a conversion on one
of them and confirms the gate goes red, then restores the bytes and asserts the restore.
"""
from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Every one of these is matched by a literal string anchor in a falsifier, a recorder or a
# gate, so a line-ending flip in any of them silently disables that guard rather than failing
# loudly. `design-lab/config/task-ledger-r3.json` earns its place the same way: the recorders
# rewrite it whole.
ANCHORED = [
    'apps/workbench/shell.ts',
    'apps/workbench/contracts.ts',
    'apps/workbench/style.css',
    'apps/workbench/tests/appshell.mjs',
    'src/design_lab/http_service.py',
    'design-lab/config/contract-bindings.json',
    'design-lab/config/task-ledger-r3.json',
    'design-lab/tests/e2e/audit_workbench_overflow.mjs',
]


def endings(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    crlf = raw.count(b'\r\n')
    return crlf, raw.count(b'\n') - crlf


class AnchoredFileEndingTests(unittest.TestCase):
    def test_every_anchored_file_exists(self):
        missing = [rel for rel in ANCHORED if not (REPO / rel).is_file()]
        self.assertEqual(missing, [],
                         'the list names files the toolchain anchors on; a renamed one means '
                         f'every anchor against it is now dead: {missing}')

    def test_anchored_files_are_pure_lf(self):
        offenders = []
        for rel in ANCHORED:
            crlf, lf = endings(REPO / rel)
            if crlf:
                offenders.append(f'{rel}: {crlf} CRLF and {lf} bare LF')
        self.assertEqual(offenders, [],
                         'these files carry CRLF line breaks, so every script whose anchor '
                         'contains "\\n" stops matching them without failing -- rewrite the '
                         'writer with Path.write_text(..., newline="\\n") or write_bytes: '
                         + '; '.join(offenders))

    def test_the_gate_convicts_a_planted_conversion(self):
        rel = 'apps/workbench/style.css'
        path = REPO / rel
        original = path.read_bytes()
        try:
            path.write_bytes(original.replace(b'\n', b'\r\n'))
            crlf, _ = endings(path)
            self.assertGreater(crlf, 0, 'the plant did not convert anything')
            offenders = [r for r in ANCHORED if endings(REPO / r)[0]]
            self.assertIn(rel, offenders,
                          'a CRLF conversion of an anchored file did not register -- this '
                          'gate would pass on the exact incident it exists for')
        finally:
            path.write_bytes(original)
        self.assertEqual(path.read_bytes(), original, 'the plant was not restored byte-exact')
        self.assertEqual(endings(path)[0], 0, 'restore left CRLF behind')


if __name__ == '__main__':
    unittest.main(verbosity=2)
