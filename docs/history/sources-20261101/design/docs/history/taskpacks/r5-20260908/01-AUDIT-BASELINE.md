# 审计基线与纠正

审计：2026-09-08；这是本次云端和本地代码核验摘要，不是新一轮Windows实机验收。

开发分支比main领先18提交，无开放PR；其最新CI成功：[34155003375](https://github.com/DTALEX66/DESIGN-LAB/actions/runs/34155003375)。[固定源码](https://github.com/DTALEX66/DESIGN-LAB/tree/ed8d45ab2857b312f6056c43f7bb5e19dd9b65eb)。main仍为c4dccd5，不能用main的旧缺陷推断开发分支全无成果。

已确认前端项目/图片导入/任务事件/原生资产校验实现；Python wheel与CLI已配置；Adobe COM和RIR转换存在；Operation/Attempt/资产事务有新代码和测试。仓库受控宿主报告包含原生工程hash，但原始AI/PSD仍在本机ignored目录，云端本轮未独立核验其文件字节。

本轮针对测试：runtime safety 41项、HTTP19项、NativeTasks12项、Operation8项，总计80项通过。报告check因本环境缺jsonschema未完成；不是报告逻辑已证实失败。没有全量回归、没有本轮Windows宿主测试。

剩余：前端原生提交/patch/取消/导出，未知宿主结果恢复，安装后的完整RIR入口，Comfy生产回执，活跃.hermes策略残留，同项目UI异步竞态。当前正式投影仍NOT_RELEASED。

R4.1纠正：UIA与Comfy不作Adobe硬前置；完整验收进入机器任务定义；Premiere的语音/音乐依赖按案例明确；不将新任务状态当旧成果归零。

软件事实以开发分支LOCAL_ENVIRONMENT为接续依据：用户确认ComfyUI、AI、PS、H3和MiniMax Design存在；存在性不等于已加载推理或完整验收。禁止重用旧盘点宣称未安装，也不凭时区判断许可地区。

历史完整性只能按已知来源逐条locator/hash验证；当前对话、附件和仓库历史不能自动代表所有历史聊天已完整恢复。DL-R5-023保留缺失与恢复任务。
