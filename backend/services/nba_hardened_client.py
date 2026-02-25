"""
NBA API Hardened Client — Phase 7
===================================
Drop-in replacement for NBAAPIConnector with production-grade hardening:

  - Configurable timeouts (default 10s, Cloud Run safe)
  - Exponential backoff with jitter (3 retries, caps at 30s)
  - 429 / 503 rate-limit detection with auto-pause
  - Circuit breaker: opens after 5 consecutive failures, resets after 60s
  - Feature flag: FEATURE_NBA_HARDENED_CLIENT
    When False: module silently falls back to original NBAAPIConnector
    When True:  HardenedNBAClient is used

Usage (in services that call the NBA API):
    from services.nba_hardened_client import get_nba_client
    client = get_nba_client()
    stats = client.get_player_stats("203999")
"""

import logging
import time
import random
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry / circuit-breaker config
# ---------------------------------------------------------------------------
_MAX_RETRIES = 3
_BASE_DELAY = 1.5        # seconds before first retry
_MAX_DELAY = 30.0        # cap on backoff
_DEFAULT_TIMEOUT = 10    # seconds — matches Cloud Run's aggressive deadline
_CIRCUIT_OPEN_AFTER = 5  # consecutive failures before opening circuit
_CIRCUIT_RESET_AFTER = 60  # seconds before attempting reset


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open."""


class HardenedNBAClient:
    """
    Hardened NBA Stats API client.

    Wraps the nba_api library with retry, timeout, and circuit-breaker logic.
    Fully backwards-compatible with NBAAPIConnector's public interface.
    """

    def __init__(self, timeout: int = _DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.min_request_interval = 1.0
        self.last_request_time = 0.0
        self._consecutive_failures = 0
        self._circuit_open_at: Optional[float] = None

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def _is_circuit_open(self) -> bool:
        if self._circuit_open_at is None:
            return False
        if time.time() - self._circuit_open_at > _CIRCUIT_RESET_AFTER:
            logger.info("[nba-hardened] Circuit breaker reset — attempting recovery")
            self._circuit_open_at = None
            self._consecutive_failures = 0
            return False
        return True

    def _record_success(self):
        self._consecutive_failures = 0
        self._circuit_open_at = None

    def _record_failure(self, err: Exception):
        self._consecutive_failures += 1
        logger.warning(
            "[nba-hardened] failure #%d: %s", self._consecutive_failures, err
        )
        if self._consecutive_failures >= _CIRCUIT_OPEN_AFTER:
            self._circuit_open_at = time.time()
            logger.error(
                "[nba-hardened] Circuit OPEN after %d consecutive failures. "
                "Will retry after %ds.", _CIRCUIT_OPEN_AFTER, _CIRCUIT_RESET_AFTER
            )

    # ------------------------------------------------------------------
    # Rate limiting + jitter
    # ------------------------------------------------------------------

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep = (self.min_request_interval - elapsed) + random.uniform(0.05, 0.3)
            time.sleep(sleep)
        self.last_request_time = time.time()

    # ------------------------------------------------------------------
    # Core retry wrapper
    # ------------------------------------------------------------------

    def _call_with_retry(self, fn, *args, **kwargs) -> Any:
        """
        Call `fn(*args, **kwargs)` with retry + backoff.
        Injects `timeout=self.timeout` into nba_api endpoint calls.
        """
        if self._is_circuit_open():
            raise CircuitOpenError("NBA API circuit breaker is open — too many recent failures")

        kwargs.setdefault("timeout", self.timeout)
        last_err = None

        for attempt in range(1, _MAX_RETRIES + 1):
            self._rate_limit()
            try:
                result = fn(*args, **kwargs)
                self._record_success()
                return result
            except Exception as e:
                last_err = e
                err_str = str(e).lower()

                # Detect rate-limit responses — back off longer
                is_rate_limited = "429" in err_str or "too many" in err_str or "rate" in err_str
                is_server_err = "503" in err_str or "502" in err_str or "500" in err_str

                delay = min(_BASE_DELAY * (2 ** (attempt - 1)), _MAX_DELAY)
                delay += random.uniform(0, delay * 0.3)  # +30% jitter

                if is_rate_limited:
                    delay = max(delay, 15.0)  # enforce minimum 15s on rate limit
                    logger.warning("[nba-hardened] Rate limited (attempt %d/%d) — sleeping %.1fs", attempt, _MAX_RETRIES, delay)
                elif is_server_err:
                    logger.warning("[nba-hardened] Server error (attempt %d/%d) — sleeping %.1fs: %s", attempt, _MAX_RETRIES, delay, e)
                else:
                    logger.warning("[nba-hardened] Request failed (attempt %d/%d) — sleeping %.1fs: %s", attempt, _MAX_RETRIES, delay, e)

                if attempt < _MAX_RETRIES:
                    time.sleep(delay)

        self._record_failure(last_err)
        raise last_err

    # ------------------------------------------------------------------
    # Public API — mirrors NBAAPIConnector interface
    # ------------------------------------------------------------------

    def fetch(self, entity_type: str, entity_id: str, query: dict = None) -> dict:
        """Generic fetch — compatible with NBAAPIConnector.fetch()."""
        if entity_type == "player_stats":
            return self.get_player_game_logs(entity_id)
        elif entity_type == "player_profile":
            return self.get_player_stats(entity_id)
        elif entity_type == "team_roster":
            return self.get_team_roster(entity_id)
        elif entity_type == "all_players":
            return self.get_all_players()
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def get_all_players(self, season: str = None) -> List[Dict]:
        from nba_api.stats.endpoints import commonallplayers
        from core.config import CURRENT_SEASON
        season = season or CURRENT_SEASON
        try:
            data = self._call_with_retry(
                commonallplayers.CommonAllPlayers,
                is_only_current_season=1,
                league_id="00",
                season=season,
            )
            return data.get_dict()["resultSets"][0]["rowSet"]
        except CircuitOpenError:
            logger.error("[nba-hardened] get_all_players skipped — circuit open")
            return []
        except Exception as e:
            logger.error("[nba-hardened] get_all_players failed: %s", e)
            return []

    def get_team_roster(self, team_id: str, season: str = None) -> List[Dict]:
        from nba_api.stats.endpoints import commonteamroster
        from core.config import CURRENT_SEASON
        season = season or CURRENT_SEASON
        try:
            data = self._call_with_retry(
                commonteamroster.CommonTeamRoster,
                team_id=team_id,
                season=season,
                league_id="00",
            )
            return data.get_dict()["resultSets"][0]["rowSet"]
        except CircuitOpenError:
            logger.error("[nba-hardened] get_team_roster skipped — circuit open")
            return []
        except Exception as e:
            logger.error("[nba-hardened] get_team_roster team=%s failed: %s", team_id, e)
            return []

    def get_player_stats(self, player_id: str, season: str = None) -> Optional[Dict]:
        from nba_api.stats.endpoints import playercareerstats
        try:
            data = self._call_with_retry(
                playercareerstats.PlayerCareerStats,
                player_id=player_id,
                per_mode36="PerGame",
            )
            data_dict = data.get_dict()
            for rs in data_dict["resultSets"]:
                if rs["name"] == "SeasonTotalsRegularSeason":
                    headers = rs["headers"]
                    rows = rs["rowSet"]
                    if not rows:
                        return None
                    return dict(zip(headers, rows[-1]))
            return None
        except CircuitOpenError:
            logger.error("[nba-hardened] get_player_stats skipped — circuit open")
            return None
        except Exception as e:
            logger.error("[nba-hardened] get_player_stats player=%s failed: %s", player_id, e)
            return None

    def get_player_game_logs(self, player_id: str, season: str = None) -> List[Dict]:
        from nba_api.stats.endpoints import playergamelog
        from core.config import CURRENT_SEASON
        season = season or CURRENT_SEASON
        try:
            data = self._call_with_retry(
                playergamelog.PlayerGameLog,
                player_id=player_id,
                season=season,
                season_type_all_star="Regular Season",
            )
            data_dict = data.get_dict()
            headers = data_dict["resultSets"][0]["headers"]
            rows = data_dict["resultSets"][0]["rowSet"]
            return [dict(zip(headers, row)) for row in rows]
        except CircuitOpenError:
            logger.error("[nba-hardened] get_player_game_logs skipped — circuit open")
            return []
        except Exception as e:
            logger.error("[nba-hardened] get_player_game_logs player=%s failed: %s", player_id, e)
            return []

    def populate_database(self) -> bool:
        players = self.get_all_players()
        if players:
            logger.info("[nba-hardened] Connected — %d players found", len(players))
            return True
        return False

    def get_circuit_status(self) -> Dict:
        """Return circuit breaker diagnostics."""
        open_ = self._is_circuit_open()
        return {
            "circuit_open": open_,
            "consecutive_failures": self._consecutive_failures,
            "open_since": self._circuit_open_at,
            "resets_after_s": _CIRCUIT_RESET_AFTER,
        }


# ---------------------------------------------------------------------------
# Factory — reads feature flag, returns hardened or legacy client
# ---------------------------------------------------------------------------

_hardened: Optional[HardenedNBAClient] = None


def get_nba_client(db_path: str = "") -> Any:
    """
    Return the appropriate NBA API client based on FEATURE_NBA_HARDENED_CLIENT.

    When enabled: HardenedNBAClient (Phase 7)
    When disabled: legacy NBAAPIConnector (safe fallback)
    """
    global _hardened

    try:
        from vanguard.core.feature_flags import flag
        use_hardened = flag("FEATURE_NBA_HARDENED_CLIENT")
    except ImportError:
        use_hardened = False

    if use_hardened:
        if _hardened is None:
            _hardened = HardenedNBAClient()
            logger.info("[nba-hardened] HardenedNBAClient activated (Phase 7)")
        return _hardened
    else:
        # Lazy import to avoid loading nba_api at module load time
        from services.nba_api_connector import NBAAPIConnector
        return NBAAPIConnector(db_path=db_path)
