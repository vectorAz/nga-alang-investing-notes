#!/usr/bin/env python3
"""Search the combined NGA Alang and priority-user archive."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "references" / "full-posts.jsonl"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--tid", type=int)
    parser.add_argument("--uid", type=int)
    parser.add_argument("--role", choices=["op", "priority_user", "legacy_op"])
    parser.add_argument("--archive-id")
    parser.add_argument("--source")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    needle = args.query.casefold()
    found = 0
    with DATA.open(encoding="utf-8") as handle:
        for line in handle:
            post = json.loads(line)
            date = post.get("postdate") or ""
            if args.pid is not None and post.get("pid") != args.pid:
                continue
            if args.tid is not None and post.get("tid") != args.tid:
                continue
            if args.uid is not None and post.get("authorid") != args.uid:
                continue
            if args.role and post.get("tracking_role") != args.role:
                continue
            if args.archive_id and post.get("archive_id") != args.archive_id:
                continue
            if args.source and post.get("source") != args.source:
                continue
            if args.since and date < args.since:
                continue
            if args.until and date > args.until + " 23:59:59":
                continue
            haystack = "\n".join(
                [post.get("plain_text") or "", post.get("raw_bbcode") or "", post.get("subject") or ""]
            ).casefold()
            if needle and needle not in haystack:
                continue
            preview = " ".join((post.get("plain_text") or "").split())[:500]
            location = post.get("source_url") or ""
            print(
                f"[{date}] {post.get('author')} UID {post.get('authorid')} "
                f"TID {post.get('tid')} PID {post.get('pid')} [{post.get('tracking_role')}]\n"
                f"{location}\n{preview}\n"
            )
            found += 1
            if found >= args.limit:
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
