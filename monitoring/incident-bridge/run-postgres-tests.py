#!/usr/bin/env python3
"""Exercise the adapter image against a disposable, isolated real PostgreSQL."""
import argparse
import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

POSTGRES = 'postgres@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True, help='Already built incident bridge image to test')
    args = parser.parse_args()
    suffix = secrets.token_hex(6)
    network, name = 'incident-test-'+suffix, 'incident-postgres-test-'+suffix
    network_created = container_created = False
    try:
        with tempfile.TemporaryDirectory(prefix='incident-queue-test-') as folder:
            root = Path(folder)
            root.chmod(0o700)
            password = secrets.token_hex(32)
            pg_env = root/'postgres.env'
            pg_env.write_text('POSTGRES_USER=queue_test\nPOSTGRES_PASSWORD='+password+'\nPOSTGRES_DB=queue_test\n')
            pg_env.chmod(0o600)
            app_env = root/'adapter.env'
            # Plaintext PostgreSQL is confined to this temporary isolated test network.
            app_env.write_text('TEST_QUEUE_DATABASE_URL=postgresql://queue_test:'+password+'@'+name+':5432/queue_test\n')
            app_env.chmod(0o600)
            test_file = root/'test_postgres.py'
            test_file.write_bytes(Path(__file__).with_name('test_postgres.py').read_bytes())
            test_file.chmod(0o444)
            subprocess.run(['docker','network','create',network], check=True, stdout=subprocess.DEVNULL)
            network_created = True
            subprocess.run(['docker','run','-d','--name',name,'--network',network,'--env-file',str(pg_env),POSTGRES],check=True,stdout=subprocess.DEVNULL)
            container_created = True
            for attempt in range(60):
                ready = subprocess.run(['docker','exec',name,'pg_isready','-U','queue_test','-d','queue_test'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                if ready.returncode == 0: break
                time.sleep(.5)
            else:
                raise RuntimeError('Disposable PostgreSQL did not become ready')
            subprocess.run(['docker','run','--rm','--network',network,'--env-file',str(app_env),
                            '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
                            '--mount','type=bind,src='+str(test_file)+',dst=/app/test_postgres.py,readonly',
                            '--entrypoint','python',args.image,'-m','unittest','-v','test_postgres'],check=True)
            print('Disposable PostgreSQL integration checks passed.')
    finally:
        if container_created:
            subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if network_created:
            subprocess.run(['docker','network','rm',network],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__ == '__main__': main()
