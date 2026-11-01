# AIWORKLAB / AI-WORK-LAB

> **WORK-LAB + DESIGN-LAB 已合并为本项目 AIWORKLAB / AI-WORK-LAB。**
> 当前状态、能力、迁移去向与未完成项**只有一个入口**：
> **[PROJECT_CURRENT.md](PROJECT_CURRENT.md)** — 先读它，再读其他任何文件。
> 项目级执行规则见 [AGENTS.md](AGENTS.md)，执行边界与授权沿革见 [INTEGRATION_POLICY.md](INTEGRATION_POLICY.md)。

本仓库是本地融合后端：统一信封 + 统一存储 + 只读验收门，把 WORK-LAB 的工作循环与 DESIGN-LAB
的专业视觉智能接在同一套对象和合同上。它不是一个"把两个旧应用塞进两个标签页"的界面工程，
前端（STITCH）尚未做，也不在本轮范围里。

## 五分钟跑起来（本地，不联网）

```bash
# 1) 起后端（token 从 stdin 读，不写进命令行也不落盘）
python -m backend

# 2) 真实 HTTP 启动探测：统一面 + 兼容面逐个路由读回，打印一条 json 判定
python scripts/boot_probe.py

# 3) 顶层入口防漂移：根入口引用的路径与数字，逐条与寄存器现值比对
python scripts/check_project_current.py --check

# 4) 全量回归（本机约 14 分钟）
python -m pytest tests/unified tests/legacy -q
```

Windows 上本仓自带解释器在 `.venv\Scripts\python.exe`；把它替换掉上面每一行的 `python` 即可，
不要假设 `python` 在 PATH 里。

## 权威在哪里（不要在这里找状态）

| 想知道 | 去看 |
|---|---|
| 现在成立什么、还差什么 | [PROJECT_CURRENT.md](PROJECT_CURRENT.md) |
| 能力族与验证状态 | `migration/capability-family-register.csv` |
| 验收子句逐条结论 | `migration/task-acceptance.csv` |
| 来源仓每个文件的去向 | `migration/source-coverage-work.csv`、`migration/source-coverage-design.csv` |
| 端点面实测 | `migration/route-surface.csv` |
| 阻断与延期 | `config/blocker-register.json`、`migration/deferral-register.json` |
| 逐轮实测与独立复审入口 | `docs/CODEX-AUDIT-ENTRY.md` |

这些表由 `scripts/build_*.py` 生成，数字一律现算，不手抄。

## 边界（如实，不夸大）

- 本轮为本地执行：不上传、不部署、不发布；系统级出站隔离**未被证明**。
- 真实宿主写入、模型推理、真实私有数据迁移、真人专业验收签字仍是 `NOT_RUN`，
  按 `docs/CODEX-AUDIT-ENTRY.md` §5 与 `migration/deferral-register.json` 记录，不拿合成回执冒充。
- 命令、日志、数据库与临时夹具只落 `.project-local/`（Git 不跟踪）。
- `D:\All projects\Project Archiving` 是统一归档原件，**只读**；不向归档反向清理。
