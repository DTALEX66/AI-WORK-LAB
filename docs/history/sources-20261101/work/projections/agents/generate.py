#!/usr/bin/env python3
"""Deterministic projection generator (WL-DIR-060).

Generates root .agents/ projections from projections/agents/source/.
Output files are marked GENERATED — DO NOT EDIT with a content hash.
CI deletes the projection and re-runs this to verify determinism via
`git diff --exit-code`.
"""
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = ROOT / "projections" / "agents" / "source"
TARGET = ROOT / ".agents"
GENERATOR_VERSION = "1.0.0"


def generate():
    """Generate all .agents projections from source."""
    if not SOURCE.exists():
        print("No source directory; nothing to generate")
        return 0

    generated = []
    for skill_dir in SOURCE.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        content = skill_md.read_text(encoding="utf-8")
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()

        header = (
            f"<!-- GENERATED — DO NOT EDIT -->\n"
            f"<!-- source: projections/agents/source/{skill_dir.name}/SKILL.md -->\n"
            f"<!-- generator: projections/agents/generate.py v{GENERATOR_VERSION} -->\n"
            f"<!-- content_hash: sha256:{sha} -->\n"
        )
        out = header + content

        out_dir = TARGET / "skills" / skill_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "SKILL.md"
        # Bytes, not text mode: on Windows write_text translates "\n" to CRLF, so the projection's
        # bytes -- and therefore the content hash a reader checks -- came out different on every
        # platform for one unchanged source. That is what test_two_generations_produce_the_same_bytes
        # was reporting as drift (same class as ERR-275, on the producing side this time).
        out_file.write_bytes(out.encode("utf-8"))
        generated.append(str(out_file))

    print(f"Generated {len(generated)} projection(s):")
    for g in generated:
        print(f"  {g}")
    return 0


if __name__ == "__main__":
    sys.exit(generate())
