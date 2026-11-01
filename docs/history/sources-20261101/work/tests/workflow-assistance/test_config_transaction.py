import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services' / 'policy'))
from config_control_plane import ConfigControlPlane, SoftwareRegistration

def test_unapproved_never_writes():
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration('hermes', 'Hermes', 'agent-harness', 'x'))
    d = ccp.diff({'a': 1}, {'a': 2})
    r = ccp.transaction('hermes', d, approved=False)
    assert r['status'] == 'WAITING_APPROVAL'

def test_apply_readback_commit():
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration('hermes', 'Hermes', 'agent-harness', 'x'))
    ccp.set_layer('official_baseline', {'model': 'm1'})
    d = ccp.diff({'model': 'm1'}, {'model': 'm2'})
    r = ccp.transaction('hermes', d, approved=True,
        backup_dir=str(Path(__file__).resolve().parents[2] / '.project-local' / 'runs' / 'config-transaction-tests'),
        apply_fn=lambda before: {'model': 'm2'},
        readback_fn=lambda: {'model': 'm2'})
    assert r['status'] == 'COMMITTED', r

def test_drift_rolls_back():
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration('hermes', 'Hermes', 'agent-harness', 'x'))
    ccp.set_layer('official_baseline', {'model': 'm1'})
    d = ccp.diff({'model': 'm1'}, {'model': 'm2'})
    r = ccp.transaction('hermes', d, approved=True,
        backup_dir=str(Path(__file__).resolve().parents[2] / '.project-local' / 'runs' / 'config-transaction-tests'),
        apply_fn=lambda before: {'model': 'm2'},
        readback_fn=lambda: {'model': 'm1'})  # mismatch -> drift
    assert r['status'] == 'ROLLBACK_REQUIRED', r

def test_no_apply_fn_unsupported():
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration('hermes', 'Hermes', 'agent-harness', 'x'))
    d = ccp.diff({'a': 1}, {'a': 2})
    r = ccp.transaction('hermes', d, approved=True)
    assert r['status'] == 'UNSUPPORTED_APPLY'

def test_noop_on_empty_diff():
    # NF-04 acceptance: "no change" is a genuine no-op — an approved empty diff
    # never enters the backup/apply/readback cycle and never reports a write.
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration('hermes', 'Hermes', 'agent-harness', 'x'))
    ccp.set_layer('official_baseline', {'model': 'm1'})
    d = ccp.diff({'model': 'm1'}, {'model': 'm1'})   # changeCount == 0
    assert d['changeCount'] == 0
    def _boom(before):
        raise AssertionError("apply_fn must NOT be called for a no-op")
    r = ccp.transaction('hermes', d, approved=True, apply_fn=_boom,
                       readback_fn=lambda: {'model': 'm1'})
    assert r['status'] == 'NOOP', r
    assert r.get('changeCount') == 0

def test_apply_failure_is_honest_undetermined():
    # NF-04 acceptance: a raised write is UNDETERMINED, never faked as a
    # rollback or a success. errorType is surfaced but exception text is not
    # (an adapter may embed private config values in the message).
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration('hermes', 'Hermes', 'agent-harness', 'x'))
    ccp.set_layer('official_baseline', {'model': 'm1'})
    d = ccp.diff({'model': 'm1'}, {'model': 'm2'})
    def _fail(before):
        raise PermissionError("secret adapter detail must not leak")
    r = ccp.transaction('hermes', d, approved=True,
                       backup_dir=str(Path(__file__).resolve().parents[2] / '.project-local' / 'runs' / 'config-transaction-tests'),
                       apply_fn=_fail, readback_fn=lambda: {'model': 'm1'})
    assert r['status'] == 'APPLY_FAILED', r
    assert r['written'] == 'UNDETERMINED'
    assert r['restored'] is False
    assert r['errorType'] == 'PermissionError'
    assert 'secret adapter detail' not in r['errorType']

