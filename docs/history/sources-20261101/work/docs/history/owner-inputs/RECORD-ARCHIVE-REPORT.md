# Record 完整归档、去重与整理交付记录

状态：PASS（资料归档与定位范围）。用户明确要求本项目资料完整归档、索引登记、去重，以及允许旧资料合并压缩/提取关键内容。
当前UI任务仍是唯一CURRENT。本次没有开始产品实现，不创建第二任务账本，不执行任何原包命令。

## 覆盖与归属

源目录：D:/All projects/Record，只读，未移动、删除或改写源文件。
本次180个文件均有登记：47个相关源文件、133个其他项目/系统独立文件明确排除，未决归属0。
名称明确属于WORK-LAB的17个顶层文件全部完整覆盖，包括上一轮未找到完整副本的8个原件。
通用名称文件按正文确认归属：旧总控入口、旧TASKPACK/START/TASKS、研究候选、UI套件审计、组件吸收计划、共享规划和工作簿均纳入。
独立AAOS/DESIGN-LAB任务、构建历史、系统审计与他方图片只登记路径/大小/理由，不读其历史库正文、不收存到本仓。

三项目VI/UI/UX混合包134文件全部有成员去向：39个WORK-LAB独立成员+17个共享品牌/字体/许可证/展示溯源成员完整保存，78个他方独立成员明确排除。
混合ZIP原件在Record保持原位，登记原ZIP摘要；本方相关成员逐个原字节归档，不冒称整个三项目ZIP已搬入本仓。
十案例作品集收存本方3张图片及9个必要共享代码/文案/溯源文件，其他案例独立图片排除。
总计102条资料来源及选定成员、1951条压缩包成员（包含嵌套）可检索。归档原件不是产品运行/设计交付验收。

## 去重、合并和关键内容

先按源摘要复用14份已有归档。新增收回资料中，9份与冻结原件或Atlas内原件完全相同，校验规范副本后去除新建的冗余裸文件，保留全部源名/版本/成员链别名；避免重复存储515516字节。
同名不同内容不合并；相同内容按SHA-256内容身份分组。索引默认相同摘要显示一条，可切换查看全部来源位置。
不可变来源ZIP中的重复成员保留原字节，不拆改原件来追求表面的文件数；已受引用的冻结快照也未删除。

36份本轮收回的历史文件无损合并为record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip：
原文件合计6630338字节，合并容器6101120字节（含内置ARCHIVE-MANIFEST.json），36个原件逐成员字节一致。
历史ZIP以完整嵌套原件保存，原ZIP摘要仍可核验；旧文档及包内AGENTS/Authority不激活。
HISTORICAL-KEY-POINTS.md按原生客户端、读写边界、通用执行、Atlas缺口、桌面验证、Radar、价格、UI及三项目归属提取交集和当前处理方式。
摘要只是阅读入口；完整原件和不同版本均保留，可按资料ID提取。

## 定位与维护

固定入口：docs/history/owner-inputs/INDEX.md，已接入仓库README、AGENTS、DOCUMENT-CENSUS、active-authority-index、顶层机器索引及下一Agent交接提示词。
资料登记唯一源为RECORD-ARCHIVE-REGISTER.json，成员登记为RECORD-ARCHIVE-MEMBERS.jsonl；CSV、Markdown、HTML是可再生视图。
scripts/maintenance/owner_material_catalog.py提供find / extract / verify / build-index；默认查登记，不再盲扫Record或私人会话。
extract只写.project-local/artifacts并校验摘要，拒绝越界和覆盖不同内容。HTML目录无外部依赖或远程上传，支持全文元数据搜索、分类关键字、摘要去重视图。
新增资料先核对已存内容、登记来源别名/新版本及成员，再再生视图、执行verify；原件写入仍按项目批准的recover_shared_root_original.py路径与artifact-flow边界。

## 验证与未执行项

完整仓内文件/成员、原Record相关源文件/混合包摘要、资料去向覆盖和目录盘点读回：PASS，结果见RECORD-ARCHIVE-VALIDATION.json。
补充定向校验和运行演示记录见RECORD-NAVIGATION-VALIDATION.json。
暂存前的3个无关dirty源码保护；本轮仅修改归档、定位工具和必要索引，不安装、不碰全局配置、不上传、不commit/push/merge。
完整产品质量门、本机桌面/UI runtime、真实采集与跨项目协作均NOT_EXECUTED；没有将资料校验写成产品完成。
Record之外的云端附件、完整历史长对话、私人native session不在本次归档范围，未宣称恢复。

## 恢复

通过资料ID定位并提取原字节；用SHA-256核验，不依赖旧的裸文件存储路径。
去重和合并前后路径分别见RECORD-DEDUPLICATION.json及RECORD-CONSOLIDATION.json，最终规范位置以资料登记为准。
Record原件仍完整存在；当前归档不改变旧资料内容。不要批量reset/clean或覆盖后续用户修改。

## 最终现场复核补充（2026-10-09）

复用本检出已有归档并对当前Record重新只读核对，不以历史PASS代替当前验证。当前180个源文件均有去向：47个相关源文件、133个他方文件；混合包56个相关成员完整收存，未决归属0。相关原件和仓内归档SHA-256/大小读回一致，源目录未修改。

重新运行build-index生成2053条可搜索位置；115条Markdown本地链接、2053条目录文件链接、资料及成员CSV一致性通过。生成目录的实际JavaScript用最小DOM验证7组查询与两种去重视图，包括多词/空白/别名/资料ID/无命中；按ID提取嵌套原件后摘要一致，越出artifacts的提取被拒绝。真实浏览器视觉渲染未执行。

最终内容分组为1299个摘要，550组有多个来源位置；此前1298/514是合并前快照，不能混作当前统计。原件包内重复仍保留字节，分组只解决定位和新入库重复存储。

当前权威、三方边界、蓝图及投影新鲜度检查通过；46个引用检查面、448个引用无断链，67个定向回归通过且无skip。当前交接另核对两包354个manifest项、35个可读镜像、38个冻结文件、186条旧行与21个新任务。验证汇总保存在RECORD-ARCHIVE-VALIDATION.json的handoffReview中，详细现场日志在项目内.project-local/artifacts/ui-priority-handoff-review-20261009。

上述PASS只覆盖文档归档与交接。产品实现、桌面运行、安装、发布和commit/push/merge未执行；exact-SHA CI未核验。原有3个无关dirty文件的摘要保持不变。
