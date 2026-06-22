#!/usr/bin/env python3
"""Search the synchronized NGA OP-post JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "references" / "full-posts.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    needle = args.query.casefold()
    found = 0
    with DATA.open(encoding="utf-8") as f:
        for line in f:
            post = json.loads(line)
            date = post.get("postdate") or ""
            if args.pid is not None and post.get("pid") != args.pid:
                continue
            if args.since and date < args.since:
                continue
            if args.until and date > args.until + " 99:99:99":
                continue
            haystack = "\n".join(
                [post.get("plain_text") or "", post.get("raw_bbcode") or "", post.get("subject") or ""]
            ).casefold()
            if needle and needle not in haystack:
                continue
            preview = " ".join((post.get("plain_text") or "").split())[:500]
            print(
                f'[{post.get("postdate")}] PID {post.get("pid")} '
                f'#{post.get("filtered_ordinal")}\n{post.get("source_url")}\n{preview}\n'
            )
            found += 1
            if found >= args.limit:
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
