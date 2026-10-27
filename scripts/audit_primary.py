#!/usr/bin/env python3
"""Refresh registered primary-thread authors and publish a content-free coverage index."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

import update_thread as updater


def audit_source(root: Path, source: dict) -> tuple[dict, list[dict]]:
    tid, uid = source['tid'], source['authorid']
    cache = root / 'references' / 'raw-pages-v2' / f'tid-{tid}' / f'uid-{uid}'
    records = {}
    errors, duplicates, unexpected_authors, page_counts = [], [], [], []
    for page in range(1, source['total_pages'] + 1):
        path = cache / f'page-{page:04d}.json'
        if not path.exists():
            errors.append({'page':page,'reason':'missing_page'})
            continue
        payload = json.loads(path.read_text(encoding='utf-8'))
        data = payload.get('data', {})
        if int(data.get('__T', {}).get('tid') or 0) != tid:
            errors.append({'page':page,'reason':'wrong_thread'})
        if data.get('__PAGE') is not None and int(data['__PAGE']) != page:
            errors.append({'page':page,'reason':'wrong_page'})
        rows = updater.rows_from(payload)
        page_counts.append({'page':page,'rows':len(rows)})
        for row in rows:
            if int(row.get('authorid') or 0) != uid:
                unexpected_authors.append({'page':page,'pid':row.get('pid'),'uid':row.get('authorid')})
                continue
            pid = int(row.get('pid') or 0)
            if pid in records:
                duplicates.append({'pid':pid,'pages':[records[pid]['page'],page]})
            date = row.get('postdate') or ''
            try:
                dt.datetime.strptime(date, '%Y-%m-%d %H:%M')
            except ValueError:
                errors.append({'page':page,'pid':pid,'reason':'invalid_timestamp'})
            records[pid] = {'tid':tid,'uid':uid,'pid':pid,'postdate':date,'timestamp':row.get('postdatetimestamp'),
                            'page':page,'author_ordinal':row.get('lou'),
                            'source_url':f'https://bbs.nga.cn/read.php?pid={pid}&opt=128' if pid else f'https://bbs.nga.cn/read.php?tid={tid}'}
    source_file = root / source['source_file']
    stored = [json.loads(line) for line in source_file.read_text(encoding='utf-8').splitlines() if line.strip()]
    stored_pids = [int(p.get('pid') or 0) for p in stored]
    absent = sorted(set(records) - set(stored_pids))
    if absent:
        errors.append({'reason':'visible_rows_not_in_archive','pids':absent})
    if len(stored_pids) != len(set(stored_pids)):
        errors.append({'reason':'duplicate_archive_pids'})
    stored_times = [(int(p.get('postdatetimestamp') or 0),int(p.get('pid') or 0)) for p in stored]
    if stored_times != sorted(stored_times):
        errors.append({'reason':'archive_timeline_not_sorted'})
    ranges = [(r['postdate'],r['pid']) for r in records.values()]
    observed = sorted(records.values(),key=lambda r:(r['postdate'],r['pid']))
    difference = source['rows_reported'] - len(records)
    head = json.loads((cache / 'page-0001.json').read_text(encoding='utf-8')).get('data', {})
    positions = {int(r['author_ordinal']) for r in records.values() if r['author_ordinal'] is not None}
    return {'tid':tid,'uid':uid,'author':source['author'],'reported_rows':source['rows_reported'],
            'row_count_basis':'json_api' if '__PAGE' in head else 'html_pager_estimate',
            'expected_pages':source['total_pages'],'checked_pages':len(page_counts),'visible_unique_posts':len(records),
            'archived_posts':len(stored),'previously_seen_not_returned':source.get('previously_seen_not_returned',0),
            'server_count_difference':difference,'first_post':min(ranges)[0] if ranges else None,
            'unreturned_author_positions':sorted(set(range(source['rows_reported']))-positions),
            'latest_post':max(ranges)[0] if ranges else None,'duplicate_page_pids':duplicates,
            'unexpected_author_rows':unexpected_authors,'page_row_counts':page_counts,
            'errors':errors,'cached_fallback_pages':source.get('cached_fallback_pages',[]),
            'visible_rows_verified':not errors and not duplicates and not unexpected_authors and not source.get('cached_fallback_pages')}, observed


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=updater.ROOT)
    parser.add_argument('--out',type=Path,default=Path('reports'))
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--cache-only',action='store_true',help='audit existing primary-source snapshots without fetching')
    args=parser.parse_args()
    root=args.data_dir.resolve()
    updater.ROOT=root; updater.REFS=root/'references'; updater.CONFIG_PATH=updater.REFS/'tracking-config.json'
    updater.SOURCES=updater.REFS/'sources';updater.CACHE=updater.REFS/'raw-pages-v2';updater.LEGACY=updater.REFS/'legacy'
    config=updater.load_config();tid=int(config['primary_thread']['tid']);op=int(config['primary_thread']['op_uid'])
    uids=sorted({op,*map(int,config['priority_users'])})
    state_path=updater.REFS/'update-state.json'
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    sources=[];failed=[];audits=[];timeline=[]
    for uid in uids:
        try:
            if args.cache_only:
                source=next(s for s in state['sources'] if s['tid']==tid and s['authorid']==uid)
            else:
                source=updater.sync_source(tid,uid,'op' if uid==op else 'priority_user',False,args.workers)
            sources.append(source)
            audit,rows=audit_source(root,source);audits.append(audit);timeline.extend(rows)
            print(json.dumps({'uid':uid,'pages':audit['checked_pages'],'posts':audit['visible_unique_posts'],
                              'server_count_difference':audit['server_count_difference'],'verified':audit['visible_rows_verified']},ensure_ascii=False),flush=True)
        except Exception as exc:
            failed.append({'tid':tid,'authorid':uid,'error':str(exc)})
            print(json.dumps(failed[-1],ensure_ascii=False),flush=True)
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')
    verified=len(audits)==len(uids) and all(s['visible_rows_verified'] for s in audits) and not failed
    report={'audited_at':now,'scope':{'tid':tid,'uids':uids,'mode':'cache_only' if args.cache_only else 'fresh_all_pages'},
            'visible_rows_verified':verified,'all_historical_replies_proven':False,
            'limitations':['Only current publicly visible author-filtered pages are verifiable.',
                          'Deleted, hidden, nested comments and undiscovered cross-thread replies may be absent.',
                          'Reported-count differences remain unresolved unless source evidence identifies the cause.'],
            'sources':audits,'errors':failed}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    timeline.sort(key=lambda r:(r['postdate'],r['pid'],r['uid']))
    with (args.out/'timeline.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['tid','uid','pid','postdate','timestamp','page','author_ordinal','source_url'])
        writer.writeheader();writer.writerows(timeline)
    keys={(s['tid'],s['authorid']) for s in sources}
    state['sources']=[s for s in state.get('sources',[]) if (s.get('tid'),s.get('authorid')) not in keys]+sources
    state.update(updated_at=now,complete_for_registered_sources=False,cross_forum_complete=False,
                 partial_refresh={'updated_at':now,'scope':'registered primary-thread authors; all pages',
                                  'sources':sources,'errors':failed,'cross_thread_refreshed':False},
                 primary_history_audit={'audited_at':now,'visible_rows_verified':verified,'all_historical_replies_proven':False})
    posts=updater.load_all_posts();state['posts_written']=len(posts);updater.write_combined(posts,state)
    print(json.dumps({'audited_at':now,'timeline_entries':len(timeline),'verified':verified,'errors':failed},ensure_ascii=False))
    return 0 if verified else 2


if __name__=='__main__':
    raise SystemExit(main())