def test_rollback_failure_is_honest():
    # NF-04 acceptance: "recovery failure" must report ROLLBACK_FAILED with
    # restored=False — never a fake ROLLED_BACK / success.
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration('hermes', 'Hermes', 'agent-harness', 'x'))
    ccp.set_layer('official_baseline', {'model': 'm1'})
    d = ccp.diff({'model': 'm1'}, {'model': 'm2'})
    def _rb(before):
        raise RuntimeError("restore target missing")
    r = ccp.transaction('hermes', d, approved=True,
                       backup_dir=str(Path(__file__).resolve().parents[2] / '.project-local' / 'runs' / 'config-transaction-tests'),
                       apply_fn=lambda before: {'model': 'm2'},
                       readback_fn=lambda: {'model': 'm1'},   # drift -> rollback
                       rollback_fn=_rb)
    assert r['status'] == 'ROLLBACK_FAILED', r
    assert r['restored'] is False
    assert r['errorType'] == 'RuntimeError'

def test_simulated_success_is_tagged_and_not_real():
    # NF-04 acceptance: a simulated adapter's success must be distinguishable
    # from a real applied success so it can never enter the real success tally.
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration('hermes', 'Hermes', 'agent-harness', 'x'))
    ccp.set_layer('official_baseline', {'model': 'm1'})
    d = ccp.diff({'model': 'm1'}, {'model': 'm2'})
    sim = ccp.transaction('hermes', d, approved=True,
                         apply_fn=lambda before: {'model': 'm2'},
                         readback_fn=lambda: {'model': 'm2'}, simulated=True)
    real = ccp.transaction('hermes', d, approved=True,
                          apply_fn=lambda before: {'model': 'm2'},
                          readback_fn=lambda: {'model': 'm2'}, simulated=False)
    assert sim['status'] == 'COMMITTED_SIMULATED'
    assert sim['simulated'] is True
    assert real['status'] == 'COMMITTED'
    assert real['simulated'] is False
    # a real-success tally must only count the non-simulated outcome
    real_successes = [s for s in (sim, real) if s['status'] == 'COMMITTED']
    assert len(real_successes) == 1 and real_successes[0] is real


# ---------------------------------------------------------------------------
# U10 — Config transaction truth: the five gap mechanisms the taskpack requires.
# All are ADDITIVE optional kwargs; omitting them preserves every frozen
# behavior above (no second engine, no drift; the §22 "preserve already-correct
# honest states" rule).
# ---------------------------------------------------------------------------

def _ccp(model="m1"):
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration("hermes", "Hermes", "agent-harness", "x"))
    ccp.set_layer("official_baseline", {"model": model})
    return ccp


def test_revision_monotonic_floor():
    # A committed transaction advances a per-software monotonic revision floor;
    # a later transaction claiming a stale (older) revision is rejected STALE,
    # so a concurrent writer can never silently overwrite a newer commit.
    ccp = _ccp()
    d = ccp.diff({"model": "m1"}, {"model": "m2"})
    ok = ccp.transaction("hermes", d, approved=True,
                        apply_fn=lambda before: {"model": "m2"},
                        readback_fn=lambda: {"model": "m2"}, revision=0)
    assert ok["status"] == "COMMITTED", ok
    # revision=0 again is now below the floor (1) -> stale.
    stale = ccp.transaction("hermes", d, approved=True,
                           apply_fn=lambda before: {"model": "m3"},
                           readback_fn=lambda: {"model": "m3"}, revision=0)
    assert stale["status"] == "STALE_REVISION", stale
    # revision=1 (the current floor) is still admissible.
    fresh = ccp.transaction("hermes", d, approved=True,
                           apply_fn=lambda before: {"model": "m3"},
                           readback_fn=lambda: {"model": "m3"}, revision=1)
    assert fresh["status"] == "COMMITTED", fresh


