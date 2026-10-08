# Requirements: Rate limiter for a public API

Build a rate limiter for a public REST API with these constraints:

- Per-API-key limit: 100 requests/minute, burst up to 20.
- Must work across multiple API server instances (no single-process assumption).
- On limit exceeded, return HTTP 429 with a `Retry-After` header.
- Should add well under 5ms of overhead per request at p99.
- Needs to survive a Redis restart without permanently banning everyone mid-restart.
