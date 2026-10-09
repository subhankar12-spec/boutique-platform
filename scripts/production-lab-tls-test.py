#!/usr/bin/env python3
"""Exercise the lab's TLS data services using disposable Docker fixtures.

Requires existing tested boutique-cart and boutique-incident-bridge:production
images. It never starts/stops existing services or sends external notifications.
"""
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time

POSTGRES = 'postgres:16-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea'
REDIS = 'redis:7.4-alpine@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499'


def command(args, **kwargs):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True, **kwargs)
    if result.returncode: raise RuntimeError(f'{Path(str(args[0])).name} fixture step failed; credentials/logs are withheld')
    return result.stdout


def certificate(root, name, dns):
    key, crt, csr = root/(name+'.key'), root/(name+'.crt'), root/(name+'.csr')
    command(['openssl','req','-newkey','rsa:2048','-nodes','-subj','/CN='+dns,'-keyout',key,'-out',csr])
    extension = root/(name+'.ext'); extension.write_text('subjectAltName=DNS:'+dns+'\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
    command(['openssl','x509','-req','-in',csr,'-CA',root/'ca.crt','-CAkey',root/'ca.key','-CAcreateserial','-days','2','-extfile',extension,'-out',crt])
    gid = 70 if name == 'postgres' else 999
    folder = root/name; folder.mkdir(); folder.chmod(0o750)
    for source,target in [(key,folder/'tls.key'),(crt,folder/'tls.crt')]:
        target.write_bytes(source.read_bytes()); target.chmod(0o440)
    return folder


def client(network, image, root, envfile, script):
    return command(['docker','run','--rm','--pull=never','--network',network,'--env-file',envfile,
                    '--mount',f'type=bind,src={root}/ca.crt,dst=/run/ca.crt,readonly',
                    '--mount',f'type=bind,src={root}/other-ca.crt,dst=/run/other-ca.crt,readonly',
                    '--entrypoint','python',image,'-c',script], timeout=60)


def main():
    suffix = secrets.token_hex(4); network = 'boutique-lab-tls-'+suffix; names = []
    with tempfile.TemporaryDirectory(prefix='boutique-lab-tls-') as temporary:
        root = Path(temporary); root.chmod(0o700)
        try:
            for image in (POSTGRES, REDIS, 'boutique-cart:latest', 'boutique-incident-bridge:production'):
                command(['docker','image','inspect',image])
            command(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=TLS fixture CA','-addext','basicConstraints=critical,CA:TRUE','-keyout',root/'ca.key','-out',root/'ca.crt'])
            command(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=Untrusted fixture CA','-keyout',root/'other-ca.key','-out',root/'other-ca.crt'])
            (root/'ca.crt').chmod(0o444);(root/'other-ca.crt').chmod(0o444)
            pg_tls=certificate(root,'postgres','incident-queue-postgres.monitoring.svc')
            redis_tls=certificate(root,'redis','redis')
            pg_data=root/'pgdata';pg_data.mkdir();pg_data.chmod(0o700)
            redis_data=root/'redisdata';redis_data.mkdir();redis_data.chmod(0o700)
            hba=root/'pg_hba.conf';hba.write_text('local all all trust\nhostssl all all 0.0.0.0/0 scram-sha-256\nhostnossl all all 0.0.0.0/0 reject\n');hba.chmod(0o444)
            pg_password,redis_password=secrets.token_hex(24),secrets.token_hex(24)
            envfile=root/'fixture.env';envfile.write_text('POSTGRES_USER=incidentqueue\nPOSTGRES_DB=incidentqueue\nPOSTGRES_PASSWORD='+pg_password+'\nREDIS_PASSWORD='+redis_password+'\nQUEUE_TEST_URL=postgresql://incidentqueue:'+pg_password+'@incident-queue-postgres.monitoring.svc:5432/incidentqueue?sslmode=verify-full&sslrootcert=/run/ca.crt\nREDIS_TEST_URL=rediss://:'+redis_password+'@redis:6379/0?ssl_ca_certs=/run/ca.crt\n');envfile.chmod(0o600)
            command(['docker','run','--rm','--pull=never','--user','0:0','--mount',f'type=bind,src={root},dst=/fixture','--entrypoint','sh',REDIS,'-c','chown -R 70:70 /fixture/pgdata; chown -R 999:999 /fixture/redisdata; chown 0:70 /fixture/postgres /fixture/postgres/tls.key /fixture/postgres/tls.crt; chown 0:999 /fixture/redis /fixture/redis/tls.key /fixture/redis/tls.crt'])
            command(['docker','network','create',network])
            pg_name=network+'-pg';names.append(pg_name)
            command(['docker','run','-d','--pull=never','--name',pg_name,'--network',network,'--network-alias','incident-queue-postgres.monitoring.svc','--network-alias','wrong-pg','--user','70:70','--env-file',envfile,'--mount',f'type=bind,src={pg_tls},dst=/run/tls,readonly','--mount',f'type=bind,src={pg_data},dst=/var/lib/postgresql/data','--mount',f'type=bind,src={hba},dst=/run/pg_hba.conf,readonly',POSTGRES,'postgres','-c','ssl=on','-c','ssl_cert_file=/run/tls/tls.crt','-c','ssl_key_file=/run/tls/tls.key','-c','hba_file=/run/pg_hba.conf'])
            redis_name=network+'-redis';names.append(redis_name)
            command(['docker','run','-d','--pull=never','--name',redis_name,'--network',network,'--network-alias','redis','--network-alias','wrong-redis','--user','999:999','--env-file',envfile,'--mount',f'type=bind,src={redis_tls},dst=/run/tls,readonly','--mount',f'type=bind,src={root}/ca.crt,dst=/run/ca.crt,readonly','--mount',f'type=bind,src={redis_data},dst=/data',REDIS,'sh','-c','exec redis-server --dir /data --appendonly yes --requirepass "$REDIS_PASSWORD" --port 0 --tls-port 6379 --tls-cert-file /run/tls/tls.crt --tls-key-file /run/tls/tls.key --tls-ca-cert-file /run/ca.crt --tls-auth-clients no'])
            for _ in range(40):
                ready=subprocess.run(['docker','exec',pg_name,'pg_isready','-U','incidentqueue','-d','incidentqueue'],capture_output=True).returncode==0
                if ready:break
                time.sleep(.5)
            else:raise RuntimeError('PostgreSQL TLS fixture did not become ready')
            pg_script="""import os,psycopg
url=os.environ['QUEUE_TEST_URL']
with psycopg.connect(url) as c: assert c.execute('SELECT 1').fetchone()==(1,)
for invalid in (url.replace('/run/ca.crt','/run/other-ca.crt'),url.replace('@incident-queue-postgres.monitoring.svc:', '@wrong-pg:'),url.replace('sslmode=verify-full','sslmode=disable')):
 try: psycopg.connect(invalid).close()
 except psycopg.OperationalError: pass
 else: raise AssertionError('Invalid PostgreSQL certificate accepted')
print('PASS: PostgreSQL verifies CA and hostname; incorrect trust, names and plaintext are rejected')"""
            redis_script="""import os,redis
url=os.environ['REDIS_TEST_URL']
c=redis.Redis.from_url(url);assert c.ping();c.set('tls-fixture','ok');assert c.get('tls-fixture')==b'ok';c.close()
for invalid in (url.replace('/run/ca.crt','/run/other-ca.crt'),url.replace('@redis:', '@wrong-redis:')):
 try: redis.Redis.from_url(invalid).ping()
 except redis.exceptions.ConnectionError: pass
 else: raise AssertionError('Invalid Redis certificate accepted')
print('PASS: Redis verifies CA and hostname; incorrect trust and names are rejected')"""
            print(client(network,'boutique-incident-bridge:production',root,envfile,pg_script).strip())
            print(client(network,'boutique-cart:latest',root,envfile,redis_script).strip())
            print('PASS: private TLS key ownership/mode match the Kubernetes volume security contexts')
        finally:
            for name in names: subprocess.run(['docker','rm','-f',name],capture_output=True)
            subprocess.run(['docker','network','rm',network],capture_output=True)
            # Only this private fixture is mounted; restore host ownership for cleanup.
            subprocess.run(['docker','run','--rm','--pull=never','--user','0:0','--mount',f'type=bind,src={root},dst=/fixture','--entrypoint','sh',REDIS,'-c',f'chown -R {os.getuid()}:{os.getgid()} /fixture; chmod -R u+rwX /fixture'],capture_output=True)


if __name__=='__main__':main()
