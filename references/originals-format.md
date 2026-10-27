# 原文备份格式与维护

`references/originals/` 是随 skill 一同提交到 GitHub 的原文备份。它覆盖当前已收录记录，并不表示已穷尽这些用户的全站回复。

- `users/<UID>/<YYYY-MM>.jsonl`：UTF-8，每行一个完整 JSON 记录，同月内按发帖时间、PID 排序；保留原记录全部字段，仅去掉会随合并顺序变化的 `filtered_ordinal`。
- `manifest.json`：格式版本、用户记录数、时间范围、分片路径、字节数和 SHA-256 校验值。
- `coverage.json`：抓取时间、覆盖范围与已知缺口；不把不同时间抓取的作者说成同一次完整刷新。
- `revisions.jsonl`：原文发生变化时保留此前的完整记录及正文校验值；没有正文变更时不生成此文件。

主键为 `record_key`，普通回复为 `post:<TID>:<PID>:<UID>`；首楼 PID 为 0，不能只用 PID 去重。Excel 等历史导入保留其已有主键。

正文使用 `raw_bbcode`，此字段为了兼容旧版保留原名。`raw_format=html` 表示保存的是 HTML 页面内提取的正文片段；其他既有记录通常为 BBCode。不得把 HTML 片段声称为站点原始 BBCode。`plain_text` 仅用于检索与便于阅读，引用核对以原文字段及原帖链接为准。引用中的他人发言不是当前作者的独立观点。`source_lou` 是作者分页位置，不是全帖楼层。

## 检索与读取原文

```sh
python scripts/search_posts.py --uid 67142257 --limit 10
python scripts/search_posts.py --tid 47288722 --pid 885930013 --raw
python scripts/search_posts.py --uid 67142257 --since 2026-10-27 --json --limit 100
```

检索默认直接读取此备份；只有旧版本尚未建立备份时才回退到 `references/full-posts.jsonl`。

## 增量维护

正常运行 `update_thread.py` 后会自动把合并结果写入本备份：已有记录不会因本次未返回而消失；同一主键更新正文时保留旧版本。也可手工导入额外 JSONL：

```sh
python scripts/archive_store.py --import-jsonl references/full-posts.jsonl
python scripts/archive_store.py
python scripts/archive_store.py --export /path/to/all-posts.jsonl
```

无参数运行校验全部分片；`--export` 输出一份按时间排序、可迁移到其他工具的完整 JSONL。导入采用输入记录覆盖同主键旧记录，原文字段逐字保留，不再次做编码修复或摘要改写。重复导入相同数据不会增加记录或修改分片。

新同步先以本备份恢复已知记录，再合并本机来源文件。`full-posts.jsonl`、Markdown 和 TSV 仍可作为本地派生视图；未更新这些派生文件的 GitHub 副本不能替代此备份。原始分页缓存不入库。发布更新时提交 `originals/`、脚本和技能说明，不提交登录 Cookie、环境文件或本机绝对路径。
