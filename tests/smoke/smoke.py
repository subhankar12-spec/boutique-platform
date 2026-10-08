import concurrent.futures,http.cookiejar,json,os,time,urllib.request,urllib.error
base=os.environ.get('BASE_URL','http://localhost:8080').rstrip('/')
def browser():return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
a,b=browser(),browser()
def req(c,path,method='GET',body=None,key=None,origin=True):
    h={'Origin':base} if origin else {}
    if key:h['Idempotency-Key']=key
    if body is not None:h['Content-Type']='application/json'
    r=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else (b'' if method=='POST' else None),headers=h,method=method)
    try:
        with c.open(r,timeout=10) as res:return res.status,json.load(res)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
for _ in range(60):
    try:
        if req(a,'/health/ready')[0]==200:break
    except Exception:pass
    time.sleep(2)
else:raise SystemExit('Readiness failed')
assert len(req(a,'/api/products')[1])==4
assert req(a,'/api/cart')[1]['items']==[]
assert req(a,'/api/cart/items/mug','PUT',{'quantity':2})[0]==200
assert req(a,'/api/cart/items/mug','PUT',{'quantity':21})[0]==400
assert req(a,'/api/cart/items/mug','PUT',{'quantity':1},origin=False)[0]==403
assert req(a,'/api/cart/items/missing','PUT',{'quantity':1})[0]==404
assert req(b,'/api/cart')[1]['items']==[]
status,o=req(a,'/api/orders','POST',key='smoke-checkout-001');assert status==200,(status,o)
assert o['total']==3600 and o['currency']=='USD'
assert req(a,'/api/orders','POST',key='smoke-checkout-001')[1]['id']==o['id']
assert req(a,'/api/orders/'+o['id'])[1]['total']==3600
assert req(b,'/api/orders/'+o['id'])[0]==404
assert req(b,'/api/orders','POST',key='smoke-empty-001')[0]==409
cookie='; '.join(f'{c.name}={c.value}' for h in a.handlers if hasattr(h,'cookiejar') for c in h.cookiejar)
def retry(_):
    with urllib.request.urlopen(urllib.request.Request(base+'/api/orders',data=b'',headers={'Origin':base,'Cookie':cookie,'Idempotency-Key':'smoke-concurrent-001'},method='POST'),timeout=15) as r:return json.load(r)['id']
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:assert len(set(pool.map(retry,range(4))))==1
assert req(a,'/api/cart/items/mug','DELETE')[1]['items']==[]
print('PASS: browse, cart, validation, origin checks, session isolation, server pricing, checkout, repeat and concurrent idempotency, order ownership, empty cart, deletion')
