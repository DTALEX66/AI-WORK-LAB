# 第一张真实参考：来源核对与 OCR 问题记录

状态：真实参考已取样、已运行 OCR、已生成未验收对象计划；完成复刻数量仍为 0。不是 5–10 张参考验收完成，不是 AI/PSD 可编辑交付。

## 参考筛选（本轮公开页面读回）

| 候选 | 核对发现 | 当前处理 |
|---|---|---|
| [Creative Commons poster — Piotr Chuchla](https://www.behance.net/gallery/5783221/Creative-Commons-poster) | 作者明确写可下载、复制、改编，作品介绍写 CC BY 2.0。图内页脚似为 CC BY 3.0 Polska，出版站通用页脚为 CC BY 4.0，不能混成同一版本 | 取一张公开 JPG 做本地识别研究；署名与版本差异保留，最终 rights receipt 未签 |
| [Modern Optical Typography — NJ Himel](https://www.behance.net/gallery/232216467/Modern-Optical-Typography-Editable-Poster-Collection) | 作品页下载入口指向 Adobe Stock 购买，不是无条件免费源工程 | 不购买、不下载付费源工程；旧候选不自动晋升已授权 |
| [HANDZ — Three Dee](https://www.behance.net/gallery/102335871/HANDZ-Free-3D-illustration-library) | 旧作品页写 CC0、PNG 和 BLEND；[当前官网](https://www.handz.design/)区分免费版与 Premium，并将源 Blender 文件列入 Premium 内容 | 存在版本/交付范围漂移，不使用旧介绍证明当前源工程免费，不购买 |
| [E commerce Wireframe — Rajasekar Thangavel](https://www.behance.net/gallery/11806993/E-commerce-Wireframe) | 页面有特定用途、最多 100 份的使用修改条款，不是通用开放许可；内容为电商线框 | 不拿线框抵扣用户所需复杂电商主图；仍需更合适作品 |
| [Urban Collages — Jorge Rigamonti](https://www.behance.net/gallery/12271737/Urban-Collages-(1966-1971)) | 页面文字与图像不同许可，图像默认 BY-NC-SA 4.0，个别图片 caption 有 BY-SA 3.0 例外 | 复杂拼贴候选；必须绑定具体图片及 caption，未下载或复刻 |

辅助出版来源：[CC Polska materials](https://creativecommons.pl/materialy/)和[English resources](https://creativecommons.pl/our-resources/)。本轮未读取可编辑 SVG 源工程来冒充从位图拆解；未下载模型、购买、上传用户素材或发布参考作品。

## 已取得的真实输入

- 作者：Piotr Chuchla；作品 Creative Commons poster；Behance 项目 5783221。
- [实际 JPG 来源](https://mir-s3-cdn-cf.behance.net/project_modules/source/f9ac4745329803.56079d5cc3d8e.jpg)。URL 来自作品页公开 HTML，而非猜测高分辨率地址。
- 本地：`.project-local/task-artifacts/reference-qualification/behance-5783221/reference.jpg`。
- SHA256：`59bf7d3738b8f5223d2f3d3248f27d5afd9ceb2a2c5b54a15d40bd615d3acb1d`。
- 600×849 像素；目视确认多行授权图解、密集波兰语小字、多组重复图标、分栏边框。不是自行生成的简单几何样例。
- 仅限当前授权的本地研究，保留作者、来源和未决许可版本，不自签人工 rights 或 release；原 JPG 保持 ignored，不上传 Git。

## 真实运行及失败

使用项目隔离 ONNX 环境和此前固定 det/rec 权重，运行本地资格脚本 `.project-local/task-artifacts/reference-qualification/ocr_reference.py`。会话 82309 退出 1；不隐藏失败。

结果目录 `behance-5783221/live-20260907T200409152407Z`；`results.json` SHA256 `94642026089bfb4d595af1c959d0edcbce1e595abf3e38b4c269ec5d7105baa7`。

模型实际检测+识别 48.864 秒，得到 124 个候选，2 个空文字、置信度 0。`Plan.from_ocr` 正确拒绝空文字，报 `DecompositionError: invalid OCR text or confidence`。模型推理已经发生，失败是在候选接入而非加载；Python audit 拒绝事件为 0，不等于操作系统级全部 I/O 证明。

目视比对预测已发现图标被误识别成汉字、波兰语重音符与细字错误。分数高也不能证明文字正确；没有 CER 真值集或人审，不发布准确率。

## 有损信息不得静默丢弃

后续本地资格脚本 `reconcile_reference.py` 读取上述固定结果（没有再调用模型），逐项保留原观测。两项空文字以 `DETECTED_NO_TEXT`、原索引、坐标和分数存入 receipt；其余 122 项进入严格对象计划。未过滤低置信度错误文字来制造好看分数，生产合同也未放宽。

输出目录：`behance-5783221/reconciled-20260907T200613188724Z`。
对象计划 SHA256：`4ffba0a6236cf8911d7cbfb9efb4d2d05793e2e1b28083212137957589ab774f`。
生产 Plan 模块 SHA256：`011b44dafb3d48f1f005ade0231389ba2e4be367810be0b43cd8264a47273012`。

122 个文字候选加 1 个未恢复内容对象，通过现有 JSON Schema；全部宿主未映射。结果状态 `PLAN_CREATED_QUALITY_UNVERIFIED`，quality `NOT_ACCEPTED`，host_execution `NOT_EXECUTED`。

## 下一步

1. 找到同作品可明确绑定的更高清位图，或在当前输入上采用带全局坐标映射的分块 OCR；不要把插值放大说成恢复真实细节。
2. 文本/图标区域分离，明确文字修正与字体替代，再转 RIR；图形不得整图贴底冒充矢量。
3. 保留空识别与低可信候选的显式修正入口，生产 runner 在严格 Plan 合同前执行有证据的分类，不静默丢弃。
4. 补充复杂电商、照片合成、2D/3D 等独立作品；上述候选数量不是完成数量。

本轮仅新增长文档及 ignored 本地研究产物，没有改核心实现。前一综合 49 项通过不作为本张参考的质量证据。开发分支上传仍受既有环境审批策略阻断，不绕过，不宣称双端一致。

## 高清出版稿续测与原生路径缺口

从上列出版站实际 A2 链接取得 [PDF](https://creativecommons.pl/wp-content/uploads/sites/3/2012/06/CC_licencje_plakat_A21.pdf)，1055464 bytes，SHA256 `8af60accd8026fe687abb8c34f437124e607ec922f450329c0f3dc6d5e7856ef`。PDF 单页、未加密、无 JavaScript。只使用 pdfinfo 的文档元数据和 pdftoppm 栅格渲染，没有提取其文字、路径或源对象来重建。

渲染命令：`pdftoppm -f 1 -singlefile -scale-to 3000 -png <publisher-a2.pdf> <publisher-3000>`。本地两文件均位于同一 `behance-5783221` 目录。PNG 2155×3000，SHA256 `5e53676d6c62826d374e81b23958444250c3c7bd57015ff913e98c93b4307e43`。目视确认同一图解内容，但出版稿含裁切标记和页边，不能与旧 600×849 JPG 不配准直接计算像素相似度。高清页脚明确写 CC BY 3.0 Polska；此证据收窄具体出版文件的许可版本，不回写其他网站历史声明或代签人工 gate。

本地 `ocr_reference_highres.py` 会话 38568 退出 0，实际检测+识别 139.162 秒，109 个候选，无空文字。结果 `highres-20260907T200935782054Z/results.json` SHA256 `421521afb83a3dc1e2aecd65a7d5b76b7c268d733d1c1502e3092f2e2aa88cb3`，对象计划 SHA256 `6bd079bb7bc172faa76e5812406190437c25a8aa2ce1c2c444d1088e8adf123c`。模型版本/权重与上一轮相同，输入和实际脚本 hash 单独记录；仍无人工真值准确率。目视抽查部分波兰语细字改善，但图标仍被识别为汉字，质量仍未接受。

另外按 `design-lab/config/reconstruction-models.json` 找到既有 VTracer 1.0.0-alpha.3，并实测二进制 SHA256 为登记值 `83d9df564119f1d21719f358c02b77372dd40e34373cc7a47b9dcc3014e7c587`。对页面图标候选区域做纯栅格裁切，再以 `--preset bw --mode spline --filter-speckle 2 --path-precision 3` 产生 `copy-icon-traced.svg`，SHA256 `c23ed50452d78f74cabe971d55945b689c6e8e80e92399fe51543fae8b9aa4e8`。首个裁切存在边缘截断，v2 裁切又包含边框；均保留为诊断，不作为已分离的完整图标或合格复刻。

该 SVG 有 2 个 path。直接将实际 path d 送入现有 `reconstruction.adobe_lowering.path_points`，2 个均报 `unsupported path syntax`。原因是输出包含相对指令/复合轮廓，而现有转换器明确只支持单轮廓绝对 M/L/C/Z。没有删除子轮廓、把孔洞填实或整页转曲来求通过。

接续实现应优先解决：有界、可审计的相对路径与复合路径规范化；保留孔洞填充语义并验证 Illustrator 原生 compound path 保存重开。先使用这个真实输出做 RED/负例，再做安全单元测试与实际宿主读回；字体与文字对象仍单独处理。当前没有新增宿主运行、没有更改原生 adapter，完整复刻数量保持 0。
