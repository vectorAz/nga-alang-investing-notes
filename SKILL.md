---
name: nga-alang-investing-notes
description: 检索、引用和归纳 NGA 主题 45974302 中楼主“-阿狼-”(UID 150058) 的完整主楼与回帖、原始 BBCode、编辑记录、引用、链接和附件，并按其公开表达的复盘框架、仓位纪律、趋势与科技投资逻辑回答问题。用于用户提到阿狼、狼大、该 NGA 帖、科技股复盘、做 T、止盈止损、趋势波段、龙头风向标，或要求更新、核对、引用楼主原话时。
---

# 阿狼 NGA 帖知识库

## 使用原则

1. 先检索 `references/posts-index.tsv`，再按 PID、日期或关键词读取 `references/full-posts.jsonl` 或 `references/full-posts.md`。
2. 区分三类内容：
   - “楼主原话”：`authorid=150058` 的主楼和回帖。
   - “引用上下文”：楼主正文中的 quote/reply BBCode。
   - “相关内容”：楼主帖子附带的评论、热评、链接、图片和附件元数据。
3. 引用观点时给出日期、PID 和原帖直链。不要把归纳改写冒充原话。
4. 遇到同一观点前后变化时，按时间顺序展示，优先采用较新的明确表述，并说明变化。
5. 对投资问题输出“资料归纳/情景分析”，不得承诺收益或把楼主观点包装成确定性指令。提醒用户结合实时行情、财务数据与自身风险承受能力独立判断。
6. 涉及“现在、今天、最新行情”时，本知识库只提供历史观点；另行获取实时数据后再分析。

## 检索方法

优先运行：

```powershell
python scripts/search_posts.py "关键词"
python scripts/search_posts.py "关键词" --since 2026-05-01 --limit 30
python scripts/search_posts.py --pid 867926538
```

也可使用 `rg -n "关键词" references/posts-index.tsv references/full-posts.jsonl`。

需要逐字核对时，读取 JSONL 中的 `raw_bbcode`；需要快速理解时，读取 `plain_text`。附件 URL 位于 `attachments`，正文图片位于 `images`。

## 回答结构

按问题复杂度选用最小必要结构：

- 结论：用一两句话概括楼主在相关时期的观点。
- 依据：列出相关发言的日期、PID、原帖链接与短摘录。
- 演变：若观点发生变化，按时间说明。
- 应用：明确哪些是楼主的方法，哪些是基于用户当前信息的推演。
- 风险：说明失效条件、信息时效和非投资建议属性。

不得仅凭印象回答；找不到直接依据时明确说“知识库中未检索到楼主对此作出直接表述”。

## 手动更新

执行完整同步（会刷新所有“只看楼主”页面，以捕捉旧帖编辑）：

```powershell
python scripts/update_thread.py
```

快速同步最近页面：

```powershell
python scripts/update_thread.py --quick
```

更新完成后检查 `references/update-state.json`。若 `complete` 不是 `true`，不得声称资料已经完整更新。`unavailable_or_deleted_rows` 表示论坛计数中存在、但接口没有返回正文的删除或不可见记录。

## 数据范围

数据源为：

`https://bbs.nga.cn/read.php?tid=45974302&authorid=150058&__output=11`

本地资料覆盖楼主的主楼与普通回帖，以及这些记录随接口返回的评论、热评、编辑信息、链接和附件。NGA 的贴条评论存放在被评论楼层的 `comment` 字段；若楼主在他人楼层下发布贴条，而该楼层不出现在“只看楼主”结果中，公开接口无法仅凭作者筛选完整枚举，回答时不要把此类贴条纳入“已穷尽”的保证。
