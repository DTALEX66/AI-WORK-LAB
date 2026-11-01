# Open Design Config Template

这个模板说明本仓库期望写入 Open Design `app-config.json` 的关键字段。

实际配置不要直接复制本文件；推荐运行：

```bash
python design-lab/scripts/configure_open_design_windows.py \
  --project-root "D:\All projects\DESIGN-LAB" \
  --permission-root "D:\All projects"
```

`--permission-root` 用于解决 Open Design 调用 Codex 时的目录权限拦截。脚本会把 `D:\All projects` 写入本机 Codex `CODEX_HOME/config.toml` 的 `sandbox_workspace_write.writable_roots`，并把该根目录标记为 trusted project；不会写入 API Key、OAuth token 或真实凭据。

## 关键字段

```json
{
  "agentId": "codex",
  "agentModels": {
    "codex": {
      "model": "gpt-5.5"
    }
  },
  "agentCliEnv": {
    "codex": {
      "CODEX_BIN": "C:\\Users\\<user>\\AppData\\Local\\OpenAI\\Codex\\bin\\<version>\\codex.exe",
      "CODEX_HOME": "C:\\Users\\<user>\\.codex"
    }
  },
  "projectLocations": [
    {
      "id": "loc_all_projects",
      "name": "All projects",
      "path": "D:\\All projects"
    },
    {
      "id": "loc_open_design_assistance",
      "name": "DESIGN-LAB",
      "path": "D:\\All projects\\DESIGN-LAB"
    }
  ],
  "defaultProjectLocationId": "loc_open_design_assistance"
}
```

## Codex 权限覆盖

本机 `%USERPROFILE%\.codex\config.toml` 需要包含：

```toml
[sandbox_workspace_write]
writable_roots = ['D:\All projects']

[projects.'d:\all projects']
trust_level = "trusted"
```

安全边界：只允许用户明确指定的项目根目录；不要把 `C:\`、`D:\` 整盘、Windows 系统目录或 `E:\` 加入 writable roots。

## 不要提交的内容

```text
.codex/auth.json
OpenAI API Key
OAuth access token
Refresh token
.env
真实 AppID / adUnitId
```
