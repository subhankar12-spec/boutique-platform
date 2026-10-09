import importlib.util, tempfile, unittest, os, json
from pathlib import Path
spec=importlib.util.spec_from_file_location("bridge",Path(__file__).with_name("bridge.py"))
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
class QueueFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); b.DB=self.temp.name+"/queue.db"; b.initialize()
        self.a={"fingerprint":"1234","startsAt":"2026-10-08T00:00:00Z","status":"firing","labels":{"alertname":"ServiceDown"}}
        self.calls=[]; self.original=b.deliver; b.deliver=lambda key,alert:self.calls.append(alert["status"])
    def tearDown(self): b.deliver=self.original; self.temp.cleanup()
class QueueTests(QueueFixture):
    def test_duplicate_and_resolution(self):
        b.enqueue(self.a); b.enqueue(self.a); b.work_once(); self.assertEqual(self.calls,["firing"])
        b.enqueue(dict(self.a,status="resolved")); b.work_once(); b.enqueue(self.a)
        self.assertEqual(self.calls,["firing","resolved"]); self.assertFalse(b.work_once())
    def test_retry_survives_reinitialize(self):
        b.enqueue(self.a)
        def fail(*args): raise ConnectionError()
        b.deliver=fail; b.work_once(); b.initialize()
        with b.connect() as db:
            self.assertEqual(db.execute("SELECT done,attempts FROM queue").fetchone(),(0,1)); db.execute("UPDATE queue SET due=0")
        b.deliver=lambda key,alert:self.calls.append(alert["status"]); b.work_once()
        self.assertEqual(self.calls,["firing"])
    def test_new_cycle_creates_distinct_queue_item(self):
        b.enqueue(self.a); b.enqueue(dict(self.a,startsAt="2026-10-09T00:00:00Z"))
        with b.connect() as db: self.assertEqual(db.execute("SELECT count(*) FROM queue").fetchone()[0],2)
    def test_resolved_before_firing(self):
        b.enqueue(dict(self.a,status="resolved")); b.enqueue(self.a); b.work_once()
        self.assertEqual(self.calls,["resolved"])

class ApiMappingTests(QueueFixture):
    def test_lost_create_response_looks_up_existing_incident(self):
        original=b.request; rows=[]; posts=[]
        def remote(method,path,body=None):
            if method=='GET': return rows
            if method=='POST':
                rows.append({'sys_id':'mock-id','state':'1'}); posts.append(body)
                raise TimeoutError('response lost after commit')
            if method=='PATCH': self.assertEqual(body['state'],'6'); return {'sys_id':'mock-id'}
        b.request=remote; b.deliver=self.original
        try:
            b.enqueue(self.a); b.work_once()
            with b.connect() as db: db.execute('UPDATE queue SET due=0')
            b.work_once(); self.assertEqual(len(posts),1)
            b.enqueue(dict(self.a,status='resolved')); b.work_once()
            with b.connect() as db:self.assertEqual(db.execute('SELECT done FROM queue').fetchone()[0],1)
        finally:b.request=original
    def test_scripted_upsert_mapping(self):
        original=b.request; calls=[]; b.request=lambda method,path,body:calls.append((method,path,body))
        b.deliver=self.original; os.environ['SERVICENOW_MODE']='scripted'
        try:
            b.enqueue(self.a); b.work_once()
            self.assertEqual(calls[0][1],'/api/x_boutique/alerts/upsert');self.assertEqual(calls[0][2]['status'],'firing')
        finally:b.request=original;os.environ.pop('SERVICENOW_MODE')

