# Windows 代理系统配置

## 三层代理体系

代理可分为三个独立层，互不干扰：

| 层 | 配置方式 | 影响范围 |
|---|---------|---------|
| **系统代理** | Windows Internet Settings | 浏览器 + 部分桌面应用 |
| **环境变量** | `HTTP_PROXY` / `HTTPS_PROXY` | 当前终端 + 子进程（含 Hermes CLI） |
| **应用配置** | `.env` 或应用内设置 | 仅该应用（如 Hermes） |

## 系统代理（Windows）

### 启用
```powershell
# 设置为本地网络代理端口；不要把代理进程误认成 CC Switch
Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable -Value 1
Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyServer -Value '127.0.0.1:7890'
```

### 关闭
```powershell
Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable -Value 0
```

### 查看当前状态
```powershell
Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' | Select-Object ProxyEnable, ProxyServer
```

## Git 代理

### 设置
```bash
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
```

### 取消
```bash
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### 查看
```bash
git config --global --get-all http.proxy
git config --global --get-all https.proxy
```

> 当 Git 代理指向不可用的代理地址时，`git push` / `git clone` 会卡死超时。排查网络问题时优先检查此项。

## 环境变量

Hermes 在启动时读取 `.env` 中的 `HTTP_PROXY` / `HTTPS_PROXY`。这些变量只影响 Hermes 进程本身，不影响浏览器或其他程序。

```env
HTTPS_PROXY=http://127.0.0.1:7890
HTTP_PROXY=http://127.0.0.1:7890
```

**陷阱：** `.env` 只在 Hermes 完全重启时读取。`/reset` 不足以重新加载代理变量。需关闭 Hermes 桌面应用重开。

## CC Switch 配置边界

不要直接修改 CC Switch 的数据库、settings 文件或凭据。通过 CC Switch 的 UI 完成代理开关，并以监听与连通 smoke 验证结果。`switch_model.py status` 和 `hermes_workflow_doctor.py` 只读检查运行状态；它们不应成为写入 CC Switch 内部状态的替代入口。

## 排查网络问题

### 代理是否运行
```bash
netstat -ano | grep LISTEN | grep ":7890"
```

### 代理能否连通外部
```bash
curl -sI --max-time 5 --proxy http://127.0.0.1:7890 https://chatgpt.com
# HTTP/1.1 200 = 正常
```

### 无代理直连是否正常
```bash
curl -sI --max-time 5 https://baidu.com
# 国内网站应能连通
```

### 三层都排查
```bash
# 1. 系统代理
# 2. Git 代理
# 3. .env 环境变量
# 依次取消/启用，定位哪层有问题
```

## 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| 浏览器无法翻墙 | 系统代理未启用 | `ProxyEnable = 1` |
| Git push 卡死 | Git 代理指向不可用地址 | `git config --global --unset http.proxy` |
| Hermes 不走代理 | `.env` 需要完全重启 | 关闭 Hermes 重开 |
| 国外网站能上但国内慢 | 代理无智能路由 | 检查 FlClashCore 规则 |
