---
name: nga-alang-investing-notes
description: 检索、引用和归纳 NGA 用户“-阿狼-”(UID 150058，常被称为狼大、阿狼) 的历史公开回复归档、NGA 主题 45974302 主楼与回帖，以及其复盘框架、仓位纪律、趋势波段、龙头风向标、科技股、AI、半导体、贵金属、大宗商品和宏观流动性观点。用于用户提到阿狼、狼大、狼的理论、NGA 帖、科技股复盘、做 T、止盈止损、趋势波段、龙头风向标、黄金/白银/铜/原油、泡沫、放水，或要求核对、引用、更新楼主原话时。
---

# 阿狼 NGA 历史回复知识库

## 使用原则

1. 先检索 `references/posts-index.tsv`，再按日期、关键词、PID 或 `archive_id` 读取 `references/full-posts.jsonl` 或 `references/full-posts.md`。
2. 区分来源：
   - `source=excel_archive`：来自用户提供的 Excel 历史回复汇总，覆盖 2016-2017、2020、2022、2025、2026 和 2026-06-26 前后一周；这类记录通常没有 NGA PID 和直链。
   - 旧 `raw-pages/`：此前从 NGA 主题 45974302 接口同步的原始页留档，可用于需要核对当前主题接口结构时参考。
3. 引用观点时给出日期和记录标识。若记录有 PID，用 PID 和原帖链接；若来自 Excel，用 `archive_id`、sheet 名和行号。
4. 不要把归纳改写冒充原话。直接引用时只引用必要短句，其余用概述。
5. 遇到同一观点前后变化时，按时间顺序展示，优先采用较新的明确表达，并说明变化。
6. 投资相关回答应输出“资料归纳 + 情景分析”，不得承诺收益，且要提醒用户结合实时行情、财务数据和自身风险承受能力独立判断。
7. 涉及“现在、今天、最新行情”时，本知识库只提供历史观点；必须另行获取实时行情后再分析。

## 检索方法

优先运行：

```powershell
python scripts/search_posts.py "关键词"
python scripts/search_posts.py "关键词" --since 2026-05-01 --limit 30
python scripts/search_posts.py --archive-id xlsx-2026-00042
python scripts/search_posts.py --pid 867926538
```

若本机没有 Python，可直接使用：

```powershell
rg -n "关键词" references/posts-index.tsv references/full-posts.jsonl
```

需要逐字核对时读取 JSONL 中的 `raw_bbcode`；需要快速理解时读取 `plain_text`。Excel 归档记录的 `source_workbook`、`source_sheet`、`source_row` 字段可定位原始表格位置。

## 回答结构

按问题复杂度使用最小必要结构：

- 结论：用一两句话概括阿狼在相关时期的观点。
- 依据：列出相关发言的日期、PID 或 `archive_id`、来源位置与短摘录。
- 演变：若观点发生变化，按时间说明。
- 应用：明确哪些是楼主的方法，哪些是基于用户当前信息的推演。
- 风险：说明失效条件、信息时效和非投资建议属性。

不得仅凭印象回答；找不到直接依据时明确说“知识库中未检索到阿狼对此作出直接表述”。

## 数据范围

主数据文件由 `狼大回复汇总+20260626-1410&往期.xlsx` 重建，包含 25,160 条去重后的历史回复。Excel 归档不保证每条都有 NGA PID、楼层或原帖直链，因此引用时优先使用日期与 `archive_id`。

此前 NGA 主题同步来源为：

`https://bbs.nga.cn/read.php?tid=45974302&authorid=150058&__output=11`

旧接口同步产物保留在 `references/raw-pages/`，但主检索以 Excel 归档重建后的 `references/full-posts.jsonl` 为准。