class WebhookTests(QueueFixture):
    def test_authentication_rotation_and_persistence(self):
        import threading,urllib.request,urllib.error
        token=Path(self.temp.name)/'token'; token.write_text('test-only-token');os.environ['WEBHOOK_TOKEN_FILE']=str(token)
        server=b.ThreadingHTTPServer(('127.0.0.1',0),b.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def post(token_value,body):
            request=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/alerts',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token_value})
            try:
                with urllib.request.urlopen(request) as response:return response.status
            except urllib.error.HTTPError as response:return response.code
        try:
            self.assertEqual(post('wrong',{'alerts':[self.a]}),401)
            self.assertEqual(post('test-only-token',{'alerts':[self.a]}),202)
            with b.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM queue').fetchone()[0],1)
            token.write_text('rotated-test-token')
            self.assertEqual(post('test-only-token',{'alerts':[self.a]}),401)
            self.assertEqual(post('rotated-test-token',{'alerts':[self.a]}),202)
            self.assertEqual(post('rotated-test-token',{'alerts':[{}]}),400)
        finally:server.shutdown();server.server_close();os.environ.pop('WEBHOOK_TOKEN_FILE')


class DeliverySafetyTests(QueueFixture):
    def test_resolution_during_delivery_is_not_acknowledged_with_firing(self):
        b.enqueue(self.a)
        def remote(key, alert):
            self.calls.append(alert['status'])
            if alert['status'] == 'firing':
                b.enqueue(dict(self.a, status='resolved'))
        b.deliver = remote
        b.work_once()
        with b.connect() as db:
            self.assertEqual(db.execute('SELECT done,revision,delivered_revision FROM queue').fetchone(), (0,2,1))
        b.work_once()
        self.assertEqual(self.calls, ['firing','resolved'])
        self.assertFalse(b.work_once())

    def test_group_is_atomic_when_later_alert_is_invalid(self):
        with self.assertRaises(ValueError):
            b.enqueue_many([self.a, {}])
        with b.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM queue').fetchone()[0], 0)

    def test_firing_refresh_does_not_duplicate_delivery(self):
        b.enqueue(dict(self.a, endsAt='2026-10-08T00:05:00Z'))
        b.work_once()
        b.enqueue(dict(self.a, endsAt='2026-10-08T00:10:00Z'))
        self.assertFalse(b.work_once())
        self.assertEqual(self.calls, ['firing'])

    def test_expired_lease_is_recovered_and_stale_owner_cannot_acknowledge(self):
        b.enqueue(self.a)
        first = b.claim()
        self.assertIsNone(b.claim())
        with b.connect() as db:
            db.execute('UPDATE queue SET lease_until=0')
        second = b.claim()
        self.assertNotEqual(first[-1], second[-1])
        b.acknowledge(first)
        with b.connect() as db:
            self.assertEqual(db.execute('SELECT done,lease_token FROM queue').fetchone(), (0,second[-1]))
        b.acknowledge(second)
        self.assertFalse(b.work_once())

    def test_exhausted_retries_are_durable_and_can_be_requeued(self):
        b.enqueue(self.a)
        def fail(*args): raise ConnectionError()
        b.deliver = fail
        for _ in range(b.MAX_ATTEMPTS):
            self.assertTrue(b.work_once())
            with b.connect() as db:
                db.execute('UPDATE queue SET due=0')
        b.initialize()
        self.assertFalse(b.work_once())
        self.assertEqual(b.queue_metrics()[3], 1)
        with b.connect() as db:
            key = db.execute('SELECT key FROM queue').fetchone()[0]
        b.retry([key])
        b.deliver = lambda key, alert: self.calls.append(alert['status'])
        self.assertTrue(b.work_once())
        self.assertEqual(self.calls, ['firing'])
        self.assertEqual(b.queue_metrics()[0], 0)

    def test_failed_firing_does_not_delay_new_resolution(self):
        b.enqueue(self.a)
        def remote(key, alert):
            if alert['status'] == 'firing':
                b.enqueue(dict(self.a, status='resolved'))
                raise TimeoutError()
            self.calls.append(alert['status'])
        b.deliver = remote
        b.work_once()
        self.assertTrue(b.work_once())
        self.assertEqual(self.calls, ['resolved'])

    def test_invalid_timestamp_and_unbounded_metadata_are_rejected(self):
        for alert in [dict(self.a, startsAt='not-a-date'), dict(self.a, startsAt='2026-10-08T00:00:00'),
                      dict(self.a, annotations={'note':'x'*4001})]:
            with self.assertRaises(ValueError): b.enqueue(alert)

class MigrationTests(unittest.TestCase):
    def test_existing_sqlite_queue_keeps_completed_and_pending_work(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            old_db = b.DB; b.DB = folder+'/queue.db'
            try:
                with sqlite3.connect(b.DB) as db:
                    db.execute("CREATE TABLE queue (key TEXT PRIMARY KEY,payload TEXT NOT NULL,state TEXT NOT NULL,done INTEGER DEFAULT 0,attempts INTEGER DEFAULT 0,due REAL DEFAULT 0,created REAL NOT NULL,error TEXT DEFAULT '')")
                    db.execute("INSERT INTO queue VALUES('completed','{}','resolved',1,0,0,1,'')")
                    db.execute("INSERT INTO queue VALUES('pending','{}','firing',0,1,0,2,'ConnectionError')")
                b.initialize(); b.initialize()
                with b.connect() as db:
                    self.assertEqual(db.execute('SELECT key,done,revision,delivered_revision,attempts FROM queue ORDER BY key').fetchall(),
                                     [('completed',1,1,1,0),('pending',0,1,0,1)])
            finally: b.DB=old_db


class WorkerHealthTests(QueueFixture):
    def test_stalled_worker_is_not_ready_but_ingestion_remains_available(self):
        import threading, urllib.request, urllib.error, time
        token = Path(self.temp.name)/'token'; token.write_text('test-only-token')
        os.environ['WEBHOOK_TOKEN_FILE'] = str(token)
        old_expected, old_tick = b.WORKER_EXPECTED, b.LAST_WORKER_TICK
        b.WORKER_EXPECTED = True; b.LAST_WORKER_TICK = time.monotonic()-b.LEASE_SECONDS-1
        server = b.ThreadingHTTPServer(('127.0.0.1',0),b.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base = 'http://127.0.0.1:'+str(server.server_port)
        try:
            with self.assertRaises(urllib.error.HTTPError) as failed:
                urllib.request.urlopen(base+'/health/ready')
            self.assertEqual(failed.exception.code,503)
            with urllib.request.urlopen(base+'/health/live') as response:
                self.assertEqual(response.status,200)
            request = urllib.request.Request(base+'/alerts',data=json.dumps({'alerts':[self.a]}).encode(),headers={'Authorization':'Bearer test-only-token'})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.status,202)
            b.LAST_WORKER_TICK = time.monotonic()
            with urllib.request.urlopen(base+'/health/ready') as response:
                self.assertEqual(response.status,200)
        finally:
            server.shutdown(); server.server_close(); os.environ.pop('WEBHOOK_TOKEN_FILE')
            b.WORKER_EXPECTED, b.LAST_WORKER_TICK = old_expected, old_tick


class LocalReceiverTests(QueueFixture):
    def test_internal_mock_bypasses_ambient_external_proxy(self):
        import threading
        from unittest.mock import patch
        class Receiver(b.BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
                self.wfile.write(b'{"result":{"status":"accepted"}}')
        password = Path(self.temp.name)/'password'; password.write_text('test-only-password')
        server = b.ThreadingHTTPServer(('127.0.0.1',0),Receiver)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with patch.dict(os.environ,{
                'ALLOW_HTTP_MOCK':'true','SERVICENOW_URL':'http://127.0.0.1:'+str(server.server_port),
                'SERVICENOW_USERNAME':'test-only','SERVICENOW_PASSWORD_FILE':str(password),
                'http_proxy':'http://127.0.0.1:1','HTTP_PROXY':'http://127.0.0.1:1','no_proxy':'','NO_PROXY':'',
            }):
                self.assertEqual(b.request('POST','/api/x_boutique/alerts/upsert',{'key':'a'*64}), {'status':'accepted'})
        finally: server.shutdown(); server.server_close()

if __name__ == '__main__': unittest.main()
