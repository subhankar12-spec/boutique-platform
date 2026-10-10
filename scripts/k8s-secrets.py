#!/usr/bin/env python3
"""Create missing local Kubernetes credentials; preserve existing secrets."""
import argparse
import base64
import json
import secrets
import subprocess


def kubectl(*arguments, document=None):
    return subprocess.run(['kubectl', *arguments],
                          input=None if document is None else json.dumps(document),
                          text=True, capture_output=True, check=True).stdout


def provision(environment):
    if environment not in ('dev', 'staging', 'production'):
        raise ValueError('Select dev, staging or production')
    namespace = 'boutique-' + environment
    # --ignore-not-found distinguishes absence from API/auth failures.
    if not kubectl('get', 'namespace', namespace, '--ignore-not-found', '-o', 'name').strip():
        kubectl('create', 'namespace', namespace)
    current = json.loads(kubectl('-n', namespace, 'get', 'secrets', '-o', 'json'))
    existing = {item['metadata']['name'] for item in current['items']}
    if ('redis-auth' in existing) != ('cart-redis' in existing):
        raise ValueError('Partial Redis secret state: restore matching credentials before retrying')
    password = secrets.token_hex(32)
    wanted = {
        'redis-auth': {'password': password},
        'cart-redis': {'url': 'redis://:' + password + '@redis:6379/0'},
        'frontend-session': {'secret': secrets.token_hex(32)},
        'orders-database': {'url': 'jdbc:postgresql://postgres:5432/boutique',
                            'username': 'boutique', 'password': secrets.token_hex(32)},
    }
    for name, values in wanted.items():
        if name in existing:
            print('Preserved', name)
            continue
        document = {'apiVersion': 'v1', 'kind': 'Secret',
                    'metadata': {'name': name, 'namespace': namespace}, 'type': 'Opaque',
                    'data': {key: base64.b64encode(value.encode()).decode() for key, value in values.items()}}
        # Create cannot overwrite a secret created concurrently by another operator.
        kubectl('create', '-f', '-', document=document)
        print('Created', name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=('dev', 'staging', 'production'), nargs='?', default='dev')
    args = parser.parse_args()
    try:
        provision(args.environment)
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError):
        # Native errors may contain object values; report no stderr or input body.
        parser.exit(1, 'Secret setup stopped; check cluster access and existing credential state locally.\n')


if __name__ == '__main__':
    main()
