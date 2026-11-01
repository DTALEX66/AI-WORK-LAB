# 配置真事务（WLR-330）

transaction(): Discover→Effective→Diff→Backup→Approval→Apply→Readback→Commit/Rollback。
APPLIED 仅 readback 一致产生。实现: config_control_plane.py。
