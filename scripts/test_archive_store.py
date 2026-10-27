"""Portable-backup invariants: exact originals, deduplication and recovery."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archive_store import load_archive, verify_archive, write_archive
import update_thread as updater


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'references' / 'originals'

    def tearDown(self):
        self.temp.cleanup()

    def post(self, tid=1, pid=0, body='原文🙂\n[quote]引用[/quote]<br/>第二行'):
        return {'record_key': f'post:{tid}:{pid}:123', 'tid': tid, 'pid': pid,
                'authorid': 123, 'postdate': '2026-10-27 16:01', 'raw_bbcode': body}

    def test_exact_body_idempotent_and_topic_first_posts_distinct(self):
        posts = [self.post(), self.post(tid=2)]
        write_archive(posts, self.root)
        first = {p.name: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        write_archive(posts, self.root)
        second = {p.name: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(first, second)
        self.assertEqual([p['raw_bbcode'] for p in load_archive(self.root)], [p['raw_bbcode'] for p in posts])
        self.assertEqual(verify_archive(self.root)['records'], 2)

    def test_revision_preserves_old_body_and_partial_update_keeps_other_posts(self):
        write_archive([self.post(), self.post(pid=2)], self.root)
        write_archive([self.post(body='新正文')], self.root)
        self.assertEqual(len(load_archive(self.root)), 2)
        revisions = [json.loads(x) for x in (self.root/'revisions.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(revisions[0]['previous_record']['raw_bbcode'], self.post()['raw_bbcode'])
        self.assertTrue(verify_archive(self.root)['verified'])

    def test_corrupted_shard_is_detected(self):
        write_archive([self.post()], self.root)
        shard = next((self.root/'users').rglob('*.jsonl'))
        shard.write_bytes(shard.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
            verify_archive(self.root)

    def test_sync_recovers_archive_without_source_caches(self):
        post = self.post()
        write_archive([post], self.root)
        refs = self.root.parent
        with patch.object(updater, 'REFS', refs), patch.object(updater, 'LEGACY', refs/'legacy'), patch.object(updater, 'SOURCES', refs/'sources'):
            recovered = updater.load_all_posts()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]['raw_bbcode'], post['raw_bbcode'])

    def test_stale_source_does_not_replace_current_original(self):
        write_archive([self.post(body='新原文')], self.root)
        refs = self.root.parent
        sources = refs/'sources'
        sources.mkdir()
        (sources/'old.jsonl').write_text(json.dumps(self.post(body='旧缓存'))+'\n', encoding='utf-8')
        with patch.object(updater, 'REFS', refs), patch.object(updater, 'LEGACY', refs/'legacy'), patch.object(updater, 'SOURCES', sources):
            self.assertEqual(updater.load_all_posts()[0]['raw_bbcode'], '新原文')


if __name__ == '__main__':
    unittest.main()
