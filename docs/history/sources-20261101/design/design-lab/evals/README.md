# evals — 评估与验收证据

DL-REL-001：人工可视与生产验收。**UI/UX、平面、3D、游戏视觉各至少一个有效案例**。

## 结构

```text
evals/
├─ benchmarks/           # BenchmarkCase（12 个域基准 + brief 定义）
│  ├─ benchmark-registry.json   # 基准注册（12 项，seed/viewport explicit-per-case）
│  └─ briefs/                   # 12 份评测 brief（描述/输入/流程/输出 schema）
├─ rubrics/              # 质量 Rubric（19 份，轴+权重+阈值）
├─ templates/            # 评分单模板（score-sheet.template.json）
├─ evidence/             # 验收证据（evidence-cards.json，12 卡）
└─ README.md             # 本文件
```

## 基准评测（12 域）

每个域对应一份 `briefs/<域>.json`（layout/typography/color/material/lighting/spatial/motion/interaction/accessibility/cross-format/originality/production），描述评测目标、输入资产、流程与输出。注册表校验：

```bash
python design-lab/scripts/verify_benchmark_registry.py
# → BENCHMARK_REGISTRY_PASS benchmarks=12 human_calibration_required=true
```

### 迭代回归对比

```bash
python design-lab/scripts/compare_visual_iterations.py before.json after.json --tolerance 0.5
# → 输出 overall_delta / axis_deltas / regressions；有回归时退出码 1
```

## 验收矩阵（DL-REL-001）

| 域 | 有效案例要求 | 当前状态 | 前置 |
|---|---|---|---|
| UI/UX | 至少 1 个真实渲染读回案例 | ⏳ 待验收 | 人工选择案例 |
| 平面 | 至少 1 个可编辑交付案例 | ⏳ 待验收 | Photoshop 运行时（用户下载安装）|
| 3D | 至少 1 个 3D 场景/资产案例 | ⏳ 待验收 | Blender 适配器 E3 |
| 游戏视觉 | 至少 1 个 fixture 视觉回归案例 | ⏳ 待验收 | minigame 多端渲染读回 |

## 评分流程（E1 辅助，人工校准）

```bash
# 1. 枚举可用 rubric
python design-lab/scripts/score_artifact.py --list

# 2. 写评分单（JSON）：scores 填各轴 0-10，权重自动应用
#    模板：design-lab/evals/templates/score-sheet.template.json（24 轴占位，复制后填分）
#    {"artifact": "案例路径", "reviewer": "审批人", "scores": {"axis-id": 9.0, ...}}

# 3. 机算判定
python design-lab/scripts/score_artifact.py \
  --rubric design-lab/evals/rubrics/<域>.rubric.json \
  --scores <评分单>.json
# → 输出加权分 + ACCEPT/REVISE/REJECT（缺分/越界 fail-closed）

# 4. 每个域 ≥1 案例 ACCEPT 后，在本 README 添加验收标记：
#    标记格式：DL-REL-001 状态 ACCEPTED（即 `DL-REL-001: <验收状态>`）
#    （该标记是 release gate 的启用条件之一；在真正验收前不要写入）
```

## 证据纪律

- 每案例记录：boundTreeSha、生成时间、执行环境、工具版本、输入 hash、人工审批人
- **不用单张 AI 图作为通过证据**（Quality gate）；官方模拟器/实机截图才为 E3
- 验收通过后才启用 DL-CI-004 release gate

## 当前证据

- `evidence/evidence-cards.json`：12 卡（E0-E2 合同/结构级，与 12 benchmarks 对齐）
- `benchmarks/briefs/`：12 份评测 brief 已就绪（BENCHMARK_REGISTRY_PASS）
- 全部 E3 读回待运行时就绪（ComfyUI/MiniMax H3 由用户下载安装，暂停推进）
