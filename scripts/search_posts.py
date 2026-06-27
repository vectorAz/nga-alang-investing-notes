#!/usr/bin/env python3
"""Search the NGA Alang historical replies JSONL."""

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
    parser.add_argument("--archive-id")
    parser.add_argument("--source")
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
            record_id = (
                f'PID {post.get("pid")}'
                if post.get("pid")
                else f'ARCHIVE {post.get("archive_id")}'
            )
            location = post.get("source_url") or ""
            if post.get("source_sheet") and post.get("source_row"):
                location += f' ({post.get("source_sheet")} R{post.get("source_row")})'
            print(f'[{date}] {record_id} #{post.get("filtered_ordinal")}\n{location}\n{preview}\n')
            found += 1
            if found >= args.limit:
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
