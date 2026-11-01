# DESIGN-LAB｜2026-09-08 R5 新任务包

基线：开发分支 ed8d45ab2857b312f6056c43f7bb5e19dd9b65eb；main c4dccd58331bc4561eb89265283d924b7630d113。交付前已远程复核两者未变。

定位：个人非商业研究、本地优先、独立设计工作台。输入参考图或生成图，经过可修正对象计划、原生软件制作、局部修改、重开验证和人工评审，得到可编辑交付。单图无法唯一恢复真实隐藏图层/背面几何，必须标明推断。

此包含28项增量任务，保留R4.1全部27项范围，新增语言治理专项。没有把已做的Python服务、工作台、Adobe桥重置为未实现；没有发布或合并仓库。

## 使用顺序

1. 先读01-AUDIT-BASELINE.md和03-EXECUTOR-HANDOFF.md。
2. 执行DL-R5-001，将差量接入当前R3账本；不直接用旧main结论覆盖开发分支。
3. 按tasks.json依赖领取任务，02-TASKS.md是同源生成的阅读版。
4. 最快主线：运行恢复/路径与资产→安装RIR门面→Adobe产品提交与修改→工作台→人工评审和M1交付。

Comfy、H3、UIA、其他DCC与跨项目联动不再是原生Adobe M1硬前置。Comfy十次基准验收仍保留于独立任务。Python/TypeScript/AdobeJS治理按04-REPOSITORY-LANGUAGE.md推进；不开展无依据全仓重写。

## 包内文件

- tasks.json：任务、依赖、已有证据、实施、验收、回退和四轴定义。
- 02-TASKS.md：完整中文任务卡。
- old-new-crosswalk.csv：R4全部27项映射。
- 01-AUDIT-BASELINE.md：审计结果与局限。
- 03-EXECUTOR-HANDOFF.md：可直接交Agent执行的指令。
- 04-REPOSITORY-LANGUAGE.md：仓库规范、语言迁移及退出条件。
- references/：开发分支原始环境记录与R3/R4.1增量映射，只作证据，不覆盖执行入口。
- SHA256SUMS.txt：文件校验清单。
