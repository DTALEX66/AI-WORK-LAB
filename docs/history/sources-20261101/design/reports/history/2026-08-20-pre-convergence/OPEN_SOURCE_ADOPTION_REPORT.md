# OPEN_SOURCE_ADOPTION_REPORT（TP-20260819 DL-P1-001）

## token / UIUX 质量底座评估

| 工具 | 许可证 | 依赖体积 | 适配判断 | 状态 |
|---|---|---|---|---|
| style-dictionary | Apache-2.0 | npm 包 | token 构建（DTCG 已对齐） | adapter E0 登记 |
| storybook | MIT | npm 大 | 组件库文档/评审（可选） | 候选 |
| playwright toHaveScreenshot | Apache-2.0 | Node 依赖 | 视觉回归基线 | adapter E0 登记 |
| axe-core | MPL-2.0 | JS 库 | 无障碍检查（uiux 域已引用） | 参考 |

## 结论

- 已吸收/登记：pixelmatch（ISC 吸收）、ckw-design-skill（MIT 吸收）、style-dictionary/playwright（adapter E0）
- 未引入重依赖：验证器仅标准库（jsonschema）；模型/操作类全走 adapter
- storybook 引入需评估（组件库场景出现时）
