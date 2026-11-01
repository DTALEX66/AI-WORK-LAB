# live-work-root —— 被测试当作"真实存在的目录"使用

`tests/conftest.py` 的 `work_project` fixture 把统一面的一个 work 项目注册到**这个目录**。
后端 F07 的判据是「绑到一个真实存在的根目录 ⇒ `data_origin = live`；合成记录永远不能中途升成 live」，
所以这个目录必须真的存在——它存在的唯一理由就是被 `is_dir()` 判定为真。

## 为什么不是宿主机器上的 WORK-LAB

这里原先用的是 `D:\All projects\WORK-LAB`。那会让 12 个测试节点通过一个共享 fixture
**隐式**依赖仓库外的目录：本机绿，而一份没有来源仓的检出直接红，且红的原因是"这台机器上没有那个仓"，
跟被测行为无关。对照实测见 `.project-local/runs/independence-20261101.json`
（两份同源克隆，唯一变量是来源路径指向不存在；因此变红的 15 个节点里有 12 个走的就是这条路）。

改成仓内目录之后：

- 断言一点没放松，`live` 仍然要求"目录真实存在"；
- 被测对象仍然是真实 HTTP 注册 + 真实存储读回，不是 mock；
- 这套测试在任何一份克隆上都成立。

## 约定

- 本目录里有两样东西：这份说明，和 `services/orchestration/run_quality_gate.py`。
  后者存在**只是为了被探测到**——`_verification()` 只有在目标根下真看到这个文件才敢点名核验命令，
  它自己一旦被执行就返回 2 并报错，免得哪天有测试把"桩跑成功了"当成真闸门过了。
  需要文件内容做断言的夹具，请建在自己的 `tmp_path` 下，不要塞进这里。
- 后端不会往项目根写任何东西（`root_path` 只被读取与校验，见
  `domains/work/orchestration/collectors.py` 与 `domains/work/control/composition_root.py`）；
  如果哪天它开始写了，请立刻把它挪出 Git，不要在本目录里留运行产物。
