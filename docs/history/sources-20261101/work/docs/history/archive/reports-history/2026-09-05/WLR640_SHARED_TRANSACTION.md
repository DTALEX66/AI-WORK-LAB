# WLR-640: 共用事务引擎

config_control_plane.transaction() 是唯一 apply 入口：
- 配置/Skill/插件 apply 全部复用（backup/readback/rollback/idempotency）
- Adapter 无官方安全写接口 -> UNSUPPORTED_APPLY
- 实现: scripts/workflow/config_control_plane.py + tests/test_config_transaction.py
