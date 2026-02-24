"""
NBA Smoke Harness - Phase 0 Baseline
=====================================
Tests all NBA integration code paths end-to-end.
Exit 0 = pass, Exit 1 = fail.

Run from project root inside venv:
    python scripts/nba_smoke.py
"""
import asyncio
import sys
import time
import logging

logging.basicConfig(level=logging.WARNING)  # suppress noise during smoke test

FAILURES = []
WARNINGS = []

def ok(msg):
    print(f"  ✅ {msg}")

def warn(msg):
    print(f"  ⚠️  {msg}")
    WARNINGS.append(msg)

def fail(msg):
    print(f"  ❌ {msg}")
    FAILURES.append(msg)


# ─────────────────────────────────────────────
# TEST 1: nba_api package importable
# ─────────────────────────────────────────────
print("\n[1] nba_api package import")
try:
    from nba_api.live.nba.endpoints import scoreboard as sb_mod, boxscore as bx_mod
    from nba_api.stats.static import teams as teams_static
    ok("nba_api.live imports OK")
    ok("nba_api.stats.static imports OK")
    HAS_NBA_API = True
except ImportError as e:
    fail(f"nba_api import failed: {e}")
    HAS_NBA_API = False


# ─────────────────────────────────────────────
# TEST 2: aiohttp available (AsyncNBAApiAdapter dependency)
# ─────────────────────────────────────────────
print("\n[2] aiohttp import")
try:
    import aiohttp
    ok(f"aiohttp {aiohttp.__version__} OK")
    HAS_AIOHTTP = True
except ImportError as e:
    fail(f"aiohttp not installed: {e}")
    HAS_AIOHTTP = False


# ─────────────────────────────────────────────
# TEST 3: AsyncNBAApiAdapter + cdn.nba.com (primary path)
# ─────────────────────────────────────────────
print("\n[3] AsyncNBAApiAdapter → cdn.nba.com scoreboard")
CDN_GAME_ID = None
try:
    sys.path.insert(0, "shared_core")
    from adapters.nba_api_adapter import AsyncNBAApiAdapter, get_nba_adapter

    adapter = get_nba_adapter()
    ok(f"Adapter version: {adapter.VERSION}")
    ok(f"aiohttp available: {adapter._aiohttp_available}")

    async def test_adapter_scoreboard():
        t0 = time.time()
        games = await adapter.fetch_scoreboard_async()
        latency = (time.time() - t0) * 1000
        return games, latency

    games, latency = asyncio.run(test_adapter_scoreboard())
    ok(f"fetch_scoreboard_async: {len(games)} games in {latency:.0f}ms")

    # Check adapter health metrics
    health = adapter.get_health()
    ok(f"requests={health['request_count']}, errors={health['error_count']}, error_rate={health['error_rate']}")

    if games:
        CDN_GAME_ID = games[0].game_id
        g = games[0]
        ok(f"First game: {g.away_team_tricode} @ {g.home_team_tricode} [{g.status}] id={g.game_id}")
    else:
        warn("No games returned today (may be off-season / no games scheduled)")

