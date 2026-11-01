# DESIGN-LAB 备份与恢复一致性修复 · 2026-10-08

范围只有一条:项目状态备份(`design-lab backup`)与恢复(`design-lab restore`)在真实断电、
并发写入、跨根迁移下会不会说谎。实现提交 `7ee682d9`、`701ace9c`。基线为实测 live main
`fc03a3033e900a8066d863a223636cc68804c4fa`。

接手时的关键事实与交接文档相反:本地检出 `1d18ae80` 相对 live main **0 ahead / 81 behind**,
交接点名的"必须先修的验收缺陷"(`test_workbench_css_single_definition.py` 阈值 50→47)在 main
上早已用正确语义修好(`37bd2622` 按 rendered rows 统计,下限仍为 50)。未提交增量按行比对后,
真正 main 上没有的是备份一致性、personal workbench e2e 与自动连接一批;前者本轮落地。

## 修掉的缺陷(每条都有复现读数)

1. **`state.db` 按文件字节归档。** WAL 下已提交行不在主文件里,复制即丢——正是 2026-10-06
   事故的新形态。改走 SQLite backup API,并且 `-wal/-shm` 不再单独归档(否则恢复出"新库配旧日志")。
   证据:`test_wal_commits_are_in_the_database_snapshot` 连接不关、WAL 有帧时归档再恢复,行仍在。
2. **路径含 `#` 时读到假版本号。** `f'file:{path}?mode=ro'` 把 `#` 当 URI fragment。本机实测:
   真实 `user_version=7` 被判成 `0`。这个数字正是兼容性恢复门的判据,所以它是"错着通过",不是失败。
3. **归档可枚举到自己。** 先前开 zip 再枚举成员,写到成员目录下即自包含。现在两侧都拒绝,
   且半成品 zip 绝不落地(`test_unsnapshottable_database_produces_no_archive`)。
4. **恢复直接写目标。** 中途失败留下半替换状态。现在暂存→校验→在暂存态重定位 artifact 索引→
   逐项 `os.replace`,任何异常按安装逆序回退旧字节。
5. **反斜杠成员名。** `PurePosixPath` 不把 `\` 当分隔符,`projects\..\..\escaped.txt` 是**一个不含
   `..` 的部分**,join 后实测解析到目标根之外。main 之所以没逃逸,靠的是 Python zipfile 存名时
   把分隔符改写这个巧合,不是守门。现在按原始字符串拒绝,并同时断言守门与汇点形状。

## 屏障:备份不再是免责声明(提交 701ace9c)

* 采集前读 `asset_writer_lock` / `asset_publication` / `native_host_guard_v1` / `attempt_state`,
  任何活着的写入直接拒绝并点名。
* 采集后再读一次,并比较单调计数器。**这一步是必需的**:一次发布若完整发生在窗口之内,两次读
  的活动集合都为空,集合差会判"一致",而字节已经动了。
* 证明(或"无法观测")写进归档 manifest;恢复回执原样转述,不会把 `WRITES_NOT_OBSERVABLE`
  升级成声明。无库的根报 `NO_STATE_DATABASE`。
* 恢复时对每条 artifact 行按摘要重验归档字节——这才是把索引和文件绑在一起的断言。无摘要的行
  与只有相对路径的行计入 `artifactsUnverifiable`,不算通过。

### 两处只有证伪才能抓到的自误

* 屏障第一版在 SQL 里比较 `expires_at > <ISO 字符串>`。`asset_writer_lock.expires_at` 存的是
  unix float(SQLite REAL),而 SQLite 的类型排序里 **数字恒小于文本**,于是每个活租约都被当成已过期,
  忙碌的根会被判成静默。现在直接复用产品自己的 `_lease_live` / `_expiration`,顺带保留
  `acquire_writer` 认的"legacy HELD 无过期时间也算占用"规则。
* 我原先以为 `publish_version` 会释放写租约(其实是调用方 `finally` 里 release,见
  `image_assets.py:131`)。因此 PREPARED 日志那条测试会被租约先挡住,门根本没被走到。修后的测试
  显式释放租约,并断言"恰好一条半成发布"。

九条门全部对**削弱后的产品代码副本**重跑并各自因预期原因变红,工装见
`.project-local/tmp/falsify_backup_gates.py`(要求匹配失败原因,不接受任何红)。
`test_project_backup.py` 37 用例通过,1 条 skip:`WinError 1314` 建符号链接缺特权,按策略不提权。

## 仍未闭合(不在本轮范围内假装完成)

* `asset_publication` 恢复日志的绝对路径跨根后仍指旧根;`recover_publications(store_root=新根)`
  用 `WHERE store_root=?` 选取,查不到旧行即静默跳过 PREPARED 日志,既不恢复也不报错。按 owner
  既有裁决"只重定位 live `artifact.path`、签名执行记录不改",这条留作已知边界。
* 不写状态库的写入者(直接改文件的外部进程)对屏障不可见,归档里 `tablesObserved` 就是这一事实的自陈。
* DB 快照与文件字节的一致性由屏障保证;**断电事务级**的跨文件原子发布(R5-005 完整交付清单)与真实宿主
  读回(E3)、人工 Jury(E4)、发布(E5)未做,相应轴不升级。
* `verify_evidence_artifact_presence` 的门只校验 `evidence[].artifacts`,不校验 `subject_files`。也就是说
  一条只绑源码摘要的证据记录即便源码漂移也不会红——本轮新增的证据记录正是用 `subject_files` 绑定的,
  这个盲区记在此处,不当已修。
