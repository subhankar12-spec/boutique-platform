#!/usr/bin/env python3
"""Generate local-only receiver credentials without printing values."""
from pathlib import Path
import secrets,os
root=Path(__file__).resolve().parent/".secrets"; root.mkdir(mode=0o700,exist_ok=True); root.chmod(0o700)
for name,value in {"slack_webhook":"http://mock-receivers:18080/slack","webhook_token":secrets.token_urlsafe(32),"servicenow_password":secrets.token_urlsafe(32),"grafana_password":secrets.token_urlsafe(32)}.items():
    f=root/name
    if not f.exists(): f.write_text(value+"\n")
    # Containers can read individual bind-mounted files; parent prevents host directory traversal.
    f.chmod(0o444)
print("Local mock receiver secrets prepared; no live Slack/ServiceNow connection.")
