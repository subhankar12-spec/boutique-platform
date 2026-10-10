# Operating sequence

1. Reuse the existing cluster/controller and connected private build agent.
2. Configure the pinned shared library, three publishing credentials and Pipeline seed.
3. Publish four tested/scanned images and charts; merge initial GitOps selections.
4. Prepare app secrets/data; connect Argo and run functional smoke checks.
5. Exercise one routine release and same-digest promotion.
6. Enable monitoring/Slack and centralized logs; test one alert.
7. Practise image/chart rollback and independent database restore.
8. Add production isolation/HA and AWS only on a suitable host/account/budget.

ServiceNow, untrusted PR workers, HA observability and regional recovery are
optional extensions with their own acceptance checks. The application stays
small; operating the delivery and recovery flow is the project focus.
