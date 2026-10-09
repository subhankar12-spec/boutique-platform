"""Durable Alertmanager-to-ServiceNow bridge: SQLite single worker or PostgreSQL HA."""
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DB = os.environ.get("QUEUE_PATH", "/data/queue.db")
LOCK = threading.Lock()
LEASE_SECONDS = 60
MAX_ATTEMPTS = 12
WORKER_EXPECTED = False
LAST_WORKER_TICK = time.monotonic()


def postgres_url():
    return os.environ.get("QUEUE_DATABASE_URL", "")


class Database:
    """Small placeholder adapter; application SQL is identical on both stores."""
    def __init__(self, connection, postgres):
        self.connection, self.postgres = connection, postgres

    def execute(self, sql, params=()):
        return self.connection.execute(sql.replace("?", "%s") if self.postgres else sql, params)


@contextmanager
def connect():
    if postgres_url():
        import psycopg
        raw = psycopg.connect(postgres_url(), connect_timeout=5, application_name="boutique-incident-bridge", prepare_threshold=None)
        raw.execute("SET statement_timeout = '10s'")
        raw.execute("SET lock_timeout = '5s'")
        try:
            with raw:
                yield Database(raw, True)
        finally:
            raw.close()
    else:
        raw = sqlite3.connect(DB, timeout=15)
        raw.execute("PRAGMA journal_mode=WAL")
        try:
            with raw:
                yield Database(raw, False)
        finally:
            raw.close()


def initialize():
    with LOCK, connect() as db:
        # PostgreSQL advisory locking makes simultaneous replica startup safe.
        if db.postgres:
            db.execute("SELECT pg_advisory_xact_lock(71934218)")
        db.execute("""CREATE TABLE IF NOT EXISTS queue (
            key TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
            due DOUBLE PRECISION NOT NULL DEFAULT 0, created DOUBLE PRECISION NOT NULL,
            error TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
            delivered_revision INTEGER NOT NULL DEFAULT 0,
            lease_token TEXT NOT NULL DEFAULT '', lease_until DOUBLE PRECISION NOT NULL DEFAULT 0,
            blocked INTEGER NOT NULL DEFAULT 0)""")
        if not db.postgres:
            columns = {row[1] for row in db.execute("PRAGMA table_info(queue)")}
            for name, definition in {
                "revision": "INTEGER NOT NULL DEFAULT 1", "delivered_revision": "INTEGER NOT NULL DEFAULT 0",
                "lease_token": "TEXT NOT NULL DEFAULT ''", "lease_until": "DOUBLE PRECISION NOT NULL DEFAULT 0",
                "blocked": "INTEGER NOT NULL DEFAULT 0",
            }.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE queue ADD COLUMN {name} {definition}")
            db.execute("UPDATE queue SET delivered_revision=revision WHERE done=1 AND delivered_revision=0")
        db.execute("CREATE INDEX IF NOT EXISTS queue_delivery_due ON queue (done,blocked,due,lease_until,created)")


def secret(name):
    value = Path(os.environ[name]).read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("empty credential file")
    return value


