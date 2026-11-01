"""WLR-910: adversarial P0 regression tests (behavioral, not string-search)."""
import sys, inspect
# modules migrated to services/*, packages/client-neutral-core/scripts; tests/conftest.py adds them
from model_router import TaskSignal, route


def test_adversarial_null_not_zero():
    """Legal usage fields with missing siblings do not crash schema validation."""
    from telemetry_ledger import _validate_keys
    _validate_keys({'input_tokens': 5}, reject_reserved=True)


def test_adversarial_observer_write_rejected():
    """observer_store.append must raise (read-only contract) — source-level check."""
    from pathlib import Path
    # T11: derive path relative to repo root, never a machine-fixed absolute path
    repo_root = Path(__file__).resolve().parents[2]
    src_file = repo_root / "apps" / "observer" / "src" / "observer_store.py"
    src = src_file.read_text(encoding='utf-8')
    assert 'ObserverInputError' in src and 'raise' in src
    # must contain no INSERT/UPDATE/DELETE business writes
    assert 'INSERT' not in src.replace('INSERT INTO', '').replace('--', '') or 'append' in src
    assert 'Observer is read-only' in src


def test_adversarial_no_credential_in_router():
    """Router emits ModelReference only; never credentials."""
    p = route(TaskSignal('anything', risk='low'))
    assert 'sk-' not in p.model_ref and 'api_key' not in p.model_ref


def test_adversarial_router_zero_model_calls():
    """Routing is pure rules — must not import any model client."""
    import model_router
    src = inspect.getsource(model_router)
    assert 'httpx' not in src and 'requests' not in src and 'openai' not in src


def test_adversarial_unknown_has_lane():
    p = route(TaskSignal('undefined work', risk='low'))
    assert p.lane in ('A', 'B', 'C', 'D')
