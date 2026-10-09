"""Local synthetic Slack and ServiceNow receivers; never a production receiver."""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

incidents, cycles, events = {}, {}, []
lock = threading.Lock()


def scripted_upsert(data):
    key, status, revision = data['key'], data['status'], data['revision']
    cycle = cycles.setdefault(key, {'status':status, 'revision':revision})
    if cycle['status'] != 'resolved' and revision > cycle['revision']:
        cycle.update(status=status, revision=revision)
    existing = next((i for i in incidents.values() if i['correlation_id'] == key), None)
    if cycle['status'] != 'resolved' and existing is None:
        ident = str(len(incidents)+1)
        existing = {'sys_id':ident, 'correlation_id':key, 'state':'1', 'short_description':data.get('summary','')}
        incidents[ident] = existing
        events.append({'receiver':'servicenow','operation':'create','sys_id':ident})
    if cycle['status'] == 'resolved' and existing and existing['state'] not in ('6','7'):
        existing['state'] = '6'
        events.append({'receiver':'servicenow','operation':'resolve','sys_id':existing['sys_id']})
    return {'status':cycle['status']}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def reply(self, value):
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def do_GET(self):
        with lock:
            if self.path == '/events':
                return self.reply({'events':events,'incidents':list(incidents.values())})
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('sysparm_query',[''])[0].removeprefix('correlation_id=')
            self.reply({'result':[i for i in incidents.values() if i['correlation_id'] == query]})

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with lock:
            if self.path == '/slack':
                events.append({'receiver':'slack','text':data.get('text','')+' '+ ' '.join(str(a.get('title',''))+' '+str(a.get('text','')) for a in data.get('attachments',[]))})
                self.send_response(200); self.end_headers(); self.wfile.write(b'ok'); return
            if self.path == '/api/x_boutique/alerts/upsert':
                return self.reply({'result':scripted_upsert(data)})
            ident = str(len(incidents)+1)
            incidents[ident] = {**data,'sys_id':ident,'state':'1'}
            events.append({'receiver':'servicenow','operation':'create','sys_id':ident})
            self.reply({'result':incidents[ident]})

    def do_PATCH(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with lock:
            ident = self.path.rsplit('/',1)[-1]
            incidents[ident].update(data)
            events.append({'receiver':'servicenow','operation':'resolve','sys_id':ident})
            self.reply({'result':incidents[ident]})


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0',18080),Handler).serve_forever()
