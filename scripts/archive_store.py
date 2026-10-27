#!/usr/bin/env python3
"""Maintain lossless, versioned JSONL originals partitioned by author/month."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / 'references' / 'originals'


def record_key(post: dict) -> str:
    return post.get('record_key') or f"post:{post.get('tid')}:{post.get('pid')}:{post.get('authorid')}"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def sort_key(post: dict) -> tuple:
    return (post.get('postdate') or '', int(post.get('pid') or 0), record_key(post))


def load_archive(root: Path = DEFAULT_ROOT) -> list[dict]:
    if not (root / 'manifest.json').exists():
        return []
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    posts = []
    for item in manifest['files']:
        path = root / item['path']
        if root.resolve() not in path.resolve().parents:
            raise ValueError('Archive file path escapes originals directory')
        posts.extend(read_jsonl(path))
    return sorted(posts, key=sort_key)


def atomic_write(path: Path, content: bytes) -> None:
    if path.exists() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(content)
    temp.replace(path)


def encode_records(posts: list[dict]) -> bytes:
    return ''.join(json.dumps(p, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n' for p in posts).encode('utf-8')


def write_archive(posts: list[dict], root: Path = DEFAULT_ROOT) -> dict:
    existing = {record_key(p): p for p in load_archive(root)}
    revisions = {}
    revision_path = root / 'revisions.jsonl'
    if revision_path.exists():
        for r in read_jsonl(revision_path):
            revisions[(r['record_key'], r['body_sha256'])] = r
    for incoming in posts:
        post = dict(incoming)
        key = record_key(post)
        post['record_key'] = key
        post.pop('filtered_ordinal', None)
        if 'raw_bbcode' not in post:
            raise ValueError(f'Missing original body: {key}')
        previous = existing.get(key)
        if previous is not None and previous.get('raw_bbcode') != post['raw_bbcode']:
            digest = hashlib.sha256(previous['raw_bbcode'].encode('utf-8')).hexdigest()
            revisions[(key, digest)] = {'record_key': key, 'body_sha256': digest, 'previous_record': previous}
        existing[key] = post
    groups = defaultdict(list)
    for post in existing.values():
        uid = int(post['authorid'])
        date = post.get('postdate') or ''
        month = date[:7] if re.match(r'^\d{4}-\d{2}', date) else 'undated'
        groups[f'users/{uid}/{month}.jsonl'].append(post)
    files = []
    for relative, group in sorted(groups.items()):
        group.sort(key=sort_key)
        payload = encode_records(group)
        atomic_write(root / relative, payload)
        files.append({'path': relative, 'records': len(group), 'bytes': len(payload),
                      'sha256': hashlib.sha256(payload).hexdigest(),
                      'earliest': group[0].get('postdate'), 'latest': group[-1].get('postdate')})
    all_posts = sorted(existing.values(), key=sort_key)
    manifest = {'schema_version': 1, 'encoding': 'UTF-8', 'timezone': 'Asia/Shanghai',
                'primary_key': 'record_key', 'body_field': 'raw_bbcode',
                'total_records': len(all_posts),
                'counts_by_uid': dict(sorted(Counter(str(p['authorid']) for p in all_posts).items())),
                'earliest': all_posts[0].get('postdate') if all_posts else None,
                'latest': all_posts[-1].get('postdate') if all_posts else None,
                'revision_count': len(revisions), 'files': files}
    if revisions:
        payload = encode_records([revisions[k] for k in sorted(revisions)])
        atomic_write(revision_path, payload)
        manifest['revisions_sha256'] = hashlib.sha256(payload).hexdigest()
    atomic_write(root / 'manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    # Remove obsolete shards only within this archive's users directory, after publishing the manifest.
    for path in (root / 'users').rglob('*.jsonl'):
        if path.relative_to(root).as_posix() not in groups:
            path.unlink()
    return manifest


def verify_archive(root: Path = DEFAULT_ROOT) -> dict:
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        path = root / item['path']
        if root.resolve() not in path.resolve().parents:
            raise ValueError('Unsafe manifest path')
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != item['sha256']:
            raise ValueError(f"Checksum mismatch: {item['path']}")
        rows = read_jsonl(path)
        if len(rows) != item['records'] or rows != sorted(rows, key=sort_key):
            raise ValueError(f"Count/order mismatch: {item['path']}")
    posts = load_archive(root)
    if len(posts) != manifest['total_records'] or len({record_key(p) for p in posts}) != len(posts):
        raise ValueError('Archive total or primary-key mismatch')
    if dict(Counter(str(p['authorid']) for p in posts)) != manifest['counts_by_uid']:
        raise ValueError('Author counts mismatch')
    if any(not isinstance(p.get('raw_bbcode'), str) for p in posts):
        raise ValueError('Original body missing')
    if manifest.get('revision_count'):
        payload = (root / 'revisions.jsonl').read_bytes()
        if hashlib.sha256(payload).hexdigest() != manifest['revisions_sha256']:
            raise ValueError('Revision checksum mismatch')
    return {'verified': True, 'records': len(posts), 'authors': len(manifest['counts_by_uid']), 'files': len(manifest['files'])}


def write_coverage(state: dict, root: Path = DEFAULT_ROOT) -> None:
    fields = ['tid', 'authorid', 'author', 'role', 'rows_reported', 'row_count_basis',
              'posts_written', 'visible_posts_written', 'previously_seen_not_returned',
              'unresolved_row_difference', 'total_pages', 'pages_complete', 'complete', 'source_url']
    target = state.get('last_targeted_sync') or {}
    sources = []
    for source in state.get('sources', []):
        item = {k: source[k] for k in fields if k in source}
        item['last_checked_at'] = (target.get('updated_at') if source.get('authorid') == target.get('authorid')
                                   else state.get('updated_at'))
        sources.append(item)
    coverage = {'primary_tid': state.get('primary_tid'), 'sources': sources,
                'complete_for_registered_sources': bool(state.get('complete_for_registered_sources')),
                'cross_forum_complete': bool(state.get('cross_forum_complete')),
                'note': 'Recorded public posts only. Different authors may have different collection times. '
                        'Unseen cross-thread replies, deleted/invisible content and nested comments may be missing. '
                        'A server count difference is not proof of deletion.'}
    atomic_write(root / 'coverage.json', (json.dumps(coverage, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--import-jsonl', type=Path, action='append', default=[])
    parser.add_argument('--export', type=Path, help='Export all originals as one chronological JSONL')
    args = parser.parse_args()
    if args.import_jsonl:
        write_archive([p for path in args.import_jsonl for p in read_jsonl(path)], args.root)
    result = verify_archive(args.root)
    if args.export:
        atomic_write(args.export, encode_records(load_archive(args.root)))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
