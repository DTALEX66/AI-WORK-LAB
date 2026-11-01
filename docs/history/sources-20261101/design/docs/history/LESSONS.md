# LESSONS — 项目经验与错误账本

- 版本：`1.0`｜状态：`ACTIVE`｜首次建立：2026-08-14
- 角色：DESIGN-LAB 项目级经验固化；每条含「问题 → 根因 → 修复 → 防复发」
- 归属：仅记录本项目范围（ComfyUI/H3 运行时布置、治理、验证链、边界纪律）
- 外部范围问题 → 交接至对应项目，不在此记录

---

## 一、运行时布置（ComfyUI / MiniMax H3）

### L-001 后台脚本 subprocess.run(timeout) 会误杀长驻服务

- **问题**：`start_comfyui.py` 用 `subprocess.run(cmd, timeout=120)` 启动 ComfyUI，120 秒后 `TimeoutExpired` 异常触发 kill，**ComfyUI 被连带杀死**（孤儿进程幸存一次、第二次直接被杀）。
- **根因**：`subprocess.run` 的 timeout 语义是"等待子进程完成"，超时即杀——不适合启动**长驻服务**。
- **修复**：改用 `subprocess.Popen` + `proc.wait()`（无限等待），日志写文件，`CREATE_NEW_PROCESS_GROUP` 防信号传递。验证：135s 后仍存活（旧脚本 120s 杀点已过）。
- **防复发**：启动守护类进程一律 Popen 常驻；临时验证可用 run+timeout，但生产启动必须常驻。

### L-002 大文件下载必须校验完整性（Content-Length + 解压测试）

- **问题**：ComfyUI 首次下载 2035MB 完成但 7-Zip `test` 报 "Can't open as archive"——文件头是合法 7z magic 但大小比服务端 Content-Length 多 160 万字节（**传输被截断/混入数据**）。
- **根因**：curl 下载中断时 `-C -` 断点续传未真正补数据（服务端返回 200 而非 206 时从头重下，日志却显示 size 不变）；文件损坏但 curl rc=0。
- **修复**：下载脚本必须 `curl --retry 3 --retry-delay 5` + 完成后 **7-Zip `t` 测试** 才算成功；`-C -` 续传仅当 size 未达预期才触发。
- **防复发**：任何 >1GB 下载：① 记录服务端 Content-Length（HEAD 请求）② 下载后校验 size ③ 压缩包必须跑 `7z t`；三者全过才继续。

### L-003 国内网络环境：GitHub 直连可用，HF 直连/镜像不可达

- **问题**：ComfyUI 官方 GitHub release 直连下载**可用**（35MB/s）；但 HuggingFace 直连 + hf-mirror.com **全部超时**（8s connect timeout）；ghproxy/gh-proxy.com 不可用（403/超时）；gitee 可用。
- **修复**：GitHub 大文件走直连（不走代理）；HF 模型走 **ModelScope 国内镜像**（`modelscope.cn`，35MB/s，`resolve/master/<path>` URL + ETag 校验）。
- **防复发**：国内下载优先级：ModelScope（模型）> GitHub 直连（软件）> 代理（最后手段，用户明确要求才用）。**用户明令禁止走 VPN 代理浪费流量**。

### L-004 8GB 显存跑 300B+ 模型：社区验证优于主观判断

- **问题**：RTX 5060 仅 8GB VRAM，MiniMax H3（322B）最小量化组合 41GB 权重——主观判断"跑不动"险些放弃。
- **根因**：用显存大小线性外推，忽略 **CPU offload + 系统内存** 路径。
- **修复**：社区调研推翻判断——ComfyUI issue #15251 明确 **8GB VRAM + partial CPU offload 是支持场景**（bug 已修）；官方推荐 `int8_convrot`（cu130 下）+ `nvfp4`（无需 Blackwell）；本机 64GB RAM 足够驻留 41GB 权重。
- **防复发**：硬件可行性判断前先查官方文档 + 社区 issue（GitHub search API），不靠显存大小拍脑袋。**模型选型看官方推荐组合**（int8 > fp8，配套 encoder/VAE 必须齐全）。

### L-005 模型文件必须放入正确目录且验证节点注册

- **问题**：H3 模型下载后需验证 ComfyUI 能识别——仅检查文件存在不够。
- **当前处置**：ComfyUI/H3 的旧运行候选记录不绑定当前 exact SHA；当前树保持 E0 占位，未将 `/object_info`、节点或模型状态当作本轮证据。任何 E3 晋级都必须重新授权并完成当前树的 runtime/provenance/read-back。
- **防复发**：运行时布置的 E3 取证 = ① 进程健康（system_stats）② 节点注册（object_info）③ 模型识别（loader input）④ 真实执行（首条出片）。

---

## 二、治理与验证链

### L-006 JSON 编辑必须保持原缩进（禁止 json.dumps 重排）

