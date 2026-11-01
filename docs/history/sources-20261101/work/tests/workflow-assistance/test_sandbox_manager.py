import tempfile
from pathlib import Path

from sandbox_manager import SandboxManager, LEVEL_NAMES


def test_levels_exist():
    assert LEVEL_NAMES[0] == "UNRESTRICTED"
    assert LEVEL_NAMES[1] == "READ_ONLY"
    assert LEVEL_NAMES[2] == "WORKSPACE_WRITE"
    assert LEVEL_NAMES[3] == "ISOLATED"


def test_level1_read_only():
    with tempfile.TemporaryDirectory() as d:
        s = SandboxManager(d)
        assert s.evaluate(level=1, action="read", target_path=str(Path(d) / "a")).allowed
        assert not s.evaluate(level=1, action="write", target_path=str(Path(d) / "a")).allowed
        assert not s.evaluate(level=1, action="execute", target_path=str(Path(d) / "a")).allowed
        assert not s.evaluate(level=1, action="read", network=True).allowed


def test_level2_workspace_boundary():
    with tempfile.TemporaryDirectory() as d:
        s = SandboxManager(d)
        assert s.evaluate(level=2, action="write", target_path=str(Path(d) / "x")).allowed
        assert not s.evaluate(level=2, action="write", target_path="C:/Windows/tmp").allowed
        assert not s.evaluate(level=2, action="delete", target_path=str(Path(d) / "x")).allowed
        assert not s.evaluate(level=2, action="read", network=True).allowed


def test_level3_isolated():
    with tempfile.TemporaryDirectory() as d:
        s = SandboxManager(d)
        assert s.evaluate(level=3, action="read", target_path=str(Path(d) / "a")).allowed
        assert not s.evaluate(level=3, action="write", target_path=str(Path(d) / "a")).allowed
        assert not s.evaluate(level=3, action="read", network=True).allowed


def test_unknown_level_rejected():
    with tempfile.TemporaryDirectory() as d:
        s = SandboxManager(d)
        assert not s.evaluate(level=9, action="read").allowed
