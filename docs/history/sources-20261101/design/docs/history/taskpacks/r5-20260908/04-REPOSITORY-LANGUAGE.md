# 仓库规范与语言治理

## 语言选择与迁移边界

Python：本地服务、状态事务、图像/模型适配、RIR转换和宿主调度。TypeScript：独立工作台和API类型。Adobe JavaScript/JSX：宿主内原生操作。Shell/PowerShell只做薄启动器。采用此组合是基于现有已实现资产与最快交付的项目决策；不要求为统一语言重写成熟组件。

当前main.ts使用浏览器可执行语法子集，不等于strict TypeScript已验收。DL-R5-028需补类型检查、API结构类型、静态资源产物策略；若引入构建，锁定依赖并在wheel包含构建产物。若仍直接服务源文件，明确无转译约束并验证实际浏览器兼容。

迁移顺序：代码与语言清单→ADR与目录归属→必要RIR门面进入src/design_lab→资源随wheel→旧import/CLI兼容→调用方迁移→无引用且回归通过后退役旧入口。每一步可独立回退；不复制两套算法长期双维护。Rust/C#/Avalonia需明确性能或系统集成瓶颈及基准后另行决策，不设为M1条件。

## 目录与数据

- src/design_lab：安装产品源码；apps/workbench：前端源；integrations：宿主/外部适配；packages/capabilities：待逐步收敛的领域能力；docs：决策与历史；reports/current：生成投影。
- .project/paths.json为当前路径配置入口；.project-local为项目运行与证据根。按实际配置区分临时数据、持久作品、模型输入和工具链，不把文档中的新路径自动当搬迁授权。
- 模型权重、会话、凭据、生成作品、数据库不提交Git。小型测试fixture须明确来源和用途。
- 清理先清单/hash/备份/调用方验证，再迁移或退役；不递归删除未知旧资料，不在历史文档中全局替换路径以伪造历史。
- .gitignore只防提交污染，路径解析和进程写入证据才验证实际边界。重点修复EXTERNAL_ASSET_INTAKE.md残留.hermes活跃规则。

## 验收

DL-R5-002负责目录与运行写入；DL-R5-003负责CI与环境；DL-R5-009负责可安装门面；DL-R5-028负责语言类型治理；DL-R5-023负责历史完整性。不得用“规范文档已写”作为以上五项完成。
