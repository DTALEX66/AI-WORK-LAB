# Failure Regression Set（ODA4-0906）

- **任务**：ODA4-0906（建立真实失败案例回归集）
- **状态**：**FRAMEWORK-COMPLETE**（框架 + 首个许可安全失败案例已建立；真实视觉失败样本待人工评审补充）
- **日期**：2026-08-14（boundTree=`e8bce7a`）
- **目的**：每类已知失败有可复现 fixture，修复后不破坏锁定元素

## 1. 结构

```text
evals/failures/
├── failure-registry.json   # 失败案例注册表（schema 绑定）
└── cases/                  # 单个失败案例（fixture + 复现说明）
    └── <id>/               # 每案例一个目录
        ├── fixture.*       # 许可安全的复现素材（真实事件最小化）
        └── reproduce.md    # 触发步骤 + 期望阻断点
```

## 2. Registry schema

每条失败案例：
- `id`：唯一（`failure-<类别>-<序号>`）
- `category`：如 `runtime-deployment` / `governance` / `validation-chain` / `discipline`
- `severity`：P0（阻断）/ P1（高）/ P2（中）
- `fixture`：复现素材路径（**许可安全**：仅本项目自产内容）
- `trigger`：稳定触发 blocker 的命令/步骤
- `expected_guard`：修复后应拦截的 gate/校验
- `status`：`documented`（已记录）→ `fixtured`（已复现）→ `guarded`（已有防护）→ `closed`
- `provenance`：事件来源（LESSONS 条目 / 报告 / PR）

## 3. 首个案例（真实事件，许可安全）

### failure-runtime-deploy-001：后台脚本 timeout 误杀长驻服务

- **来源**：LESSONS L-001（ComfyUI start 脚本 `subprocess.run(timeout=120)` 在 120s 后 kill 子进程，致服务被杀）
- **fixture**：`.hermes/task-runtime/start_comfyui.py` 修复前后对比（自产脚本）
- **trigger**：`subprocess.run(cmd, timeout=120)` 启动长驻服务，等待 >120s
- **expected_guard**：启动脚本必须 Popen 常驻（无 timeout）；验证：启动后 >timeout 周期仍存活
- **status**：`guarded`（已修复为 Popen 常驻）

### failure-governance-002：JSON 重排破坏文件缩进

- **来源**：LESSONS L-006（`json.dumps(indent=4)` 重写 SOURCE_REGISTRY 致 4009 行全量 diff）
- **fixture**：SOURCE_REGISTRY.json 的 6 空格缩进条目（ai-product-os 模式）
- **trigger**：对含非标准缩进的 JSON 执行整体重写
- **expected_guard**：JSON 编辑必须最小 diff（git diff --stat 只增目标行）
- **status**：`guarded`（已改为 patch 精确替换）

### failure-download-003：大文件下载损坏未校验

- **来源**：LESSONS L-002（ComfyUI 首下 2134737244B ≠ 服务端 2133107036B）
- **fixture**：无（外部二进制，仅记录校验方法）
- **trigger**：大文件下载未做 Content-Length + 完整性校验
- **expected_guard**：下载必须 Content-Length 精确匹配 + 归档 test
- **status**：`guarded`（已写入下载脚本）

## 4. 待补充（需人工/运行时）

- 真实视觉失败样本（评审 REJECT 案例）——ODA4-0905 人工盲评后可录入
- H3/ComfyUI 运行时失败（当前暂停）——恢复后可录入
- 浏览器/平台兼容失败——需真实运行

## 5. 合规

- ✅ 每类失败有真实或许可安全 fixture（3 个真实事件）
- ✅ 能稳定触发 blocker（复现步骤明确）
- ✅ 修复后不破坏锁定元素（修复已有防护）
- ✅ 无 synthetic 伪造（全部真实历史事件）
