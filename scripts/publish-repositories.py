#!/usr/bin/env python3
"""Create private GitHub repositories and push committed main branches.
Explicit invocation publishes code. Requires GitHub API and HTTPS Git access.
Existing repositories are preserved; pushes never force or replace history.
"""
import json, re, subprocess
from pathlib import Path
root = Path(__file__).resolve().parents[2]
manifest = json.loads((root / 'boutique-platform/workspace/workspace.json').read_text())
owner = manifest['github_owner']
if not re.fullmatch(r'[A-Za-z0-9-]{1,39}', owner):
    raise SystemExit('Invalid GitHub owner')
# Confirm API authentication before creating anything. Do not print credential values.
subprocess.run(['gh', 'api', 'user', '--jq', '.login'], check=True)
for name in manifest['repositories']:
    path = root / name
    subprocess.run(['git', '-C', str(path), 'rev-parse', '--verify', 'main'], check=True, stdout=subprocess.DEVNULL)
    if subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain']).strip():
        raise SystemExit('Commit or preserve local changes before publishing ' + name)
    full = owner + '/' + name
    exists = subprocess.run(['gh', 'api', 'repos/' + full], capture_output=True, text=True)
    if exists.returncode != 0:
        if '404' not in exists.stderr:
            raise SystemExit('Could not establish repository availability: ' + full)
        subprocess.run(['gh', 'repo', 'create', full, '--private', '--description', 'Shipyard Boutique DevOps lab — ' + name], check=True)
    remote = 'https://github.com/' + full + '.git'
    configured = subprocess.run(['git', '-C', str(path), 'remote', 'get-url', 'origin'], capture_output=True, text=True)
    if configured.returncode:
        subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', remote], check=True)
    elif configured.stdout.strip() != remote:
        raise SystemExit('Unexpected origin; refusing to replace it for ' + name)
    subprocess.run(['git', '-C', str(path), 'push', '-u', 'origin', 'main'], check=True)
    local = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'main'], text=True).strip()
    remote_head = subprocess.check_output(['git', '-C', str(path), 'ls-remote', 'origin', 'refs/heads/main'], text=True).split()[0]
    if local != remote_head:
        raise SystemExit('Remote verification failed: ' + full)
    print('Verified https://github.com/' + full)
