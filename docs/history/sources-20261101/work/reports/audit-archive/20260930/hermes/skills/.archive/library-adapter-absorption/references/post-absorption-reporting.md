# Post-Absorption Status Reporting Pattern

## User expectation

When the user asks "都吸收完了吗？", they want a single organized table showing:

1. What's been **absorbed** (with depth: pip, vendor, format adoption)
2. What's **deferred** (with clear reason: needs model, bake-off, H2+)
3. What's **blocked** (license, product boundary)
4. What's **in progress** (CI pending, PR open)

Do NOT just say "most are done" — show the breakdown.

## Template

```
## 吸收完成状态

### ✅ 已吸收
| 层 | 项目 | 许可 | 方式 | 落点 |
|---|---|---|---|---|
| 文件检测 | Magika | Apache-2.0 | 源码 vendored + ONNX模型 | shared/file_detection.py |

### 🔄 后置（需模型/H2 bake-off/重型依赖）
| 项目 | 原因 |
|---|---|
| faster-whisper | 需 CTranslate2 + 模型（H2 bake-off） |

### 🛠️ 开发工具（CI配置级）
| Syft, pip-audit, Gitleaks | 已在 CI/gateplan |

### 🚫 不可吸收
| MinerU, PyMuPDF4LLM, tldraw, ... | 许可或产品边界不兼容 |
```

## Key rules

- **Never just say** "most have been absorbed" without the table
- **Always explain WHY** something is deferred (not just "deferred")
- **Group by category**, not by PR number
- **Show depth of absorption**: pip dep vs vendored source vs format adoption
- **Keep it one screen**: if the table gets too long, defer items go to a collapsed section
