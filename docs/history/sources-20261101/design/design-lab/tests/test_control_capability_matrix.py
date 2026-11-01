# SPDX-License-Identifier: MIT
"""P1-CONTROL-SPIKE: 控制能力矩阵验证器的 PASS/FAIL 回归（DESIGN-LAB）。

验证器 (``design-lab/scripts/verify_control_capability_matrix.py``) 的核心红线
在这里被固定：

* 合法矩阵（全 ``supported=false``，诚实 E0 声明）必须 PASS；
* 任何"能力声明超出证据等级"的变异必须 FAIL（supported=true 但 E0/E1）；
* supported=true 但没有 qualified_sha → FAIL（live claim 不可定位）；
* no_bypass_license=false → FAIL（任务书红线：不绕过授权）；
* reachability=computer-use 且 truth=none → FAIL（GUI 管 reachability 但
  必须配 native/artifact truth 层，"能点 Photoshop ≠ 解决集成"）；
* 缺 browser / minimax-design host → FAIL（矩阵必须覆盖已声明的 adapter 路由）。

负控矩阵写进 ``.project-local/task-artifacts/control-spike/``（gitignored），
从不污染跟踪树。Nothing here claims a real host run.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / 'design-lab' / 'scripts'
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from verify_control_capability_matrix import (  # noqa: E402
    DEFAULT_MATRIX, SCHEMA_PATH, validate_matrix)

BAD_DIR = ROOT / '.project-local' / 'task-artifacts' / 'control-spike'


def _load_default() -> dict:
    return json.loads(DEFAULT_MATRIX.read_text(encoding='utf-8'))


def _one_supported_false(matrix: dict, host: str, cap_name: str) -> dict:
    """Deep-copy helper: clone the default matrix and flip one capability to false."""
    import copy
    m = copy.deepcopy(matrix)
    for h in m['hosts']:
        if h['host'] == host:
            for c in h['capabilities']:
                if c['name'] == cap_name:
                    c['supported'] = False
                    c['evidence_level'] = 'E0'
                    c['qualified_sha'] = None
    return m


class ControlCapabilityMatrixTests(unittest.TestCase):

    # -- tracked matrix is structurally valid and PASS ---------------------
    def test_default_matrix_passes(self):
        findings, caps = validate_matrix(_load_default())
        self.assertEqual(findings, [])
        self.assertGreater(caps, 0)

    def test_schema_file_parses(self):
        self.assertTrue(SCHEMA_PATH.is_file())
        json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))  # must not raise

    # -- supported=true 但证据等级不足 → FAIL -----------------------------
    def test_supported_true_with_e0_fails(self):
        m = _load_default()
        for h in m['hosts']:
            if h['host'] == 'minimax-design':
                h['capabilities'][0]['supported'] = True
                h['capabilities'][0]['evidence_level'] = 'E0'
                h['capabilities'][0]['qualified_sha'] = 'deadbeef'
        findings, _ = validate_matrix(m)
        self.assertTrue(any('evidence_level=E0' in f for f in findings),
                        f'expected E0 finding, got {findings}')

    def test_supported_true_with_e1_fails(self):
        m = _load_default()
        for h in m['hosts']:
            if h['host'] == 'photoshop':
                h['capabilities'][0]['supported'] = True
                h['capabilities'][0]['evidence_level'] = 'E1'
                h['capabilities'][0]['qualified_sha'] = 'deadbeef'
        findings, _ = validate_matrix(m)
        self.assertTrue(any('evidence_level=E1' in f for f in findings),
                        f'expected E1 finding, got {findings}')

    # -- supported=true 但没有 qualified_sha → FAIL -----------------------
    def test_supported_true_missing_qualified_sha_fails(self):
        m = _load_default()
        for h in m['hosts']:
            if h['host'] == 'minimax-design':
                h['capabilities'][0]['supported'] = True
                h['capabilities'][0]['evidence_level'] = 'E3'
                h['capabilities'][0]['qualified_sha'] = None
        findings, _ = validate_matrix(m)
        self.assertTrue(any('qualified_sha' in f for f in findings),
                        f'expected qualified_sha finding, got {findings}')

    # -- no_bypass_license=false → FAIL（红线）------------------------------
    def test_bypass_license_fails(self):
        m = _load_default()
        for h in m['hosts']:
            if h['host'] == 'photoshop':
                h['authorization']['no_bypass_license'] = False
        findings, _ = validate_matrix(m)
        self.assertTrue(any('no_bypass_license' in f for f in findings),
                        f'expected no_bypass_license finding, got {findings}')

    # -- computer-use reachability 但无 truth 层 → FAIL --------------------
    def test_computer_use_without_truth_fails(self):
        m = _load_default()
        for h in m['hosts']:
            if h['host'] == 'minimax-design':
                h['truth_model'] = 'none'
        findings, _ = validate_matrix(m)
        self.assertTrue(any('truth_model=none' in f for f in findings),
                        f'expected truth_model finding, got {findings}')

    # -- 缺 browser / minimax-design host → FAIL ---------------------------
    def test_missing_browser_host_fails(self):
        m = _load_default()
        m['hosts'] = [h for h in m['hosts'] if h['host'] != 'browser']
        findings, _ = validate_matrix(m)
        self.assertTrue(any('browser' in f for f in findings),
                        f'expected missing-host finding, got {findings}')

    def test_missing_minimax_host_fails(self):
        m = _load_default()
        m['hosts'] = [h for h in m['hosts'] if h['host'] != 'minimax-design']
        findings, _ = validate_matrix(m)
        self.assertTrue(any('minimax-design' in f for f in findings),
                        f'expected missing-host finding, got {findings}')

    # -- 结构破坏 → FAIL ---------------------------------------------------
    def test_hosts_not_a_list_fails(self):
        m = _load_default()
        m['hosts'] = {'browser': {}}
        findings, _ = validate_matrix(m)
        self.assertTrue(any('non-empty array' in f for f in findings),
                        f'expected array finding, got {findings}')

    def test_empty_matrix_fails(self):
        findings, _ = validate_matrix({})
        self.assertTrue(findings, 'empty dict must fail')

    # -- 负控矩阵落盘（gitignored，不污染跟踪树）---------------------------
    def test_negative_control_matrix_written(self):
        BAD_DIR.mkdir(parents=True, exist_ok=True)
        bad = _load_default()
        for h in bad['hosts']:
            if h['host'] == 'minimax-design':
                h['capabilities'][0]['supported'] = True
                h['capabilities'][0]['evidence_level'] = 'E0'
                h['capabilities'][0]['qualified_sha'] = 'deadbeef'
        bad_path = BAD_DIR / 'bad-matrix.json'
        bad_path.write_text(json.dumps(bad, ensure_ascii=False, indent=2),
                            encoding='utf-8')
        # 验证负控矩阵确实 FAIL（与 --matrix 入口一致的判定）
        findings, _ = validate_matrix(json.loads(bad_path.read_text(encoding='utf-8')))
        self.assertTrue(any('evidence_level=E0' in f for f in findings))


if __name__ == '__main__':
    unittest.main()
