#!/usr/bin/env python3
"""Synchronize the configured NGA thread and priority users."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import html
import json
import math
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

PAGE_SIZE = 20
BASE = "https://bbs.nga.cn"
UA = "Nga_Official/90032"
ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "references"
CONFIG_PATH = REFS / "tracking-config.json"
SOURCES = REFS / "sources"
CACHE = REFS / "raw-pages-v2"
LEGACY = REFS / "legacy"

DEFAULT_CONFIG = {
    "primary_thread": {"tid": 47288722, "op_uid": 150058},
    "priority_users": [60916468, 67145714, 39700287, 65329649],
    "priority_aliases": {
        "60916468": "兔",
        "67145714": "P",
        "39700287": "UID39700287",
        "65329649": "UID65329649",
    },
    "related_threads": [],
    "user_threads": {
        "60916468": [],
        "67145714": [],
        "39700287": [],
        "65329649": [],
    },
    "legacy_thread": {"tid": 45974302, "op_uid": 150058},
}


class NgaLoginRequired(RuntimeError):
    pass


class NgaBusy(RuntimeError):
    pass


def cjk_count(value: str) -> int:
    return sum(1 for char in value if "\u3400" <= char <= "\u9fff")


def repair_text(value: str) -> str:
    """Repair the three mojibake forms intermittently returned by NGA/CDN pages."""
    if not value:
        return value
    original = value
    candidates: list[str] = []
    for source_encoding in ("latin1", "cp1252"):
        try:
            raw = original.encode(source_encoding)
        except (UnicodeEncodeError, LookupError):
            continue
        for target_encoding in ("utf-8", "gb18030"):
            try:
                candidates.append(raw.decode(target_encoding))
            except UnicodeDecodeError:
                pass
    try:
        candidates.append(original.encode("gb18030").decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    current = original
    for candidate in candidates:
        if "\ufffd" in candidate:
            continue
        old_cjk = cjk_count(current)
        new_cjk = cjk_count(candidate)
        latin_noise = sum(1 for char in current if 0x80 <= ord(char) <= 0xFF)
        if new_cjk > old_cjk and (latin_noise or new_cjk >= 2):
            current = candidate
            continue
        if old_cjk and new_cjk and len(candidate) <= max(1, int(len(current) * 0.75)):
            current = candidate
    return current


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, value)
    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def tolerant_json(payload: str) -> dict:
    try:
        return json.loads(payload, strict=False)
    except json.JSONDecodeError:
        fixed = re.sub(r"\\u(?![0-9a-fA-F]{4})", r"\\\\u", payload)
        fixed = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r"\\\\", fixed)
        return json.loads(fixed, strict=False)


def fetch_json(url: str, cookie: str = "", attempts: int = 5) -> dict:
    headers = {"User-Agent": UA}
    if cookie:
        headers["Cookie"] = cookie
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=35) as response:
                payload = response.read().decode("utf-8", errors="replace")
            return tolerant_json(payload)
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(min(8, 1.5**attempt))
    raise RuntimeError(f"request failed after {attempts} attempts: {last_error} ({url})")


def fetch_search_html(url: str, cookie: str, attempts: int = 8) -> str:
    if not cookie:
        raise NgaLoginRequired("NGA_COOKIE is not set")
    headers = {"User-Agent": UA, "Cookie": cookie}
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=40) as response:
                body = response.read()
            text = body.decode("gb18030", errors="replace")
            title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
            title = strip_html(title_match.group(1)) if title_match else ""
            if "你必须登录" in text or "必须登录" in title:
                raise NgaLoginRequired("NGA login is required for searchpost")
            busy_markers = ("系统繁忙", "服务器繁忙", "访问频率", "稍后再试", "请稍候")
            if any(marker in text for marker in busy_markers):
                raise NgaBusy(title or "NGA is busy")
            return text
        except NgaLoginRequired:
            raise
        except (NgaBusy, OSError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                wait_seconds = min(10.0, 1.5 ** (attempt + 1))
                print(
                    f"searchpost busy/error; retry {attempt + 2}/{attempts} in {wait_seconds:.1f}s",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)
    raise RuntimeError(f"searchpost failed after {attempts} attempts: {last_error}")


def strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def read_url(tid: int, uid: int, page: int) -> str:
    params = urllib.parse.urlencode(
        {"tid": tid, "authorid": uid, "page": page, "__output": 11}
    )
    return f"{BASE}/read.php?{params}"


def read_html_url(tid: int, uid: int, page: int) -> str:
    params = urllib.parse.urlencode(
        {"tid": tid, "authorid": uid, "page": page, "opt": 262144}
    )
    return f"{BASE}/read.php?{params}"


def fetch_thread_html_page(tid: int, uid: int, page: int) -> dict:
    url = read_html_url(tid, uid, page)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=35) as response:
        payload = response.read().decode("gb18030", errors="replace")
    soup = BeautifulSoup(payload, "html.parser")
    rows = []
    username = ""
    for index, node in enumerate(soup.select("tr.postrow")):
        slot_match = re.search(r"(\d+)$", str(node.get("id") or ""))
        slot = slot_match.group(1) if slot_match else str(index)
        anchor = node.find(id=re.compile(r"^pid\d+Anchor$"))
        content = node.find(id=f"postcontent{slot}") or node.select_one(".postcontent")
        postdate = node.find(id=f"postdate{slot}")
        author = node.find(id=f"postauthor{slot}")
        if not anchor or not content or not postdate:
            continue
        pid_match = re.match(r"pid(\d+)Anchor", str(anchor.get("id") or ""))
        if not pid_match:
            continue
        date_text = postdate.get_text(" ", strip=True)
        try:
            timestamp = int(
                dt.datetime.strptime(date_text, "%Y-%m-%d %H:%M")
                .replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))
                .timestamp()
            )
        except ValueError:
            timestamp = 0
        if author and not username:
            username = repair_text(author.get_text(" ", strip=True))
        raw = repair_text(content.decode_contents())
        rows.append(
            {
                "pid": int(pid_match.group(1)),
                "tid": tid,
                "authorid": uid,
                "postdate": date_text,
                "postdatetimestamp": timestamp,
                "content": raw,
                "content_length": len(strip_html(raw)),
                "lou": (page - 1) * PAGE_SIZE + index,
            }
        )

    pager = re.search(
        r"var\s+__PAGE\s*=\s*\{0:.*?,1:(\d+),2:\d+,3:(\d+)\}", payload, flags=re.S
    )
    if pager:
        total_pages = int(pager.group(1))
        page_size = int(pager.group(2))
        total_rows = total_pages * page_size
        if page == 1 and total_pages > 1:
            try:
                last_req = urllib.request.Request(
                    read_html_url(tid, uid, total_pages), headers={"User-Agent": UA}
                )
                with urllib.request.urlopen(last_req, timeout=35) as response:
                    last_payload = response.read().decode("gb18030", errors="replace")
                last_count = len(BeautifulSoup(last_payload, "html.parser").select("tr.postrow"))
                if last_count:
                    total_rows = (total_pages - 1) * page_size + last_count
            except (OSError, urllib.error.URLError):
                pass
    else:
        total_rows = (page - 1) * PAGE_SIZE + len(rows)
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    subject_match = re.search(r"在\s*-\s*(.*?)\s*-\s*中的回复", title)
    subject = subject_match.group(1) if subject_match else title
    return {
        "data": {
            "__R": rows,
            "__ROWS": total_rows,
            "__T": {"tid": tid, "subject": subject, "this_visit_rows": total_rows},
            "__U": {str(uid): {"uid": uid, "username": username or f"UID:{uid}"}},
        }
    }


def fetch_thread_page(tid: int, uid: int, page: int) -> dict:
    try:
        return fetch_json(read_url(tid, uid, page))
    except RuntimeError as exc:
        print(
            f"JSON fetch failed for tid={tid} uid={uid} page={page}; using HTML fallback: {exc}",
            file=sys.stderr,
        )
        return fetch_thread_html_page(tid, uid, page)


def rows_from(data: dict) -> list[dict]:
    rows = data.get("data", {}).get("__R", [])
    if isinstance(rows, dict):
        rows = list(rows.values())
    return [row for row in rows if isinstance(row, dict)]


def strip_bbcode(value: str) -> str:
    text = html.unescape(repair_text(value or ""))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"\[img\](.*?)\[/img\]", r"[图片: \1]", text, flags=re.I | re.S)
    text = re.sub(r"\[url=([^\]]+)\](.*?)\[/url\]", r"\2 (\1)", text, flags=re.I | re.S)
    text = re.sub(r"\[url\](.*?)\[/url\]", r"\1", text, flags=re.I | re.S)
    text = re.sub(
        r"\[(?:/?(?:b|i|u|s|quote|collapse|color|size|font|align)|reply|tid|pid|uid)[^\]]*\]",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\[s:[^\]]+\]", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r", "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


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
        if item.get("type") == "img" or item.get("attachurl"):
            images.append(copy["url"])
    return sorted(set(link_urls)), sorted(set(images)), attachments


def user_name(data: dict, uid: int) -> str:
    users = data.get("data", {}).get("__U", {}) or {}
    entry = users.get(str(uid)) or users.get(uid) or {}
    name = entry.get("username") if isinstance(entry, dict) else ""
    if uid == 150058:
        return "-阿狼-"
    return repair_text(name or f"UID {uid}")


def normalize(row: dict, tid: int, uid: int, author: str, role: str, subject: str) -> dict:
    raw = repair_text(row.get("content") or "")
    links, images, attachments = collect_urls(raw, row)
    pid = int(row.get("pid") or 0)
    return {
        "record_key": f"post:{tid}:{pid}:{uid}",
        "record_kind": "post",
        "tid": tid,
        "pid": pid,
        "authorid": uid,
        "author": author,
        "tracking_role": role,
        "thread_subject": subject,
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
        "comments": row.get("comment") or [],
        "hotreply": row.get("hotreply") or [],
        "source": "nga",
        "source_url": (
            f"{BASE}/read.php?tid={tid}" if pid == 0 else f"{BASE}/read.php?pid={pid}&opt=128"
        ),
    }


def source_paths(tid: int, uid: int) -> tuple[Path, Path]:
    source_id = f"tid-{tid}-uid-{uid}"
    return SOURCES / f"{source_id}.jsonl", CACHE / f"tid-{tid}" / f"uid-{uid}"


def sync_source(tid: int, uid: int, role: str, quick: bool, workers: int) -> dict:
    source_file, cache_dir = source_paths(tid, uid)
    cache_dir.mkdir(parents=True, exist_ok=True)
    first_cache = cache_dir / "page-0001.json"
    try:
        first = fetch_thread_page(tid, uid, 1)
    except Exception:
        if not quick or not first_cache.exists():
            raise
        first = json.loads(first_cache.read_text(encoding="utf-8"))
        print(f"using cached tid={tid} uid={uid} page=1 after repeated fetch failure", file=sys.stderr)
    data = first.get("data", {})
    if data.get("__MESSAGE") or not data.get("__T"):
        raise RuntimeError(f"NGA did not return thread {tid} for UID {uid}")
    meta = data.get("__T", {})
    total_rows = int(data.get("__ROWS") or meta.get("this_visit_rows") or 0)
    total_pages = max(1, math.ceil(total_rows / PAGE_SIZE))
    all_pages = list(range(1, total_pages + 1))
    page_numbers = all_pages
    if quick:
        page_numbers = sorted(set([1] + list(range(max(1, total_pages - 9), total_pages + 1))))

    results = {1: first}
    remaining = [page for page in page_numbers if page != 1]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(fetch_thread_page, tid, uid, page): page for page in remaining
        }
        for future in concurrent.futures.as_completed(futures):
            page = futures[future]
            try:
                results[page] = future.result()
            except Exception:
                cached_page = cache_dir / f"page-{page:04d}.json"
                if not quick or not cached_page.exists():
                    raise
                results[page] = json.loads(cached_page.read_text(encoding="utf-8"))
                print(
                    f"using cached tid={tid} uid={uid} page={page} after repeated fetch failure",
                    file=sys.stderr,
                )
            print(f"fetched tid={tid} uid={uid} page={page}/{total_pages}", file=sys.stderr)

    for page, payload in results.items():
        (cache_dir / f"page-{page:04d}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    if quick:
        for path in cache_dir.glob("page-*.json"):
            page = int(path.stem.split("-")[-1])
            if page not in results:
                results[page] = json.loads(path.read_text(encoding="utf-8"))

    subject = repair_text(html.unescape(str(meta.get("subject") or "")))
    author = user_name(first, uid)
    posts: list[dict] = []
    seen: set[int] = set()
    for page in sorted(results):
        for row in rows_from(results[page]):
            if int(row.get("authorid") or 0) != uid:
                continue
            pid = int(row.get("pid") or 0)
            if pid in seen:
                continue
            seen.add(pid)
            posts.append(normalize(row, tid, uid, author, role, subject))
    posts.sort(key=lambda p: (int(p.get("postdatetimestamp") or 0), int(p.get("pid") or 0)))
    source_file.parent.mkdir(parents=True, exist_ok=True)
    with source_file.open("w", encoding="utf-8", newline="\n") as handle:
        for post in posts:
            handle.write(json.dumps(post, ensure_ascii=False, separators=(",", ":")) + "\n")

    pages_present = sorted(
        int(path.stem.split("-")[-1]) for path in cache_dir.glob("page-*.json")
    )
    return {
        "tid": tid,
        "authorid": uid,
        "author": author,
        "role": role,
        "subject": subject,
        "rows_reported": total_rows,
        "posts_written": len(posts),
        "unavailable_or_deleted_rows": max(0, total_rows - len(posts)),
        "total_pages": total_pages,
        "pages_present": pages_present,
        "complete": pages_present == all_pages,
        "source_file": str(source_file.relative_to(ROOT)).replace("\\", "/"),
        "source_url": f"{BASE}/read.php?tid={tid}&authorid={uid}&__output=11",
    }


def nested_tids(value: object) -> set[int]:
    found: set[int] = set()
    if isinstance(value, dict):
        if str(value.get("tid", "")).isdigit():
            found.add(int(value["tid"]))
        for child in value.values():
            found.update(nested_tids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(nested_tids(child))
    return found


def discover_authored_topics(uid: int, cookie: str) -> set[int]:
    params = urllib.parse.urlencode(
        {"__lib": "load_topic", "__act": "load_topic_by_uid", "uid": uid, "__output": 11}
    )
    try:
        return nested_tids(fetch_json(f"{BASE}/nuke.php?{params}", cookie=cookie).get("data"))
    except RuntimeError as exc:
        print(f"topic discovery failed for UID {uid}: {exc}", file=sys.stderr)
        return set()


def discover_reply_threads(uid: int, cookie: str, max_pages: int) -> tuple[set[int], dict]:
    state = {
        "uid": uid,
        "source_url": f"{BASE}/thread.php?searchpost=1&authorid={uid}",
        "pages_fetched": 0,
        "rows_seen": 0,
        "threads_found": 0,
        "complete_for_search_window": False,
        "login_required": False,
        "error": "",
    }
    if not cookie:
        state["login_required"] = True
        state["error"] = "Set NGA_COOKIE temporarily to use the login-only searchpost endpoint."
        return set(), state
    tids: set[int] = set()
    try:
        for page in range(1, max(1, max_pages) + 1):
            params = urllib.parse.urlencode({"searchpost": 1, "authorid": uid, "page": page})
            page_url = f"{BASE}/thread.php?{params}"
            page_html = fetch_search_html(page_url, cookie)
            soup = BeautifulSoup(page_html, "html.parser")
            rows = soup.select("tr.topicrow")
            state["pages_fetched"] = page
            state["rows_seen"] += len(rows)
            for row in rows:
                topic = row.select_one(".c2 a.topic") or row.select_one("a.topic")
                if not topic:
                    continue
                match = re.search(r"tid=(\d+)", topic.get("href") or "")
                if match:
                    tids.add(int(match.group(1)))
            next_link = soup.find(
                "a",
                string=lambda value: bool(value and ("下一页" in value or "加载下一页" in value)),
            )
            if not rows or not next_link:
                state["complete_for_search_window"] = True
                break
            if page < max_pages:
                time.sleep(0.7)
        state["threads_found"] = len(tids)
    except NgaLoginRequired as exc:
        state["login_required"] = True
        state["error"] = str(exc)
    except Exception as exc:
        state["error"] = str(exc)
    return tids, state


def archive_legacy_if_needed(config: dict) -> None:
    legacy = config.get("legacy_thread") or {}
    old_data = REFS / "full-posts.jsonl"
    old_state = REFS / "update-state.json"
    legacy_file = LEGACY / f"tid-{legacy.get('tid')}-uid-{legacy.get('op_uid')}.jsonl"
    if legacy_file.exists() or not old_data.exists() or not old_state.exists():
        return
    try:
        state = json.loads(old_state.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if int(state.get("tid") or 0) != int(legacy.get("tid") or 0):
        return
    LEGACY.mkdir(parents=True, exist_ok=True)
    with old_data.open(encoding="utf-8") as source, legacy_file.open(
        "w", encoding="utf-8", newline="\n"
    ) as target:
        for line in source:
            post = json.loads(line)
            post.setdefault("record_key", f"post:{post.get('tid')}:{post.get('pid')}:{post.get('authorid')}")
            post.setdefault("record_kind", "post")
            post["tracking_role"] = "legacy_op"
            post.setdefault("source", "nga")
            target.write(json.dumps(post, ensure_ascii=False, separators=(",", ":")) + "\n")
    shutil.copy2(old_state, LEGACY / f"tid-{legacy.get('tid')}-update-state.json")


def load_all_posts() -> list[dict]:
    paths = list(LEGACY.glob("*.jsonl")) + list(SOURCES.glob("*.jsonl"))
    records: dict[str, dict] = {}
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                post = json.loads(line)
                for field in (
                    "author",
                    "thread_subject",
                    "subject",
                    "raw_bbcode",
                    "plain_text",
                    "alterinfo",
                ):
                    if isinstance(post.get(field), str):
                        post[field] = repair_text(post[field])
                if isinstance(post.get("raw_bbcode"), str):
                    post["plain_text"] = strip_bbcode(post["raw_bbcode"])
                key = post.get("record_key") or f"post:{post.get('tid')}:{post.get('pid')}:{post.get('authorid')}"
                records[key] = post
    posts = list(records.values())
    posts.sort(key=lambda p: (int(p.get("postdatetimestamp") or 0), int(p.get("pid") or 0)))
    for index, post in enumerate(posts):
        post["filtered_ordinal"] = index
    return posts


def write_combined(posts: list[dict], state: dict) -> None:
    jsonl_path = REFS / "full-posts.jsonl"
    index_path = REFS / "posts-index.tsv"
    md_path = REFS / "full-posts.md"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for post in posts:
            handle.write(json.dumps(post, ensure_ascii=False, separators=(",", ":")) + "\n")
    with index_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("ordinal\tpostdate\ttid\tpid\tauthorid\trole\tsource_url\tpreview\n")
        for post in posts:
            preview = (
                re.sub(r"\s+", " ", post.get("plain_text") or "")[:240]
                .replace("\t", " ")
                .rstrip()
            )
            handle.write(
                f"{post['filtered_ordinal']}\t{post.get('postdate')}\t{post.get('tid')}\t"
                f"{post.get('pid')}\t{post.get('authorid')}\t{post.get('tracking_role')}\t"
                f"{post.get('source_url')}\t{preview}\n"
            )
    with md_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# NGA 阿狼及重点用户发言资料库\n\n")
        handle.write(f"- 主追踪帖：{state['primary_thread_url']}\n")
        handle.write(f"- 合并记录：{len(posts)}\n")
        handle.write(f"- 更新时间：{state['updated_at']}\n\n")
        for post in posts:
            markdown_text = "\n".join(
                line.rstrip() for line in (post.get("plain_text") or "").splitlines()
            ).strip()
            handle.write(
                f"## #{post['filtered_ordinal']} · {post.get('postdate')} · "
                f"{post.get('author')} (UID {post.get('authorid')}) · TID {post.get('tid')} · PID {post.get('pid')}\n\n"
                f"[原帖]({post.get('source_url')})\n\n{markdown_text}\n\n"
            )
    (REFS / "update-state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    primary_source = next(
        (
            source
            for source in state.get("sources", [])
            if source.get("tid") == state.get("primary_tid") and source.get("role") == "op"
        ),
        {},
    )
    thread_meta = {
        "tid": state.get("primary_tid"),
        "subject": primary_source.get("subject"),
        "author": primary_source.get("author"),
        "authorid": state.get("op_uid"),
        "priority_users": state.get("priority_users", []),
        "source_url": state.get("primary_thread_url"),
        "updated_at": state.get("updated_at"),
    }
    (REFS / "thread-meta.json").write_text(
        json.dumps(thread_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="refresh the latest ten pages per source")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--add-thread", type=int, action="append", default=[])
    parser.add_argument(
        "--add-thread-for",
        action="append",
        default=[],
        metavar="UID:TID",
        help="register a related thread for one priority user",
    )
    parser.add_argument("--discovery-pages", type=int, default=12)
    parser.add_argument("--no-reply-search", action="store_true")
    parser.add_argument("--no-discover", action="store_true")
    args = parser.parse_args()

    config = load_config()
    archive_legacy_if_needed(config)
    primary = config["primary_thread"]
    primary_tid = int(primary["tid"])
    op_uid = int(primary["op_uid"])
    priority_users = sorted({int(uid) for uid in config.get("priority_users", [])})
    related = {int(tid) for tid in config.get("related_threads", [])}
    related.update(args.add_thread)
    related.discard(primary_tid)
    user_threads = {
        str(uid): {int(tid) for tid in config.get("user_threads", {}).get(str(uid), [])}
        for uid in priority_users
    }
    for item in args.add_thread_for:
        try:
            uid_text, tid_text = item.split(":", 1)
            uid, tid = int(uid_text), int(tid_text)
        except ValueError as exc:
            raise SystemExit(f"invalid --add-thread-for value: {item}; expected UID:TID") from exc
        if uid not in priority_users:
            raise SystemExit(f"UID {uid} is not configured as a priority user")
        if tid != primary_tid:
            user_threads[str(uid)].add(tid)

    cookie = os.environ.get("NGA_COOKIE", "").strip()
    discovered: set[int] = set()
    discovered_by_user: dict[str, list[int]] = {}
    reply_search_states: list[dict] = []
    if not args.no_discover:
        for uid in priority_users:
            discovered.update(discover_authored_topics(uid, cookie))
            if not args.no_reply_search:
                reply_tids, reply_state = discover_reply_threads(uid, cookie, args.discovery_pages)
                reply_tids.discard(primary_tid)
                new_for_user = reply_tids - user_threads[str(uid)]
                user_threads[str(uid)].update(reply_tids)
                discovered_by_user[str(uid)] = sorted(new_for_user)
                reply_search_states.append(reply_state)
    discovered.discard(primary_tid)
    related.update(discovered)
    config["related_threads"] = sorted(related)
    config["user_threads"] = {
        uid: sorted(tids) for uid, tids in sorted(user_threads.items(), key=lambda item: int(item[0]))
    }
    save_config(config)

    jobs = [(primary_tid, op_uid, "op")]
    jobs += [(primary_tid, uid, "priority_user") for uid in priority_users]
    jobs += [(tid, uid, "priority_user") for tid in sorted(related) for uid in priority_users]
    jobs += [
        (tid, int(uid), "priority_user")
        for uid, tids in user_threads.items()
        for tid in sorted(tids)
    ]
    jobs = list(dict.fromkeys(jobs))
    source_states = []
    errors = []
    for tid, uid, role in jobs:
        try:
            source_states.append(sync_source(tid, uid, role, args.quick, args.workers))
        except Exception as exc:
            errors.append({"tid": tid, "authorid": uid, "error": str(exc)})
            print(f"skipped tid={tid} uid={uid}: {exc}", file=sys.stderr)

    posts = load_all_posts()
    updated_at = dt.datetime.now().astimezone().isoformat()
    state = {
        "primary_tid": primary_tid,
        "op_uid": op_uid,
        "priority_users": priority_users,
        "related_threads": sorted(related),
        "user_threads": {uid: sorted(tids) for uid, tids in user_threads.items()},
        "newly_discovered_threads": sorted(discovered),
        "newly_discovered_reply_threads": discovered_by_user,
        "reply_search": reply_search_states,
        "primary_thread_url": f"{BASE}/read.php?tid={primary_tid}",
        "posts_written": len(posts),
        "sources": source_states,
        "errors": errors,
        "complete_for_registered_sources": bool(source_states)
        and all(source["complete"] for source in source_states)
        and not errors,
        "cross_forum_complete": False,
        "cross_forum_note": (
            "NGA searchpost requires login and can be rate-limited. The database covers the primary "
            "thread plus cumulatively registered threads found in the configured search window."
        ),
        "authenticated_discovery": bool(cookie),
        "updated_at": updated_at,
    }
    write_combined(posts, state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
