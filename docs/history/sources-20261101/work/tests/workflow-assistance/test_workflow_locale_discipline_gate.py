"""Gate: no recorded CI command may depend on the runner's locale encoding.

`scripts/ci/reproduce_ci_commands.py` runs every interpreter command in both workflow files in a
bare shell, which surfaced a command that passed on an ubuntu runner only because Python's default
text encoding there is UTF-8: `json.load(open(f))` over schema files containing em dashes fails
outright under a GBK locale. A gate can only be trusted as evidence if it computes the same thing
on every machine, so a recorded command must state the encoding it reads with.

Negative controls below inject the exact shape that shipped, so the matcher cannot rot into a
wildcard that accepts anything.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = (ROOT / ".github" / "workflows" / "work-lab-gate.yml",
             ROOT / ".github" / "workflows" / "wlr-060-gates.yml")

PYTHON_INVOKE = re.compile(r"\bpython[\w.]*\b")
BUILTIN_OPEN = re.compile(r"(?<![\w.])open\s*\(")
METHOD_TEXT_READ = re.compile(r"\.(read_text|read_lines)\s*\(")
BINARY_MODE = re.compile(r"['\"][rwa+]*b[rwa+]*['\"]")
UTF8_ENV = re.compile(r"PYTHONUTF8\s*=\s*1|PYTHONIOENCODING\s*=\s*utf-?8", re.I)


def run_blocks(path: Path) -> list[tuple[str, str, str]]:
    """(job, step, command) for every `run:` in a workflow file."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = []
    for job, jdef in (doc.get("jobs") or {}).items():
        for step in (jdef.get("steps") or []):
            cmd = step.get("run")
            if isinstance(cmd, str):
                env = "\n".join(f"{k}={v}" for k, v in (step.get("env") or {}).items())
                out.append((job, str(step.get("name") or step.get("id") or ""), cmd, env))
    return out


def _args(command: str, idx: int) -> str:
    """Argument text between the paren at `idx` and its matching close, one level of nesting."""
    depth, out = 1, []
    for ch in command[idx:idx + 400]:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
        out.append(ch)
    return "".join(out)


def violations(command: str, env: str) -> list[str]:
    if not PYTHON_INVOKE.search(command):
        return []
    if UTF8_ENV.search(command) or UTF8_ENV.search(env):
        return []
    bad = []
    for pattern in (BUILTIN_OPEN, METHOD_TEXT_READ):
        for m in pattern.finditer(command):
            args = _args(command, m.end())
            if "encoding" not in args and not BINARY_MODE.search(args):
                bad.append(f"locale-dependent text read {m.group(0).strip()!r}: "
                           f"...{command[max(0, m.start() - 10):m.start() + 90]}")
    return bad


class WorkflowLocaleDisciplineGate(unittest.TestCase):
    def setUp(self) -> None:
        self.blocks = [(wf.name, *b) for wf in WORKFLOWS for b in run_blocks(wf)]

    def test_gate_actually_reads_both_workflows(self) -> None:
        self.assertEqual({n for n, *_ in self.blocks}, {"work-lab-gate.yml", "wlr-060-gates.yml"})
        self.assertGreaterEqual(len(self.blocks), 40)

    def test_no_recorded_command_depends_on_the_runner_locale(self) -> None:
        found = [f"{name}/{job}/{step}: {v}"
                 for name, job, step, cmd, env in self.blocks for v in violations(cmd, env)]
        self.assertEqual(found, [], "recorded CI commands that read text without an encoding")

    def test_the_schema_command_now_states_utf8(self) -> None:
        hits = [cmd for _, job, step, cmd, _ in self.blocks
                if "schemas" in cmd and "json.load" in cmd]
        self.assertTrue(hits, "the schema-validation command disappeared from the workflow")
        for cmd in hits:
            self.assertIn("encoding='utf-8'", cmd)

    # ---------------- negative controls: the shipped shape must turn this gate red
    def test_the_shape_that_shipped_is_refused(self) -> None:
        shipped = ("python -c \"import json,glob; [json.load(open(f)) for f in "
                   "glob.glob('packages/contracts/schemas/**/*.json',recursive=True)]\"")
        self.assertTrue(violations(shipped, ""), "the gate accepts the command it exists to refuse")

    def test_a_read_text_without_encoding_is_refused(self) -> None:
        self.assertTrue(violations("python -c \"print(open('a.json').read_text())\"", ""))

    def test_the_method_read_text_shape_is_refused(self) -> None:
        self.assertTrue(violations("python -c \"from pathlib import Path;"
                                   "print(Path('a.md').read_text())\"", ""))

    def test_explicit_encoding_is_accepted(self) -> None:
        self.assertEqual(violations("python -c \"print(open('a.json', encoding='utf-8'))\"", ""), [])
        self.assertEqual(violations("python -c \"from pathlib import Path;"
                                    "print(Path('a.md').read_text(encoding='utf-8'))\"", ""), [])

    def test_binary_mode_is_accepted(self) -> None:
        self.assertEqual(violations("python -c \"print(open('a.bin', 'rb'))\"", ""), [])

    def test_a_step_that_forces_utf8_is_accepted(self) -> None:
        self.assertEqual(violations("python -c \"print(open('a').read())\"",
                                    "PYTHONUTF8=1"), [])

    def test_non_python_commands_are_out_of_scope(self) -> None:
        self.assertEqual(violations("cat notes.md | grep open(", ""), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
