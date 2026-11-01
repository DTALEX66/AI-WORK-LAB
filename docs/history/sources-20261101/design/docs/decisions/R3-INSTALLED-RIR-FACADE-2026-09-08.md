# 安装版 RIR 到 Adobe job 门面

状态：安装包转换与 Photoshop 受控运行已验证；不是自动参考拆解、完整工作台或 release 完成。
基线 `ed8d45ab2857b312f6056c43f7bb5e19dd9b65eb` 加本轮候选源码。

## 交付与边界

现有 reconstruction 的 `__init__.py`、`contracts.py`、`adobe_job.py`、`adobe_lowering.py` 由构建清单直接装入 `design_lab.reconstruction`，RIR/run 两份 schema 作为资源打包。没有复制维护第二份转换器；源码入口继续兼容。

```python
from design_lab.reconstruction.adobe_job import build_adobe_job, build_photoshop_job
job = build_photoshop_job(rir, approved_run, project_root=project_root, text_styles=styles)
# 或 build_adobe_job(...).to_dict()
```

安装入口必须传明确 project_root，复用已有路径解析器验证运行根位于该项目的 `.project-local`。RIR 图像路径从该项目解析，不再从 site-packages 推测；输入仍必须先暂存到 approved_run。省略项目根、越界输入/运行根均拒绝。schema 从安装资源读取，无仓库路径注入。

本次只安装 RIR 验证/规范化和 AI/PSD 转换切片。旧 `validate_run_contract` 依赖仓库的 legacy run 合同，在安装模块中显式拒绝，不能误用 site-packages 当工程根；安装服务使用既有持久化 operation/attempt 合同。未搬迁全部重建算法、未开放任意脚本/网页原生 POST、未自签 rights。

## 行为测试

`test_reconstruction_explicit_owner.py` 在新独立项目及非仓库 cwd 启动 `python -I -B` 子进程，构造真实透明 PNG，验证两个 host job 的图像归属及 Y 坐标，拒绝 parent traversal、URL、绝对外部路径及项目运行根之外的目录，并确认未写 host 输出。

先观察 source builder 不接受 project_root 的 RED；加入显式 owner 后 PASS。以 `DL_TEST_INSTALLED_RIR=1`、安装解释器运行同一测试，旧 wheel 实际报缺少 `design_lab.reconstruction`；安装新 wheel 后 PASS，测试明确不将仓库 src/capabilities 加到 sys.path。源码模式另行 PASS。
既有 RIR contracts 29 项、Adobe producer 8 项、Photoshop producer 3 项均 PASS；不把本组等同全仓单测。

统一检查会话 81520 终态退出 0，`VERIFY_DESIGN_LAB=OK total=49 failed=0`；报告生成与 `--check` PASS。历史 Comfy E3 文案不能充当本轮推理证据。基线提交 CI `34155003375` 已直接读回 completed/success，新提交 CI 另验。

完整 reconstruction 回归会话 84066 已终态退出 0：`.venv/Scripts/python.exe -B -m unittest discover -s design-lab/tests -p 'test_reconstruction_*.py'`，277 tests / 1364.902s / OK。期间持续沿同一会话读回，未因耗时重新启动。该范围不等于全仓测试或复杂参考集验收。

## 安装产物与真实 Photoshop

Wheel `.project-local/task-artifacts/rir-installed-wheel/design_lab-0.1.0a0-py3-none-any.whl` SHA256 `c630dbe77f5559c98e017c79d3de8d60bc46f32bb25245a424ba0c14398c711c`；56 项，无缓存或运行目录污染，四个模块和两个 schema 与源文件逐字节一致。仅重新安装到项目隔离环境 `workbench-installed`，未全局安装或发布。

以该环境 `python -I -B design-lab/tests/host_fixtures/prepare_photoshop_lowered.py --installed` 生成 job，再用 `qualify_native_tasks.py` 经安装的 durable executor 执行。实际 producer 文件位于 site-packages；SHA256 `2af310917ac4cfcb3eb79967178a0b1b061a7f8f9f5a65484b9a02b5a24d0384`。

Run：`.project-local/task-artifacts/photoshop-rir-20260908/run-6cd6954a96a24a1ebcdb88ba12fc11b1`；原始输入/producer binding/native-task-readback 均保留。

- Photoshop 26.7.0，UTC 2026-09-07 19:22:25–19:22:30。
- 项目 `17aa27af5b7b4f4db0bb6fef3018882d`；attempt `att-0a58bcb0e8814ecf95dda3a7e282b465`；版本 `v-f433c6df289b4e52bb5bafc50bd0f591`。
- PSD 197297 bytes，SHA256 `d736ce900dd31514c44c7332011fb803b7ee22f45689ebf4175ed0ca0124b371`。
- 文档 0→0、保存重开结构读回 PASS；重放只有 1 个 RUNNING 事件，剩余 guard 0。
- 与此前 source producer run `run-1bffa7c8518a4cfdbf4d35f77a8ce7f0` 的 800×600 预览逐 RGB 像素比较，difference bbox 为 None。文件字节 hash 不同，不伪称二进制一致。

这是同一受控 RIR 的安装链路资格验证，非新复杂参考案例或人类 Jury。原生产物保持本地 ignored，不上传 Git。

下一步：真实参考→可修正对象计划→工作台受控提交→两次局部修改与完整原生交付；继续 Comfy/15 秒视频资格和既有未完成项。H3 条件未清保持关闭；知识迁移延后。
