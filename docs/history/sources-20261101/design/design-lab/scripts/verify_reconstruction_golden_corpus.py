#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify rights, topology, frozen hashes, and anti-reference-overlay lineage."""
from __future__ import annotations

import sys
from pathlib import Path


DESIGN_LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESIGN_LAB))
sys.path.insert(0, str(DESIGN_LAB.parent / "packages" / "capabilities"))

from reconstruction.golden_corpus import load_corpus  # noqa: E402


def main() -> int:
    corpus_path = DESIGN_LAB / "evals" / "reconstruction" / "golden-corpus.json"
    try:
        corpus = load_corpus(corpus_path)
        for case in corpus.cases:
            if case.reference_sha256 != case.actual_reference_sha256:
                raise ValueError(f"hash mismatch: {case.case_id}")
            if case.reference_sha256 in case.allowed_output_asset_hashes:
                raise ValueError(f"reference overlay registered as output: {case.case_id}")
    except Exception as exc:
        print(f"RECONSTRUCTION_GOLDEN=FAIL reason={exc}")
        return 1
    print(f"RECONSTRUCTION_GOLDEN=PASS cases={len(corpus.cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