def normalize(alert):
    if not isinstance(alert, dict) or alert.get("status") not in ("firing", "resolved"):
        raise ValueError("invalid alert status")
    fingerprint = alert.get("fingerprint", "")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", fingerprint):
        raise ValueError("invalid fingerprint")
    starts = alert.get("startsAt", "")
    if not isinstance(starts, str) or len(starts) > 64:
        raise ValueError("invalid startsAt")
    try:
        instant = datetime.fromisoformat(starts.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("startsAt requires timezone")
    except ValueError:
        raise ValueError("invalid startsAt") from None
    # Alertmanager changes endsAt while firing: it is not a new delivery revision.
    clean = {"status": alert["status"], "fingerprint": fingerprint, "startsAt": starts}
    for field in ("labels", "annotations"):
        values = alert.get(field, {})
        if not isinstance(values, dict) or len(values) > 64:
            raise ValueError("invalid alert metadata")
        if any(not isinstance(k, str) or not isinstance(v, str) or len(k) > 128 or len(v) > 4000 for k, v in values.items()):
            raise ValueError("invalid alert metadata")
        clean[field] = values
    if not clean["labels"].get("alertname"):
        raise ValueError("alert requires labels.alertname")
    return clean


def enqueue_many(alerts):
    clean = [normalize(alert) for alert in alerts]
    # An entire Alertmanager group commits before the HTTP acknowledgement.
    with LOCK, connect() as db:
        for alert in clean:
            key = hashlib.sha256((alert["fingerprint"] + alert["startsAt"]).encode()).hexdigest()
            payload = json.dumps(alert, sort_keys=True, separators=(",", ":"))
            db.execute("""INSERT INTO queue(key,payload,state,created) VALUES(?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,state=excluded.state,
                revision=queue.revision+1,done=0,due=0,attempts=0,blocked=0,error=''
                WHERE queue.state <> 'resolved' AND queue.payload <> excluded.payload""",
                       (key, payload, alert["status"], time.time()))


def enqueue(alert):
    enqueue_many([alert])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect rejected", headers, fp)


def request(method, path, body=None):
    base = os.environ["SERVICENOW_URL"].rstrip("/")
    url = urllib.parse.urlparse(base)
    local_mock = url.scheme == "http" and os.environ.get("ALLOW_HTTP_MOCK") == "true" and url.hostname in ("localhost", "127.0.0.1", "mock-receivers")
    if url.scheme != "https" and not local_mock:
        raise ValueError("ServiceNow requires HTTPS")
    if url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
        raise ValueError("invalid ServiceNow base URL")
    credential = base64.b64encode((os.environ["SERVICENOW_USERNAME"] + ":" + secret("SERVICENOW_PASSWORD_FILE")).encode()).decode()
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), method=method,
                                 headers={"Authorization": "Basic " + credential, "Content-Type": "application/json", "Accept": "application/json"})
    # Internal mock receivers must not be sent to an ambient external HTTP proxy.
    handlers = [NoRedirect()]
    if local_mock:
        handlers.append(urllib.request.ProxyHandler({}))
    with urllib.request.build_opener(*handlers).open(req, timeout=10) as response:
        # The API should return small incident metadata, never an unbounded response.
        data = response.read(1048577)
        if len(data) > 1048576:
            raise ValueError("ServiceNow response too large")
        return json.loads(data)["result"]


def deliver(key, alert):
    if os.environ.get("SERVICENOW_MODE", "table") == "scripted":
        request("POST", "/api/x_boutique/alerts/upsert", {
            "key": key, "status": alert["status"], "revision": alert.get("deliveryRevision", 1),
            "summary": str(alert.get("annotations", {}).get("summary", alert["labels"]["alertname"]))[:160],
            "description": json.dumps({"labels": alert["labels"], "annotations": alert.get("annotations", {})})[:4000]})
        return
    query = urllib.parse.urlencode({"sysparm_query": "correlation_id=" + key, "sysparm_fields": "sys_id,state", "sysparm_limit": "1"})
    records = request("GET", "/api/now/table/incident?" + query)
    if alert["status"] == "resolved":
        if records:
            request("PATCH", "/api/now/table/incident/" + records[0]["sys_id"], {
                "state": "6", "close_code": os.environ.get("SERVICENOW_CLOSE_CODE", "Solved (Permanently)"),
                "close_notes": "Alertmanager reports this alert cycle resolved."})
        return
    if records:
        return
    labels, notes = alert["labels"], alert.get("annotations", {})
    request("POST", "/api/now/table/incident", {
        "correlation_id": key, "short_description": str(notes.get("summary", labels["alertname"]))[:160],
        "description": json.dumps({"labels": labels, "annotations": notes})[:4000],
        "impact": "2", "urgency": "2", "category": "software"})


def claim():
    token, now = uuid.uuid4().hex, time.time()
    # SQLite is explicitly one replica. PostgreSQL workers lease different rows.
    with LOCK, connect() as db:
        suffix = " FOR UPDATE SKIP LOCKED" if db.postgres else ""
        row = db.execute("""SELECT key,payload,attempts,revision FROM queue
            WHERE done=0 AND blocked=0 AND due<=? AND lease_until<=?
            ORDER BY created LIMIT 1""" + suffix, (now, now)).fetchone()
        if row:
            db.execute("UPDATE queue SET lease_token=?,lease_until=? WHERE key=?", (token, now + LEASE_SECONDS, row[0]))
    return None if row is None else (*row, token)


