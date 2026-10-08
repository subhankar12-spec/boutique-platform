#!/usr/bin/env python3
"""Local mock-only integration check. Never reads live receiver credentials."""
import datetime,json,time,urllib.request,urllib.error,uuid
BASE="http://127.0.0.1:18080"
def req(url,data=None):
    r=urllib.request.Request(url,data=None if data is None else json.dumps(data).encode(),headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=5) as response:
        body=response.read(); return json.loads(body) if body else None
def wait(predicate,seconds=60):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try: value=req(BASE+"/events")
        except (urllib.error.URLError,ConnectionError,TimeoutError):
            time.sleep(1); continue
        if predicate(value): return value
        time.sleep(1)
    raise AssertionError("Mock notification delivery timed out")
now=datetime.datetime.now(datetime.timezone.utc)
ident="DeliveryTest"+uuid.uuid4().hex[:8]
alert={"labels":{"alertname":ident,"environment":"production","severity":"critical","service":"synthetic","cluster":"local-test"},"annotations":{"summary":ident},"startsAt":now.isoformat(),"endsAt":(now+datetime.timedelta(minutes=10)).isoformat()}
req("http://127.0.0.1:9093/api/v2/alerts",[alert])
firing=wait(lambda v:any(i["short_description"]==ident for i in v["incidents"]) and any(ident in e.get("text","") for e in v["events"]))
matching=[i for i in firing["incidents"] if i["short_description"]==ident];assert len(matching)==1
req("http://127.0.0.1:9093/api/v2/alerts",[alert])
alert["endsAt"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
req("http://127.0.0.1:9093/api/v2/alerts",[alert])
resolved=wait(lambda v:any(i["short_description"]==ident and i["state"]=="6" for i in v["incidents"]) and any(ident in e.get("text","") and "RESOLVED" in e.get("text","") for e in v["events"]))
assert len([i for i in resolved["incidents"] if i["short_description"]==ident])==1
print("PASS: grouped Slack delivery, one ServiceNow incident, duplicate firing, incident resolution (local mocks only)")
