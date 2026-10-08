#!/usr/bin/env python3
"""Generate secrets in Kubernetes directly; never write secret values into Git."""
import json,secrets,subprocess,sys
namespace='boutique-'+(sys.argv[1] if len(sys.argv)>1 else 'dev')
assert namespace in ['boutique-dev','boutique-staging','boutique-production']
subprocess.run(['kubectl','create','namespace',namespace],capture_output=True)
def exists(name):return subprocess.run(['kubectl','-n',namespace,'get','secret',name],capture_output=True).returncode==0
def apply(name,data):
    if exists(name):print('Preserved',name);return
    doc={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':namespace},'type':'Opaque','stringData':data}
    subprocess.run(['kubectl','apply','-f','-'],input=json.dumps(doc),text=True,check=True,stdout=subprocess.DEVNULL)
    print('Created',name)
password=secrets.token_hex(32)
if not exists('redis-auth') and exists('cart-redis'):raise SystemExit('Partial Redis secret state: restore matching credentials before retrying')
if exists('redis-auth') and not exists('cart-redis'):raise SystemExit('Partial Redis secret state: restore matching credentials before retrying')
apply('redis-auth',{'password':password});apply('cart-redis',{'url':'redis://:'+password+'@redis:6379/0'})
apply('frontend-session',{'secret':secrets.token_hex(32)})
apply('orders-database',{'url':'jdbc:postgresql://postgres:5432/boutique','username':'boutique','password':secrets.token_hex(32)})
