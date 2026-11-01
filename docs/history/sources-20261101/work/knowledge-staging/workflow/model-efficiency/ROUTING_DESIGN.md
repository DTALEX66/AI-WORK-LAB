# 模型路由设计（WLR-400/410）

规则路由零模型调用: 隐私→D/视觉→C/复杂→B/日常→A + 预算降级。
实现: scripts/workflow/model_router.py + WorkUnit.create 集成。
行业: Nvidia NeMo Switchyard/LiteLLM/RouteLLM（借鉴不照搬）。
