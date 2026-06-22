#!/usr/bin/env python3
"""Synchronize all OP posts from NGA thread 45974302."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import html
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TID = 45974302
AUTHOR_ID = 150058
PAGE_SIZE = 20
BASE = "https://bbs.nga.cn/read.php"
UA = "Nga_Official/90032"
ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "references"
CACHE = REFS / "raw-pages"


def fetch_page(page: int, attempts: int = 5) -> dict:
    params = urllib.parse.urlencode(
        {"tid": TID, "authorid": AUTHOR_ID, "page": page, "__output": 11}
    )
    req = urllib.request.Request(f"{BASE}?{params}", headers={"User-Agent": UA})
    last_error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = response.read().decode("utf-8")
            data = json.loads(payload)
            if "data" not in data:
                raise ValueError(f"page {page}: response has no data")
            return data
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(min(8, 1.5**attempt))
    raise RuntimeError(f"page {page} failed after {attempts} attempts: {last_error}")


def rows_from(data: dict) -> list[dict]:
    rows = data.get("data", {}).get("__R", [])
    if isinstance(rows, dict):
        rows = list(rows.values())
    return [row for row in rows if isinstance(row, dict)]


def strip_bbcode(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"\[img\](.*?)\[/img\]", r"[图片: \1]", text, flags=re.I | re.S)
    text = re.sub(r"\[url=([^\]]+)\](.*?)\[/url\]", r"\2 (\1)", text, flags=re.I | re.S)
    text = re.sub(r"\[url\](.*?)\[/url\]", r"\1", text, flags=re.I | re.S)
    text = re.sub(r"\[(?:/?(?:b|i|u|s|quote|collapse|color|size|font|align)|"
                  r"reply|tid|pid|uid)[^\]]*\]", "", text, flags=re.I)
    text = re.sub(r"\[s:[^\]]+\]", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def absolute_attachment(path: str) -> str:
    path = (path or "").lstrip("./")
    return f"https://img.nga.178.com/attachments/{path}"


def collect_urls(raw: str, row: dict) -> tuple[list[str], list[str], list[dict]]:
    links = re.findall(r"\[url(?:=([^\]]+))?\](.*?)\[/url\]", raw, flags=re.I | re.S)
    link_urls = [a or strip_bbcode(b) for a, b in links]
    link_urls += re.findall(r"https?://[^\s\[\]<]+", raw)
    image_paths = re.findall(r"\[img\](.*?)\[/img\]", raw, flags=re.I | re.S)
    images = [absolute_attachment(p) if not p.startswith("http") else p for p in image_paths]
    attachments = []
    for item in row.get("attachs") or []:
        if not isinstance(item, dict):
            continue
        copy = dict(item)
        copy["url"] = absolute_attachment(item.get("attachurl") or item.get("name") or "")
        attachments.append(copy)
        if item.get("type") == "img":
            images.append(copy["url"])
    return sorted(set(link_urls)), sorted(set(images)), attachments


def normalize(row: dict, filtered_ordinal: int) -> dict:
    raw = row.get("content") or ""
    links, images, attachments = collect_urls(raw, row)
    pid = int(row.get("pid") or 0)
    comments = row.get("comment") or []
    hotreply = row.get("hotreply") or []
    return {
        "tid": TID,
        "pid": pid,
        "authorid": int(row.get("authorid") or 0),
        "author": "-阿狼-",
        "filtered_ordinal": filtered_ordinal,
        "source_lou": row.get("lou"),
        "postdate": row.get("postdate"),
        "postdatetimestamp": row.get("postdatetimestamp"),
        "subject": row.get("subject") or "",
        "raw_bbcode": raw,
        "plain_text": strip_bbcode(raw),
        "alterinfo": row.get("alterinfo") or "",
        "content_length": row.get("content_length"),
        "score": row.get("score"),
        "links": links,
        "images": images,
        "attachments": attachments,
        "comments": comments,
        "hotreply": hotreply,
        "source_url": (
            f"https://bbs.nga.cn/read.php?tid={TID}"
            if pid == 0
            else f"https://bbs.nga.cn/read.php?pid={pid}&opt=128"
        ),
    }


def write_outputs(posts: list[dict], meta: dict, fetched_pages: list[int], total_pages: int) -> None:
    REFS.mkdir(parents=True, exist_ok=True)
    jsonl_path = REFS / "full-posts.jsonl"
    md_path = REFS / "full-posts.md"
    index_path = REFS / "posts-index.tsv"

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as f:
        for post in posts:
            f.write(json.dumps(post, ensure_ascii=False, separators=(",", ":")) + "\n")

    with index_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("ordinal\tpostdate\tpid\tcontent_length\tsource_url\tpreview\n")
        for post in posts:
            preview = re.sub(r"\s+", " ", post["plain_text"])[:240].replace("\t", " ")
            f.write(
                f'{post["filtered_ordinal"]}\t{post["postdate"]}\t{post["pid"]}\t'
                f'{post["content_length"]}\t{post["source_url"]}\t{preview}\n'
            )

    with md_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {meta.get('subject', 'NGA 楼主完整发言')}\n\n")
        f.write(f"- 主题：{TID}\n- 楼主：-阿狼-（UID {AUTHOR_ID}）\n")
        f.write(f"- 同步条数：{len(posts)}\n- 同步时间：{dt.datetime.now().astimezone().isoformat()}\n\n")
        for post in posts:
            f.write(
                f'## #{post["filtered_ordinal"]} · {post["postdate"]} · PID {post["pid"]}\n\n'
                f'[原帖]({post["source_url"]})\n\n{post["plain_text"]}\n\n'
            )
            if post["images"]:
                f.write("图片：\n\n")
                for url in post["images"]:
                    f.write(f"- {url}\n")
                f.write("\n")
            if post["alterinfo"]:
                f.write(f'编辑/管理记录：`{post["alterinfo"]}`\n\n')

    reported_rows = int(meta.get("this_visit_rows") or 0)
    all_pages_present = fetched_pages == list(range(1, total_pages + 1))
    state = {
        "tid": TID,
        "authorid": AUTHOR_ID,
        "subject": meta.get("subject"),
        "thread_replies": meta.get("replies"),
        "filtered_rows_reported": reported_rows,
        "posts_written": len(posts),
        "unavailable_or_deleted_rows": max(0, reported_rows - len(posts)),
        "total_pages": total_pages,
        "pages_fetched": fetched_pages,
        "complete": all_pages_present,
        "updated_at": dt.datetime.now().astimezone().isoformat(),
        "source": f"{BASE}?tid={TID}&authorid={AUTHOR_ID}&__output=11",
    }
    (REFS / "thread-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (REFS / "update-state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="refresh only the latest 10 pages")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    REFS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    first = fetch_page(1)
    first_data = first["data"]
    meta = first_data.get("__T", {})
    total_rows = int(first_data.get("__ROWS") or meta.get("this_visit_rows") or 0)
    total_pages = max(1, math.ceil(total_rows / PAGE_SIZE))

    if args.quick:
        page_numbers = sorted(set([1] + list(range(max(1, total_pages - 9), total_pages + 1))))
    else:
        page_numbers = list(range(1, total_pages + 1))

    results = {1: first}
    remaining = [p for p in page_numbers if p != 1]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(fetch_page, page): page for page in remaining}
        for future in concurrent.futures.as_completed(futures):
            page = futures[future]
            results[page] = future.result()
            print(f"fetched {page}/{total_pages}", file=sys.stderr)

    for page, payload in results.items():
        (CACHE / f"page-{page:04d}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    if args.quick:
        for path in CACHE.glob("page-*.json"):
            page = int(path.stem.split("-")[-1])
            if page not in results:
                results[page] = json.loads(path.read_text(encoding="utf-8"))

    available_pages = sorted(results)
    posts = []
    ordinal = 0
    seen = set()
    for page in available_pages:
        for row in rows_from(results[page]):
            if int(row.get("authorid") or 0) != AUTHOR_ID:
                continue
            key = int(row.get("pid") or 0)
            if key in seen:
                continue
            seen.add(key)
            posts.append(normalize(row, ordinal))
            ordinal += 1

    posts.sort(key=lambda p: (int(p.get("postdatetimestamp") or 0), int(p["pid"])))
    for index, post in enumerate(posts):
        post["filtered_ordinal"] = index
    write_outputs(posts, meta, available_pages, total_pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
