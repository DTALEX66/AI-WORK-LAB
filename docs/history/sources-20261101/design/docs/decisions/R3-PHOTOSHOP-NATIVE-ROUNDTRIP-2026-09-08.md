# Photoshop 原生 PSD 闭环与接续交接

## 结论与边界

Photoshop 26.7.0 的 Windows COM → 固定 ExtendScript 桥已真实完成：新建含可编辑文字、独立像素层、组及组蒙版的 PSD → 保存/关闭/重开/结构读回 → 修改文字另存新 PSD → 移动图像另存新 PSD → 重开原基线恢复。非 UXP 实测，不替 UXP modal/token 资格背书。

这是 E2 受控合成 fixture，不是复杂参考复刻、工作台产品闭环或 E4 人审。R3 ledger 仍为唯一任务真值；R4.1 附件仅已审阅。知识迁移继续延后。

本轮基于 `02867f1f1dd06a223171c5a7a5afb700423f59a5` 的未提交候选树实测，绑定下列精确源码 hash，不把基线 SHA 冒充包含本轮新源码的提交。

## 代码与运行

- 桥：`integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx`。封闭 job；建文档前验证字段、范围、字体、输入/输出路径、唯一 ID；拒绝覆盖现存输出。
- 资格运行器：`design-lab/tests/host_fixtures/prepare_photoshop_native.py`。默认仅准备；显式 `--execute-com` 调用固定测试序列。UUID 新目录，项目解析器检查路径；COM 脚本走 stdin，无 profile、无策略修改、无 GUI 点击。
- 只在没有打开文档时运行该资格测试；正常结束文档数 0→0。未更改 Photoshop 首选项，不触及用户工程。超时/失败保留部分效果，不自动重试、关闭无关文档或杀宿主。
- 当前桥是内部候选，尚未包装为正式 Python Photoshop adapter/HTTP API；原生路径检查不独立证明无 junction/race，调用方仍须执行项目解析器、输入校验、单写租约和资产发布事务。不能将此 JSX 任意暴露给外部 job。

实际命令：

```powershell
.venv/Scripts/python.exe -B design-lab/tests/host_fixtures/prepare_photoshop_native.py --execute-com
```

Windows `Windows-11-10.0.26100-SP0`、Python 3.13.14、Pillow 12.3.0、Photoshop 26.7.0、ArialMT。

两轮真实运行保留于 `.project-local/task-artifacts/photoshop-native-20260908/`：

1. `run-164275c01a3a4375badee3991b0745cd`：原始桥，11.34 秒；首次通过两次修改和恢复。
2. `run-02c732a7515e42b1ae4c7a88eb75204a`：最终桥，9.14 秒；矩形选区改为显式 px UnitValue 后重新全链实测。

最终轮 UTC `2026-09-07T18:15:47.823350+00:00` 至 `18:15:56.961594+00:00`，退出码 0、stderr 空。实际回执：`PASS / 26.7.0 / 0 / 0 / text-edit / image-move / baseline-restored`。

## 最终轮证据

| 对象 | SHA-256 |
|---|---|
| 桥源码 | `f8f0cf33a083f24663c71a48c7862448f60b214e491396767a5ac274a143276d` |
| 执行脚本 | `5894d54688a41564ab98d86958b23754de1beaa2d6885f43e20d8bb571f46054` |
| Job | `38c614fe2967ced228242d0cfd0a19a4d3f75bacaf4cadc092f85848774e6181` |
| 输入 PNG | `b957f69c5db42b973beb44d3e7b63de125002d396af99245ecf0cdde83846520` |
| baseline.psd | `c70240d04f6fa6cd6a58ce668573a2d9f71c92e004e1970c74f6b4c551b7aa43` |
| text-edit.psd | `214dbdcf913023d3abcd85a91ae436ce5e2df392586da6ceabfae74005afc618` |
| image-edit.psd | `2980d6069239d426a6686f7dca2f1bd4c6bbeec345f7a19b133959bf646beba4` |

宿主重开验证：画布尺寸、文件身份、直接层数量、组和蒙版存在、文字类型/内容/字体/字号、独立正常像素层；patch 后验证新文字和像素层边界平移。独立 Python 验证 PSD `8BPS` 文件头、800×600 PNG、输入 hash 不变。

解码 RGB 像素差异包围盒：文字修改 `[269,57,380,80]`；图像修改 `[300,175,475,385]`，严格位于组蒙版内；基线与恢复差异为 null，即解码像素相同。PNG 元数据导致文件 hash 不同，不宣称二进制完全相同。预览已视觉查看：文字、面板、独立图像与裁切区域存在；合成测试不计入用户要求的 5–10 张复杂参考。

本地 PSD/PNG、job 和结果在 ignored 目录，不上传带字体的测试原生工程；换机应视为证据缺失，按资格命令真实重跑，不能伪造日志。

## 测试、失败与修正

- `test_photoshop_legacy_native.py`：15 个非法 job 在文档创建前拒绝；桥缺失的 RED 已先观察。增加显式像素坐标回归：原实现返回裸数字，RED；改为 px UnitValue 后 GREEN，再跑真实 Photoshop。
- `test_photoshop*.py`：3 项 PASS，包含独立的 UXP 测试；Node doubles 只证明静态/受控合同，不证明 UXP 宿主。
- 上一提交 CI `34149900925` 在 `02867f1` 失败，804 tests、2 failures、1 error、6 skipped。根因是 Illustrator 测试合成项目继承外层 `PROJECT_LOCAL_ROOT`，产品路径保护正确拒绝。设置同名环境变量后本机复现 3 项失败；只修测试 setUp 的环境隔离，产品保护不变；同环境复测 5 项 PASS，Illustrator 全组 8 项 PASS。
- 新桥改变报告输入指纹，`--check` 先报告 DRIFT；使用官方生成器重生成，未手改派生状态。
- 本轮统一检查 `.venv/Scripts/python.exe -B design-lab/scripts/verify_design_lab.py`（执行会话 6191）终态退出 0，`total=49 failed=0`。其历史 Comfy E3 字样不构成本轮 Comfy/H3 推理证据；全量 Python 单测交由新 exact-SHA CI 另验，不把 49 项统一检查冒充 806 个单测。
- 提交后的 exact-SHA CI 需重新读回；不能沿用上一 SHA 的失败或其他 SHA 的绿灯。

## 下一执行器直接接续

1. 将已实测的 PS 桥接入带严格 Python preflight 的可安装 adapter；支持输入预算/hash、宿主文档身份、固定脚本资源、输出封存和 outcome-unknown。
2. AI/PS 一起接到持久化 operation/attempt、租约/fencing、取消对账与资产事务，再开放工作台生成/局部修改/导出。不要先启用空按钮或重复做同一张合成图。
3. 真实参考拆解、5–10 张复杂多类型参考及两次修改/读回；支持分层透明图，但不以整图贴底冒充复刻。当前未测试组蒙版本身的局部编辑、复杂色彩/字体/混合、崩溃中断恢复和用户多文档共存。
4. Comfy/H3 15 秒小说分镜视频独立推进；H3 许可、资源资格未清时 fail closed。人类 Jury、rights、production、release 仍不能自动签署。
5. 保持开发分支同步，不等于 main 合并或正式发布。配额百分比无可读依据，不推测“剩余 30%”；按工作里程碑同步。
