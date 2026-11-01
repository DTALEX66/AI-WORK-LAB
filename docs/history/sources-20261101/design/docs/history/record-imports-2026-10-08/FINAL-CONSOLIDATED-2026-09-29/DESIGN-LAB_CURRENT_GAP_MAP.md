# 当前缺口与分期

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。


| ID | 状态 | 缺口 | 维度 | 现有任务关联 | 完成条件 |
| --- | --- | --- | --- | --- | --- |
| G01 | BLOCKED | 原始完整对话与指定9/28原件缺失 | history | SOURCE registry missing队列 | 取原件/hash，不能伪造完成 |
| G02 | 未完成 | EVIDENCE_POLICY/registry路径与计数漂移 | governance | DL-R5-001/023 | 下位文档/路径修正；无Authority重写 |
| G03 | 未完成 | Bundle list class未接HTTP/UI | backend/frontend | DL-R5-005/010 | 项目隔离、正确predicate、分页、空/失败状态 |
| G04 | 未完成 | Token写入/版本/发布回滚 | persistence/frontend | DL-R5-005/010 | 复用DTCG格式与项目绑定 |
| G05 | 未完成 | 商业UI全状态与真实指标 | frontend | DL-R5-010 | demo数据清楚隔离、真实状态与禁用原因 |
| G06 | Owner Decision Needed | 视觉token冲突与组件路线 | visual | DL-R5-010 | 有限范围兼容benchmark后选择 |
| G07 | 未完成 | 宿主资格UI与可恢复任务 | host/readback | DL-R5-004/006/007 | 资格不等于存在/启动；取消ACK与恢复 |
| G08 | BLOCKED当前环境 | 当前PS/AI真实闭环证据 | runtime | DL-R5-011/012/015 | Windows授权项目实机；不是本云端截图 |
| G09 | 未完成 | Human Jury/rights/preflight/交付接收 | quality/delivery | DL-R5-014/005 | 硬门与独立接受，重开源文件 |
| G10 | 未完成 | Comfy生产协议完整性 | tool | DL-R5-008 | WS/history/取消/重试/10次真实模型 |
| G11 | DEFERRED / BLOCKED资格 | H3/视频/3D本地模型 | models | DL-R5-018/019/020/025 | 许可+资源+bench；不得默认安装 |
| G12 | DEFERRED | 包装/展陈/出版高级域 | domain | DL-R5-023扩展映射 | 真实专业规格再开域 |
| G13 | 未完成 | 安装后的Windows可用性/a11y | release | DL-R5-009/010/015 | wheel/CSP/键盘/IME/读屏/升级回滚 |
| G14 | BLOCKED权限 | 完整branch protection管理字段 | governance | 只读审计附录 | 需有管理读取权限的导出；现9checks已知 |
| G15 | 未完成 | 本轮artifact字节独立验证 | evidence | DL-R5-003 | 下载当前CI产物hash，不把元数据当bytes |
| G16 | REJECT_CORE | 通用Agent OS/第二画布/全局客户端管理 | boundary | 不派发到DL核心 | 保留外部接口，不内置实现 |

## 优先级

P0：G02/G03/G05/G15，使已有数据和证据可达且诚实。P1：G04/G07/G08/G09/G13，做真实设计交付闭环。P2：G10与第二宿主群、更多领域。H3/视频/3D按资源资格推进，不反向阻塞无生成模型的Adobe闭环。

历史恢复G01独立保留阻塞；本包不声称补齐其内容。当前main变更后必须重读并重新绑定，不能靠此报告永久固定所有优先级。
