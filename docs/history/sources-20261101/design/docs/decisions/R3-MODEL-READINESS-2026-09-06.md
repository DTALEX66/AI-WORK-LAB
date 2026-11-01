# R3-08：模型清单与机器探测的证据分层

本轮是部分实现。未运行任何真实 OCR、ASR、H3 加载或推理，未提升模型可用状态。

## 状态与命令

移除缓存目录推导出的含混 READY。`ModelCacheProbe` 保留兼容 Python 入口，
没有受审清单时只报告 `ABSENT` 或 `METADATA_ONLY`，不递归搜索目录内容。
默认缓存由项目路径解析器决定，不读取用户 HF_HOME、MODELSCOPE_CACHE 或私有
profile。共享模型库仅在调用者明确传入其子路径时只读访问，不自动遍历。

`verify_model_files` 逐文件检查受审清单的非零 SHA-256、字节数、固定 revision、
索引 weight_map 与全部声明分片的闭合关系。检查失败保持 METADATA_ONLY；
全部通过至多 WEIGHTS_COMPLETE。LOAD_VERIFIED、INFERENCE_VERIFIED 必须由
后续真实受控加载、输出核验提供，本轮两者明确为 NOT_EXECUTED。
OCR det/rec 不能因文件存在而 ready，ASR 文件存在也不等于转写成功，更不代表 TTS。

可用命令（MANIFEST_JSON 是 MODEL_DIRECTORY 内的相对 JSON 文件）：

```powershell
.venv/Scripts/python.exe -B scripts/design_lab_doctor.py --model-root MODEL_DIRECTORY --model-manifest MANIFEST_JSON --json
.venv/Scripts/python.exe -B scripts/design_lab_doctor.py --json
```

模型命令退出 0 仅表示相对受审清单的权重完整，不表示推理成功；未完整退出 2。
文件清单 Schema：`design-lab/schemas/model-manifest.schema.json`。
必要字段 model_id、40 位固定 revision、来源、文件列表（path/size/sha256/role）。
schema 不接受零摘要、零字节、未知字段；文件角色包括 weight/config/tokenizer/index/support。

## 清单信任边界

不能从本地任意几个文件自算哈希后宣称模型完整。项目 Owner 控制的
`design-lab/config/model-manifest-trust.json` 是独立批准表，默认 `approved: []`。
调用方的模型清单不能自行写入批准，也不能通过模型目录内同名文件替代它。

批准条目绑定 model_id、revision、manifest_sha256、approved_by、source、
observed_at、expires_at；时间必须带时区，重复身份或过期批准不能通过。
manifest_sha256 使用 UTF-8 JSON，键排序、紧凑分隔符，默认 JSON ASCII 转义，
禁止非有限数值。应先核对上游固定版本的完整文件清单及源哈希，再由 Owner
批准；本轮没有批准任何真实模型。批准表应当受版本审查，不能把模型或外部
代理的声明自动转入其中。批准不授予模型用途许可，rights 仍由 R3-07/Human Gate 控制。

全部文件路径预检先于载荷读取；只接受项目本地根或显式选择的已登记模型库。
目录重解析点统一用 lstat 检测，不依赖 Python 3.12 新增的 is_junction。
HF 文件符号链接只允许指向同一模型根内的普通 blob；目标再次检查私有路径。
拒绝目录跳转、链接链、硬链接、私有文件、路径穿越和受保护盘。
读取有总字节预算、单个索引 16 MiB 上限；哈希前后及整次探测结束检查稳定性，
结束时再次确认批准仍有效。并发写者应暂停；这不是操作系统级文件系统快照。

## 工具版本探测

doctor 对 ffmpeg 使用 `-version`，检查真实退出码，解析版本并比较最低要求。
报告具体路径、搜索来源、版本命令、退出码、超时／启动失败／版本不明等结果。
当前 PATH 未找到只表示本次搜索范围未找到。版本命令成功仅证明该进程运行了
版本查询，workflow_status、plugins_status 仍为 NOT_EXECUTED。
锁检查辅助函数固定项目 CWD，默认 CLI 不调用；无 uv 或执行失败不会报告通过。

实际版本查询曾暴露 `gyan.dev` / `developers` 被误判为 dev 预发布，已用真实
输出形态回归并修正为仅解析版本 token。最终日志见
`.project-local/task-artifacts/r3-execution/model-readiness-final/`。

## 尚未验证

- Windows 原生符号链接创建在当前进程报 WinError 1314；对应集成测试明确跳过，
  不算 PASS，不提权或更改系统配置。链接目标逻辑和重解析元数据另有受控单元测试。
- 真实模型上游清单批准、全量权重核验、加载、OCR 样例识别、ASR 转写、H3 推理。
- 实时可用显存、Photoshop 占用、模型峰值及 GPU 工作流；实际宿主／插件启动。
- 全部依赖 R3-02 的完成验收、Python 3.12/3.11 的完整环境资格、CI 和发布。

R3-08 继续保持 PARTIAL；本轮不安装、下载、迁移或删除用户模型缓存。
