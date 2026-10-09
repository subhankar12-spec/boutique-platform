#!/usr/bin/env python3
"""Check receiver routing from local config files; sends no notifications."""
import os
import subprocess
from pathlib import Path

AMTOOL = os.environ.get('AMTOOL', 'amtool')
for config in ('alertmanager.yml', 'alertmanager-local.yml'):
    path = Path(__file__).with_name(config)
    scenarios = [
        ('slack', ['environment=production','severity=critical','service=incident-bridge','incident_delivery=disabled','alertname=IncidentDeliveryDeadLetters']),
        ('slack', ['environment=production','severity=critical','service=incident-bridge','incident_delivery=disabled','alertname=IncidentWorkerStalled']),
        ('servicenow,slack', ['environment=production','severity=critical','service=orders','alertname=BoutiqueServiceDown']),
        ('slack', ['environment=production','severity=warning','service=orders','alertname=BoutiqueHighLatency']),
        ('slack', ['environment=dev','severity=critical','service=orders','alertname=BoutiqueServiceDown']),
    ]
    for receivers, labels in scenarios:
        subprocess.run([AMTOOL,'config','routes','test','--config.file='+str(path),'--verify.receivers='+receivers,*labels],check=True,stdout=subprocess.DEVNULL)
print('PASS: delivery failures stay Slack-only; production application critical alerts reach Slack and ServiceNow.')
