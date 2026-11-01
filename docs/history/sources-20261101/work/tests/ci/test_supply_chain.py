from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "verify_supply_chain.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_supply_chain", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SupplyChainTests(unittest.TestCase):
    def test_canonical_supply_chain_passes_with_hash_locked_python_dependencies(self) -> None:
        self.assertEqual(load_module().verify(ROOT), [])

    def test_all_supported_pip_launchers_accept_only_canonical_lock(self) -> None:
        module = load_module()
        commands = (
            "python -m pip install --require-hashes -r packages/client-neutral-core/requirements.lock",
            "python3 -m pip install --require-hashes --requirement=packages/client-neutral-core/requirements.lock",
            "pip install --require-hashes -rpackages/client-neutral-core/requirements.lock",
            "pip3 install --require-hashes --requirement packages/client-neutral-core/requirements.lock",
        )
        for command in commands:
            with self.subTest(command=command):
                tokens = module.shlex.split(command, comments=True, posix=True)
                self.assertTrue(module._is_approved_pip_install(tokens), command)

    def test_missing_hash_locked_requirements_fails_closed(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "gate.yml").write_text(
                "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
                encoding="utf-8",
            )
            errors = module.verify(root)
        self.assertTrue(any("requirements.lock" in error for error in errors), errors)

    def test_nested_project_workflow_is_scanned(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflow_dir = root / "module" / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            lock = root / "packages" / "client-neutral-core" / "requirements.lock"
            lock.parent.mkdir(parents=True)
            lock.write_text("example==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
            (workflow_dir / "nested.yml").write_text(
                "run: python -m pip install -r attacker-requirements.lock\n"
                "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
                encoding="utf-8",
            )
            errors = module.verify(root)
        self.assertTrue(any("nested.yml:1:" in error for error in errors), errors)

    def test_mixed_safe_and_unpinned_python_install_fails_closed(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            lock = root / "packages" / "client-neutral-core" / "requirements.lock"
            lock.parent.mkdir(parents=True)
            lock.write_text("example==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
            (workflow_dir / "gate.yml").write_text(
                "run: |\n"
                "  python -m pip install --require-hashes -r packages/client-neutral-core/requirements.lock\n"
                "  python -m pip install -r unpinned.txt\n"
                "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
                encoding="utf-8",
            )
            errors = module.verify(root)
        self.assertTrue(any(":3:" in error for error in errors), errors)

    def test_same_line_chained_safe_and_unpinned_install_fails_closed(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            lock = root / "packages" / "client-neutral-core" / "requirements.lock"
            lock.parent.mkdir(parents=True)
            lock.write_text("example==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
            (workflow_dir / "gate.yml").write_text(
                "run: python -m pip install --require-hashes -r packages/client-neutral-core/requirements.lock; "
                "python -m pip install -r unpinned.txt\n"
                "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
                encoding="utf-8",
            )
            errors = module.verify(root)
        self.assertTrue(any(":1:" in error for error in errors), errors)

    def test_bare_pip_install_without_lock_fails_closed(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            lock = root / "packages" / "client-neutral-core" / "requirements.lock"
            lock.parent.mkdir(parents=True)
            lock.write_text("example==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
            (workflow_dir / "gate.yml").write_text(
                "run: pip3 install -r unpinned.txt\n"
                "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
                encoding="utf-8",
            )
            errors = module.verify(root)
        self.assertTrue(any(":1:" in error for error in errors), errors)

    def test_noncanonical_lock_comment_spoof_and_mixed_requirements_fail_closed(self) -> None:
        module = load_module()
        cases = (
            "pip install --require-hashes -r attacker-requirements.lock",
            "pip install -r packages/client-neutral-core/requirements.lock # --require-hashes",
            "pip install --require-hashes -r packages/client-neutral-core/requirements.lock -r attacker-requirements.lock",
            "pi\\p install -r attacker-requirements.lock",
            "'p'ip install -r attacker-requirements.lock",
            "installer=pip; $installer install -r attacker-requirements.lock",
            "bash -c 'pip install -r attacker-requirements.lock'",
            "sh -c 'python -m pip install -r attacker-requirements.lock'",
            "echo $(pip install -r attacker-requirements.lock)",
        )
        for command in cases:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                workflow_dir = root / ".github" / "workflows"
                workflow_dir.mkdir(parents=True)
                lock = root / "packages" / "client-neutral-core" / "requirements.lock"
                lock.parent.mkdir(parents=True)
                lock.write_text("example==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
                (workflow_dir / "gate.yml").write_text(
                    f"run: {command}\n"
                    "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
                    encoding="utf-8",
                )
                errors = module.verify(root)
            self.assertTrue(any(":1:" in error for error in errors), errors)

    def test_backslash_continuation_is_checked_as_one_pip_invocation(self) -> None:
        module = load_module()
        cases = (
            (
                "safe",
                "run: |\n"
                "  pip \\\n"
                "    install --require-hashes -r packages/client-neutral-core/requirements.lock\n",
                False,
            ),
            (
                "unsafe",
                "run: |\n"
                "  pip \\\n"
                "    install -r attacker-requirements.lock\n",
                True,
            ),
            (
                "unsafe-launcher-token",
                "run: |\n"
                "  pi\\\n"
                "    p install -r attacker-requirements.lock\n",
                True,
            ),
        )
        for name, run_block, should_fail in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                workflow_dir = root / ".github" / "workflows"
                workflow_dir.mkdir(parents=True)
                lock = root / "packages" / "client-neutral-core" / "requirements.lock"
                lock.parent.mkdir(parents=True)
                lock.write_text("example==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
                (workflow_dir / "gate.yml").write_text(
                    run_block
                    + "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
                    encoding="utf-8",
                )
                errors = module.verify(root)
            self.assertEqual(bool(errors), should_fail, errors)
            if should_fail:
                self.assertTrue(any(":2:" in error for error in errors), errors)

    def test_comments_and_quoted_pip_text_do_not_count_as_installations(self) -> None:
        module = load_module()
        commands = (
            "# pip install -r attacker-requirements.lock",
            'echo "pip install -r attacker-requirements.lock"',
        )
        for command in commands:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                workflow_dir = root / ".github" / "workflows"
                workflow_dir.mkdir(parents=True)
                lock = root / "packages" / "client-neutral-core" / "requirements.lock"
                lock.parent.mkdir(parents=True)
                lock.write_text("example==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
                (workflow_dir / "gate.yml").write_text(
                    f"run: {command}\n"
                    "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
                    encoding="utf-8",
                )
                self.assertEqual(module.verify(root), [])


    def test_shell_separators_and_pip_launchers_cannot_bypass_lock_requirement(self) -> None:
        module = load_module()
        cases = (
            ("&&", "python3 -m pip"),
            ("||", "pip"),
            ("|", "pip3"),
        )
        for separator, launcher in cases:
            with self.subTest(separator=separator, launcher=launcher), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                workflow_dir = root / ".github" / "workflows"
                workflow_dir.mkdir(parents=True)
                lock = root / "packages" / "client-neutral-core" / "requirements.lock"
                lock.parent.mkdir(parents=True)
                lock.write_text("example==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
                (workflow_dir / "gate.yml").write_text(
                    "run: python -m pip install --require-hashes -r "
                    f"packages/client-neutral-core/requirements.lock {separator} "
                    f"{launcher} install -r unpinned.txt\n"
                    "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
                    encoding="utf-8",
                )
                errors = module.verify(root)
            self.assertTrue(any(":1:" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()