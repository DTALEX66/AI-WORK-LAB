# 状态机与模块级单例的测试模式（validated 2026-08-14, ArcheAxis-Knowledge-OS AXW-RUN-204）

FastAPI 后端生命周期状态机（`app/workspace/supervisor.py`：`BackendSupervisor`，
7 态枚举 + `_ALLOWED_TRANSITIONS` 表）与 `/api/v1/system` 路由（`app/workspace/system.py`
模块级 `supervisor = BackendSupervisor()` 单例）的测试经验。

## 1. 公开方法前置守卫 vs 内部状态机表的报错信息不同——两条路径都要测

```python
# start() 有前置守卫，READY 时调用抛的是守卫消息，不是状态机表消息：
with pytest.raises(ValueError, match="cannot start from state ready"):
    supervisor.start()          # 守卫：READY -> STARTING 被拒
# 状态机自身的表也拒绝非法迁移（绕过公开方法直呼内部方法）：
with pytest.raises(ValueError, match="illegal state transition"):
    supervisor._transition_locked(BackendSupervisorState.STARTING, "direct attempt")
```

教训：断言 regex 别只写一种消息——先跑一次看真实 raise 站点再写 `match`；
公开方法自己的守卫（`cannot start from state X`）与内部迁移表（`illegal state transition`）
是两个不同 raise 点，都想覆盖就分别断言（同 python-testing 主文"error message must match
the REAL raise site"一节）。

## 2. 路由消费模块级单例：每测试换新实例保证确定性

TestClient 路由函数在调用时读模块全局 `supervisor`。跨测试共享真实单例会让
状态（ready/failed/stopped）泄漏，测试顺序决定结果。fixture 里换新实例：

```python
@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHEAXIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("ARCHEAXIS_RUNTIME_PROFILE", raising=False)
    from app.workspace.supervisor import BackendSupervisor
    import app.workspace.system as system_module
    monkeypatch.setattr(system_module, "supervisor", BackendSupervisor())  # 换新实例
    from app.main import app
    return TestClient(app)
```

要点：
- patch 目标是**消费模块的属性**（`app.workspace.system.supervisor`），不是构造处——路由在调用时解析模块全局，所以替换模块属性即生效；App 导入顺序（先 import app.main 还是先 patch）都行，只要请求发出前 patch 完成。
- 需要"默认状态"的断言（如 stopped → restart 409）天然成立；需要别的状态就在测试内显式 `system_module.supervisor.start()` 再发请求。
- 这是"Module-level singleton INSTANCES"一节的第三种变体：没有源模块可 patch、也没有 `_initialised` latch——只有一个消费端模块属性，换实例即可。

## 3. 环境变量哨兵的一次性提示测试

一次性 stderr 迁移提示用环境变量哨兵防重复（`ARCHEAXIS_LEGACY_HINT_SHOWN`），
测试模式：

```python
def test_hint_printed_only_once(monkeypatch, capsys):
    monkeypatch.delenv(_LEGACY_MIGRATION_HINT_SENTINEL, raising=False)  # 重新武装
    monkeypatch.setenv("COGNITIVE_DATA_DIR", "C:/legacy/data")
    monkeypatch.delenv("ARCHEAXIS_DATA_DIR", raising=False)
    resolve_runtime_path("data/a")
    resolve_runtime_path("data/b")
    err = capsys.readouterr().err
    assert err.count("[migration]") == 1          # 同进程只提示一次
```

- 每个测试开头 `delenv` 哨兵 = 重新武装，测试间互不污染。
- 注意：conftest/其他模块 import 时若已触发提示，真实 stderr 会有一次，但 capsys 只捕当前测试的 stderr，不影响计数断言。
- 行为断言分两支：ARCHEAXIS 优先（两者都设 → canonical 赢）、COGNITIVE 回退（canonical 缺省 → legacy + 提示）。用 `Path("C:/...").is_relative_to(...)` 或等值断言解析结果。