def test_missing_vs_explicit_null():
    # diff must distinguish a key that is ABSENT from a key explicitly set to
    # null — conflating them hides real config semantics.  The strict
    # comparison is opt-in (frozen default keeps .get() semantics).
    ccp = _ccp()
    absent = ccp.diff({}, {"k": 1}, strict_missing=True)          # k: MISSING -> 1
    explicit = ccp.diff({"k": None}, {"k": 1}, strict_missing=True)  # k: None -> 1
    assert absent["changedFields"]["k"]["before"] != explicit["changedFields"]["k"]["before"]
    # and the two whole diffs differ in the before-state.
    assert absent != explicit
    # frozen default still conflates the two via .get() semantics.
    assert ccp.diff({}, {"k": 1}) == ccp.diff({"k": None}, {"k": 1})


def test_expected_before_conflict():
    # Optimistic concurrency: the caller declares the before-state it read. If
    # the live before-state has drifted from it, the transaction CONFLICTs and
    # never writes.
    ccp = _ccp(model="m1")
    d = ccp.diff({"model": "m1"}, {"model": "m2"})
    r = ccp.transaction("hermes", d, approved=True,
                       apply_fn=lambda before: {"model": "m2"},
                       readback_fn=lambda: {"model": "m2"},
                       expected_before={"model": "m0"})  # caller read m0, live is m1
    assert r["status"] == "CONFLICT", r
    # matching expected_before proceeds.
    r2 = ccp.transaction("hermes", d, approved=True,
                        apply_fn=lambda before: {"model": "m2"},
                        readback_fn=lambda: {"model": "m2"},
                        expected_before={"model": "m1"})
    assert r2["status"] == "COMMITTED", r2


def test_write_set_enforced():
    # When a write_set is declared, the apply result may only touch those keys.
    # An apply_fn that smuggles in a key outside the write set is rejected.
    ccp = _ccp(model="m1")
    d = ccp.diff({"model": "m1"}, {"model": "m2"})
    r = ccp.transaction("hermes", d, approved=True,
                       apply_fn=lambda before: {"model": "m2", "rogue": True},
                       readback_fn=lambda: {"model": "m2", "rogue": True},
                       write_set=["model"])
    assert r["status"] == "WRITE_SET_VIOLATION", r
    # staying inside the write set commits.
    r2 = ccp.transaction("hermes", d, approved=True,
                        apply_fn=lambda before: {"model": "m2"},
                        readback_fn=lambda: {"model": "m2"},
                        write_set=["model"])
    assert r2["status"] == "COMMITTED", r2


def test_typed_readback_failure():
    # A readback of the wrong type (non-dict) is a distinct, honest failure —
    # never coerced into a commit and never faked as drift-clean.
    ccp = _ccp(model="m1")
    d = ccp.diff({"model": "m1"}, {"model": "m2"})
    r = ccp.transaction("hermes", d, approved=True,
                       apply_fn=lambda before: {"model": "m2"},
                       readback_fn=lambda: "not-a-dict")
    assert r["status"] == "READBACK_FAILED_TYPED", r
    assert r["committed"] is False


def test_expected_after_verification():
    # When an intended after-state is declared, the readback must be checked
    # against it; a readback that lands on a different value is READBACK_MISMATCH
    # even if apply_fn "succeeded".
    ccp = _ccp(model="m1")
    d = ccp.diff({"model": "m1"}, {"model": "m2"})
    good = ccp.transaction("hermes", d, approved=True,
                          apply_fn=lambda before: {"model": "m2"},
                          readback_fn=lambda: {"model": "m2"},
                          expected_after={"model": "m2"})
    assert good["status"] == "COMMITTED", good
    # readback lands on m3 while the intent was m2 -> mismatch, not commit.
    bad = ccp.transaction("hermes", d, approved=True,
                         apply_fn=lambda before: {"model": "m3"},
                         readback_fn=lambda: {"model": "m3"},
                         expected_after={"model": "m2"})
    assert bad["status"] == "READBACK_MISMATCH", bad
    assert bad["committed"] is False
