#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute the real C5 API/CLI lifecycle regression suite."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    design_lab = Path(__file__).resolve().parents[1]
    tests = design_lab / "tests"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(tests),
            "-p",
            "test_reconstruction_pipeline.py",
            "-v",
        ],
        cwd=design_lab.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = completed.stdout + "\n" + completed.stderr
    match = re.search(r"Ran (\d+) tests?", combined)
    cases = int(match.group(1)) if match else 0
    if completed.returncode != 0 or cases <= 0:
        print(combined)
        print(f"RECONSTRUCTION_PIPELINE=FAIL cases={cases}")
        return 1
    print(f"RECONSTRUCTION_PIPELINE=PASS cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
