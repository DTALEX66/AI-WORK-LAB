# R3-02 项目路径解析与接入边界

此文记录已实现的项目内切片，不表示全部 Agent／Adobe 写入治理完成。
配置入口：`.project/paths.json`；实现：`src/design_lab/runtime/paths.py`。

## 解析规则

`explicit project_local_root` → `PROJECT_LOCAL_ROOT` 环境变量 → 项目配置 → `.project-local` 默认值。
相对路径始终从代码所属项目解析，不从 CWD、用户 Home 或相邻项目推断。
显式值与环境值仍受本仓 `.project-local` 边界限制；仓外、旧 `.hermes`、UNC、
父路径逃逸、ADS、Windows 设备名、链接／junction 均拒绝，而不是悄悄回退。
修改环境覆盖值后需重启该任务进程，运行中的重建合同不热切换根目录。

| 数据类别 | 默认位置 | 使用边界 |
|---|---|---|
| 运行与临时数据 | `.project-local/task-runtime` | 可再生、按 namespace/run ID 隔离 |
| 验证证据 | `.project-local/task-artifacts` | 保留日志与哈希，生成时间不等于实测时间 |
| 持久作品 | `.project-local/projects` | 作品与运行临时目录分开，不自动搬动旧作品 |
| 新模型缓存 | `.project-local/cache/models` | `child_environment` 提供 HF/Torch 路径，不自动下载 |
| 共用模型／设计资料库 | 已声明的两个 D 盘库 | 只读输入声明，本解析器不扫描、不写入 |
| Agent profile | 不读取 | 不从用户私有配置、凭据或会话判断写入来源 |

`resolve_paths`、`describe`、`task_dir` 与 `child_environment` 均不创建目录。
调用实际写入 API 前仍需对应任务授权、路径再校验与单写约束。
诊断中 `writable` 是归属策略，不是已执行 ACL／磁盘写入探测。

## 已接入与待接入

- `scripts/design_lab_doctor.py --paths --json`：从非仓库 CWD 也解析同一入口；非法覆盖退出 2。
- 旧 reconstruction `runtime_roots`：转发到同一解析器；保留原合同词汇，拒绝危险 run ID。
- 双进程测试调用真实 reconstruction `atomic_write`；Python audit hook 捕获 mkdir/open/rename
  的 PID、PPID、目标，并对输出做 SHA-256 读回。仅证明这两个受控 Python 进程，
  不冒充系统级跟踪、IDE、所有 Agent 或 Adobe 宿主测试。
- 已接入资产发布器、三个数据库初始化入口、报告暂存、摄取 CLI、资产侧车摘要与
  证据证明文件写入入口。显式 DB／产物路径不能绕过所选根；DB 的 WAL/SHM/journal
  路径也经过链接与硬链接检查。三组旧 DB 单元测试的临时目录已显式固定在项目内。
- 尚未交付的服务／工作台及真实宿主入口仍待接入；不能宣称所有已安装 Agent 都已治理。
- UI／Adobe／安装后的 Agent 多入口实测、取消／失败路径、真实作品库备份还原尚未完成。

## 迁移预演与回退约束

本轮没有移动、删除或修改任何旧运行目录或用户数据库。路径诊断继续返回
`migration: NOT_EXECUTED`。新增只读预演命令：

```powershell
.venv/Scripts/python.exe -B scripts/design_lab_doctor.py --migration-preview .project-local/task-artifacts/r3-execution/migration-demo/selection.json --json
```

清单格式为 `design-lab/migration-selection/v1`，`files` 数组逐条提供项目相对
`source` 和 `destination`，不接受通配扫描；最多 1000 条、默认哈希预算 512 MiB。
仅接受项目 `.project-local` 或明确的旧 reconstruction 产物路径，拒绝私有状态、
外置路径、链接、硬链接和不支持的类型。目标冲突不覆盖；源文件缺失不编造。
SQLite 有 WAL/SHM/journal 时阻止快照声明；无伴随文件仍必须另行停写和备份。
`PREVIEW_READY` 只表示清单可进入备份阶段，`migration_executed` 始终为 false。
仓内示例仅使用合成 JSON，不代表已经盘点或搬迁用户作品。

正式迁移前必须完成以下清单：

1. 仅枚举已授权的本项目旧数据路径，排除凭据、私有会话与 Agent profile；不扫描共享盘根。
2. 对每个源建立相对 locator、大小、哈希、目标、冲突状态、拥有者；无法证明归属的不迁移。
3. 暂停本项目写入者，备份 DB 及关联产物；先确认无 WAL／活动事务再做一致性复制。
4. 校验全部哈希与 DB 关系，保留源只读副本；一次切换一个项目，不让新旧根双写。
5. 失败时停止新写入，恢复配置与备份，重开读回；不能只改路径字符串就称恢复成功。

以上复制／切换／恢复步骤尚未执行，不是迁移证据。完整 R3-02 仍为 PARTIAL。
