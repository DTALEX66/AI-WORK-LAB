# 流成本基线 · 2026-10-18（W06 的测量半条）

> 这是**测量记录**，不是承诺：数字属于这台机器与这次运行，重跑会变。
> 重跑命令见文末；口径与自检都在 `scripts/audit/observer_stream_cost_probe.py` 的文档串里。
> 权威顺序不变：`WORK-LAB-AUTHORITY.md` → 机器权威索引 → 任务包 → open register > 本文。

## 1. 为什么现在才测

W06 的一半（"少读一次"）是**计数问题**，已被测试断言：流健康时十个周期零请求、断开即恢复、同签名不重渲染。
另一半（"CPU 与端到端数据延迟"）**无法断言，只能测**——它只在真跑一个 sidecar、真开一条流的时刻存在。
交接里把它列为"可自行开工、不需要 owner"的两条之一。

## 2. 这次运行的数字

口径：本机 2026-10-18，`--events 10 / --idle-seconds 45 / --stream-idle-seconds 30 / --gap-seconds 1`，
sidecar 以 `--no-worker` 启动（数字是流本身，不是采集器）。

| 窗口 | CPU（单核百分比） | 窗口长度 |
|---|---|---|
| 无消费者（只有 canonical watcher 在轮询） | **0.17%** | 45.0 s |
| 有消费者、无写入（SSE 已连接） | **0.36%** | 30.0 s |
| 有消费者 + 10 次写入 | **1.04%** | 75.0 s |

端到端数据延迟（从 `append_telemetry()` 提交返回到收到携带更新 revision 的 SSE 帧）：

| n | min | p50 | p95 | max |
|---|---|---|---|---|
| 10 | 6.484 s | 6.500 s | 7.485 s | 7.485 s |

## 3. 怎么读这组数（**别读错方向**）

- **延迟由节拍决定，不是由实现慢**：canonical watcher 每 **0.25 s** 轮询一次（改动**被检测到**很快），
  SSE 处理器每 `HEARTBEAT_SECONDS / 2` = **7.5 s** 才醒一次并把累积的帧推出去（改动**被送达**要等节拍）。
  探针把这两个常量**从源码读出来**与样本并排写，就是为了让"被节拍限制"不被读成"实现退化"。
- 观测到的 min 6.484 s 接近一个完整节拍，是因为写入间隔 1 s 短于节拍，几乎每次都落在上一拍刚过之后。
- 由此得到一个**产品层面的推论**：W06 让前端在流健康时不再轮询（45 s 陈旧度阈值以内跳过读取），
  那么"健康流"下用户可见的数据陈旧度上界就是**推送节拍 7.5 s**。这不是缺陷，是设计包络；
  但它必须和 45 s 的 `MAX_STALENESS_MS` 一起被理解，否则"我关了轮询"会被误读成"我更实时了"。
- CPU 的三个窗口只差一件事（有没有消费者 / 有没有写入），所以差值就是那一件事的成本：
  连接一条流 +0.19 个百分点，写入期的整条链路约 1 个百分点。**这个量级不值得为它做缓存优化**——
  这也回答了 W02 那条"token-monitor 要不要加缓存"的一半疑问：就流这条路径而言，省下来的绝对值很小。

## 4. 仪器本身被查过（这是本文最该继承的部分）

本机**外部读取子进程 CPU 是坏的**：控制实验让一个 helper 自报 `process_time()` 为 0.8125 s，
父进程用 `GetProcessTimes` 同期只看到 0.0938–0.125 s 且**冻结不动**。
若照原样写，探针会把每个窗口都报成 `0.0%`——一个"免费"的假结论。

所以探针**先跑仪器自检**：helper 烧掉已知 CPU，探针用将要用于 sidecar 的同一手法去读它。
读不到就判定外部采样器不可用，改用**同进程托管**（`time.process_time()`，同一台机器上自测 1.969 s / 2.0 s 准确），
并在报告的 `instrumentCheck` 与 `effectiveMode` 里写明原因与降级。
上表三个 CPU 数字因此来自同进程模式，`cpuAttribution` 字段写明了它包含了什么（探针自己的读线程、探针自己的写入）。

**这不是"退而求其次"，这是把仪器的盲区变成报告的一部分**：宁可写清"这个数是在哪个模式下得到的"，
也不要交一个来源不明的小数。

## 5. 仍然没测的（写清，不留白）

- **前端渲染成本**：需要真窗口（U19 域）。请求数那半已由测试断言，不在这里重复计时。
- **采集器成本**：`--no-worker`，所以数字里没有 collectors。
- **长跑**：45 s / 30 s 是短窗。真要判定"整天开着是否发烫"，需要在真实工作负载下跑小时级；
  本基线只能证明**空闲与低写入下流本身的成本在 1% 单核以内**。

## 6. 重跑

```bash
PY=.project-local/toolchains/wl-py311/Scripts/python.exe
$PY scripts/audit/observer_stream_cost_probe.py \
  --json-out .project-local/artifacts/observer-stream-cost.json
# 期望 OBSERVER_STREAM_COST_MEASURED；退出码 0=MEASURED / 1=FAILED / 3=INCOMPLETE（INCOMPLETE 不是通过）
```

机器可读结果在 `.project-local/artifacts/observer-stream-cost.json`（本地证据，不入库）。
测试：`tests/ci/test_observer_stream_cost_probe.py`（9 例，含"仪器盲区必须降级"与"帧没到必须 INCOMPLETE"）。

## 7. 同一轮里发现并修掉的缺陷

按文档启动 sidecar（`apps/observer/README.md` 与 `apps/observer/start-observer.cmd` 的写法）在**干净 shell 里起不来**：

```
ModuleNotFoundError: No module named 'canonical_store'
```

根因不是丢文件，是**两条入口不是同一条路**：`tests/conftest.py` 会给测试注入模块根，
所以 CI 里每一次绿都经过引导；而**发布出去的启动器一次都没经过**。
处置：`services/orchestration/sidecar.py` 顶部按自身位置推导模块根（并写明为什么），
新增 `tests/ci/test_sidecar_documented_launch.py` 用**清空 `PYTHONPATH`** 的环境跑一次文档命令，
并要求 `/api/v1/snapshot` 真的应答——只看 banner 不算"起得来"。
