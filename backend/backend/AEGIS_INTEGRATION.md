# Aegis Integration Guide

**Version**: 1.0.0  
**Status**: Phase 1 Complete - Ready for Endpoint Migration  
**Date**: January 28, 2026

---

## Quick Start

The Aegis-Sovereign Data Router is now available in `server.py` as a global instance. Use it to fetch data with automatic caching, integrity verification, and offline fallback.

### Basic Usage

```python
from aegis import AegisBrain

# Aegis is already initialized in server.py as `aegis_router`
# Access it directly in your endpoints

@app.get("/player/{player_id}/stats")
async def get_player_stats(player_id: int):
    # Old way - direct API/DB call
    # stats = nba.get_player_stats(player_id)
    
    # New way - use Aegis router
    result = await aegis_router.route_request({
        'type': 'player_stats',
        'id': player_id,
        'priority': 'normal'  # or 'high', 'critical'
    })
    
    return {
        'player': result['data'],
        'source': result['source'],  # 'cache' or 'api'
        'freshness': result['freshness'],  # 'fresh', 'warm', 'stale', 'live'
        'latency_ms': result.get('latency_ms', 0)
    }
```

---

## Available Components

All components are initialized in `server.py` and accessible globally:

| Component | Variable | Purpose |
| ----------- | ---------- | --------- |
| Router | `aegis_router` | Main routing engine |
| Cache | `aegis_cache` | SQLite persistence layer |
| Rate Governor | `aegis_governor` | API rate limiting |
| Integrity Healer | `aegis_healer` | SHA-256 verification |
| Schema Enforcer | `aegis_enforcer` | Pydantic validation |
| Atomic Writer | `aegis_writer` | Transaction-safe writes |
| Mode Detector | `aegis_detector` | ML/Classic detection |
| Health Monitor | `aegis_monitor` | System health tracking |

---

## Migration Patterns

### Pattern 1: Simple Player Stats

**Before:**

```python
@app.get("/player/{player_id}")
def get_player(player_id: int):
    # Direct database query
    player = db.query("SELECT * FROM players WHERE id = ?", player_id)
    return player
```

**After:**

```python
@app.get("/player/{player_id}")
async def get_player(player_id: int):
    # Use Aegis router
    result = await aegis_router.route_request({
        'type': 'player_profile',
        'id': player_id
    })
    
    # Monitor the request
    aegis_monitor.record_request(success=True)
    
    return {
        'data': result['data'],
        'meta': {
            'source': result['source'],
            'cached': result['source'] == 'cache',
            'freshness': result['freshness']
        }
    }
```

---

## Best Practices

### ✅ DO

- **Always use async/await** - Aegis is async for non-blocking I/O
- **Set appropriate priorities** - Use 'critical' sparingly
- **Monitor health** - Check `aegis_monitor` regularly
- **Handle offline mode** - Gracefully degrade when API unavailable
- **Validate before writing** - Use `aegis_enforcer` for all writes

### ❌ DON'T

- **Don't bypass Aegis** - Always route through `aegis_router`
- **Don't ignore freshness** - Check `result['freshness']` for stale data
- **Don't abuse 'critical' priority** - It bypasses emergency brake
- **Don't write without validation** - Always use schema enforcer

---

## Performance Metrics

Expected performance after migration:

| Metric | Before Aegis | With Aegis | Improvement |
| -------- | -------------- | ------------ | ------------- |
| Cache Hit Latency | 50ms (DB query) | 0-2ms | **25-50x faster** |
| API Call Rate | Unlimited | Governed | **Quota protected** |
| Data Integrity | Manual checks | Automatic | **100% verified** |
| Write Failures | Partial writes possible | Zero | **Atomic guarantee** |
| Offline Capability | Hard failures | Graceful fallback | **Always available** |

---

**Aegis is production-ready. Start migrating your endpoints today!** 🚀
