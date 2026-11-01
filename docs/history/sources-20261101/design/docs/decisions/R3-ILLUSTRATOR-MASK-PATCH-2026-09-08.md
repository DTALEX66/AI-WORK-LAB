# Illustrator 蒙版与对象局部修改实机交接

状态：IMPLEMENTED_LOCAL / scoped TESTED_LOCAL；R3-11 全项仍未完成。
测试基线 `3d6a922a3b23bd0fcf8ec1178d437512d0c83ffa` 加本次工作区修改。
Windows、Illustrator 29.5.1；非 exact-SHA 发布或独立人审结论。

## 本次实际完成

- 产品 JSX 支持递归 group、闭合路径裁切蒙版、唯一对象 ID 与复杂度上限。
- `applyApprovedPatch` 只修改一个现有文字或同拓扑路径对象；拒绝错误/未保存文档、歧义对象、越界路径、已有输出和非法数据。
- 每次修改保存新的 AI，关闭重开并读回；不通过重建整层或整图贴底冒充局部修改。
- 原生夹具创建带蒙版工程 → 改文字 → 改 Bezier 控制点 → 从未覆盖的 baseline.ai 恢复。
- 每阶段保存实际对象 TSV 与 PNG；任务前后文档数 0→0。

实机入口：[illustrator_editable_native.jsx](../../design-lab/tests/host_fixtures/illustrator_editable_native.jsx)。
经 Computer Use 在 File → Scripts → Other Script 中选择已审查脚本；绘制、保存与读回均为原生 JSX。
输入是已有合成 PNG，非真实参考图质量案例。脚本使用固定本机项目路径，不是可移植产品启动器。

## 本地证据与独立检查

忽略目录：`.project-local/task-artifacts/illustrator-editable-20260908/run-1788799336709/`。
`result.tsv`：PASS、stages=4、textCount=1、documentsBefore=0、documentsAfter=0。

| 阶段 | 文字实际读回 | 曲线首点右控制柄 | 对象与蒙版 |
|---|---|---|---|
| baseline | DESIGN LAB | 200,520 | 1 text / 2 paths / 1 raster；clipped=true |
| text | DESIGN LAB / EDITED | 200,520 | 同上 |
| geometry | DESIGN LAB / EDITED | 200,420 | 同上 |
| restored | DESIGN LAB | 200,520 | 同上 |

四阶段 maskBounds 均为 `300,230,420,100`。实际 PNG 均为 800×600 RGBA。
Pillow 独立像素比较：baseline→text 2569 像素变化，bbox `(341,45,542,81)`；
text→geometry 18100 像素变化，bbox `(40,236,697,376)`；baseline→restored 0 像素变化。
整幅 y≥380 区域在两个编辑后保持一致。恢复 PNG 和 TSV 的 SHA-256 也分别与基线相同。
这不是完整 raster-by-object 哈希校验，也不是感知相似度或用户质量验收。

## SHA-256

| 文件 | SHA-256 |
|---|---|
| 产品 reconstruction-assemble.jsx | `b1a7542d47fdcb0af2acb922654dc48f5904dde7f69fee2e7d7aa14916d1c48c` |
| 原生测试夹具 | `28e0508f43c821c131e531674ce7ccf576704a0fd521e53a28018763dcf04d0e` |
| input.png | `b957f69c5db42b973beb44d3e7b63de125002d396af99245ecf0cdde83846520` |
| baseline.ai | `e69ae94da1a967a7935402ca50cb7f6e1b6464124a090c1562ea5fe5b5ccd16b` |
| text-edited.ai | `03f23bce0dba255f45038845256315ade988513d53f5dea303efce9aad241061` |
| geometry-edited.ai | `388389843e53297d841fe9dc730a658e3b0a364e6fd4197f2d50506e94468852` |
| stage-baseline.png / stage-restored.png | `273597367c19c093c709ab1ad5fc45a23338e9c24256850ae59f381d7ad88ace` |
| stage-text.png | `0c8fa53ef354560e89a9e54f151fb4bb7ebf9c7603d2504a31bee2050b72592e` |
| stage-geometry.png | `4b75ad8daeadad282afbc557895bc7a97b0c3db8a3394305d0e1050301f617e6` |
| stage-baseline.tsv / stage-restored.tsv | `7942afd40e4c6b1441fc81a74f82a592d9083c58a062ad516a2dd4872e649f72` |
| stage-text.tsv | `60059e736f997640a76a55c41fd4d44c8180e57f567d32a232efc02feb3d4e68` |
| stage-geometry.tsv | `6b34423c799f956871273d2ee9debfc13d7adc341187507bab0499e90ea67390` |
| result.tsv | `44bd7977e81192d191365b024bf417ec7313bfaab6dffc25539a2e36c4c71bd1` |

## 测试、失败与纠正

- `.venv/Scripts/python.exe -B -m unittest discover -s design-lab/tests -p 'test_illustrator*.py'`：3 方法 PASS；实际 JSX 经 Node VM 执行，覆盖 28 个非法 job、12 个非法 patch、正向 patch 和既有 10 个路径案例。宿主 DOM/文件边界使用 doubles，不是实机证明。
- `test_reconstruction_illustrator_adapter.py`：2 个既有静态测试 PASS。
- `design-lab/scripts/verify_design_lab.py`：取回此前运行 session 93383 的终态，49 PASS；未重新启动重复全门。其历史 Comfy E3 文案不作为当前 Comfy 推理证据。
- 新阶段预览函数最初使用变量 `native`，Illustrator 提示 Error 9，line 21，非法使用保留字。夹具 SHA 当时为 `fba49c995bfe2a6561b9b050b5e19dc999bd090845e5cb96e042572f9e669a25`。解析期失败，没有新 run 目录。改名 `nativeCheckpoint` 后同一路径实机通过；产品 JSX 未因该错误修改。
- 首次独立图像检查把 y=370 起区域当作完全不受影响，断言失败；实际曲线差异延伸到 y=375，故该区域不是隔离的 raster 检查。保留这项检查设计错误，不将修改区域缩小后的通过宣称为完整位图对象校验。
- 项目没有 `scripts/workflow/execution_preflight.py`；未猜测或创建替代路径。直接验证精确解释器 `.venv/Scripts/python.exe` 和 Pillow import 后运行检查。

## 接续与边界

1. 将同步 JSX 接到产品 API 的 operation/attempt/lease/receipt，补中断、重复提交、未知副作用与产品级回滚；当前恢复只由测试夹具重新打开基线实现。
2. 补 Adobe job schema 与 JSX 校验一致性、颜色/位置/层叠及位图对象读回；可信 root、rights 与真实 RIR hash 绑定由上游承担，夹具非零 RIR 字符串仅测试标记。
3. 完成 Photoshop 原生可编辑 PSD；当前 `integrations/hosts/adobe/photoshop-reconstruction/index.js` 仍是 NOT_EXECUTED 结构入口。
4. 完成 UI→服务→真实参考拆解→AI/PSD→两次局部修改闭环，覆盖 5–10 张复杂多类型参考，不以本合成图替代。
5. Comfy/H3 的小说内容、分镜和 15 秒视频仍未完成；许可/资源资格未清不能开启模型。独立 Human Jury、rights、production、release 门未代签。
6. 知识迁移继续延后。R3 账本仍是状态权威；R4.1 不静默替换，不重置已有成果。

原生产物保持本地 ignored；SVG 可能嵌入字体，不上传原生产物或字体。
代码回退应使用经审查的 forward/revert commit，不能 reset 用户工作或删除其文件。
本文件形成时尚未发布本次修改；提交/云端读回以实际 Git SHA 为准，不由本文件自证。
