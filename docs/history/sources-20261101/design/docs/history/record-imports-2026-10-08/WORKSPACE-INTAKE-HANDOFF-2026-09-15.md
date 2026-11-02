# DESIGN-LAB｜本次监控材料接入交接
审计日期：2026-09-15。
本文是审计后的增量建议，不是新的权威TaskPack，不授权安装、付费、修改仓库或生产替换。
原始报告中的作者成绩、价格快照、代码/模型存在、实际账户可用、运行验收是不同状态。
先读本项目当前AGENTS/任务账本/实际代码；已有能力补测，重复任务合并；不要由聊天摘要直接派工。
本次来源分为research与models两个命名空间。原任务完整映射见03_43条原任务_去重映射.json；
候选分类见02_候选分流_28条.json；外部核验范围与URL见04_来源与核验范围.json。

### DESIGN-LAB：补现有资产验收，不把Penpot升级成默认底座
- 本轮源码src/design_lab/interop/penpot.py明确只做声明、归档结构验证和计划；没有真实import/export/host call。
  所以DL-R01应接现有Codex真实宿主队列，不重复让DeepSeek写第二套Penpot骨架。
- DL-R00与D01合入已有Requirement/DesignIR/环境盘点；先查.project/paths.json和LOCAL_ENVIRONMENT，别误判没安装。
- DL-R02+D04：补语义损失、原生源文件/交换文件/预览文件区别。PNG/MP4可以有价值，但不能替代约定的可编辑对象。
- DL-R01：写入前后验证目标file/page/object，跨tab焦点切换要拒绝或重新确认，副本中重开与恢复。
- D02/D03/D05：Flare/Sunburst模型对照测局部编辑、字形、真实alpha、非目标区域变动、比例/透视；
  原件与可编辑几何/文本由产品和宿主保留，不能让生成图像成为唯一尺寸真值。
- DL-R04+D06：Codex真实操作/原生重开证据与独立专业质量分别验收。
- DL-R03 Figma只在已有权益时可选；不新增订阅、不卡住Adobe第一条生产闭环。
- DSH只做结构、离线测试、素材清单与回归准备；实际Adobe/Penpot/GPU/质量交Codex和Human。
- 原生资产、客户Brief与试验输出留本项目；只按现有受审KnowledgeCandidate出口反馈ArcheAxis。


## 本项目全部原任务对账

|来源|原ID|原任务|合并主题|执行边界|
|---|---|---|---|---|
|research|DL-R00|确认 Design IR、宿主与原生资产边界|现状与资源确认|DeepSeek只读|
|research|DL-R01|Penpot 原生编辑与保存重开验证|Penpot原生往返|Codex真实宿主；Human质量|
|research|DL-R02|可编辑资产、生产预检与交换损失表|资产交换损失/预检|DeepSeek结构；Codex原生读回|
|research|DL-R03|Figma 与 Penpot 的可选对照|Figma可选对照|Codex真实宿主|
|research|DL-R04|真实工具执行与交付验收分离|真实交付验收|Codex与独立Human|
|models|D01|冻结参考与约束|冻结参考/要求|DeepSeek结构|
|models|D02|严格局部编辑|局部编辑|Codex图像工具；Human|
|models|D03|文字材质透明度|文字/材质/alpha|DeepSeek测试准备；Codex实测|
|models|D04|可编辑中间结构|可编辑中间结构|DeepSeek结构；Codex重开|
|models|D05|场景尺度与透视|场景尺度/透视|Codex实测；Human|
|models|D06|质量费用与回流|质量成本回流|Codex+Human；受控知识出口|

G00/G01/L01为共享准备工作，按各项目资源边界独立完成，不强制三个项目串行。任何结果都未被本次审计标为运行通过。
