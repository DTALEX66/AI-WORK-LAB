# Domain Pack Spec V2（ODA4-0204）

## 目的
定义职业领域 Domain Pack 的强制结构。**Prompt-only pack 不能通过**；每个领域包必须包含完整十要素。

## 强制十要素
| # | 要素 | 路径约定 | 强制 |
|---|---|---|---|
| 1 | manifest | `manifest.json` | ✅ |
| 2 | brief schema | `schemas/brief.schema.json` | ✅ |
| 3 | scenario | `scenario.md` | ✅ |
| 4 | profile | `profile.json` | ✅ |
| 5 | rubric | `rubric.json` | ✅ |
| 6 | preflight | `preflight.json` | ✅ |
| 7 | handoff contract | `handoff-contract.json` | ✅ |
| 8 | source mapping | `sources.json` | ✅ |
| 9 | benchmark cases | `benchmarks/*.json` | ✅ |
| 10 | evidence cards | `evidence/*.json` | ✅ |

只增加 Prompt、README、模板或人物名单**不算领域完成**。

## 包体与依赖预算
- 默认 `size_bytes_budget <= 5 MiB`（5_242_880 字节）。
- `dependencies` 必须显式列出运行依赖；未声明依赖视为不可复现。
- 大型二进制（>1 MiB）必须走 LFS / Release Artifact，不进包。

## 验证
- 机器可读 schema：`design-lab/schemas/domain-pack.schema.json`。
- 校验器：`design-lab/scripts/verify_domain_pack_v2.py`。
- 正面/负面 fixture 测试确保 prompt-only pack 被拒。

## 证据
- 领域包自身证据等级必须与其声明一致（E1/E2/E3/E4/E5 不互冒充）。
- 每个 Evidence Card 绑定 exact tree、reviewer、timestamp、expiry。

## 目录
预期 Domain Pack：UI/UX、平面、品牌、电商、展馆、3D、动效/视频、音频、游戏、包装/印刷、编辑/出版、插画/IP、数据可视化（13 个）。