except Exception as e:
    fail(f"AsyncNBAApiAdapter failed: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────
# TEST 4: Boxscore fetch (CDN + fallback)
# ─────────────────────────────────────────────
print("\n[4] AsyncNBAApiAdapter → cdn.nba.com boxscore")
if CDN_GAME_ID:
    try:
        async def test_adapter_boxscore(game_id):
            t0 = time.time()
            box = await adapter.fetch_boxscore_async(game_id)
            latency = (time.time() - t0) * 1000
            return box, latency

        box, latency = asyncio.run(test_adapter_boxscore(CDN_GAME_ID))
        if box:
            active = box.all_active_players()
            ok(f"fetch_boxscore_async for {CDN_GAME_ID}: {latency:.0f}ms, {len(active)} active players")
            if active:
                p = active[0]
                ok(f"  Top player: {p.name} ({p.team_tricode}) {p.pts}pts/{p.reb}reb/{p.ast}ast")
        else:
            warn(f"Boxscore for {CDN_GAME_ID} returned None (game may not be live)")
    except Exception as e:
        fail(f"Boxscore fetch failed: {type(e).__name__}: {e}")
else:
    warn("Skipping boxscore test — no game_id available from scoreboard")


# ─────────────────────────────────────────────
# TEST 5: nba_api.live.ScoreBoard (nba_api package direct)
# ─────────────────────────────────────────────
print("\n[5] nba_api.live.ScoreBoard (direct package call)")
NBA_GAME_ID = None
if HAS_NBA_API:
    try:
        t0 = time.time()
        sb = sb_mod.ScoreBoard()
        data = sb.get_dict()
        latency = (time.time() - t0) * 1000
        live_games = data.get("scoreboard", {}).get("games", [])
        ok(f"ScoreBoard(): {len(live_games)} games in {latency:.0f}ms")

        if live_games:
            NBA_GAME_ID = live_games[0].get("gameId")
            g = live_games[0]
            ok(f"  Game: {g.get('awayTeam',{}).get('teamTricode')} @ {g.get('homeTeam',{}).get('teamTricode')} status={g.get('gameStatus')}")
        else:
            warn("No games from nba_api.live.ScoreBoard today")
    except Exception as e:
        fail(f"nba_api.live.ScoreBoard failed: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────
# TEST 6: nba_api.stats.static teams (always works if pkg installed)
# ─────────────────────────────────────────────
print("\n[6] nba_api.stats.static teams (offline static data)")
if HAS_NBA_API:
    try:
        all_teams = teams_static.get_teams()
        ok(f"static teams: {len(all_teams)} teams loaded (no network required)")
        ok(f"  Sample: {all_teams[0]['full_name']} ({all_teams[0]['abbreviation']})")
    except Exception as e:
        fail(f"static teams failed: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────
# TEST 7: NBAScheduleService (uses cdn.nba.com via requests)
# ─────────────────────────────────────────────
print("\n[7] NBAScheduleService → cdn.nba.com")
try:
    sys.path.insert(0, ".")
    from services.nba_schedule import NBAScheduleService
    svc = NBAScheduleService()
    t0 = time.time()
    games = svc.get_todays_games()
    latency = (time.time() - t0) * 1000
    ok(f"NBAScheduleService.get_todays_games(): {len(games)} games in {latency:.0f}ms")
    if games:
        ok(f"  First: {games[0].get('display')} [{games[0].get('status')}]")
except Exception as e:
    fail(f"NBAScheduleService failed: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────
# TEST 8: health_monitor.check_nba_api (stats.nba.com via httpx)
# ─────────────────────────────────────────────
print("\n[8] health_monitor.check_nba_api → stats.nba.com")
try:
    from vanguard.health_monitor import SystemHealthMonitor
    monitor = SystemHealthMonitor()

    async def test_health():
        return await monitor.check_nba_api()

    result = asyncio.run(test_health())
    status = result.get("status")
    latency = result.get("latency_ms", "N/A")
    error = result.get("error", "")

    if status == "healthy":
        ok(f"health_monitor NBA check: healthy ({latency:.0f}ms)")
    elif status == "warning":
        warn(f"health_monitor NBA check: warning — {error} ({latency:.0f}ms)")
    else:
        fail(f"health_monitor NBA check: {status} — {error}")
        warn("NOTE: stats.nba.com blocks via Cloud Run VPC — CDN path is the workaround")
except Exception as e:
    fail(f"health_monitor check failed: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────
# TEST 9: baseline_populator import (season stats)
# ─────────────────────────────────────────────
print("\n[9] baseline_populator import check")
try:
    from services.baseline_populator import (
        populate_all_baselines,
        populate_players_only,
        NBA_API_SEASON
    )
    ok(f"baseline_populator imports OK (season={NBA_API_SEASON})")
    ok("  populate_all_baselines + populate_players_only accessible")
except Exception as e:
    fail(f"baseline_populator import failed: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("NBA SMOKE HARNESS SUMMARY")
print("="*60)
print(f"Failures:  {len(FAILURES)}")
print(f"Warnings:  {len(WARNINGS)}")

if FAILURES:
    print("\nFAILED:")
    for f in FAILURES:
        print(f"  ❌ {f}")

if WARNINGS:
    print("\nWARNINGS:")
    for w in WARNINGS:
        print(f"  ⚠️  {w}")

if not FAILURES:
    print("\n✅ ALL TESTS PASSED (warnings are informational)")
    sys.exit(0)
else:
    print(f"\n❌ {len(FAILURES)} FAILURE(S) — see above")
    sys.exit(1)
