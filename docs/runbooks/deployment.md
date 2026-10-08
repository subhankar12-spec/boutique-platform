# Deployment

Release a reviewed source SHA. Record the tested image digest and SBOM. Open a dev GitOps PR, merge and wait for Argo CD reconciliation. Verify rollout and smoke tests. Promote the same digest to staging and repeat. Review staging evidence and compatible migrations before production approval. Verify production after reconciliation; a merged PR is not rollout success.
