"""Gate: a surface declared FROZEN must stay byte-identical, or the run says which file moved.

Three history surfaces carry a `FROZEN.md` declaration and a `FROZEN-MANIFEST.json` listing every other
tracked file with `bytes` and `sha256`. Before this, "frozen" was a sentence: DOCUMENT-CENSUS described
`90-archive/` as holding frozen historical reports, and the directory had long since been converged down
to one marker file — nobody could tell, because nothing compared the bytes.

The manifest cannot digest itself, so it is excluded by name; that exclusion is asserted here rather
than assumed, because an unlisted exemption is how a "frozen" tree starts accepting edits.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_NAME = "FROZEN-MANIFEST.json"
SURFACES = ("knowledge-staging", "docs/history/archive", "reports/audit-archive")

spec = importlib.util.spec_from_file_location(
    "frozen_manifest", ROOT / "scripts" / "audit" / "generate_frozen_surface_manifest.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)  # type: ignore[attr-defined]


def tracked(root: str) -> list[str]:
    # `-z` is not cosmetic: without it git quotes any path with a non-ASCII byte, the quoted string is
    # not a real filename, and a sum over "files that resolved" silently under-counts a tree that is
    # 96% one CJK-named archive. That is how the census number for docs/history/archive came to read
    # 1.09 MB when the bytes are 38.5 MB.
    out = subprocess.run(["git", "ls-files", "-z", "--", root], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return sorted(p.replace("\\", "/") for p in (out.stdout or "").split("\0") if p.strip())


def derive(root: str) -> dict[str, dict]:
    members = {}
    for rel in tracked(root):
        rel = rel.replace("\\", "/")
        if rel == f"{root}/{MANIFEST_NAME}":
            continue
        digest, size = gen.sha256_of(rel)
        members[rel] = {"path": rel, "bytes": size, "sha256": digest}
    return members


def drift(listed: dict[str, dict], now: dict[str, dict]) -> list[str]:
    """What moved between a published manifest and the tree as it is now.

    Split out so a test can hand it a planted state: the alternative is a "negative control" that only
    proves two hand-written dictionaries differ, which is not the same claim.
    """
    problems: list[str] = []
    for added in sorted(set(now) - set(listed)):
        problems.append(f"ADDED {added}")
    for removed in sorted(set(listed) - set(now)):
        problems.append(f"REMOVED {removed}")
    for path in sorted(set(listed) & set(now)):
        if listed[path]["sha256"] != now[path]["sha256"]:
            problems.append(f"CHANGED {path} manifest={listed[path]['sha256'][:12]} "
                            f"now={now[path]['sha256'][:12]}")
        elif listed[path]["bytes"] != now[path]["bytes"]:
            problems.append(f"SIZE {path} manifest={listed[path]['bytes']} now={now[path]['bytes']}")
    return problems


class FrozenSurfaceTests(unittest.TestCase):
    def test_every_declared_surface_is_intact(self) -> None:
        problems: list[str] = []
        for root in SURFACES:
            manifest = ROOT / root / MANIFEST_NAME
            self.assertTrue(manifest.is_file(), f"{root}: {MANIFEST_NAME} is missing")
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            listed = {m["path"]: m for m in doc["files"]}
            for message in drift(listed, derive(root)):
                problems.append(f"{root}: {message}")
            self.assertEqual(doc["totals"], {"files": len(listed),
                                             "bytes": sum(m["bytes"] for m in listed.values())},
                             f"{root}: the manifest disagrees with its own entries")
        self.assertEqual(problems, [], "frozen surfaces drifted:\n  " + "\n  ".join(problems[:20]))

    def test_the_declaration_states_what_the_manifest_cannot(self) -> None:
        for root in SURFACES:
            text = (ROOT / root / "FROZEN.md").read_text(encoding="utf-8")
            self.assertIn("Normative:** NO", text, f"{root}/FROZEN.md does not disclaim authority")
            self.assertIn(MANIFEST_NAME, text, f"{root}/FROZEN.md does not name its manifest")
            self.assertIn("generate_frozen_surface_manifest.py", text,
                          f"{root}/FROZEN.md does not say how to regenerate deliberately")

    def test_the_manifest_excludes_only_itself(self) -> None:
        for root in SURFACES:
            doc = json.loads((ROOT / root / MANIFEST_NAME).read_text(encoding="utf-8"))
            paths = {m["path"] for m in doc["files"]}
            self.assertNotIn(f"{root}/{MANIFEST_NAME}", paths,
                             f"{root}: the manifest lists itself, so it can never match a re-derivation")
            self.assertIn(f"{root}/FROZEN.md", paths,
                          f"{root}: the declaration is outside its own freeze, so it could be rewritten "
                          f"without a trace")

    def test_a_frozen_surface_is_not_empty(self) -> None:
        # An empty tree hashes to a plausible digest; refusing it is the difference between a freeze and
        # a fabricated one.
        for root in SURFACES:
            doc = json.loads((ROOT / root / MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertGreater(doc["totals"]["files"], 50, f"{root} is too small to be the surface claimed")
            self.assertGreater(doc["totals"]["bytes"], 100000, f"{root} has no real bytes behind it")


class GeneratorRefusalsTests(unittest.TestCase):
    def test_a_surface_with_no_tracked_files_is_refused_not_published(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            gen.build("tests/ci/no-such-surface-xyz")
        self.assertIn("tracked_files=0", str(caught.exception))

    def test_the_detector_names_a_changed_an_added_and_removed_file(self) -> None:
        # Real coverage for the comparison used above, driven through the same function the gate calls.
        listed = {"a.md": {"path": "a.md", "bytes": 10, "sha256": "a" * 64},
                  "b.md": {"path": "b.md", "bytes": 20, "sha256": "b" * 64}}
        now = {"a.md": {"path": "a.md", "bytes": 10, "sha256": "f" * 64},
               "b.md": {"path": "b.md", "bytes": 21, "sha256": "b" * 64},
               "c.md": {"path": "c.md", "bytes": 5, "sha256": "c" * 64}}
        found = drift(listed, now)
        self.assertEqual(sorted(f.split()[0] for f in found), ["ADDED", "CHANGED", "SIZE"])
        self.assertIn("CHANGED a.md", " ".join(found))
        self.assertIn("ADDED c.md", " ".join(found))
        self.assertIn("SIZE b.md", " ".join(found))
        self.assertEqual(drift(listed, dict(listed)), [], "an unchanged tree must produce no drift")
        self.assertEqual(drift(listed, {}), ["REMOVED a.md", "REMOVED b.md"],
                         "a surface that vanished has to be reported, not read as clean")


if __name__ == "__main__":
    unittest.main(verbosity=2)
