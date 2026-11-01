"""The Observer's one-click launcher has to describe a chain that actually exists.

Recorded defect (2026-10-19, standalone run): `apps/observer/start-observer.cmd` opened a static
HTML path under an `apps/observer/` directory the repository does not contain, and polled a
hardcoded port 61867 while starting the sidecar with `--port 0` (a random free port). Both ends of
the documented chain were therefore unrunnable, and nothing guarded either half: the sibling
`test_sidecar_documented_launch.py` proves the *command* starts, not that the launcher reaches a UI.

These cases read the shipped launcher and the shipped README, so re-introducing a dead path, a
guessed port, or a lone-LF batch file fails here rather than on a user's double-click.
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "apps/observer/start-observer.cmd"
README = ROOT / "apps/observer/README.md"
SIDECAR = ROOT / "services/orchestration/sidecar.py"
BUILD_OUTPUT = "apps/observer/frontend/dist"


def launcher_text() -> str:
    return LAUNCHER.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")


class LauncherShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(LAUNCHER.is_file(), "the one-click launcher is missing")
        self.text = launcher_text()

    def test_the_launcher_is_crlf_only_because_cmd_no_ops_on_lone_lf(self) -> None:
        raw = LAUNCHER.read_bytes()
        lone = raw.count(b"\n") - raw.count(b"\r\n")
        self.assertEqual(0, lone, "a lone-LF line in a .cmd can silently skip its body")
        # The bytes alone are a host property: an unattributed text file is stored LF and a Linux checkout
        # hands back LF, which is how this assertion passed on every Windows worktree and failed on the
        # 2026-10-20 exact-SHA run. The durable claim is the declared materialization, so assert it too.
        attr = subprocess.run(["git", "check-attr", "text", "eol", "--",
                               LAUNCHER.relative_to(ROOT).as_posix()],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        self.assertIn("eol: crlf", attr.stdout, attr.stdout + attr.stderr)

    def test_every_tracked_batch_launcher_is_declared_crlf(self) -> None:
        """One file was not the defect; the family was. Enumerate it from the index, not from memory.

        `packages/client-neutral-core/bin/*.cmd` are the declared launchers behind the five-dimension
        runtime baseline (one entry per software, reachable from the desktop shortcut). A lone-LF batch
        there no-ops silently on double-click, the same failure already recorded for `.bat` files.
        """
        listed = subprocess.run(["git", "ls-files", "-z", "--", "*.cmd", "*.bat"],
                                cwd=ROOT, capture_output=True, check=True)
        batch = [p.decode("utf-8") for p in listed.stdout.split(b"\0") if p]
        self.assertGreaterEqual(len(batch), 2, f"only {len(batch)} batch launchers tracked: {batch}")
        for rel in batch:
            raw = (ROOT / rel).read_bytes()
            self.assertEqual(0, raw.count(b"\n") - raw.count(b"\r\n"),
                             f"{rel} carries lone-LF lines")
            attr = subprocess.run(["git", "check-attr", "eol", "--", rel],
                                  cwd=ROOT, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            self.assertIn("eol: crlf", attr.stdout, f"{rel} is not declared CRLF: {attr.stdout}")

    def test_every_observer_path_the_launcher_names_exists_on_disk(self) -> None:
        """The original defect: the launcher opened a file that does not exist.

        Only live command lines are scanned, not `rem` comments, because a comment is allowed to
        name a path that used to be wrong. The one exempt path is the build output: it is gitignored,
        so a fresh checkout legitimately has no bundle, and
        `test_the_launcher_targets_the_directory_the_build_is_configured_to_write` is what pins it to
        something real instead of hoping it is present.
        """
        offenders = []
        for line in self._live_lines():
            for token in re.findall(r"apps[\\/][A-Za-z0-9_.\\/-]+", line):
                relative = token.rstrip("\\/").replace("\\", "/")
                if relative == BUILD_OUTPUT:
                    continue
                if not (ROOT / relative).exists():
                    offenders.append((line.strip()[:70], relative))
        self.assertEqual([], offenders, "the launcher names a path that does not exist")

    def _live_lines(self) -> list[str]:
        return [line for line in self.text.split("\n")
                if line.strip() and not line.strip().lower().startswith("rem ")]

    def test_the_launcher_serves_the_built_bundle_from_the_sidecar_itself(self) -> None:
        self.assertIn("--frontend-root", self.text)
        referenced = self._frontend_root_argument()
        self.assertEqual(BUILD_OUTPUT, referenced,
                         "the launcher must serve the directory the build actually writes")
        self.assertTrue((ROOT / "apps/observer/frontend/index.html").is_file(),
                        "the Vite source root has to exist, or the build output is a fiction")
        if not (ROOT / BUILD_OUTPUT / "index.html").is_file():
            # `dist/` is gitignored, so a fresh checkout legitimately has no bundle. Failing here would be a
            # false red about the environment rather than about the launcher; the CI job builds first.
            self.skipTest(f"{BUILD_OUTPUT}/index.html is a build output (npm run build); "
                          "not present in this checkout, so the served-file claim is unmeasured here")

    def _frontend_root_argument(self) -> str:
        for line in self._live_lines():
            match = re.search(r"--frontend-root\s+\"?%ROOT%[/\\\\]([^\"' ]+)", line)
            if match:
                # The capture is already repository-relative (`%ROOT%` is the repo root), so nothing is
                # prefixed here — the first version of this helper prepended the frontend directory and
                # then compared against a path that already carried it.
                return match.group(1).rstrip("\\/").replace("\\", "/")
        self.fail("no --frontend-root argument on a live launcher line")

    def test_the_launcher_targets_the_directory_the_build_is_configured_to_write(self) -> None:
        """Vite's default outDir is `dist`; if that ever changes, the launcher must change with it."""
        config = (ROOT / "apps/observer/frontend/vite.config.ts").read_text(encoding="utf-8")
        configured = re.search(r"outDir\s*:\s*['\"]([^'\"]+)['\"]", config)
        expected = "apps/observer/frontend/" + (configured.group(1) if configured else "dist")
        self.assertEqual(expected, self._frontend_root_argument())

    def test_the_launcher_derives_its_url_from_the_descriptor_not_a_guessed_port(self) -> None:
        self.assertIn("sidecar-endpoint.json", self.text)
        self.assertIn("projectionUrl", self.text)
        literals = [line.strip()[:70] for line in self._live_lines()
                    if re.search(r"(?<![\d.])\d{4,5}(?![\d.])", line)]
        self.assertEqual([], literals,
                         "a literal port cannot be right when the sidecar binds --port 0")


class ContractAndDocTests(unittest.TestCase):
    def test_the_sidecar_actually_accepts_the_flag_the_launcher_relies_on(self) -> None:
        result = subprocess.run([sys.executable, str(SIDECAR), "--help"], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
        self.assertEqual(0, result.returncode, result.stderr[-300:])
        self.assertIn("--frontend-root", result.stdout)

    def test_the_readme_documents_the_same_entry_as_the_launcher(self) -> None:
        block = README.read_text(encoding="utf-8", errors="replace")
        start = block.index("sidecar.py --project-root")
        command = block[start - 200:start + 240]
        self.assertIn("--frontend-root", command,
                      "the documented start command must also serve a UI, or a reader following "
                      "the README gets an API with no page")


if __name__ == "__main__":
    unittest.main()
