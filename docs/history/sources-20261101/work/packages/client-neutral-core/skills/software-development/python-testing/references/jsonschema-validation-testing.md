# jsonschema 校验代码的测试模式（validated 2026-08-14, ArcheAxis-Knowledge-OS AXW-DATA-401 / AXW-CAP-502）

契约文件（`contracts/<domain>/*.schema.json`）+ `shared/*.py` 里
"jsonschema 可用则用它、否则手写 fail-closed 校验"双路径实现的测试经验。
同一个坑在本会话踩了两次（workspace manifest、plugin manifest），以下每条都对应真实 pytest 失败。

## 1. jsonschema 错误消息不带字段名——match 断言要宽容

- **`const` 违规**：`"schema_version": {"const": "1.0"}` 被违反时，
  `jsonschema.ValidationError.message` 是 `"'1.0' was expected"`——**没有字段名**。
  断言 `match="schema_version"` 会失败（失败在消息，不在行为）。
- **`pattern` 违规**同理：`"'UPPER CASE' does not match '^[a-z0-9]...$'"`，
  不含 `plugin_id` 字样。

修法：宽容交替正则，同时兼容 jsonschema 与手写路径的消息形状：

```python
with pytest.raises(ValueError, match=r"was expected|schema_version"):   # const
with pytest.raises(ValueError, match=r"UPPER CASE|plugin_id"):          # pattern
```

## 2. jsonschema 只报第一个错误

缺多个必填字段的 manifest 只报最先命中的（如 `'name' is a required property`），
即使测试想验证的是 `permissions` 门。两种处理：
- 断言 `match=r"required|permissions"`；或
- 构造"只缺被测字段"的最小变体（`{k: v for k, v in VALID.items() if k != 'permissions'}`），
  让它精确失败在被测字段上。

## 3. 手写回退校验器是第二条代码路径——必须单独测

常见 fail-closed 架构：`try: import jsonschema; except ImportError: 手写校验`。
强制走回退路径的标准手法（Python 对 `sys.modules[name] = None` 的条目
`import` 时抛 ImportError）：

```python
def test_handwritten_validator_matches_schema_contract(monkeypatch):
    monkeypatch.setitem(sys.modules, "jsonschema", None)   # 之后的 import jsonschema 抛 ImportError
    validate(json.loads(json.dumps(VALID_MANIFEST)))       # 合法样例必须仍通过
    # 同一套拒绝矩阵：缺每个必填字段、未知顶层键（对应 additionalProperties:false）、
    # 数组项形状（capability_lock 缺 version_range 等）
```

另：schema 文件缺失时也应回退到手写路径（validator 里 `if not _SCHEMA_PATH.exists():`
分支），两个回退条件（包不可用 / 文件不存在）至少覆盖一个测试。

## 4. 架构要点（为什么双路径能成立）

- schema 文件用 `Path(__file__).resolve().parents[1] / "contracts" / ...` 定位
  （从 shared/ 模块锚定项目根），打包运行时文件缺席自动走手写路径。
- 两条路径抛同一异常类型（ValueError）且消息都含字段名（手写路径自己拼
  `f"missing required field '{key}'"`），测试才不用区分来源。
- `jsonschema>=4.0` 在项目 `ci` 依赖组里，铁律测试命令
  `uv run --frozen --group ci --group ci-adapters pytest` 下可用——所以默认测试
  走的是 schema 路径，手写路径只能靠 `sys.modules` 技巧单独覆盖。

## 5. 相关：版本区间兼容性（api_contract）fail-closed 测试

区间解析支持 `1.x` / `1.2.x` / `>=1.0,<2.0` / `1.2.3` / `*`，按半开区间求交；
**任何不可解析的区间直接判不兼容（返回 False），绝不宽容**。测试矩阵：
- 相交通过（`1.x` ∩ `>=1.5,<2.5`）；不相交拒绝（`1.x` ∩ `>=2.0`、`1.x` ∩ `<1.0`、`1.x` ∩ `2.x`）。
- 单子句比较符（`>=1.0` 无逗号）要能单独解析为无上界区间——初版实现把
  `>=1.0` 误当精确版本解析返回 None，导致合法范围被判不兼容（已修）。
- 平台匹配：manifest os/arch 为 `any` 通配；host 缺 os/arch 字段 → 不兼容（fail-closed）。
