---
name: nga-alang-investing-notes
description: 检索、引用、更新和归纳 NGA 主题 47288722 中楼主“-阿狼-”(UID 150058)及重点用户 UID 60916468、67145714、39700287、65329649 的发言，并累计追踪这些重点用户在已发现或手工登记的其他主题中的公开发言；同时保留旧主题 45974302 的阿狼历史资料。用于用户提到阿狼、狼大、新救赎版帖子、重点用户、科技股复盘、做 T、止盈止损、趋势波段、龙头风向标，或要求更新、核对、引用原话时。
---

# 阿狼及重点用户 NGA 资料库

## 检索

先运行检索脚本，再按 PID、TID、UID 或日期读取 `references/full-posts.jsonl` 中的 `raw_bbcode` 核对原文。

```powershell
python scripts/search_posts.py "关键词" --limit 30
python scripts/search_posts.py "关键词" --uid 60916468
python scripts/search_posts.py --uid 67145714 --since 2026-08-01
python scripts/search_posts.py --tid 47288722 --pid 877002447
```

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

快速刷新每个来源最近十页；只有缓存页齐全时该来源才会标记完整：

```powershell
python scripts/update_thread.py --quick
```

手工登记重点用户出现过的其他主题，并立即同步：

```powershell
python scripts/update_thread.py --add-thread 主题TID
python scripts/update_thread.py --add-thread-for 60916468:主题TID
```

配置位于 `references/tracking-config.json`。主追踪地址固定为 `https://bbs.nga.cn/read.php?tid=47288722`，楼主 UID 为 150058；重点 UID 为 60916468、67145714、39700287、65329649。更新后检查 `references/update-state.json`：

- `complete_for_registered_sources=true` 只表示已登记来源的公开“只看作者”页面抓取完整。
- `reply_search` 分别记录各重点用户的跨版面检索页数、结果行数、发现主题数、登录要求和错误。
- `cross_forum_complete` 通常为 `false`。`searchpost` 需要登录、可能限流且检索窗口有限，不得把累计主题覆盖说成全站穷尽。
- `errors` 非空时说明部分来源失败；回答时披露缺口。

脚本会尝试从公开用户主题接口发现新主题，并在存在 `NGA_COOKIE` 时使用 `searchpost=1` 发现重点用户回复过的主题，再通过主题“只看作者”接口补齐 PID、原始 BBCode、引用和附件。不得在技能文件、日志或回答中保存或回显 Cookie。即使有登录态，也不要声称全站回复已完整覆盖。

## 资料边界

“只看作者”通常覆盖主题内普通楼层，但楼中楼评论、已删除/不可见内容以及未被发现的跨主题回复可能缺失。重点用户在其他主题中的内容采用累计登记制：发现 TID 后使用 `--add-thread` 纳入后续手动更新。

涉及“今天、现在、最新行情”时，本资料库只作为历史观点来源；另行获取北京时间实时行情、公告和财务数据后再分析。输出资料归纳与情景分析，不承诺收益或把任何作者观点包装为确定性指令。
