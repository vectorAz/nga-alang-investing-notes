---
name: nga-alang-investing-notes
description: 检索、引用、更新和归纳 NGA 主题 47288722 中楼主“-阿狼-”(UID 150058)及重点用户 UID 60916468、67142257（兰斯洛t）、67145714、39700287、65329649 的发言，并累计追踪这些重点用户在已发现或手工登记的其他主题中的公开发言；同时保留旧主题 45974302 的阿狼历史资料。用于用户提到阿狼、狼大、新救赎版帖子、重点用户、科技股复盘、做 T、止盈止损、趋势波段、龙头风向标，或要求更新、核对、引用原话时。
---

# 阿狼及重点用户 NGA 资料库

## 检索

原文统一从随 skill 发布的 `references/originals/` 备份读取，先运行检索脚本，再按 PID、TID、UID 或日期用 `--raw`／`--json` 核对完整原文。不要仅凭检索预览引用，也不要优先读取可能陈旧的 `full-posts.jsonl` 派生副本。备份覆盖全部已收录用户与记录，不代表全站完整回复。

```powershell
python scripts/search_posts.py "关键词" --limit 30
python scripts/search_posts.py "关键词" --uid 60916468
python scripts/search_posts.py --uid 67145714 --since 2026-08-01
python scripts/search_posts.py --tid 47288722 --pid 877002447
python scripts/search_posts.py --tid 47288722 --pid 885930013 --raw
python scripts/search_posts.py --uid 67142257 --since 2026-10-27 --json --limit 100
```

备份按用户和月份保存为 UTF-8 JSONL，`manifest.json` 提供数量和 SHA-256 校验，`coverage.json` 记录抓取范围与缺口。格式、校验、增量导入与导出方法见 [原文备份格式与维护](references/originals-format.md)。原文字段保留为 `raw_bbcode`；`raw_format=html` 时实际为 HTML 页面提取的正文片段，不能声称是站点原始 BBCode。

区分以下身份：

- `tracking_role=op`：新主追踪帖楼主阿狼。
- `tracking_role=priority_user`：重点用户在主帖或已登记相关主题中的发言。
- `tracking_role=legacy_op`：旧主题 45974302 的阿狼历史发言。

引用时给出作者/UID、日期、TID、PID 和原帖链接。明确区分“作者原话”“引用上下文”和“基于资料的推演”，不要把归纳改写冒充原话。观点变化按时间顺序展示，较新的明确表述优先。

## 更新

完整同步主帖、重点用户及已登记相关主题：

```powershell
python scripts/update_thread.py
```

更新脚本会以原文备份恢复已有记录，合并本机来源后自动更新备份及派生索引。原文变化时保留旧版本；本次未返回的已知记录不会从备份删除。提交 GitHub 更新时一并提交 `references/originals/`；不要提交 Cookie 或原始分页缓存。可运行 `python scripts/archive_store.py` 校验全部分片。

若终端临时设置了 `NGA_COOKIE`，更新脚本会使用登录态入口检索全部重点用户的跨版面回复；遇到“系统繁忙”、频率限制或网络错误时最多退避重试 8 次。例如：

```text
https://bbs.nga.cn/thread.php?searchpost=1&authorid=60916468
https://bbs.nga.cn/thread.php?searchpost=1&authorid=67145714
https://bbs.nga.cn/thread.php?searchpost=1&authorid=39700287
https://bbs.nga.cn/thread.php?searchpost=1&authorid=65329649
```

默认检索最近 12 页（每页约 30 条），可调整窗口：

```powershell
python scripts/update_thread.py --discovery-pages 30
```

快速刷新每个来源最近十页，并补抓此前缺失的所有历史页；回退到旧缓存不算本次完整刷新：

```powershell
python scripts/update_thread.py --quick
```

核对六位已登记作者在主帖内的全部当前可见历史回复：

```powershell
python scripts/audit_primary.py --data-dir 本地技能目录 --out reports/YYYY-MM-DD
```

审计会重新抓取每位作者所有分页，检查页号、作者、PID 去重、时间排序以及分页到归档的对应关系，输出 `coverage.json` 和不含正文的 `timeline.csv`。`--cache-only` 只核对已有缓存，不等于联网重新验证。

- `visible_rows_verified=true` 只说明当前返回的可见回复都能在归档中找到，不代表曾存在过的每一次回复均可找回。
- `server_count_difference` 保留 NGA 报告总数与实际可见唯一 PID 数之间的差额，不擅自将其归因于删帖。
- 曾抓到、但本次不再返回的记录仍保留在本机来源文件中，并标记 `visibility_at_sync=not_returned`。
- `source_lou`／`author_ordinal` 为只看作者分页中的位置，不应当作全帖楼层号。

手工登记重点用户出现过的其他主题，并立即同步：

```powershell
python scripts/update_thread.py --add-thread 主题TID
python scripts/update_thread.py --add-thread-for 60916468:主题TID
```

配置位于 `references/tracking-config.json`。主追踪地址固定为 `https://bbs.nga.cn/read.php?tid=47288722`，楼主 UID 为 150058；重点 UID 为 60916468、67142257、67145714、39700287、65329649。更新后检查 `references/update-state.json`：

- `complete_for_registered_sources=true` 只表示已登记来源的公开“只看作者”页面抓取完整。
- `reply_search` 分别记录各重点用户的跨版面检索页数、结果行数、发现主题数、登录要求和错误。
- `cross_forum_complete` 通常为 `false`。`searchpost` 需要登录、可能限流且检索窗口有限，不得把累计主题覆盖说成全站穷尽。
- `errors` 非空时说明部分来源失败；回答时披露缺口。

脚本会尝试从公开用户主题接口发现新主题，并在存在 `NGA_COOKIE` 时使用 `searchpost=1` 发现重点用户回复过的主题，再通过主题“只看作者”接口补齐 PID、原始 BBCode、引用和附件。不得在技能文件、日志或回答中保存或回显 Cookie。即使有登录态，也不要声称全站回复已完整覆盖。

## 资料边界

“只看作者”通常覆盖主题内普通楼层，但楼中楼评论、已删除/不可见内容以及未被发现的跨主题回复可能缺失。重点用户在其他主题中的内容采用累计登记制：发现 TID 后使用 `--add-thread` 纳入后续手动更新。

涉及“今天、现在、最新行情”时，本资料库只作为历史观点来源；另行获取北京时间实时行情、公告和财务数据后再分析。输出资料归纳与情景分析，不承诺收益或把任何作者观点包装为确定性指令。
