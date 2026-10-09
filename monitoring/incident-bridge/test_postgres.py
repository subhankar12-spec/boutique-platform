"""Real PostgreSQL integration tests. Use a dedicated disposable database only."""
import concurrent.futures
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

import bridge as b

URL = os.environ.get('TEST_QUEUE_DATABASE_URL', '')

@unittest.skipUnless(URL, 'TEST_QUEUE_DATABASE_URL must point to a disposable dedicated database')
class PostgreSQLQueueTests(unittest.TestCase):
    def setUp(self):
        self.old_url = os.environ.get('QUEUE_DATABASE_URL')
        os.environ['QUEUE_DATABASE_URL'] = URL
        b.initialize()
        with b.connect() as db:
            db.execute('TRUNCATE queue')
        self.alert = {'fingerprint':'1234','startsAt':'2026-10-08T00:00:00Z','status':'firing','labels':{'alertname':'ServiceDown'}}
        self.original = b.deliver

    def tearDown(self):
        b.deliver = self.original
        if self.old_url is None: os.environ.pop('QUEUE_DATABASE_URL', None)
        else: os.environ['QUEUE_DATABASE_URL'] = self.old_url

    def test_two_independent_processes_claim_different_rows(self):
        b.enqueue_many([dict(self.alert, fingerprint=str(i)) for i in range(8)])
        code = 'import bridge,json; r=bridge.claim(); print(json.dumps(None if r is None else r[0]))'
        env = dict(os.environ, QUEUE_DATABASE_URL=URL)
        def process(_):
            result = subprocess.run([sys.executable,'-c',code], cwd=Path(__file__).parent, env=env,
                                    capture_output=True, text=True, check=True)
            return result.stdout.strip()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            claims = list(executor.map(process, range(8)))
        self.assertEqual(len(set(claims)), 8)
        self.assertNotIn('null', claims)
        self.assertIsNone(b.claim())

    def test_skip_locked_does_not_block_other_replica(self):
        b.enqueue_many([self.alert, dict(self.alert, fingerprint='another')])
        with b.connect() as holding:
            locked = holding.execute('SELECT key FROM queue ORDER BY created LIMIT 1 FOR UPDATE').fetchone()[0]
            row = b.claim()
            self.assertIsNotNone(row)
            self.assertNotEqual(row[0], locked)
        b.acknowledge(row)
        next_row = b.claim()
        self.assertEqual(next_row[0], locked)

    def test_resolution_arrives_while_other_replica_delivers(self):
        b.enqueue(self.alert)
        delivering, proceed = threading.Event(), threading.Event()
        statuses = []
        def remote(key, alert):
            statuses.append(alert['status'])
            if alert['status'] == 'firing':
                delivering.set()
                self.assertTrue(proceed.wait(5))
        b.deliver = remote
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            task = executor.submit(b.work_once)
            self.assertTrue(delivering.wait(5))
            b.enqueue(dict(self.alert, status='resolved'))
            self.assertFalse(b.work_once())
            proceed.set()
            self.assertTrue(task.result(timeout=5))
        with b.connect() as db:
            self.assertEqual(db.execute('SELECT done,revision,delivered_revision FROM queue').fetchone(), (0,2,1))
        self.assertTrue(b.work_once())
        self.assertEqual(statuses, ['firing','resolved'])

    def test_crashed_worker_lease_and_resolution_survive_reinitialization(self):
        b.enqueue(self.alert)
        stale = b.claim()
        b.enqueue(dict(self.alert, status='resolved'))
        b.initialize()
        with b.connect() as db: db.execute('UPDATE queue SET lease_until=0')
        active = b.claim()
        self.assertEqual(active[3], 2)
        b.acknowledge(stale)
        with b.connect() as db:
            self.assertEqual(db.execute('SELECT done,lease_token FROM queue').fetchone(), (0,active[-1]))
        b.acknowledge(active)
        b.enqueue(self.alert)
        self.assertIsNone(b.claim())

    def test_concurrent_replicas_enqueue_one_cycle(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(lambda _:b.enqueue(self.alert), range(32)))
        with b.connect() as db:
            self.assertEqual(db.execute('SELECT count(*),max(revision) FROM queue').fetchone(), (1,1))

if __name__ == '__main__':
    if not URL:
        raise SystemExit('Set TEST_QUEUE_DATABASE_URL to an isolated disposable database; refusing an unconfigured integration test.')
    unittest.main()
