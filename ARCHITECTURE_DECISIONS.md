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

---

## ADR-005: ML Incident Classifier Architecture

**Date:** 2026-02-26  
**Status:** Accepted  
**Context:** Heuristic triage (Phase 5) achieves ~25-35% accuracy on the incident corpus. Most incidents (73.6% HTTPError404) fall through to a low-confidence fallback. An ML classifier can improve classification accuracy and provide confidence-calibrated predictions.

**Decision:** RandomForestClassifier with lazy-loaded GCS wrapper, inserted into the Gemini → ML → Heuristic → Stub fallback chain. Model is feature-flagged (`FEATURE_ML_CLASSIFIER_ENABLED`).

**Technical Details:**

- Model: RandomForestClassifier (100 estimators, max_depth=15)
- Imbalance handling: class_weight='balanced' + SMOTE-ENN (imblearn pipeline)
- Quality gate: F1-macro ≥ 0.70 on stratified holdout
- Lazy loading: functools.lru_cache pattern, GCS → /tmp cache
- Serialization: joblib, estimated <5MB
- Feature vector: 40+ features (HTTP codes, endpoint topology, temporal, severity, text signals)
- Confidence threshold: ≥0.75 to use ML prediction, otherwise falls through to heuristic

**Consequences:**

- ML classification available within 0.1ms (post-load)
- Cold start adds ~2-3s for GCS model download
- Graceful degradation: model unavailability falls through to heuristic/stub
- Requires `scikit-learn`, `joblib`, `imbalanced-learn` in requirements.txt
- Model artifacts stored in gs://quantsight-ml-artifacts/models/incident_classifier/

---

## ADR-006: Predictive Circuit Breaker

**Date:** 2026-02-26  
**Status:** Accepted  
**Context:** Current circuit breaker (Phase 4) is reactive — it opens after 50% failure rate over 60s with ≥10 requests. By the time OPEN triggers, significant damage has occurred to users. Leading indicators (latency spikes, error rate velocity, consecutive error bursts) can predict failures before they reach threshold.

**Decision:** Add PREDICTIVE_OPEN state to CircuitBreakerV2. Returns 429 (Too Many Requests) instead of 503 (Service Unavailable) — a softer signal that allows clients to retry.

**State Machine Extension:**

```
CLOSED ──[ML predicts failure]──→ PREDICTIVE_OPEN (429)
PREDICTIVE_OPEN ──[actual failure > 50%]──→ OPEN (503)
PREDICTIVE_OPEN ──[error rate drops < 20%]──→ CLOSED
```

**Leading Indicators (heuristic-based, not ML model):**

1. Error rate velocity > 10% per 30s
2. Latency p95 > 2000ms
3. Consecutive errors ≥ 5
4. Error rate 30-50% (approaching threshold)

**Consequences:**

- Feature-flagged: `FEATURE_PREDICTIVE_CB_ENABLED`
- No additional model required (heuristic signal combination)
- Blast-radius rules enforced (healthz, readyz, vanguard/* never predicted)
- Prediction failure silently falls through to normal CB evaluation

---

## ADR-007: BigQuery Data Pipeline

**Date:** 2026-02-26  
**Status:** Accepted  
**Context:** ML model training requires structured, queryable training data. Firestore is not suitable for analytical workloads. BigQuery provides standard SQL access, automatic schema enforcement, and integrates with GCP ML tooling.

**Decision:** Nightly batch export from Firestore to BigQuery via `load_table_from_dataframe()` (Apache Arrow). Dataset: `quantsight_ml` with 3 tables.

**Tables:**

| Table | Partition | Clustering | Purpose |
|---|---|---|---|
| `incidents` | exported_at | error_type, severity | Classifier training |
| `circuit_events` | occurred_at | endpoint, event_type | Predictive CB training |
| `player_stats` | snapshot_date | player_id, team_id | Aegis predictor training |

**Data Pipeline:**

1. GitHub Actions cron (3:00 AM UTC daily)
2. Firestore → Python SDK → pandas DataFrame → BigQuery
3. Incremental export via `last_seen` timestamp
4. Dataset TTL: 90 days (auto-expiration)

**Consequences:**

- Requires `google-cloud-bigquery`, `google-cloud-storage`, `pyarrow`
- GCS bucket `gs://quantsight-ml-artifacts/` must be created
- BigQuery API must be enabled in GCP project
- Service account needs `bigquery.dataEditor` role
- Load jobs are atomic (all-or-nothing), safe for idempotent reruns
