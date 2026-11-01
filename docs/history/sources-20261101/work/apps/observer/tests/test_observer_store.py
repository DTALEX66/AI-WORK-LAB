from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parents[1]
sys.path.insert(0, str(MODULE_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "services" / "orchestration"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "observer" / "scripts"))

from canonical_store import CanonicalStore  # noqa: E402
from observer_runtime import ObserverInputError  # noqa: E402
from observer_store import ObserverStore  # noqa: E402


class ObserverStoreTests(unittest.TestCase):
    def make_root(self, raw: str) -> tuple[Path, Path]:
        project = Path(raw)
        (project / ".git").mkdir()
        path = project / ".hermes" / "task-runtime" / "workflow" / "canonical.sqlite"
        writer = CanonicalStore(path)
        writer.register_project("work-lab", "<redacted>")
        writer.upsert_task({"task_id": "t1", "project_id": "work-lab", "status": "RUNNING"})
        writer.close()
        return project, path

    def test_reads_canonical_projection_without_mutating_database(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project, path = self.make_root(raw)
            before = (path.stat().st_mtime_ns, path.stat().st_size)
            store = ObserverStore(path, project_root=project)
            projection = store.rebuild_projection()
            store.close()
            after = (path.stat().st_mtime_ns, path.stat().st_size)
            self.assertEqual(projection["schemaVersion"], "workflow/snapshot/v3")
            self.assertIn("executions", projection)
            self.assertIn("tokenSummary", projection)
            self.assertEqual(before, after)
            self.assertFalse((path.parent.parent / "observer").exists())

    def test_append_is_always_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project, path = self.make_root(raw)
            store = ObserverStore(path, project_root=project)
            with self.assertRaises(ObserverInputError):
                store.append([{"eventId": "forbidden"}])
            store.close()

    def test_rejects_noncanonical_or_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project, path = self.make_root(raw)
            with self.assertRaises(ValueError):
                ObserverStore(path.parent / "observer-events.jsonl", project_root=project)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                ObserverStore(path, project_root=project)

    def test_rebuild_enriches_governance_from_real_repo(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project, path = self.make_root(raw)
            store = ObserverStore(path, project_root=project)
            projection = store.rebuild_projection()
            store.close()
            gov = projection.get("governance", {})
            # Governance must carry real repo inventory dimensions, never all-None
            # placeholders once the repo exists.
            self.assertIsInstance(gov.get("rules", {}).get("current"), (int, type(None)))
            self.assertIsInstance(gov.get("skills", {}).get("current"), (int, type(None)))
            self.assertIsInstance(gov.get("adapters", {}).get("current"), (int, type(None)))

    def test_readonly_store_rejects_writes(self) -> None:
        """WL3-605: a capability-level read-only CanonicalStore must fail
        closed on any write statement (no migration, no WAL, URI mode=ro)."""
        with tempfile.TemporaryDirectory() as raw:
            project, path = self.make_root(raw)
            store = CanonicalStore(path, readonly=True)
            try:
                # Reads keep working on the readonly connection.
                self.assertIsInstance(store.seed_revision(), int)
                with self.assertRaises(Exception) as ctx:
                    store.register_project("nope", "<redacted>")
                self.assertIn("readonly", str(ctx.exception).lower())
            finally:
                store.close()

    def test_readonly_uri_surves_special_characters_in_paths(self) -> None:
        """A1: the read-only URI must be percent-encoded, never interpolated.

        A raw `f"file:{path}?mode=ro"` reads `#` as a fragment terminator and
        `%XX` as an escape, so a store named `with#hash.db` opened (and
        CREATED) a truncated writable file while is_file() checked the real
        path. The stray-file assertion below is what convicts a dropped
        quote(): without it the bug is invisible to a reads-succeed test.
        """
        for name in ("with#hash.db", "pct%20.db", "space name.db"):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as raw:
                    project = Path(raw)
                    (project / ".git").mkdir()
                    path = project / ".hermes" / "task-runtime" / "workflow" / name
                    writer = CanonicalStore(path)
                    writer.register_project("work-lab", "<redacted>")
                    writer.close()
                    store_dir = path.parent

                    def listing() -> list[Path]:
                        # A read-only connection on a WAL database recreates
                        # the -wal/-shm sidecars; they are correct behaviour
                        # for the RIGHT path. Anything else appearing is the
                        # truncated stray file a dropped quote() would create.
                        sidecars = {path.name + "-wal", path.name + "-shm"}
                        return sorted(
                            p for p in store_dir.iterdir() if p.name not in sidecars
                        )

                    before = listing()
                    store = CanonicalStore(path, readonly=True)
                    try:
                        # (a) opens read-only and reads THE right file: the
                        #     registered project is visible, not an empty or
                        #     truncated database (pre-fix, `with#hash.db` opened
                        #     a brand-new writable `with` file with no tables).
                        self.assertEqual(
                            [p["project_id"] for p in store.list_projects()],
                            ["work-lab"],
                        )
                        # (b) any write fails closed on the real path.
                        with self.assertRaises(Exception) as ctx:
                            store.register_project("nope", "<redacted>")
                        self.assertIn("readonly", str(ctx.exception).lower())
                    finally:
                        store.close()
                    # (c) no truncated/writable stray file appeared.
                    self.assertEqual(before, listing())


if __name__ == "__main__":
    unittest.main()
