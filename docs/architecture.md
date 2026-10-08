# Application architecture

Browser → frontend → catalogue / cart / orders. Orders fetches cart contents and current catalogue prices, then creates the order transactionally in PostgreSQL. No payment, stock reservation, user login or external email provider. This is a demo shop, not a commercial ecommerce implementation.

Frontend issues a random 256-bit session identifier with an HMAC signature. Cookies are HttpOnly and SameSite=Strict; HTTPS environments enable Secure. Mutation requests require the configured browser Origin. Incoming session headers are never forwarded: the frontend derives ownership from the signed cookie. Backends are internal ClusterIP services with namespace network policies. There is no service-to-service cryptographic identity in this baseline.

Cart quantities are bounded to 1–20. Product IDs are the small demo catalogue allowlist. Orders recomputes prices, rejects empty/invalid carts, and stores an immutable snapshot of line items and integer minor-unit totals. PostgreSQL transaction-scoped advisory locks plus a unique session/idempotency-key constraint serialize concurrent retries across replicas. Reusing a key returns the original order; the cart remains available after checkout so no later edit is lost. A new order requires a new key.

Anonymous sessions have no account recovery. Rotating the signing secret invalidates existing cookies. Shared browser sessions in multiple tabs can update the same cart; snapshot semantics are deliberate. Do not use the smoke suite against a real payment system: it creates synthetic orders.

## Internal APIs

| Service | API |
|---|---|
| Catalogue | GET /products; GET /products/{id} |
| Cart | GET /carts/{session}; PUT/DELETE /carts/{session}/items/{product} |
| Orders | POST /orders; GET /orders/{id} |

Orders requires X-Session-ID, and POST additionally requires Idempotency-Key. Frontend maps these to `/api/products`, `/api/cart`, `/api/cart/items/{product}`, `/api/orders`, and `/api/orders/{id}`. Cart automatically exposes its OpenAPI schema; full cross-language contract schemas are a later extension.

## Environments

Dev/staging use separate namespaces on nonprod. AWS production runs in a separate VPC/cluster. Each AWS environment has its own RDS database instance, Redis replication group, application secret and external-secrets IAM role. Homelab environments each own their PVCs and generated credentials, but share one host and cluster.
