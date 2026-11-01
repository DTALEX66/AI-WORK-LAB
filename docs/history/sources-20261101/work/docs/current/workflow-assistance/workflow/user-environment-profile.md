# 用户覆盖层画像（User Environment Profile v2）

## 目的

`config/user-environment-profile.json` 是可移植、字段级 allowlist 的用户覆盖层，
不是机器快照。它只记录 `config/config-ownership.json` 明确标记为 `MANAGE` 的
非密偏好和项目治理边界。

## 允许内容

- 语言、主题、默认 Agent 等明确的用户偏好；
- 用户规则、Skills、插件声明的“来源/策略”，不包含本机清单；
- 项目与安全边界；
- 能力发现要求，不记录发现出的绝对路径。

以下内容禁止进入 tracked profile：完整原生客户端配置、provider/model 路由、
环境变量键名、Skills/Rules 文件清单、Home/安装目录、会话、记忆正文、日志、
缓存、认证状态和任何凭据。

## 导出与应用

默认命令只生成 plan，不写文件：

```bash
python packages/client-neutral-core/scripts/user_profile_export.py
```

只有在审阅计划后才可显式写入项目画像：

```bash
python packages/client-neutral-core/scripts/user_profile_export.py --write
```

画像不直接应用到 Codex/Hermes/CC Switch。任何 live apply 都必须另行授权，并
通过客户端官方接口执行备份、差异、读回和回滚；不受 WORK-LAB 管理的字段保持
原样。

## 安全边界

- 导出器不遍历用户 Home，不读取原生配置、`.env`、认证库、会话库或记忆库；
- 输出不得包含绝对路径、provider/model、环境键名或本机 inventory；
- 不确定字段按 `OBSERVE + QUARANTINE` 处理，不能自动升级为 `MANAGE`。
