import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'workflow'))
from model_router import TaskSignal, route, route_with_budget
import pytest


def test_privacy_routes_local_lane():
    p = route(TaskSignal('handle API key rotation', privacy_required=True))
    assert p.lane == 'D'


def test_vision_routes_vision_lane():
    v = route(TaskSignal('analyze this screenshot for UI issues', task_type='visual'))
    assert v.lane == 'C'


def test_complex_code_routes_reasoning_lane():
    c = route(TaskSignal('refactor the architecture of the auth module', risk='high'))
    assert c.lane == 'B'


def test_simple_daily_routes_fast_lane():
    s = route(TaskSignal('translate this paragraph to Chinese', task_type='doc'))
    assert s.lane == 'A'


def test_budget_downgrade_cost_threshold():
    b = route_with_budget(TaskSignal('complex debugging session', risk='high'), budget_usd=0.05)
    assert b.lane == 'A'


def test_budget_ok_keeps_lane():
    b2 = route_with_budget(TaskSignal('complex debugging session', risk='high'), budget_usd=2.0)
    assert b2.lane == 'B'


def test_unknown_task_defaults_fast_lane():
    p2 = route(TaskSignal('do something undefined', risk='low'))
    assert p2.model_ref