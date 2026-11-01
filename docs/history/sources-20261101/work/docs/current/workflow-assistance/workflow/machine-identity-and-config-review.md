# 跨电脑机器身份与配置审查

## 结论

可以识别“当前项目运行在此前登记过的哪台电脑”，但这不是登录识别、授权系统或硬件指纹系统。实现采用**项目级、本地生成、随机 opaque `machine_id`**：

- 首次在某台电脑的某个项目副本运行时，脚本只以计划模式生成 UUIDv4 候选；它不写入项目 runtime。持久化该 ID 必须通过单独、受审查的项目本地工作流创建 ignored runtime 文件。
- 用户确认后，人工通过受审查的 Git 变更把该 ID 和标签登记到 `config/machine-registry.json`；脚本不会改写该受跟踪文件。标签不应包含用户名、路径或设备序列号。
- 同一项目副本再次运行时读取本地 ID，并与登记表比较，从而区分 `KNOWN_MACHINE`、`NEW_MACHINE` 和需要审查的配置状态。
- 设备 ID 只表示“这个项目安装曾在此设备初始化”；它不证明用户身份、不授予权限，也不能替代认证。
- 这是项目安装身份，不是物理硬件身份：新 clone 通常会生成新 ID；若完整复制包含该运行时文件的项目目录，ID 也会被复制。因此它只能触发人工复核，不能证明“必然是同一台电脑”。

**不能**用硬件序列号、MAC、Windows MachineGuid、用户名、完整路径、认证文件内容、Token、API key、密码、连接字符串或完整硬件指纹生成 ID。ID 丢失时应按新机器审查，不应通过硬件猜测恢复。

## 状态模型

| 状态 | 含义 | 下一步 |
|---|---|---|
| `IDENTITY_NOT_INITIALIZED` | 本地还没有项目级 ID | 先审阅计划，再显式初始化 |
| `NEW_MACHINE` | 本地 ID 存在，但没有登记到项目 registry | 审阅设备标签和配置，再显式登记 |
| `KNOWN_MACHINE` | ID 已登记，画像摘要未变化 | 可执行只读 `plan/verify`；不需要机器登记动作 |
| `CONFIGURATION_REVIEW_REQUIRED` | 已登记 ID 的非敏感项目画像摘要变化 | 先看差异、跑 `plan/verify`，再决定是否升级 |

当前实现不把“换电脑”直接等同于“必须覆盖配置”：新机器只触发 review；配置变更只触发 plan/verify；任何 apply 仍需用户另行批准，并受 `config-ownership.json` 的 MANAGE/OBSERVE/SECRET 边界约束。

## 安全边界

- `machine-identity.json` 位于项目忽略目录，只保存 schema、随机 ID、创建时间和非敏感 user overlay 画像摘要。
- `machine-registry.json` 只保存随机 ID、人工标签、首次登记时间；不保存账户、路径、IP、硬件、认证、会话、prompt/response、global state 正文。
- 所有脚本命令均为只读或只输出计划；即使传入 `--write` 也不会写入 runtime 或 registry。
- 所有路径必须在当前项目 Git 根内；显式 E: 路径直接拒绝。不会扫描 PATH、访问 E: 或探测用户 Home。
- 设备识别不会自动调用 Windows Repair/Reset、删除 `.codex`、清除认证、覆盖 provider/model/base URL、改写 CC Switch 路由或修改 OBSERVE/SECRET 字段。
- `config/machine-registry.json` 是登记提示，不是信任根；它被篡改或复制时，仍必须人工审查并重新运行验证。

## 操作

在 WORK-LAB Git 根运行（`services/…` 本身就是仓库根相对路径，旧文档写作"先进入
`10-workflow/workflow-assistance`"是该目录被拆分前的写法，按它执行会找不到路径）：

```powershell
# 只读：查看当前项目副本状态；不写文件
python services/authority/machine_identity.py status

# 只读：生成初始化计划；不写文件
python services/authority/machine_identity.py init

# 即使带 --write 仍只输出计划；持久化必须走单独、受审查的项目本地工作流
python services/authority/machine_identity.py init --write

# 只读：生成登记计划；不写 registry
python services/authority/machine_identity.py record --label 'office-pc'

# 即使带 --write 仍只输出登记计划；登记表必须通过受审查的 Git 变更维护
python services/authority/machine_identity.py record --label 'office-pc' --write
```

`--label` 只用于人工识别，不要填写真实姓名、用户名、路径、序列号或账号信息。

## 与配置升级的关系

建议的跨电脑流程是：

1. 在新电脑运行 `status`，确认状态为 `IDENTITY_NOT_INITIALIZED` 或 `NEW_MACHINE`。
2. 审阅 `init`/`record` 计划；不要把设备 ID 当作授权凭据。
3. 初始化/登记后，运行现有 overlay `plan` 和 `verify`，生成配置差异。
4. 只允许恢复合同中明确的 MANAGE 字段；OBSERVE 使用 `preserve_unknown`，SECRET 完全不读。
5. 用户单独批准后才 `apply`；apply 前后都做 readback 和回滚准备。
6. 运行完整质量门禁并记录结果。换电脑本身不能成为自动 apply 的理由。

## 设计限制与后续候选

当前 registry 是项目内显式登记，适合用户自己的跨电脑工作流，不是集中设备管理服务。未来若需要多副本协作，可增加**签名的非秘密登记记录**或用户维护的设备清单，但不得把私钥、Token 或认证正文放入项目；任何远程同步仍需单独授权。设备 ID 轮换、丢失恢复和撤销应通过人工 registry 变更处理，而不是静默重识别。
