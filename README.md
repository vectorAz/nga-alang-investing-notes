# NGA 狼楼追踪与历史完整性检查

追踪主帖 `47288722` 的六位作者：阿狼（150058）、兰斯洛t（67142257）、灰兔尾（60916468）、P（67145714）、39700287、65329649。旧主题资料单独保留，不混入本次主帖检查。

## 安装与运行

需要 Python 3.10 或更新版本：

```sh
python -m pip install -r requirements.txt
python scripts/update_thread.py --quick
```

快速模式刷新每个来源首尾页并补齐所有缺失历史页。完整模式不加 `--quick`，会刷新配置中的全部登记来源，可能包括不可访问的跨主题来源。

## 只核对主帖六位作者

```sh
python scripts/audit_primary.py --data-dir /path/to/local/skill --out reports/YYYY-MM-DD
```

此命令全量刷新主帖的作者分页，输出：

- `coverage.json`：每位作者的页数、可见唯一回复数、时间范围、异常和站点报告总数差额。
- `timeline.csv`：按时间排序的每条可见回复 UID、PID、时间、作者分页位置和原帖链接，不含论坛正文。

`references/originals/` 随 skill 发布全部已收录原文，按 UID 与月份分片保存为 UTF-8 JSONL，附带数量、SHA-256 校验和覆盖范围。后续检索默认直接从此备份读取；来源缓存及旧合并视图仍保留兼容用途。详见 [原文备份格式与维护](references/originals-format.md)。

```sh
python scripts/search_posts.py --uid 67142257 --limit 10
python scripts/search_posts.py --tid 47288722 --pid 885930013 --raw
python scripts/archive_store.py
python scripts/archive_store.py --export /path/to/all-posts.jsonl
```

更新脚本自动增量维护此备份，同一主键的原文变化会保留旧版本。GitHub 提交包含原文备份；原始分页响应、登录态和本机路径不提交。2026-10-27 的备份初始收录六位作者 11,255 条记录；作者抓取时间不一致，兰斯洛t 的主帖记录更新至当天 16:01，分页推算数与实际解析记录相差 4 条。

`reports/2026-10-27/` 是本次检查结果。`visible_rows_verified` 表示全部被检查页面实际返回的回复都已落入本机归档；删除、隐藏、楼中楼评论、未被发现的跨主题回复无法据此证明完整。若站点总数与返回数不同，差额会明确记录，不能直接写成“已删除”。

曾抓到但本次已不再返回的记录会保留并标记 `not_returned`，不会因刷新覆盖而丢失。作者分页中的位置不是原主题的全帖楼层号。

## 检查脚本

```sh
python -m unittest discover -s scripts -p test_history_sync.py
```

这些检查使用合成数据覆盖缺历史页、旧缓存回退、失效多余页、原记录保留、页号错误及归档缺记录，不需要联网。
