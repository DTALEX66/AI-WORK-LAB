# R3 仓库规范化：本地验证与剩余边界（2026-09-07）

状态：PARTIAL。这是可供人工审计的实际变更与证据记录，不是宿主验收、M1 或发布证书。

## 本轮完成的切片

- 四个外置根已经进入 `.project/paths.json`，用途与公开安装信息见 [本机环境](../LOCAL_ENVIRONMENT.md)。运行数据仍在本项目 `.project-local/`；未迁移或写入共享库。
- README / AGENTS 指向同一 R3 任务包和本机环境记录。ComfyUI、PS、AI、MiniMax Design 与 H3 不再混为一种能力，安装登记不冒充运行成功。
- canonical workflow 去掉顶层路径过滤，既有 jobs 保留。resvg v0.47.0 下载有 HTTP 失败处理、超时与重试；归档位于项目运行根，SHA-256 校验成功后才解压。
- 报告读取器仅允许 `.github/workflows/` 直属 YAML 作为公开源证据。内容改变使旧证据失效；其他 `.github`、私有、越界、嵌套路径仍被拒绝。
- DP V1/V2 原件冻结，验收结果在新记录追加，不修改 V2 自身字段或重写其 hash 清单。

## 实际测试证据

所有路径相对仓库；原日志在 ignored 目录，换机缺失时必须显示 MISSING，不能重造日志。

| 证据目录（`.project-local/task-artifacts/normalization-20260907/` 下） | 实际结果 | 范围 |
|---|---|---|
| `20260906T171029031776Z/` | 743 项：742 通过、1 跳过；49 统一门通过；许可、路径诊断通过 | 增补 CI 证据读取规则前的全量 Python 树；1039.992 秒测试时间 |
| `20260906T173524875720Z/` | 16 路径 + 24 报告测试通过；49 统一门、许可、路径诊断通过；源 hash 前后一致 | 上述源码增量之后的定向回归；没有声称再次跑过全量 |
| `renderer-20260906T173900372571Z/` | Bash 语法、实际官方归档校验/列表通过，损坏输入返回非零 | Windows Git Bash 执行 workflow 中的 checksum 命令；未执行 Linux 二进制或写 `/opt` |

来源：GitHub 官方 `linebender/resvg` v0.47.0 release API；Linux archive 1606404 字节，SHA-256 `5c84dcbcd032fe7e8d96e616fd6807a2f9df6561d2e6582b37e91e63c6cb4fe7`。PowerShell 实际下载的归档 hash 与官方发布元数据一致。

新增报告负例先观察到原规则拒绝 workflow 路径，修复后测试通过；合法 YAML 内容改动后 unit 自动变成 UNVERIFIED。静态只读审查未发现本轮限定增量的具体缺陷。

## 失败记录与未验证范围

- 第一次 Git Bash curl 下载返回 56（连接重置），记录在 `renderer-20260906T173638672079Z/`；未禁用 TLS。该早期结果的 scope 文案描述测试目标，实际执行以 commands/result 为准，损坏输入当时未执行。
- PowerShell 同一官方 URL 下载成功。首次跨壳验证中 tar 将 `D:` 当远程主机，记录在 `renderer-20260906T173822068822Z/`；修正测试 harness 的 MSYS 路径后通过，没有为 Windows 测试改写 Linux 产品路径。
- 全量套件的 1 项原生 Windows 链接权限跳过不是通过；保留其限制，不自动提权。
- unified 的 ComfyUI gate 含历史 E3 文案；此处只验该检查命令，不把历史证据升级成本轮 ComfyUI 推理。
- Linux 干净 checkout、托管 GitHub CI、exact-SHA 发布、双端一致：NOT EXECUTED。工作树含未提交成果，HEAD 不是完整源码快照。
- 实际所有入口写入追踪、Adobe 工程保存重开/回滚、ComfyUI 任务及本地模型推理仍待实机证据；R3-02/04 不因本轮切片自动整项完成。
- 历史补齐按独立清单继续；不恢复私人会话，不删除重复历史产物，不做全局配置治理。知识迁移继续延后。

## 接续与人工审计

唯一状态编辑源仍是 `design-lab/config/task-ledger-r3.json`。本轮追加新鲜且范围明确的 receipt 后生成 current 投影并执行 `scripts/generate_current_reports.py --check`；旧 receipt 保留并允许显示 STALE。

下一步按照原 R3 依赖完成真实入口/宿主与模型验证，再接服务、工作台和复刻。人工审计需要分别查看：证据新鲜度、视觉差异、原生结构、可编辑性、失败恢复、rights 和发布范围。自动测试不能代签 Human Gate。
