"""Gate: the shared CDP harness waits for the page to mount, and still takes its screenshots.

`scripts/audit/topbar_geometry_via_cdp.serve_and_eval` is the browser bootstrap behind three instruments
(the geometry gate, the legibility sweep, the handle-latency probe). It used to wait with fixed sleeps
(2.0 s for the endpoint, 0.4 s for the reflow, 1.0 s before evaluating) whose budget was the development
host's boot time. Measured 2026-10-21 at `79f48a54` on windows-latest: the FIRST session of the geometry job
came back with every selector `{"absent": true}` while the two sessions that followed it, on the same bundle,
measured normally — and the same bundle passes all three views locally. A cold runner was being reported as
a product red.

The wait is now bounded and observable. These cases prove the two ways it could be wrong: a wait that never
gives up (it would hang the job), and a wait that gives up but reports success (it would turn a broken render
green). The structural cases guard the code path around it, because the first draft of this fix silently
deleted the screenshot branch while replacing the sleep.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "scripts" / "audit" / "topbar_geometry_via_cdp.py"
SWEEP = ROOT / "scripts" / "audit" / "text_legibility_via_cdp.py"


def _load():
    spec = importlib.util.spec_from_file_location("geometry_harness", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load()


class FakeCdp:
    """Answers a mount probe with a scripted sequence; `None` means "raise like a dead session"."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0
        self.evaluated = []

    def evaluate(self, expression):
        self.calls += 1
        self.evaluated.append(expression)
        if not self.answers:
            return True
        answer = self.answers.pop(0)
        if answer is None:
            raise RuntimeError("no CDP response")
        return answer


class WaitForMountTests(unittest.TestCase):
    def test_a_mounted_page_returns_immediately_with_the_time_it_took(self) -> None:
        cdp = FakeCdp([True])
        waited, mounted = harness.wait_for_mount(cdp, ".app", budget_s=5, poll_s=0.01)
        self.assertTrue(mounted)
        self.assertLess(waited, 1000)
        self.assertEqual(1, cdp.calls)
        self.assertIn('querySelector(".app")', cdp.evaluated[0])

    def test_it_keeps_polling_until_the_subject_exists(self) -> None:
        cdp = FakeCdp([False, False, True])
        _waited, mounted = harness.wait_for_mount(cdp, ".app", budget_s=5, poll_s=0.01)
        self.assertTrue(mounted)
        self.assertEqual(3, cdp.calls, "a single look is the fixed sleep this replaced")

    def test_a_session_that_is_not_answering_yet_is_not_mounted_not_an_error(self) -> None:
        cdp = FakeCdp([None, None, True])
        _waited, mounted = harness.wait_for_mount(cdp, ".app", budget_s=5, poll_s=0.01)
        self.assertTrue(mounted)
        self.assertEqual(3, cdp.calls)

    def test_the_wait_gives_up_and_says_so(self) -> None:
        cdp = FakeCdp([False] * 500)
        waited, mounted = harness.wait_for_mount(cdp, ".app", budget_s=0.2, poll_s=0.01)
        self.assertFalse(mounted, "timeout must never be reported as mounted")
        self.assertLessEqual(waited, 2000, "the bound is milliseconds, not an unbounded retry")

    def test_the_budget_is_a_real_time_bound_not_an_attempt_count(self) -> None:
        # 500 scripted answers would outlive the budget; a loop keyed on attempts would run all of them.
        cdp = FakeCdp([False] * 500)
        harness.wait_for_mount(cdp, ".app", budget_s=0.15, poll_s=0.01)
        self.assertLess(cdp.calls, 500)

    def test_a_selector_is_quoted_into_the_probe_rather_than_interpolated_raw(self) -> None:
        # The probe text is executed by the page; a selector must not be able to break out of the string.
        cdp = FakeCdp([True])
        harness.wait_for_mount(cdp, 'a"b', budget_s=1, poll_s=0.01)
        self.assertIn('a\\"b', cdp.evaluated[0])


class HarnessStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = ast.parse(HARNESS.read_text(encoding="utf-8"))
        self.funcs = {n.name: n for n in ast.walk(self.tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def _source(self, node) -> str:
        return ast.get_source_segment(HARNESS.read_text(encoding="utf-8"), node) or ""

    def test_the_bootstrap_still_captures_the_screenshot_it_was_given(self) -> None:
        body = self._source(self.funcs["serve_and_eval"])
        self.assertIn("shot is not None", body,
                      "serve_and_eval lost its screenshot branch — a silent capability loss in every "
                      "instrument that passes `shot`")
        self.assertIn("Page.captureScreenshot", body)

    def test_the_fixed_pre_evaluate_sleep_is_gone(self) -> None:
        body = self._source(self.funcs["serve_and_eval"])
        self.assertNotIn("time.sleep(1.0)\n                raw = cdp.evaluate", body.replace("\r\n", "\n"),
                         "a fixed 1 s wait immediately before evaluating is the cold-runner defect")

    def test_the_wait_reports_itself_into_the_result(self) -> None:
        body = self._source(self.funcs["serve_and_eval"])
        self.assertIn("readyWait", body,
                      "the wait must travel with the numbers or a later red cannot be told from a cold runner")

    def test_the_module_declares_the_bound_once(self) -> None:
        self.assertEqual(".app", harness.MOUNT_SELECTOR)
        self.assertGreaterEqual(harness.MOUNT_BUDGET_S, 20.0,
                                "the bound is a runner's cold boot; the development host's 3.4 s is not it")



class EvaluateBudgetTests(unittest.TestCase):
    """The runner that judged main red at `ed7b8fa6` hit the harness's ANSWER timeout, not a product fault.

    One sweep session clicks 31 rail lanes and walks every scroll range of every view, so the 60 s that
    fits a single shell is not a budget for it. The fix declares the number where it is used and keeps the
    refusal: a genuine timeout is still NOT_RUN, never a smaller sample.
    """

    def setUp(self) -> None:
        self.harness_src = HARNESS.read_text(encoding="utf-8")
        self.sweep_src = SWEEP.read_text(encoding="utf-8")

    def test_the_answer_budget_is_a_parameter_not_a_hardcoded_socket_default(self) -> None:
        self.assertIn("evaluate_timeout_s: float = 60.0", self.harness_src)
        self.assertIn("connect_with_retry(cdp_port, evaluate_timeout_s=evaluate_timeout_s)",
                      self.harness_src, "the budget must reach the socket that waits for the answer")

    def test_the_budget_travels_into_the_receipt(self) -> None:
        self.assertIn('"evaluateTimeoutS": evaluate_timeout_s', self.harness_src,
                      "a verdict must state which budget it was produced under")

    def test_the_sweep_declares_its_own_larger_budget_and_passes_it(self) -> None:
        declared = re.search(r"^SWEEP_EVALUATE_TIMEOUT_S = ([0-9.]+)", self.sweep_src, re.M)
        self.assertIsNotNone(declared, "the sweep never declares an answer budget")
        self.assertGreater(float(declared.group(1)), 60.0,
                           "the sweep inherits the single-shell default it already timed out against")
        self.assertLess(float(declared.group(1)), 900.0,
                        "an unbounded wait turns one hung session into a hung job")
        self.assertIn("evaluate_timeout_s=SWEEP_EVALUATE_TIMEOUT_S", self.sweep_src)

    def test_a_timeout_still_refuses_instead_of_shrinking_the_sample(self) -> None:
        # Located by the statement, not by the phrase: the comment above declares that phrase too, and a
        # guard that matches its own prose is a guard that can never fail.
        lines = [ln for ln in self.sweep_src.splitlines()
                 if 'LEGIBILITY_GATE_NOT_RUN views/' in ln and ln.lstrip().startswith("print(")]
        self.assertEqual(1, len(lines), f"expected one refusal site, found {len(lines)}")
        site = self.sweep_src.index(lines[0])
        self.assertIn("return 3", self.sweep_src[site:site + 200],
                      "a failed sweep must exit NOT_RUN, not continue with fewer lanes")




class SweepRetryTests(unittest.TestCase):
    """A launch race may be retried; a re-roll nobody can see may not.

    The runner killed the whole-rail sweep twice on `main` within seconds of a green geometry step and never
    on the development host, with the traceback swallowed by the handler that printed only `repr(exc)` — so
    the red existed and was unattributable at the same time. These cases pin both halves of the fix: the
    attempt is counted and printed, and a retry that keeps failing still raises.
    """

    def setUp(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts" / "audit"))
        spec = importlib.util.spec_from_file_location("legibility", SWEEP)
        self.sweep = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.sweep)

    class FakeGeometry:
        def __init__(self, outcomes):
            self.outcomes = list(outcomes)
            self.calls = 0

        def serve_and_eval(self, *args, **kwargs):
            self.calls += 1
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return dict(outcome)

    def test_a_failed_session_is_retried_once_and_the_attempt_is_counted(self) -> None:
        geometry = self.FakeGeometry([TimeoutError("timed out"), {"nodes": 1}])
        got = self.sweep.run_views_session(geometry, ROOT, "chrome", None, "/p", "1280,900",
                                           1280, "expr", "dark", None, attempts=2)
        self.assertEqual(2, geometry.calls)
        self.assertEqual(2, got["sweepAttempts"], "the receipt must say this came from a retry")

    def test_a_persistent_failure_still_raises_rather_than_reporting_a_small_sample(self) -> None:
        geometry = self.FakeGeometry([TimeoutError("a"), TimeoutError("b")])
        with self.assertRaises(Exception) as caught:
            self.sweep.run_views_session(geometry, ROOT, "chrome", None, "/p", "1280,900",
                                         1280, "expr", "dark", None, attempts=2)
        self.assertEqual(2, geometry.calls)
        self.assertEqual("b", str(caught.exception), "the last attempt's error is the one reported")

    def test_attempts_can_be_set_to_one_without_becoming_silent(self) -> None:
        geometry = self.FakeGeometry([TimeoutError("only")])
        with self.assertRaises(TimeoutError):
            self.sweep.run_views_session(geometry, ROOT, "chrome", None, "/p", "1280,900",
                                         1280, "expr", "dark", None, attempts=1)
        self.assertEqual(1, geometry.calls)

    def test_the_refusal_site_prints_a_traceback_not_only_a_repr(self) -> None:
        src = SWEEP.read_text(encoding="utf-8")
        self.assertGreaterEqual(src.count("traceback.print_exc()"), 2,
                                "a swallowed traceback is why the two main-head reds could not be attributed")


class OneBudgetAcrossBothLayersTests(unittest.TestCase):
    """The answer budget must be ONE number that governs both layers, not two that disagree.

    `ChromeCDP` kept a loop deadline in `self.timeout` and a hardcoded 10 s socket timeout from
    `create_connection`. Raising the first (ERR-287) therefore changed nothing for a caller whose
    expression is quiet for longer than 10 s: `_recv_text` -> `one_frame` -> `recv` timed out and the
    sweep died identically on both attempts at ff3348bf. Two thresholds, one of them invisible, is how a
    "fixed" gate stays red.
    """

    class FakeSock:
        def __init__(self) -> None:
            self.sent = 0

        def sendall(self, data: bytes) -> None:
            self.sent += 1

        def recv(self, _n: int) -> bytes:
            return b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\n"

        def close(self) -> None:
            pass

    def _connect_timeout(self, timeout: float):
        import unittest.mock
        recorded: dict = {}
        sock = self.FakeSock()

        def fake_create_connection(address, timeout=None, **kwargs):
            recorded["address"] = address
            recorded["timeout"] = timeout
            return sock

        with unittest.mock.patch.object(harness.socket, "create_connection", fake_create_connection):
            cdp = harness.ChromeCDP("ws://127.0.0.1:9222/devtools/page/X", timeout=timeout)
        return recorded, cdp

    def test_the_socket_read_timeout_follows_the_declared_answer_budget(self) -> None:
        recorded, cdp = self._connect_timeout(300.0)
        self.assertEqual(300.0, recorded["timeout"],
                         "the socket read kept its own ceiling, so a bigger declared budget was a lie")
        self.assertEqual(cdp.timeout, recorded["timeout"], "one budget, two layers, must be the same number")

    def test_the_default_is_still_bounded(self) -> None:
        recorded, _cdp = self._connect_timeout(60.0)
        self.assertEqual(60.0, recorded["timeout"])

    def test_the_hardcoded_ten_second_read_is_gone(self) -> None:
        src = HARNESS.read_text(encoding="utf-8")
        init = src[src.index("class ChromeCDP"):]
        init = init[:init.index("def send(")]
        self.assertNotIn("timeout=10)", init,
                         "a per-read timeout below the declared answer budget re-creates the silent 10 s wall")

# The runner is the last statement on purpose. This suite executes each module as a script, so a
# class defined below `unittest.main()` is never collected: 2026-10-25 measured 14 tests run against
# 21 collected here, and the seven invisible ones were exactly the two classes appended after the guard.
if __name__ == "__main__":
    unittest.main()
