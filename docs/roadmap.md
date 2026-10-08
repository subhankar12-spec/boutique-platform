# Learning order

1. Run Compose, inspect the four service APIs and complete smoke tests.
2. Set up Jenkins validation, build one service, inspect its image/SBOM and deliberately break a test.
3. Connect trusted release publication and verify registry permissions.
4. Run local Kubernetes, then Argo CD; deploy dev and practise rollback.
5. Add staging, review digest promotion and record smoke evidence.
6. Add production namespace for a homelab exercise; understand its shared-host limitations.
7. Read/validate AWS Terraform; provision only after budget and account review.
8. Enable monitoring and perform one controlled failure and a restore drill.

Avoid adding application features until the delivery path works. Deferred items include real payments, account authentication, full contract schemas, automated signed attestation verification, service mesh, distributed tracing, multi-region and sophisticated autoscaling.
