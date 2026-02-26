# QuantSight Architecture Decision Records (ADR)

## ADR-001: Redis Cross-Region Strategy

**Date:** 2026-02-26  
**Status:** Accepted  
**Context:** Cloud Memorystore for Redis does not support native cross-region replication. Redis is used for rate limiting and idempotency cache, both of which operate with FAIL OPEN semantics — Redis unavailability degrades gracefully without causing service outages.  

**Decision:** Single-region Redis (us-central1) with FAIL OPEN semantics. Cross-region Redis is deferred until >20% of traffic originates outside us-central1.  

**Consequences:**

- Rate limiting and idempotency cache are unavailable during regional Redis failure
- Firestore fallback is active for idempotency (Phase 1 design)
- Rate limiting defaults to allow-all on Redis failure (Phase 2 design)
- No additional operational cost for cross-region Redis management
- Acceptable risk at current scale (single-region user base)

**Revisit Trigger:** When Cloud Monitoring shows >20% of requests originating from non-us-central1 regions.

---

## ADR-002: Cloud Armor Geo-Restriction Rationale

**Date:** 2026-02-26  
**Status:** Deferred  
**Context:** Cloud Armor provides WAF capabilities including geo-restriction, XSS/SQLi blocking, and IP-based rate limiting. However, Cloud Armor requires a Global External HTTPS Load Balancer — Cloud Run direct invocation (`.run.app` URLs) cannot use Cloud Armor.  

**Decision:** Cloud Armor provisioning deferred. Current Cloud Run services use direct invocation. Load balancer provisioning is a significant infrastructure change requiring DNS migration, TLS certificate management, and traffic rerouting.  

**Rationale for geo-blocking (when implemented):**

- CN, RU, KP: High-risk regions with no expected legitimate user traffic for an NBA analytics platform
- Application-layer rate limiting (Phase 2 RateLimiterMiddleware) provides interim protection
- Vanguard's internal ingress already protects admin endpoints

**Consequences:**

- No WAF protection at network edge (application-layer protections remain active)
- Direct Cloud Run URLs remain the entry point
- Revisit when custom domain + LB is required for business reasons

---

## ADR-003: Bigtable vs Firestore for Pulse Data

**Date:** 2026-02-26  
**Status:** Accepted  
**Context:** Pulse data (live game scores, player leader stats) is high-velocity write data that updates every 30 seconds during live NBA games. Firestore handles this workload adequately at current scale but Bigtable was introduced in Phase 6 for future multi-cluster read distribution and higher write throughput.  

**Decision:** Dual-write strategy with Firestore as primary, Bigtable as secondary (feature-flagged via `FEATURE_BIGTABLE_WRITES`). Bigtable migration completes when:

1. Read path is validated with multi-cluster routing
2. Write path shows reliable operation for 14 days
3. Firestore read path is deprecated (not deleted — 14-day zero-caller rule)

**Consequences:**

- Marginal additional write latency during dual-write phase (~5ms per Bigtable write)
- Bigtable provides automatic multi-cluster failover for reads
- Row key design (game_id#timestamp, team#player_id#timestamp) optimized for time-series scans
- Column families (cf_game, cf_player, cf_meta) aligned with access patterns

---

## ADR-004: Firestore Multi-Region Confirmation

**Date:** 2026-02-26  
**Status:** Confirmed  
**Context:** Firestore is configured with `nam5` (US multi-region) location, confirmed in `firebase.json`. This provides automatic replication across Iowa and South Carolina data centers.  

**Decision:** No migration needed. Firestore multi-region (`nam5`) is already active with 99.999% availability SLA.  

**Consequences:**

- Reads from any US region are served with low latency
- No data export/import migration required
- Firestore location exposed in `/health/deps` as `firestore_region: "nam5"`
