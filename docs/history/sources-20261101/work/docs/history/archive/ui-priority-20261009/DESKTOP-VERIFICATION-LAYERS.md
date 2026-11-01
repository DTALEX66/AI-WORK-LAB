# 桌面验收的环境分层（W04）

> 这份文件回答一个问题：**在什么条件下，才允许启动一次"真实桌面读回"？**
> 它不替换任何现有门，只把"环境能不能画"与"产品画得对不对"分成两件事。

## 为什么需要它（实测的失败模式）

U19 的判定曾经建立在四样东西上：GitHub 作业标志、后端通过、探针构建成功、进程存活。
**这四样都证明不了产品在画。** 记录在案的实例是：在没有交互桌面的 runner 上，harness 记下
`SKIPPED_HEADLESS` 然后 **exit 0** —— 一个绿勾的含义于是变成"我们没检查"。

所以分层的目的不是更严格，而是**把"没检查"从"通过"里赶出去**。

## 六层与各自的证明力

| 层 | 命令 | 它证明什么 | 它**不**证明什么 |
|---|---|---|---|
| `session` | `SESSIONNAME` | 会话看起来是交互式的（**启发式**，证据里这样标注） | 不是"画过了"——那是 `draw` 的事 |
| `display` | `GetSystemMetrics(0/1)` | 存在带真实尺寸的显示（headless 报 0×0 或失败） | 不是"能画"——有显示不等于有图形路径 |
| `draw` | `CreateCompatibleDC` + `SetPixel` + `GetPixel` | **真的画了一个像素并读回来**（读回值必须等于所绘值） | 不是"产品能画"——它不加载产品 |
| `webview2` | 注册表 `...\EdgeUpdate\Clients\{F3017226-…}` | WebView2 运行时**已注册**（含版本） | 不是"产品在它里面渲染"——那是产品自己的读回 |
| `loopback` | `bind(127.0.0.1, 0)` → 释放 → 重绑 | CDP 读回所需的端口能拿到**且能归还** | 不是"端口上有人应答" |
| `cleanup` | 建临时树 → 删 | 这个 runner 会**收拾自己造的东西** | 不是"没有别的残留" |

`draw` 层的证据形状被测试钉住：它必须给出 `painted_pixel` 与 `expected` 两个值，而不是一个布尔。
**能力标志可以是错的，读回来的像素不会**——它要么等于我们画的值，要么不等于。

## 判定算术（核心规矩）

```
存在 FAIL              → FAIL（具名列出）
否则存在必需层的未解决  → INCOMPLETE（未解决的层逐一具名）
否则                   → PASS
```

`NOT_AVAILABLE` / `NOT_RUN` / `SKIPPED` / `NOT_APPLICABLE` **永远不进 PASS**。
必需层是 `display` / `draw` / `loopback` / `cleanup`；`session` 与 `webview2` 只作旁证。
总 `deadline`（默认 90s）到点后，剩余层记 `NOT_RUN` 并带上原因——**因为超时而没跑**与**跑了通过**
同样不能混为一谈。

CLI 退出码：`0` PASS / `1` FAIL / `3` INCOMPLETE。**INCOMPLETE 不是 0。**

## 使用方式与证据落点

```
python scripts/audit/desktop_capability_probe.py --json-out .project-local/runs/ci/desktop_capability.json
```

- 机器可读结果：`.project-local/runs/ci/desktop_capability.json`（随 observer 作业的 CI artifact 一起上传）；
- 该探针**不启动产品、不改配置、不装东西**，只读环境；
- 真实桌面读回（U19）**只允许在必需层全部 PASS 的环境里尝试**；否则 harness 应记下环境原因并以
  INCOMPLETE 结束，**不得**用 `SKIPPED_*` 冒充通过。

## 本机实测（2026-10-17，作为该层的样例读数，不是 CI 的读数）

```
DESKTOP_CAPABILITY_PASS platform=win32 elapsed=0.047s
  session   PASS  SESSIONNAME=Console（启发式）
  display   PASS  2048x1152
  draw      PASS  painted_pixel=0xff00 == expected
  webview2  PASS  version=155.0.4283.45（注册表）
  loopback  PASS  port=63317 released
  cleanup   PASS  created+removed
```

## CI runner 实测（2026-10-18，run `39121405373`，`observer` 作业，artifact `ci-summary-observer`）

```
DESKTOP_CAPABILITY_FAIL platform=win32 elapsed=0.0s deadline=90s
  session   FAIL  SESSIONNAME=null（无交互会话；证据自述是启发式，不是"没画出窗口"）
  display   PASS  1024x768
  draw      PASS  painted_pixel=0xff00 == expected
  webview2  PASS  version=154.0.4258.62（注册表）
  loopback  PASS  port=61869 released
  cleanup   PASS  created+removed
```

**读法**：`session` 层 FAIL 是**环境事实**，不是产品缺陷——GitHub 托管的 Windows runner 没有交互桌面会话，
`SESSIONNAME` 为空。其余五层（含真画像素的 `draw`）在 runner 上是 PASS，说明该探针能把"环境缺一层"和
"画不出来"分开报。按本文件上一节的规则，这种环境**不得**尝试 U19 的真实桌面读回，harness 应记环境原因并以
INCOMPLETE 结束。探针不阻断 CI（`observer` 作业 success），它只把这条事实写进 artifact。

代码本机与 runner 的差异只有环境：本机 WebView2 `155.0.4283.45`、runner `154.0.4258.62`。
