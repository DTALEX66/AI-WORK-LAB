# 同一 RIR 到 Photoshop 原生工程

状态：受控生产者/消费者运行通过；不是自动参考拆解、复杂复刻或 M1 完成。
基线 `f3aea7080db46e926d451fe892a964dba9c0a0ee` 加本轮候选源码。

## 改动

`packages/capabilities/reconstruction/adobe_job.py` 新增 `build_photoshop_job`，复用现有 RIR schema、图层排序、资产路径和 Illustrator 对象转换校验，再转成固定 Photoshop job。不会执行脚本、调用模型或改写输入。

支持明确字体/字号/颜色的活文字、独立 PNG/JPEG（包括已物化 alpha）、矩形填充、组和矩形蒙版。坐标从 Illustrator 的底部原点转换回 Photoshop 顶部原点。PSD 填充是独立像素层，不声称为矢量形状层。曲线、斜边、交叉矩形、未支持外观或非矩形蒙版被拒绝，不能静默丢失或贴整图冒充可编辑复刻。

转换器仍在仓库 reconstruction 模块；本轮没有把整个 RIR 系统安装进 wheel。实际宿主执行则使用已有安装包 `design_lab.native_tasks`，不是测试脚本自己的 COM 旁路。Web 受控提交、参考识别和 patch API 仍需接续。

## 回归证据

新增 `test_reconstruction_photoshop_job.py`：先观察 3 项缺失生产者的 RED，再实现并观察 3 项 PASS。验证文字/矩形坐标与 zOrder、透明图像和矩形蒙版的独立性、曲线拒绝及既有 PSD 不覆盖；正向 job 交给实际 JSX 的 `psValidate` 在 Node 中验证，替身仅在 Adobe DOM 边界。
既有 `test_reconstruction_adobe_job.py` 8 项和 `test_photoshop_com_adapter.py` 6 项 PASS，共 17 项，不是全量 Python 测试。

本轮统一检查会话 31700 终态退出 0：`VERIFY_DESIGN_LAB=OK total=49 failed=0`；报告生成及 `--check` PASS。其中历史 Comfy E3 文案不是本轮推理证据。基线提交的 CI `34154430261` 五个 job 已直接读回 success；本次提交的 CI 另验。

## 真实 Photoshop 执行

准备命令：`.venv/Scripts/python.exe -B design-lab/tests/host_fixtures/prepare_photoshop_lowered.py`。
执行命令：`.project-local/task-runtime/workbench-installed/Scripts/python.exe -I -B design-lab/tests/host_fixtures/qualify_native_tasks.py <repo> photoshop <run>/job.json`。

本轮 run：`.project-local/task-artifacts/photoshop-rir-20260908/run-1bffa7c8518a4cfdbf4d35f77a8ce7f0`。
包含 RIR、明确 text styles、实际 producer job、producer-binding、原生 PSD/PNG、native-task-readback；全部留在 ignored 本地运行根，不进入 Git。

- Photoshop 26.7.0，2026-09-07 UTC 19:14:09–19:14:15；约 5.46 秒。
- 项目 `0ac7f0a94cb847a1a0a87c7db4d7a376`，attempt `att-c3c229d45c384f71a42bdeac77b2bd00`。
- 资产版本 `v-22cc782e136e4a41a37a8b0e35a65ffd`；PSD 197297 bytes，SHA256 `33d6c78d34195aba0319fd262bd7498d11b4a398ba418d16a4ecc41f3b7531b6`。
- 预览 PNG SHA256 `8c490d5f546b699895a83b9983ddb27d75dec6b91689e8179a4cb9f6c62e5174`，800×600，已人工工具查看确认非空、标题/面板/独立图像可见；不是 Human Jury 接受。
- 文档数量 0→0；保存重开后实际结构读回通过；重复请求返回同一版本，RUNNING 事件只有 1，剩余宿主 guard 为 0。
- 运行使用安装模块 `native_tasks.py` SHA256 `c27f06b26eebfe28b0ea1eddc540d4a9d4143082c2a6b52fcfbf63bd45c43756`；桥 SHA256 `1bab069422dcf520e8527d73c1f884b615720fc80fc9d3b058f5999d6fcf3c30`。

该输入为手工构造的受控 RIR 与既有专用图像 fixture，不是声称模型已还原真实参考的源图层。已有两次原生修改证据是先前单独测试，本轮没有将它冒充此 RIR 新任务的修改结果。

## 接续

优先接可安装的 RIR 门面与真实参考对象计划、受控提交及局部修改；不因本轮简单资格图而缩减 5–10 张复杂多类型参考、视频和完整可编辑交付目标。rights/人工 Jury/production/release 仍未通过；知识迁移延后。
