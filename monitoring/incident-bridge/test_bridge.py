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

if __name__=="__main__": unittest.main()
