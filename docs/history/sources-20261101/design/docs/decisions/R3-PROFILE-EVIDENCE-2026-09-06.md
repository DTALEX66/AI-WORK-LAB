# R3-07：证据驱动的软件／模型选择

范围：本地选择器、证据合同与用途阻塞分类。不是宿主或 H3 实机验收。

## 输入与信任边界

`src/design_lab/runtime/profile_resolver.py` 保留 `resolve(request)` 入口；旧调用
不再凭格式返回“可用软件”。项目配置 `design-lab/config/profiles.json` 仅登记
候选身份，全部默认关闭且没有运行证据。不存在硬编码软件价格或 H3 永久许可结论。

调用方可传 `catalog`、`context`、时区明确的 `now`、`project_root`。
当前 context 必须由受控探测／派发层提供 `repo_sha`、`os` 和
`versions[profile_id] = {host, adapter}`，不能从待验历史证据反向生成。
证据合同位于 `design-lab/schemas/profile-evidence.schema.json`。

证据只应由受控探测程序和经过批准的条件审查程序产生，不能直接信任模型输出、
下载资料或外部 manifest。哈希验证证明引用文件未变化，不证明记录作者可信、
授权真实或通过独立验收；调用方负责受审目录写入权与证据来源。
本选择器不会抓取许可、扫描模型库、启动软件、写入文件或批准执行。

## 判断顺序

1. 校验请求与候选结构；重复 ID、未知字段、错误布尔值和非法数值拒绝。
2. 默认关闭、无证据、无当前 context、版本／OS／SHA 不匹配均阻止选中。
3. 证据需达到 E2，launch、readback、rollback 均 PASS；E0/E1 不够。
4. 核验总证据以及许可、地区、资源、依赖各自的生效／失效时间。
   任一条件 DENIED、UNKNOWN 或过期均单独报告，不被新宿主探测覆盖。
5. 默认用途是 `PERSONAL_RESEARCH_NONCOMMERCIAL`，不蕴含商业授权。
   请求地区必须明确且被证据覆盖；用途字符串精确匹配，不提供通配许可。
6. 格式和操作必须有同一实测能力条目同时满足可编辑性和离线要求。
7. `resources` 接受带单位的非负有限数值，例如 `vram_mb`、`ram_mb`；
   所需维度必须有足够的 `resource_capacity` 实测值。未传资源要求不等于
   硬件无限可用：resources 条件 PASS 仍是必要条件，派发层须传实际任务需求。
8. fixture、输出以及四类条件凭证均限制在选定项目的 task-artifacts 根，
   检查实际 SHA-256、大小上限、读取前后稳定性；拒绝越界／链接／硬链接。
   默认单个证据文件上限 512 MiB，不读取模型权重本体。模型校验值必须非零，
   与受控探测记录一致；模型文件的完整校验由 R3-08 探测层负责。
9. 只对合格候选评分。默认等权 100 分、按 ID 确定性排序；可配置带来源、
   生效／失效时间的 0–100 偏好分，过期偏好退回等权，不伪称实测成本。

手动指定通过 `manual_profile` 表达：始终返回候选与验证步骤，未合格时
`selected = null`，不暗中换另一个软件。即使合格，结果仍为
`execution_authorized = false`，派发器必须再次核验并执行既有 Human Gates。

## 证据与未完成项

本轮测试使用项目内临时合成文件，覆盖正向选择、反例、文件篡改／缺失、版本
漂移、独立条件过期、资源超限、H3 用途分离、手动选择及确定性。
合成 H3 PASS 测试只证明没有永久品牌封禁，不证明本地 H3 授权或可运行。
只读审查发现原生产物后缀白名单遗漏；已补齐 cdr/psb/eps/fig/blend 的合成
文件回归，同时补测并拒绝 Python NaN 凭证。测试不证明这些合成字节是有效原生文件。
本轮最终命令和源哈希见 `.project-local/task-artifacts/r3-execution/profile-reviewed-final/`。

R3-08 的真实探测结果接入、R3-09 的派发前重新核验、R3-10 的界面候选展示仍待
后续任务完成；没有 Adobe/GPU 实机、商业许可审定、CI 或发布证据。
旧静态表保留于 Git 基线 `c4dccd58331bc4561eb89265283d924b7630d113`，只供历史
读取，不提供回退到误报“可用”的运行开关。
