# DL-KNW-000 — 外置资料库登记

- 任务：DL-KNW-000 External Asset Library Registration
- 状态：已登记（E0/E1 级，仅登记不读取）

## 外置原始真源

```text
D:\All projects\Design assets
  = 原始设计资料、图片、视频、音频、字体、PSD/AI/INDD/BLEND、
    参考项目、采购素材等的本地真源（用户建立，不进入 Git）
```

## 边界规则

- `Design assets` **不作为** Git 子模块、软链接、复制目录、默认扫描根或运行时依赖提交；
- DESIGN-LAB 不读取/写入其中的凭据、私有客户资料或未获授权内容；
- 转换只在用户明确选择的子目录上本地执行，默认只读；
- `.gitignore` 已忽略 `/Design assets/`、`/design-assets/` 及本地知识缓存。

## 进/出边界

| 留在 `Design assets` | 进入 DESIGN-LAB Git |
|---|---|
| 原始图片/视频/音频、PSD/AI/INDD/BLEND、字体、模型权重、大体积 PDF、客户源文件 | SourceRecord、内容 hash、许可证/权利状态、受限摘要、结构化 KnowledgeCard、MethodCard、Token、Rubric、BenchmarkCase、转换脚本与统计索引 |

## 规则

- 不复制原始大文件，不保存绝对本地路径，不保存密钥/账号/客户隐私；
- 原始文件本体和本地转换缓存留在外置资料库或其忽略缓存；
- 未知权利默认 `reference-only`，不得进入可发布资产或训练/微调流程。