def acknowledge(row, error=""):
    key, payload, attempts, revision, token = row
    with LOCK, connect() as db:
        if not error:
            db.execute("""UPDATE queue SET
                delivered_revision=CASE WHEN delivered_revision<? THEN ? ELSE delivered_revision END,
                done=CASE WHEN revision=? THEN 1 ELSE 0 END,
                attempts=0,error='',due=0,lease_token='',lease_until=0
                WHERE key=? AND lease_token=?""", (revision, revision, revision, key, token))
        else:
            attempts += 1
            db.execute("""UPDATE queue SET
                attempts=CASE WHEN revision=? THEN ? ELSE 0 END,
                blocked=CASE WHEN revision=? AND ?>=? THEN 1 ELSE 0 END,
                error=CASE WHEN revision=? THEN ? ELSE '' END,
                due=CASE WHEN revision=? THEN ? ELSE 0 END,
                lease_token='',lease_until=0 WHERE key=? AND lease_token=?""",
                       (revision, attempts, revision, attempts, MAX_ATTEMPTS, revision, error, revision,
                        time.time() + min(900, 2 ** min(attempts, 9)), key, token))


def work_once():
    row = claim()
    if row is None:
        return False
    key, payload, attempts, revision, token = row
    error = ""
    try:
        alert = json.loads(payload)
        alert["deliveryRevision"] = revision
        deliver(key, alert)
    except Exception as exc:
        error = type(exc).__name__
        print("incident delivery failed:", error, flush=True)
    # Acknowledgement only covers the claimed revision. A concurrent resolution stays pending.
    acknowledge(row, error)
    return True


def worker():
    global LAST_WORKER_TICK
    while True:
        try:
            LAST_WORKER_TICK = time.monotonic()
            if not work_once():
                time.sleep(1)
        except Exception as exc:
            print("queue worker failed:", type(exc).__name__, flush=True)
            time.sleep(5)


def queue_metrics():
    with connect() as db:
        return db.execute("""SELECT count(*),min(created),coalesce(sum(attempts),0),
            coalesce(sum(blocked),0) FROM queue WHERE done=0""").fetchone()


def retry(keys):
    if not isinstance(keys, list) or not 1 <= len(keys) <= 100 or any(not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{64}", key) for key in keys):
        raise ValueError("invalid retry keys")
    with LOCK, connect() as db:
        for key in keys:
            db.execute("UPDATE queue SET blocked=0,attempts=0,due=0,error='' WHERE key=? AND done=0", (key,))


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass

    def reply(self, code, text):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode())

    def do_GET(self):
        if self.path == "/health/live":
            return self.reply(200, "ok")
        if self.path not in ("/health/ready", "/metrics"):
            return self.reply(404, "missing")
        try:
            pending, oldest, retries, blocked = queue_metrics()
            age = time.monotonic() - LAST_WORKER_TICK
            if self.path == "/metrics":
                return self.reply(200, f"boutique_incident_pending {pending}\nboutique_incident_oldest_seconds {0 if oldest is None else max(0, time.time()-oldest)}\nboutique_incident_retry_attempts {retries}\nboutique_incident_dead_letters {blocked}\nboutique_incident_worker_heartbeat_age_seconds {age if WORKER_EXPECTED else 0}\n")
            if WORKER_EXPECTED and age > LEASE_SECONDS:
                return self.reply(503, "worker stalled")
            return self.reply(200, "ok")
        except Exception:
            self.reply(503, "queue unavailable")

    def do_POST(self):
        if self.path not in ("/alerts", "/retry"):
            return self.reply(404, "missing")
        try:
            authorized = hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + secret("WEBHOOK_TOKEN_FILE"))
        except Exception:
            return self.reply(503, "credential unavailable")
        if not authorized:
            return self.reply(401, "unauthorized")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 1048576:
                return self.reply(413, "body size")
            body = json.loads(self.rfile.read(size))
            if self.path == "/retry":
                retry(body["keys"])
            else:
                alerts = body["alerts"]
                if not isinstance(alerts, list) or len(alerts) > 100:
                    raise ValueError("alerts size")
                enqueue_many(alerts)
            self.reply(202, "queued")
        except (ValueError, KeyError, TypeError):
            self.reply(400, "invalid alerts")
        except Exception:
            self.reply(503, "queue unavailable")


if __name__ == "__main__":
    initialize()
    WORKER_EXPECTED = True
    threading.Thread(target=worker, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8084), Handler).serve_forever()
