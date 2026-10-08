import json, threading, urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
incidents={}; events=[]; lock=threading.Lock()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,value):
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(json.dumps(value).encode())
    def do_GET(self):
        with lock:
            if self.path=="/events": return self.reply({"events":events,"incidents":list(incidents.values())})
            query=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("sysparm_query",[""])[0].removeprefix("correlation_id=")
            self.reply({"result":[i for i in incidents.values() if i["correlation_id"]==query]})
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with lock:
            if self.path=="/slack":
                events.append({"receiver":"slack","text":data.get("text","")+" "+" ".join(str(a.get("title",""))+" "+str(a.get("text","")) for a in data.get("attachments",[]))}); self.send_response(200); self.end_headers(); self.wfile.write(b"ok"); return
            ident=str(len(incidents)+1); incidents[ident]={**data,"sys_id":ident,"state":"1"}; events.append({"receiver":"servicenow","operation":"create","sys_id":ident}); self.reply({"result":incidents[ident]})
    def do_PATCH(self):
        data=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with lock:
            ident=self.path.rsplit("/",1)[-1]; incidents[ident].update(data); events.append({"receiver":"servicenow","operation":"resolve","sys_id":ident}); self.reply({"result":incidents[ident]})
ThreadingHTTPServer(("0.0.0.0",18080),Handler).serve_forever()
