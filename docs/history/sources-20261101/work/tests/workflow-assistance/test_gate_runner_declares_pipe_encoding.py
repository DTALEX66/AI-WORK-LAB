"""Gate: no text-mode subprocess pipe in tracked Python may decode with the host locale.

Measured 2026-10-08: the canonical aggregate gate produced **no receipt at all**. It raised
`TypeError: can only concatenate str (not "NoneType") to str` in `_run_governance_batch`, and the same
mechanism one gate further down (`run_root_governance_suite.py`) would have followed. The chain:
`subprocess.run(..., text=True)` with no `encoding=` decodes with the locale, which on this host is cp936,
while mandatory modules print Chinese failure text under a pinned `PYTHONIOENCODING=utf-8`. On the invalid
byte, subprocess's own `_readerthread` raised `UnicodeDecodeError`; the threading module printed it and the
thread died, so `communicate()` returned **None** for that stream. The crash named neither codec nor module,
and three sibling tests failed with `TypeError: argument of type 'NoneType' is not iterable`, looking like
broken assertions when nothing was asserting anything. Measured in one healthy call: stdout a 100,374-char
str, stderr None.

CI on Ubuntu could never show this -- its locale already matches the child -- so the guard is structural
rather than behavioural and covers every tracked `.py` file, not just the ones that crashed: a gate's
receipt is only as reliable as the pipes that read it.

The sibling gate `test_workflow_locale_discipline_gate.py` polices the *recorded CI commands* for the same
class; this one polices the pipes the code itself opens.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPE_FUNCTIONS = {"run", "Popen", "check_output", "check_call", "call"}


def _spawn(source: str, *, console_encoding: str) -> subprocess.CompletedProcess:
    """Run a child whose console codec this test chooses, with bytes pipes so the decoding is chosen twice.

    PYTHONIOENCODING has to be in the child's environment at exec time -- by the first statement of `-c`
    code, sys.stdout already exists -- and the parent reads raw bytes rather than letting the host locale
    decide what it can decode.
    """
    env = {key: value for key, value in os.environ.items() if key.upper() != "PYTHONIOENCODING"}
    env["PYTHONIOENCODING"] = console_encoding
    return subprocess.run([sys.executable, "-c", source], capture_output=True, env=env, cwd=ROOT, check=False)

# Capability floor, measured 2026-10-08: the 642 tracked Python files open 223 text-mode pipes. The floor is
# what makes "zero violations" mean "the rule holds" instead of "the scanner saw nothing"; it sits well below
# the measured count so ordinary work can only raise it.
TOTAL_PIPE_FLOOR = 150


def text_mode_pipes(source: str) -> tuple[list[int], list[int]]:
    """(undeclared-encoding line numbers, all text-mode pipe line numbers) for one source."""
    tree = ast.parse(source)
    undeclared: list[int] = []
    every: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "attr", None) not in PIPE_FUNCTIONS:
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords}
        mode = next((keywords[name] for name in ("text", "universal_newlines") if name in keywords), None)
        if mode is None:
            continue
        # bytes mode decodes nothing, so it is not this rule's subject; a value the scan cannot read is
        # treated as text mode, because a call that might decode must state what it decodes with.
        if isinstance(mode, ast.Constant) and mode.value in (False, 0):
            continue
        every.append(node.lineno)
        if "encoding" not in keywords:
            undeclared.append(node.lineno)
    return sorted(undeclared), sorted(every)


def tracked_python() -> list[str]:
    raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z", "*.py"],
                         cwd=ROOT, capture_output=True).stdout.split(b"\0")
    return [name.decode("utf-8", "replace") for name in raw if name]


def bytes_mode_with_encoding(source: str) -> list[int]:
    """Lines where a call asks for BYTES mode and also declares a text encoding.

    The reverse half of the rule, and the half I broke: a mechanical sweep anchored on the presence of the
    `text` keyword without reading its value flipped `subprocess.run([...], text=False)` -- a deliberate raw
    read of `git ls-files -z`, split on b"\\0" -- into text mode, and the caller died with
    `TypeError: must be str or None, not bytes`. A bytes call must not carry an encoding.
    """
    tree = ast.parse(source)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "attr", None) not in PIPE_FUNCTIONS:
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords}
        mode = next((keywords[name] for name in ("text", "universal_newlines") if name in keywords), None)
        if mode is None or "encoding" not in keywords:
            continue
        if isinstance(mode, ast.Constant) and mode.value in (False, 0):
            hits.append(node.lineno)
    return sorted(hits)


class PipeEncodingTests(unittest.TestCase):
    def test_no_text_pipe_anywhere_decodes_with_the_locale(self) -> None:
        offenders: list[str] = []
        total = 0
        unreadable: list[str] = []
        for rel in tracked_python():
            path = ROOT / rel
            try:
                undeclared, every = text_mode_pipes(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, OSError) as error:
                unreadable.append(f"{rel}: {type(error).__name__}")
                continue
            total += len(every)
            if undeclared:
                offenders.append(f"{rel}:{','.join(str(line) for line in undeclared)}")
        self.assertEqual(
            unreadable, [],
            f"the scan could not parse {len(unreadable)} tracked file(s): a file it cannot read is a "
            f"file it cannot convict -- {unreadable[:5]}",
        )
        self.assertGreaterEqual(
            total, TOTAL_PIPE_FLOOR,
            f"the scan saw {total} text-mode pipes across all tracked Python; below {TOTAL_PIPE_FLOOR} "
            "the empty offender list is the scanner going blind, not the rule holding",
        )
        self.assertEqual(
            offenders, [],
            f"{len(offenders)} file(s) open a text-mode pipe without declaring an encoding: "
            f"{offenders[:10]} -- on a cp936 host a child that prints non-ASCII kills the reader thread "
            "and the stream comes back None, which destroys the caller's verdict (ERR-211)",
        )

    def test_no_bytes_mode_call_carries_a_text_encoding(self) -> None:
        offenders: list[str] = []
        for rel in tracked_python():
            try:
                hits = bytes_mode_with_encoding((ROOT / rel).read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue  # the pass above already fails the suite on an unreadable file
            if hits:
                offenders.append(f"{rel}:{','.join(str(line) for line in hits)}")
        self.assertEqual(
            offenders, [],
            f"bytes-mode pipes that also declare a text encoding: {offenders} -- encoding= silently turns "
            "the call into text mode and the caller's `b\"\\0\"` split then dies (ERR-211's own sweep made "
            "exactly this mistake at scripts/ci/regression_report.py:62)",
        )

    def test_the_bytes_control_shape_is_recognised(self) -> None:
        # Without this, the test above could pass because the matcher lost the shape entirely.
        source = (
            "import subprocess\n"
            "subprocess.run(['git', 'ls-files', '-z'], text=False, encoding='utf-8')\n"
            "subprocess.run(['git', 'ls-files'], text=False)\n"
        )
        self.assertEqual(bytes_mode_with_encoding(source), [2])
        self.assertEqual(text_mode_pipes(source)[0], [], "a bytes call was counted as needing an encoding")

    def test_the_matcher_fires_on_the_bad_shape_and_not_on_the_good_one(self) -> None:
        bad, good = text_mode_pipes(
            "import subprocess\n"
            "subprocess.run(['python', 'x.py'], text=True, capture_output=True)\n"
            "subprocess.run(['python', 'y.py'], text=True, encoding='utf-8', errors='replace')\n"
        )
        self.assertEqual(bad, [2], "an undeclared text pipe was not detected -- the rule cannot hold")
        self.assertEqual(good, [2, 3], "the scan lost a pipe that already declares its encoding")

    def test_a_bytes_call_and_a_non_subprocess_run_are_not_pipes(self) -> None:
        # `Runner(repo=repo).run("repair the migration", risk="high")` is not a subprocess pipe, and an
        # earlier draft of this matcher convicted it for ending in a literal; `text=False` is bytes mode,
        # which decodes nothing, so it is not the rule's subject either. Both must be invisible, while the
        # genuinely text-mode call on the last line must still be caught.
        sample = (
            "Runner(repo=repo).run('repair the migration', risk='high')\n"
            "subprocess.run(['git', 'status'], text=False)\n"
            "subprocess.run(['python', 'z.py'], capture_output=True, text=True)\n"
        )
        undeclared, every = text_mode_pipes(sample)
        self.assertEqual(every, [3], f"a non-pipe or a bytes call was counted as a pipe: {every}")
        self.assertEqual(undeclared, [3])

    def test_the_batch_child_env_pins_the_output_encoding(self) -> None:
        source = (ROOT / "services" / "orchestration" / "run_quality_gate.py").read_text(encoding="utf-8")
        start = source.index("def _run_governance_batch")
        body = source[start:source.index("\ndef ", start + 1)]
        self.assertIn('env["PYTHONIOENCODING"]', body,
                      "the batch child writes with whatever locale it inherited while the parent reads "
                      "UTF-8; both ends have to be pinned or the two disagree on a Chinese failure line")

    def test_the_runner_survives_a_non_unicode_console(self) -> None:
        """The PARENT stream, which the two checks above are silent about.

        Measured 2026-10-10 (ERR-233): a mandatory test whose output contains `↔` reached
        `_report_governance_failure`, the runner's own `print` raised UnicodeEncodeError against the
        Windows console default, and the traceback replaced the receipt -- so the run that existed to say
        WHICH module went red destroyed the statement that any module went red. Pinning the child pipes is
        not enough if the process holding the verdict cannot speak.

        Forced to cp936 on every OS rather than "whatever this host happens to prefer", so CI on Ubuntu
        exercises the same branch instead of passing by luck. Captured as bytes and decoded here: the child
        may emit a stream this test cannot assume is UTF-8.
        """
        runner = ROOT / "services" / "orchestration" / "run_quality_gate.py"
        imports = (
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('wl_gate_under_test', {str(runner)!r})\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "print('ARROW:' + chr(0x2194))\n"
            "print('ENCODING:' + sys.stdout.encoding)\n"
        )
        with_declaration = _spawn(imports, console_encoding="gbk")
        # The control: the same print, without importing the runner, on the same forced console. If this
        # exits 0 the scenario is not actually hostile and the pass above would be decoration.
        without_declaration = _spawn("print(chr(0x2194))\n", console_encoding="gbk")

        self.assertEqual(
            without_declaration.returncode, 1,
            "the control print survived a forced gbk console, so this test proves nothing about the "
            f"declaration -- {without_declaration.stdout.decode('utf-8', 'replace')!r}",
        )
        self.assertIn(
            "UnicodeEncodeError", without_declaration.stderr.decode("utf-8", "replace"),
            "the control failed for some reason other than the console codec, so it is not the fault "
            "the product path is being asked to survive",
        )
        self.assertEqual(
            with_declaration.returncode, 0,
            "importing the runner did not make its own stream writable in UTF-8: the failure reporter can "
            "still be killed mid-line by a non-ASCII test output (ERR-233) -- "
            f"{with_declaration.stderr.decode('utf-8', 'replace')[:400]!r}",
        )
        printed = with_declaration.stdout.decode("utf-8", "replace")
        self.assertIn("ARROW:\u2194", printed,
                      "the parent printed a substitute character instead of the arrow; a reporter line "
                      f"containing one would reach the receipt mangled -- {printed!r}")
        codec = printed.partition("ENCODING:")[2].strip().lower().replace("-", "").replace("_", "")
        self.assertEqual(codec, "utf8",
                         f"the parent stream still reports {codec!r}, not UTF-8")


if __name__ == "__main__":
    unittest.main()
