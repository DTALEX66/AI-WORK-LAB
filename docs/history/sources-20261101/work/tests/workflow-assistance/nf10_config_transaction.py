"""U10 negative-control module: config-transaction truth gaps are fail-closed.

Task D (taskpack 20260918 U10) deliverable 3: pin the five gap mechanisms of
`ConfigControlPlane.transaction()` / `diff()` as a dedicated negative-control
module.  (The same six controls also live as additions in
`test_config_transaction.py`; this module is the spec-named nf10 home.)

Typed statuses asserted here are the module's OWN honest literals
(`STALE_REVISION`, `WRITE_SET_VIOLATION`, `READBACK_MISMATCH`, `CONFLICT`,
`COMMITTED`) — never a generic "failed".

Discovery-safe: plain asserts, no pytest fixtures, sibling sys.path convention.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services' / 'policy'))
from config_control_plane import ConfigControlPlane, SoftwareRegistration


def _ccp():
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration('obs', 'Observer', 'agent-harness', 'v1'))
    return ccp


def test_stale_revision_is_rejected_with_typed_status():
    # monotonic floor: a commit claiming revision=1 advances the floor to 2,
    # so any later generation at revision 1 is stale and can never apply.
    ccp = _ccp()
    d1 = ccp.diff({}, {'a': 1})
    r1 = ccp.transaction('obs', d1, approved=True,
                         apply_fn=lambda b: {'a': 1}, readback_fn=lambda: {'a': 1},
                         revision=1)
    assert r1['status'] == 'COMMITTED', r1
    # claiming the already-consumed generation (1 < floor 2) is typed-stale:
    r2 = ccp.transaction('obs', ccp.diff({}, {'a': 1}), approved=True,
                         apply_fn=lambda b: {'a': 1}, readback_fn=lambda: {'a': 1},
                         revision=1)
    assert r2['status'] == 'STALE_REVISION', r2
    assert r2['requestedRevision'] == 1 and r2['currentRevision'] == 2
    # nothing was written by the stale attempt: live layers still have no 'a'
    assert ccp.effective('obs').get('a') is None


def test_missing_vs_explicit_null_produce_different_diffs():
    ccp = _ccp()
    d_missing = ccp.diff({'a': 1}, {}, strict_missing=True)
    d_null = ccp.diff({'a': 1}, {'a': None}, strict_missing=True)
    # strict mode: ABSENT is a distinct sentinel value, NULL is Python None
    assert d_missing['changedFields']['a']['after'] is not None
    assert d_null['changedFields']['a']['after'] is None
    assert d_missing['changedFields'] != d_null['changedFields']
    # frozen default still conflates the two via .get() semantics
    assert ccp.diff({'a': 1}, {}) == ccp.diff({'a': 1}, {'a': None})


def test_write_outside_set_is_rejected_typed():
    ccp = _ccp()
    d = ccp.diff({}, {'a': 1, 'b': 2})
    r = ccp.transaction('obs', d, approved=True,
                       apply_fn=lambda b: {'a': 1, 'b': 2},
                       readback_fn=lambda: {'a': 1, 'b': 2},
                       write_set=['a'])
    assert r['status'] == 'WRITE_SET_VIOLATION', r
    assert 'b' in r['smuggledKeys'] and r['committed'] is False
    # staying inside the set commits.
    r2 = ccp.transaction('obs', ccp.diff({}, {'a': 1}), approved=True,
                        apply_fn=lambda b: {'a': 1}, readback_fn=lambda: {'a': 1},
                        write_set=['a'])
    assert r2['status'] == 'COMMITTED', r2


def test_expected_after_mismatch_is_not_a_commit():
    ccp = _ccp()
    d = ccp.diff({}, {'a': 5})
    r = ccp.transaction('obs', d, approved=True,
                       apply_fn=lambda b: {'a': 5},
                       readback_fn=lambda: {'a': 5},
                       expected_after={'a': 9})
    assert r['status'] == 'READBACK_MISMATCH', r
    assert r['committed'] is False


def test_expected_before_conflict_is_typed():
    ccp = _ccp()
    d = ccp.diff({}, {'a': 1})
    # caller claims it read a live state that does not exist -> CONFLICT,
    # no write of any kind.
    r = ccp.transaction('obs', d, approved=True,
                       apply_fn=lambda b: {'a': 1}, readback_fn=lambda: {'a': 1},
                       expected_before={'a': 999})
    assert r['status'] == 'CONFLICT', r
    assert ccp.effective('obs').get('a') is None


def test_verified_commit_path_still_succeeds():
    # positive control: real apply + matching native readback => COMMITTED.
    ccp = _ccp()
    d = ccp.diff({}, {'a': 1})
    r = ccp.transaction('obs', d, approved=True,
                       apply_fn=lambda b: {'a': 1}, readback_fn=lambda: {'a': 1})
    assert r['status'] == 'COMMITTED', r
