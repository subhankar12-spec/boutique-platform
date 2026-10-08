"""Durable Alertmanager to ServiceNow ITSM adapter. One replica per SQLite volume."""
import base64, hashlib, hmac, json, os, sqlite3, threading, time, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
from pathlib import Path
DB = os.environ.get("QUEUE_PATH", "/data/queue.db")
LOCK = threading.Lock()
@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=15)
    db.execute("PRAGMA journal_mode=WAL")
    try:
        with db: yield db
    finally: db.close()

def initialize():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS queue (key TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL, done INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0, due REAL DEFAULT 0, created REAL NOT NULL, error TEXT DEFAULT '')")

def secret(name):
    value = Path(os.environ[name]).read_text(encoding="utf-8").strip()
    if not value: raise ValueError("empty credential file")
    return value

def enqueue(alert):
    if alert.get("status") not in ("firing", "resolved") or not alert.get("fingerprint") or not alert.get("startsAt"):
        raise ValueError("alert requires status, fingerprint and startsAt")
    labels = alert.get("labels", {})
    if not isinstance(labels, dict) or not labels.get("alertname"):
        raise ValueError("alert requires labels.alertname")
    key = hashlib.sha256((str(alert["fingerprint"]) + str(alert["startsAt"])).encode()).hexdigest()
    payload = json.dumps(alert)
    with LOCK, connect() as db:
        old = db.execute("SELECT state,payload FROM queue WHERE key=?", (key,)).fetchone()
        # A delayed firing notification must never reopen a resolved alert cycle.
        if old and (old[0] == "resolved" or old[1] == payload):
            return
        db.execute("INSERT INTO queue(key,payload,state,created) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,state=excluded.state,done=0,due=0,attempts=0", (key,payload,alert["status"],time.time()))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url,code,"Redirect rejected",headers,fp)

def request(method, path, body=None):
    base = os.environ["SERVICENOW_URL"].rstrip("/")
    url = urllib.parse.urlparse(base)
    if url.scheme != "https" and not (os.environ.get("ALLOW_HTTP_MOCK") == "true" and url.hostname in ("localhost", "127.0.0.1", "mock-receivers")):
        raise ValueError("ServiceNow requires HTTPS")
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("invalid ServiceNow base URL")
    credential = base64.b64encode((os.environ["SERVICENOW_USERNAME"]+":"+secret("SERVICENOW_PASSWORD_FILE")).encode()).decode()
    req = urllib.request.Request(base+path, data=None if body is None else json.dumps(body).encode(), method=method, headers={"Authorization":"Basic "+credential,"Content-Type":"application/json","Accept":"application/json"})
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=10) as response:
        return json.load(response)["result"]

def deliver(key, alert):
    if os.environ.get("SERVICENOW_MODE", "table") == "scripted":
        request("POST", "/api/x_boutique/alerts/upsert", {"key":key,"status":alert["status"],"summary":str(alert.get("annotations",{}).get("summary",alert["labels"]["alertname"]))[:160],"description":json.dumps({"labels":alert["labels"],"annotations":alert.get("annotations",{})})[:4000]})
        return
    query = urllib.parse.urlencode({"sysparm_query":"correlation_id="+key,"sysparm_fields":"sys_id,state","sysparm_limit":"1"})
    records = request("GET", "/api/now/table/incident?"+query)
    if alert["status"] == "resolved":
        if records:
            request("PATCH", "/api/now/table/incident/"+records[0]["sys_id"], {"state":"6","close_code":os.environ.get("SERVICENOW_CLOSE_CODE","Solved (Permanently)"),"close_notes":"Alertmanager reports this alert cycle resolved."})
        return
    if records:
        return
    labels, notes = alert["labels"], alert.get("annotations", {})
    request("POST", "/api/now/table/incident", {"correlation_id":key,"short_description":str(notes.get("summary",labels["alertname"]))[:160],"description":json.dumps({"labels":labels,"annotations":notes})[:4000],"impact":"2","urgency":"2","category":"software"})

def work_once():
    # Serialize delivery and ingestion so a resolved update cannot be lost during acknowledgement.
    with LOCK, connect() as db:
        row = db.execute("SELECT key,payload,attempts FROM queue WHERE done=0 AND due<=? ORDER BY created LIMIT 1", (time.time(),)).fetchone()
        if not row:
            return False
        try:
            deliver(row[0],json.loads(row[1]))
            db.execute("UPDATE queue SET done=1,error='' WHERE key=?", (row[0],))
        except Exception as exc:
            attempts = row[2]+1
            db.execute("UPDATE queue SET attempts=?,due=?,error=? WHERE key=?", (attempts,time.time()+min(900,2**min(attempts,9)),type(exc).__name__,row[0]))
            print("incident delivery failed:",type(exc).__name__,flush=True)
        return True

def worker():
    while True:
        try:
            if not work_once(): time.sleep(1)
        except Exception as exc:
            print("queue worker failed:",type(exc).__name__,flush=True); time.sleep(5)

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup(); self.connection.settimeout(10)
    def log_message(self,*args): pass
    def reply(self,code,text):
        self.send_response(code); self.send_header("Content-Type","text/plain; version=0.0.4; charset=utf-8"); self.end_headers(); self.wfile.write(text.encode())
    def do_GET(self):
        if self.path == "/health/live": return self.reply(200,"ok")
        try:
            with connect() as db:
                pending, oldest, retries = db.execute("SELECT count(*),min(created),coalesce(sum(attempts),0) FROM queue WHERE done=0").fetchone()
            if self.path == "/metrics":
                self.reply(200,f"boutique_incident_pending {pending}\nboutique_incident_oldest_seconds {0 if oldest is None else time.time()-oldest}\nboutique_incident_retry_attempts {retries}\n")
            elif self.path in ("/health/live","/health/ready"): self.reply(200,"ok")
            else: self.reply(404,"missing")
        except Exception: self.reply(503,"queue unavailable")
    def do_POST(self):
        if self.path != "/alerts": return self.reply(404,"missing")
        if not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+secret("WEBHOOK_TOKEN_FILE")):
            return self.reply(401,"unauthorized")
        try:
            size=int(self.headers.get("Content-Length","0"))
            if size<=0 or size>1048576: return self.reply(413,"body size")
            alerts=json.loads(self.rfile.read(size))["alerts"]
            if not isinstance(alerts,list) or len(alerts)>100: raise ValueError("alerts size")
            for alert in alerts: enqueue(alert)
            self.reply(202,"queued")
        except (ValueError,KeyError,TypeError): self.reply(400,"invalid alerts")
        except Exception: self.reply(503,"queue unavailable")

if __name__ == "__main__":
    initialize(); threading.Thread(target=worker,daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0",8084),Handler).serve_forever()
