"""Offline regression checks for missing history, stale caches and retained records."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import update_thread as updater
from audit_primary import audit_source


class HistorySyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(updater, key, value) for key, value in {
            'ROOT':self.root,'REFS':self.root/'references','SOURCES':self.root/'references/sources',
            'CACHE':self.root/'references/raw-pages-v2'}.items()]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def payload(self, page, total=60):
        return {'data':{'__PAGE':page,'__ROWS':total,'__T':{'tid':123,'subject':'Synthetic thread'},
                        '__U':{'456':{'username':'Synthetic author'}},
                        '__R':[{'pid':page,'authorid':456,'postdate':f'2026-01-{page:02d} 12:00',
                                'postdatetimestamp':page,'content':'Synthetic test content'}]}}

    def cache(self, page, total=60):
        _,directory=updater.source_paths(123,456)
        directory.mkdir(parents=True,exist_ok=True)
        (directory/f'page-{page:04d}.json').write_text(json.dumps(self.payload(page,total)),encoding='utf-8')

    def test_quick_sync_backfills_older_missing_pages(self):
        # 15 pages: quick refresh covers 6..15 but must also fetch missing 2..5.
        self.cache(1,300)
        fetched=[]
        def fetch(tid,uid,page):fetched.append(page);return self.payload(page,300)
        with patch.object(updater,'fetch_thread_page',side_effect=fetch):
            source=updater.sync_source(123,456,'priority_user',True,2)
        self.assertEqual(set(fetched),set(range(1,16)))
        self.assertEqual(source['visible_posts_written'],15)
        self.assertTrue(source['pages_complete'])

    def test_cache_fallback_does_not_claim_fresh_complete(self):
        for page in range(1,4):self.cache(page)
        with patch.object(updater,'fetch_thread_page',side_effect=RuntimeError('offline')):
            source=updater.sync_source(123,456,'priority_user',True,1)
        self.assertTrue(source['pages_complete'])
        self.assertFalse(source['complete'])
        self.assertEqual(source['cached_fallback_pages'],[1,2,3])

    def test_old_extra_cache_pages_are_not_used_as_current_posts(self):
        self.cache(4,80)
        with patch.object(updater,'fetch_thread_page',side_effect=lambda t,u,p:self.payload(p,40)):
            source=updater.sync_source(123,456,'priority_user',True,1)
        self.assertEqual(source['visible_posts_written'],2)

    def test_previously_seen_post_is_retained_if_source_hides_it(self):
        file,_=updater.source_paths(123,456);file.parent.mkdir(parents=True,exist_ok=True)
        old={'pid':99,'tid':123,'authorid':456,'postdate':'2025-12-01 12:00','postdatetimestamp':0,'raw_bbcode':'Synthetic historical post'}
        file.write_text(json.dumps(old)+'\n',encoding='utf-8')
        with patch.object(updater,'fetch_thread_page',return_value=self.payload(1,1)):
            source=updater.sync_source(123,456,'priority_user',False,1)
        rows=[json.loads(s) for s in file.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(source['previously_seen_not_returned'],1)
        self.assertEqual(source['visible_posts_written'],1)
        self.assertEqual(next(p for p in rows if p['pid']==99)['visibility_at_sync'],'not_returned')

    def test_wrong_page_is_rejected(self):
        bad=self.payload(2,1)
        with patch.object(updater,'fetch_thread_page',return_value=bad):
            with self.assertRaisesRegex(RuntimeError,'Wrong page'):
                updater.sync_source(123,456,'priority_user',False,1)

    def test_quick_sync_rejects_wrong_historical_cached_page(self):
        for page in range(1,16):self.cache(page,300)
        _,directory=updater.source_paths(123,456)
        (directory/'page-0002.json').write_text(json.dumps(self.payload(99,300)),encoding='utf-8')
        with patch.object(updater,'fetch_thread_page',side_effect=lambda t,u,p:self.payload(p,300)):
            with self.assertRaisesRegex(RuntimeError,'Wrong cached page'):
                updater.sync_source(123,456,'priority_user',True,1)

    def test_audit_fails_when_visible_post_is_missing_from_archive(self):
        with patch.object(updater,'fetch_thread_page',return_value=self.payload(1,1)):
            source=updater.sync_source(123,456,'priority_user',False,1)
        (self.root/source['source_file']).write_text('',encoding='utf-8')
        report,_=audit_source(self.root,source)
        self.assertFalse(report['visible_rows_verified'])
        self.assertEqual(report['errors'][0]['reason'],'visible_rows_not_in_archive')


if __name__=='__main__':unittest.main()
