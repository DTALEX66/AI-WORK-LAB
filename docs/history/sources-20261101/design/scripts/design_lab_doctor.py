#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Repository-compatible doctor entry; installation entry is owned by R3-09."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from design_lab.runtime.doctor import main

if __name__ == '__main__':
    raise SystemExit(main())