- **问题**：SOURCE_REGISTRY.json 中 ai-product-os 条目用 `json.dumps(indent=4)` 重写，导致 **4009 insertions / 4009 deletions** 全量 diff（原文件部分条目是 6 空格缩进的手工条目）。
- **根因**：`json.dumps` 会统一缩进，破坏原文件局部不一致的格式；项目要求最小 diff。
- **修复**：`git reset` 恢复 → 用 `patch` 精确替换目标行的值（6 行，保持 6 空格缩进）→ 净变更 +6 -6。
- **防复发**：**JSON 编辑优先用 patch 行级替换**，绝不整体重写；必须整体格式化时先确认原文件缩进一致性（`git show HEAD:file` 检查）。

### L-007 验证器状态耦合：gate 必须接受合法状态全集

- **历史问题**：旧记录曾把 ComfyUI E3 运行状态写入 evidence README，导致 gate 输出 E3；当前 gate 支持 E0 占位或有完整证据的 E3，但本树按冻结范围明确保持 E0，旧候选记录不得复用。
- **根因**：gate 设计前提是"运行时未就绪"（E0），未考虑 E3 合法路径——**验证器与状态耦合**。
- **修复**：gate 改为双态：E0（占位+未执行）或 E3（运行时验证+证据文件存在）；输出信息动态反映实际状态。
- **防复发**：验证器必须接受全部合法状态（fail-closed 不等于单状态）；新增状态转移时同步更新 gate。

### L-008 治理记录必须与物理状态同步（registry vs 实际）

- **问题**：ai-product-os 前端源码已隔离（quarantine，源码外置 Design assets），但 SOURCE_REGISTRY 条目仍是 `vendor-adapt / adopt-now`——**治理记录与实际状态漂移**。
- **修复**：条目同步为 `quarantine / review-required` + 备注外置位置；`VERIFY_SOURCE_REGISTRY=OK`（162 sources, 0 errors）。
- **防复发**：隔离/移除资产后必须同步 registry（integration_mode + status + runtimeEvidence）；CI 无法自动检测物理状态，需人工核对。

### L-009 报告审计必须对照当前树验证（不能复述旧 SHA 结论）

- **问题**：审计报告基于 efee84c（#77）判定"CI 仍把 Open Design 当硬依赖、.license 错误再授权、schema 缺 required"——但这些在 #78/#79 已修复，报告结论过时。
- **修复**：逐条对照当前 main（c2f1b2f→5ab842a）用代码验证：CI 已条件化、.license 38 个第三方全为真实权利人、schema 已含 licenseStatus/version required。
- **防复发**：审计结论必须先核对目标 SHA 的当前代码，报告与代码树绑定（boundTree）；旧 SHA 结论不得直接套用到新树。

---

## 三、项目边界纪律

### L-010 会话归属判定先于操作（cwd 漂移教训）

- **问题**：系统 cwd 指向其他项目但用户对象是 DESIGN-LAB——曾在 DESIGN-LAB 会话处理其他项目的 overlay 配置修复，被用户纠正。
- **根因**：① cwd 默认值误导 ② 任务名与外部项目技能字面匹配 ③ 未先确认项目边界。
- **修复**：会话归属 = 用户当前工作对象（非 cwd）；非本项目问题只写交接文档，不执行修复。
- **防复发**：操作前先问"这是哪个项目的职责"；跨项目问题一律交接不代办。

---

## 四、Git 与交付

### L-011 PR 合并后 head 分支自动删除 + 定期 fetch --prune

- **问题**：远端残留 12 个已合并 PR 的 head 分支（docs/*、feat/*、fix/*、test/*）——GitHub auto-delete-head-branches 对新合并分支生效，但历史残留需手动清。
- **修复**：确认仓库设置开启 auto-delete；已合并分支用 API 删除（`git refs/heads/<name>`，分支名含 `/` 需 URL 编码）。
- **防复发**：每次合并后确认分支自动删除；定期 `git fetch --prune` 清理本地 stale ref。

### L-012 验证链全绿 + 双端一致 + CI success 三者缺一不可

- **问题**：曾有 CI 通过但本地验证链 FAIL（gate 单状态）——交付判断不能只看单一信号。
- **修复**：每次交付确认 ① 本地 `VERIFY_DESIGN_LAB=OK total=15` ② Python `168 passed`（当前新增证据面回归后） ③ 云端 CI run success ④ main 双端一致（git rev-parse 对比）。
- **防复发**：交付收尾固定跑四件套；任一失败即停。

---

## 关联文档

- 运行时布置细则：`integrations/generators/comfyui/evidence/E3-20260814.md`、`minimax-h3/evidence/E3-20260814.md`
- 证据分级：`docs/EVIDENCE_POLICY.md`
- 治理政策：`KNOWLEDGE_ASSET_POLICY.md`（外置资料库 + 体积门禁）
- 项目边界：`docs/BOUNDARY_CONTRACT.md`
