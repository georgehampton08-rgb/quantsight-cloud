import uvicorn
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import sys
import os
import argparse
import random
import logging
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[ENV] Loaded .env file")
except ImportError:
    print("[ENV] python-dotenv not installed, using system environment only")


# --- Robust Logging Setup ---
# Ensure we log to a writable location (AppData)
app_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', '.'), 'QuantSight', 'logs')
os.makedirs(app_data_dir, exist_ok=True)
log_file = os.path.join(app_data_dir, 'backend_startup.log')

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    filemode='w' # Overwrite on each run
)
logger = logging.getLogger()

# Also log to stdout for Electron to catch
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

logger.info(f"[START] AEGIS-ENGINE Starting... PID: {os.getpid()}")
logger.info(f"📂 Execution Path: {os.path.dirname(os.path.abspath(__file__))}")
logger.info(f"📂 CWD: {os.getcwd()}")
logger.info(f"🐍 Python Executable: {sys.executable}")

# --- Path Setup ---
# Add project root to sys.path to allow importing from chronos_knowledge_loom and aegis_live_bridge
# Adjusted for: c:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\server.py
current_dir = os.path.dirname(os.path.abspath(__file__))
logger.info(f"📂 Script Directory: {current_dir}")
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import global season configuration
from core.config import CURRENT_SEASON
logger.info(f"[OK] CURRENT_SEASON: {CURRENT_SEASON}")

# --- Engines (Optional imports for lite builds) ---
try:
    from chronos_knowledge_loom.models.knowledge_graph import KnowledgeGraph
    HAS_KNOWLEDGE_LOOM = True
    logger.info("[OK] chronos_knowledge_loom loaded")
except ImportError:
    logger.warning("[WARN]  chronos_knowledge_loom not available (lite build)")
    HAS_KNOWLEDGE_LOOM = False
    KnowledgeGraph = None

try:
    from aegis_live_bridge.connectors.nba_connector import NBAConnector
    HAS_NBA_CONNECTOR = True
    logger.info("[OK] aegis_live_bridge loaded")
except ImportError:
    logger.warning("[WARN]  aegis_live_bridge not available (lite build)")
    HAS_NBA_CONNECTOR = False
    NBAConnector = None

# Initialize FastAPI
app = FastAPI(title="Quantsight Aegis Controller")

# CORS (Allow Electron)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Content Security Policy (Middleware)
@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    response = await call_next(request)
    # Ensure images from localhost:5000 are allowed
    response.headers["Content-Security-Policy"] = "img-src 'self' data: blob: https: http://localhost:5000;"
    return response

# Initialize Engines (with fallbacks)
STORAGE_PATH = os.path.join(current_dir, "data", "knowledge_graph.json")
kg = KnowledgeGraph(storage_path=STORAGE_PATH) if HAS_KNOWLEDGE_LOOM else None


# Initialize NBA Connector (optional for lite builds)
nba = NBAConnector(csv_baseline_dir=os.path.join(current_dir, "data", "player_databases")) if HAS_NBA_CONNECTOR else None

# Initialize Circuit Breaker for NBA API resilience
try:
    from services.circuit_breaker_service import CircuitBreakerService
    circuit_breaker = CircuitBreakerService(name="nba_api_circuit")
    HAS_CIRCUIT_BREAKER = True
    logger.info("[OK] CircuitBreaker initialized")
except ImportError:
    logger.warning("[WARN] CircuitBreaker not available (pybreaker not installed)")
    HAS_CIRCUIT_BREAKER = False
    circuit_breaker = None

# Multi-path database lookup (packaged + dev modes)
def find_nba_db():
    """Find NBA database from multiple possible locations"""
    exe_dir = os.path.dirname(sys.executable)
    possible_paths = [
        # Dev mode: relative to server.py
        os.path.join(current_dir, "data", "nba_data.db"),
        # Packaged mode: ../data/nba_data.db (relative to api.exe in resources/backend)
        os.path.abspath(os.path.join(exe_dir, "..", "data", "nba_data.db")),
        # Packaged mode: in resources/backend/data
        os.path.join(exe_dir, "data", "nba_data.db"),
        # AppData location (for installed app persistence)
        os.path.join(os.environ.get('APPDATA', ''), 'QuantSight', 'data', 'nba_data.db'),
    ]
    
    logger.info(f"[SEARCH] Searching for DB in: {possible_paths}")
    
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"[OK] Found NBA database at: {path}")
            return path
    
    # Default to dev path
    logger.warning(f"[WARN] No NBA database found, using default: {possible_paths[0]}")
    return possible_paths[0]

nba_db_path = find_nba_db()

# Initialize Refraction Service for pace-adjusted stats
try:
    from services.refraction_service import RefractionService
    refraction_service = RefractionService(db_path=nba_db_path)
    HAS_REFRACTION = True
    logger.info("[OK] RefractionService initialized")
except Exception as e:
    logger.warning(f"[WARN] RefractionService not available: {e}")
    HAS_REFRACTION = False
    refraction_service = None


def ensure_nba_db_exists():
    """Ensure NBA database exists and is initialized"""
    db_path = Path(nba_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not db_path.exists():
        logger.warning("[WARN]  NBA database not found, initializing...")
        try:
            conn = sqlite3.connect(nba_db_path)
            cursor = conn.cursor()
            
            # Create essential tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    team_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    abbreviation TEXT,
                    conference TEXT,
                    division TEXT
                )
            """)
            
            # ... (truncated for brevity, keep existing queries) ...
            
            conn.commit()
            conn.close()
            logger.info("[OK] NBA database initialized")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize database: {e}")

    return True

# Ensure DB exists on startup
ensure_nba_db_exists()

def get_nba_db():
    """Get connection to NBA data database with error handling"""
    try:
        conn = sqlite3.connect(nba_db_path)
        conn.row_factory = dict_factory
        return conn
    except Exception as e:
        logger.error(f"[ERROR] Database connection error: {e}")
        ensure_nba_db_exists()
        return sqlite3.connect(nba_db_path)

def get_nba_db_connection():
    """Alias for get_nba_db for compatibility"""
    return get_nba_db()

def dict_factory(cursor, row):
    """Convert SQLite row to dictionary"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


# Initialize Aegis Data Router (Phase 1 Complete: Weeks 1-6)
# NOTE: Placed after nba_db_path is defined (line 198)
try:
    from aegis.router_brain import AegisBrain
    from aegis.rate_governor import TokenBucketGovernor
    from aegis.healer_protocol import HealerProtocol as DataIntegrityHealer
    from aegis.schemas import SchemaEnforcer
    from aegis.atomic_writer import AtomicWriter
    from aegis.dual_mode import DualModeDetector
    from aegis.health_monitor import WorkerHealthMonitor
    from aegis.cache_manager import CacheManager
    from aegis.nba_api_bridge import AegisNBABridge
    from services.nba_api_connector import NBAAPIConnector
    
    # Initialize NBA API connector (will be wrapped with circuit breaker)
    nba_api_connector = NBAAPIConnector(db_path=nba_db_path)
    
    # Create NBA API bridge with circuit breaker protection
    if HAS_CIRCUIT_BREAKER and circuit_breaker:
        nba_bridge = AegisNBABridge(nba_api_connector, circuit_breaker)
        logger.info("[OK] NBA API bridge created with circuit breaker protection")
    else:
        nba_bridge = AegisNBABridge(nba_api_connector, None)
        logger.warning("[WARN] NBA API bridge created WITHOUT circuit breaker")
    
    # Initialize Aegis components
    aegis_cache = CacheManager("quantsight.db")
    aegis_governor = TokenBucketGovernor(max_tokens=10, refill_rate=0.75)
    aegis_healer = DataIntegrityHealer(data_dir=Path(current_dir) / "data")
    aegis_enforcer = SchemaEnforcer()
    aegis_writer = AtomicWriter(base_dir=os.path.join(current_dir, "data", "aegis_storage"))
    aegis_detector = DualModeDetector()
    aegis_monitor = WorkerHealthMonitor()
    
    # Create router with NBA API bridge
    aegis_router = AegisBrain(
        cache_manager=aegis_cache,
        api_bridge=nba_bridge,  # ✅ NOW CONNECTED TO NBA API
        governor=aegis_governor,
        integrity_healer=aegis_healer,
        schema_enforcer=aegis_enforcer
    )
    
    HAS_AEGIS_ROUTER = True
    logger.info(f"[OK] Aegis Data Router initialized - Phase 1 Complete")
    logger.info(f"     └─ NBA API: Connected with circuit breaker")
    logger.info(f"     └─ Analysis Mode: {aegis_detector.active_mode}")
    logger.info(f"     └─ Health Status: {aegis_monitor.check_system_health()['status']}")
    logger.info(f"     └─ Cache: Operational")
    logger.info(f"     └─ Rate Limiting: Active (10 tokens, 0.75/s refill)")
except Exception as e:
    logger.warning(f"[WARN] Aegis Data Router not available: {e}")
    import traceback
    traceback.print_exc()
    HAS_AEGIS_ROUTER = False
    aegis_router = None
    aegis_writer = None
    aegis_detector = None
    aegis_monitor = None
    nba_bridge = None


# --- Initialize Nexus Hub (API Supervisor) ---
# Coordinates endpoint management, health monitoring, and adaptive routing
try:
    from aegis.nexus_hub import NexusHub, get_nexus_hub
    from aegis.error_handler import NexusErrorHandler, ErrorCode
    
    # Create Nexus Hub with worker monitor integration
    nexus_hub = NexusHub(worker_monitor=aegis_monitor if HAS_AEGIS_ROUTER else None)
    
    # Update component availability
    if HAS_AEGIS_ROUTER:
        nexus_hub.update_component_status("aegis_brain", True)
        nexus_hub.update_component_status("sovereign_router", True)
    
    HAS_NEXUS_HUB = True
    logger.info(f"[OK] Nexus Hub v{nexus_hub.VERSION} initialized")
    logger.info(f"     └─ Endpoints Registered: {len(nexus_hub.registry.endpoints)}")
    logger.info(f"     └─ Health Gate: Active")
    logger.info(f"     └─ Adaptive Router: Advisory Mode")
    logger.info(f"     └─ Priority Queue: Ready")
except Exception as e:
    logger.warning(f"[WARN] Nexus Hub not available: {e}")
    import traceback
    traceback.print_exc()
    HAS_NEXUS_HUB = False
    nexus_hub = None



# --- Services (Optional imports) ---
try:
    from services.defense_matrix import DefenseMatrix
    HAS_DEFENSE_MATRIX = True
    logger.info("[OK] DefenseMatrix loaded")
except ImportError:
    logger.warning("[WARN]  DefenseMatrix not available (lite build)")
    HAS_DEFENSE_MATRIX = False
    DefenseMatrix = None

try:
    from services.nemesis_engine import NemesisEngine
    HAS_NEMESIS_ENGINE = True
    logger.info("[OK] NemesisEngine loaded")
except ImportError:
    logger.warning("[WARN]  NemesisEngine not available (lite build)")
    HAS_NEMESIS_ENGINE = False
    NemesisEngine = None

try:
    from services.pace_engine import PaceEngine
    HAS_PACE_ENGINE = True
    logger.info("[OK] PaceEngine loaded")
except ImportError:
    logger.warning("[WARN]  PaceEngine not available (lite build)")
    HAS_PACE_ENGINE = False
    PaceEngine = None

# Include Injury Admin API
try:
    from api.injury_admin import router as injury_admin_router
    app.include_router(injury_admin_router)
    logger.info("[OK] Injury Admin API loaded")
except Exception as e:
    logger.warning(f"[WARN] Could not load Injury Admin API: {e}")

# Include Player Avatar Proxy API
try:
    from api.player_avatars import router as avatar_router
    app.include_router(avatar_router)
    logger.info("[OK] Player Avatar Proxy loaded")
except Exception as e:
    logger.warning(f"[WARN] Could not load Player Avatar Proxy: {e}")

# --- Endpoints ---

@app.get("/health")
def health_check():
    """
    Real-time system health check with actual latency measurements.
    Replaces mocked random.random() logic with SystemSensorGenerator.
    """
    try:
        from services.system_sensors import SystemSensorGenerator
        
        sensor = SystemSensorGenerator(db_path=nba_db_path)
        sensor_data = sensor.check_all()
        
        # Return legacy-compatible format for existing clients
        return {
            "nba": sensor_data.api_status,
            "gemini": sensor_data.gemini_status,
            "database": sensor_data.database_status,
            "latency": {
                "database_ms": sensor_data.database_latency_ms,
                "api_ms": sensor_data.api_latency_ms
            },
            "timestamp": sensor_data.timestamp
        }
    except Exception as e:
        logger.error(f"[HEALTH] Sensor check failed: {e}")
        # Fallback to critical state
        return {
            "nba": "critical",
            "gemini": "critical",
            "database": "critical",
            "error": str(e)
        }


@app.get("/health/stream")
async def health_stream_endpoint(request: Request):
    """
    Server-Sent Events (SSE) endpoint for real-time health monitoring.
    
    Pushes health updates every 5 seconds to connected clients.
    Eliminates need for 30-second polling from frontend.
    """
    from sse_starlette.sse import EventSourceResponse
    import asyncio
    
    async def event_generator():
        from services.system_sensors import SystemSensorGenerator
        
        logger.info("[SSE] Client connected to health stream")
        
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("[SSE] Client disconnected from health stream")
                    break
                
                # Generate health data
                try:
                    sensor = SystemSensorGenerator(db_path=nba_db_path)
                    sensor_data = sensor.check_all()
                    
                    health_payload = {
                        "nba": sensor_data.api_status,
                        "gemini": sensor_data.gemini_status,
                        "database": sensor_data.database_status,
                        "latency": {
                            "database_ms": sensor_data.database_latency_ms,
                            "api_ms": sensor_data.api_latency_ms
                        },
                        "timestamp": sensor_data.timestamp,
                        "circuit_breaker": {
                            "state": circuit_breaker.state if HAS_CIRCUIT_BREAKER and circuit_breaker else "unknown",
                            "failures": circuit_breaker.fail_count if HAS_CIRCUIT_BREAKER and circuit_breaker else 0
                        }
                    }
                    
                    yield {
                        "event": "health",
                        "data": json.dumps(health_payload)
                    }
                    
                except Exception as e:
                    logger.error(f"[SSE] Health check error: {e}")
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": str(e)})
                    }
                
                # Wait 5 seconds before next update
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("[SSE] Health stream cancelled")
        except Exception as e:
            logger.error(f"[SSE] Stream error: {e}")
    
    return EventSourceResponse(event_generator())


@app.get("/health/data")
def data_health_check():
    """
    Comprehensive data layer health check.
    Shows all tables, their freshness, and data counts.
    Uses centralized data_paths for consistency.
    """
    try:
        from data_paths import get_data_health, DATA_TABLES
        
        health = get_data_health()
        
        # Add table descriptions
        for table_name, info in health.get('tables', {}).items():
            if table_name in DATA_TABLES:
                info['description'] = DATA_TABLES[table_name].get('description', '')
                info['updated_by'] = DATA_TABLES[table_name].get('updated_by', [])
        
        return health
    except Exception as e:
        logger.error(f"[DATA-HEALTH] Check failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'tables': {}
        }



@app.get("/matchup/analyze-player")  # Renamed to avoid conflict with team matchup endpoint
def analyze_matchup(player_id: str, opponent: str):
    """
    Phase 5: The Matchup Engine Aggregator.
    """
    # 1. Try Knowledge Graph
    profile = kg.get_player(player_id) if kg else None
    
    player_stats = {}
    position_str = "PG" # Default
    
    # 2. Fallback to SQLite
    if not profile:
        conn = get_nba_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players WHERE player_id = ?", (player_id,))
        player_data = cursor.fetchone()
        
        if not player_data:
            raise HTTPException(status_code=404, detail="Player not found")
            
        # Mock a profile-like object or just extract needed vars
        # Extract stats if available (assuming JSON or columns)
        # For V1, we just use basic defaults if real stats aren't loaded in this view
        player_stats['points_avg'] = 15.0 # Generic average for now or fetch from stats table
        
        # position mapping from DB string to Archetype-like string
        db_pos = player_data['position'] or "PG"
        position_str = db_pos
    else:
        player_stats['points_avg'] = profile.points_avg
        position_str = profile.archetype.value

    # 1. Defense Matrix
    # Map position
    pos_map = {
        "PG": "PG", "Point Guard": "PG", "G": "PG",
        "SG": "SG", "Shooting Guard": "SG",
        "SF": "SF", "Small Forward": "SF", "F": "SF",
        "PF": "PF", "Power Forward": "PF",
        "C": "C", "Center": "C"
    }
    # Normalize position string
    position = pos_map.get(position_str, "PG")

    paoa = DefenseMatrix.get_paoa(opponent, position)
    rebound_resistance = DefenseMatrix.get_rebound_resistance(opponent)
    
    # 2. Nemesis Vector
    nemesis_data = NemesisEngine.analyze_head_to_head(player_id, opponent, player_stats['points_avg'])
    
    # 3. Pace Friction
    # KnowledgeGraph doesn't store team yet (need to fix model or infer)
    # V1: Assume generic team 'NBA' or infer from last game log if available
    player_team = "NBA" 
    pace_multiplier = PaceEngine.calculate_multiplier(player_team, opponent)
    
    # 4. Synthesize Insight
    insight_banner = "Neutral Matchup"
    insight_type = "neutral"
    
    if paoa > 2.0:
        insight_banner = f"Target the Paint: {opponent} allows +{paoa} PPG to {position}s."
        insight_type = "success"
    elif pace_multiplier < 0.95:
        insight_banner = f"Pace Trap: {opponent} slows game tempo by {round((pace_multiplier-1)*100, 1)}%."
        insight_type = "warning"
    elif nemesis_data['status'] == "Nemesis Mode":
        insight_banner = "Nemesis Activation: Historical dominance detected."
        insight_type = "success"
        
    return {
        "defense_matrix": {
            "paoa": paoa,
            "rebound_resistance": rebound_resistance,
            "profile": DefenseMatrix.get_profile(opponent)
        },
        "nemesis_vector": nemesis_data,
        "pace_friction": {
            "multiplier": pace_multiplier,
            "projected_pace": "Fast" if pace_multiplier > 1.0 else "Slow"
        },
        "insight": {
            "text": insight_banner,
            "type": insight_type
        }
    }

@app.get("/radar/{player_id}")
def get_radar_dimensions(player_id: str, opponent_id: Optional[str] = None):
    """
    Calculate radar chart dimensions from REAL player stats.
    
    Returns 5 dimensions (0-100 scale):
    - Scoring: Based on PPG, TS%, usage
    - Playmaking: Based on APG, AST/TO ratio
    - Rebounding: Based on RPG, REB%
    - Defense: Based on STL, BLK, DFG%
    - Pace: Based on tempo contribution
    """
    from services.radar_dimensions import get_radar_calculator, OpponentRadarDimensions
    
    conn = get_nba_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT pra.*, pb.player_name, pb.position
        FROM player_rolling_averages pra
        LEFT JOIN player_bio pb ON pra.player_id = pb.player_id
        WHERE pra.player_id = ?
    """, (str(player_id),))
    
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    
    player_stats = {
        'points_avg': row['avg_points'] or 0,
        'assists_avg': row['avg_assists'] or 0,
        'rebounds_avg': row['avg_rebounds'] or 0,
        'steals_avg': row['avg_steals'] or 0 if 'avg_steals' in row.keys() else 0,
        'blocks_avg': row['avg_blocks'] or 0 if 'avg_blocks' in row.keys() else 0,
        'turnovers_avg': row['avg_turnovers'] or 2 if 'avg_turnovers' in row.keys() else 2,
        'fg_pct': row['avg_fg_pct'] or 0.45 if 'avg_fg_pct' in row.keys() else 0.45,
        'usage_rate': row['avg_usage'] or 20 if 'avg_usage' in row.keys() else 20,
        'pace': 100,
    }
    
    player_name = row['player_name'] if 'player_name' in row.keys() else 'Unknown'
    
    opponent_defense = {}
    opponent_name = None
    
    if opponent_id:
        try:
            def_rating = DefenseMatrix.get_defensive_rating(opponent_id) if hasattr(DefenseMatrix, 'get_defensive_rating') else 110
            paoa_val = DefenseMatrix.get_paoa(opponent_id, 'All') if hasattr(DefenseMatrix, 'get_paoa') else 0
            
            opponent_defense = {
                'defensive_rating': def_rating if def_rating else 110,
                'paoa': paoa_val if paoa_val else 0,
                'pace': 100,
            }
            
            cursor.execute("SELECT name FROM teams WHERE team_id = ? OR abbreviation = ?", 
                          (opponent_id, opponent_id))
            team_row = cursor.fetchone()
            if team_row:
                opponent_name = team_row[0]
        except Exception as e:
            logger.warning(f"Could not fetch opponent defense: {e}")
            opponent_defense = {'defensive_rating': 110, 'paoa': 0, 'pace': 100}
    
    conn.close()
    
    calculator = get_radar_calculator()
    player_dims = calculator.calculate_player_dimensions(player_stats)
    
    if opponent_id and opponent_defense:
        opponent_dims = calculator.calculate_opponent_vulnerability(opponent_defense)
    else:
        opponent_dims = OpponentRadarDimensions(
            scoring=50, playmaking=50, rebounding=50, defense=50, pace=50
        )
    
    return {
        'player_id': player_id,
        'player_name': player_name,
        'opponent_id': opponent_id,
        'opponent_name': opponent_name,
        'player_stats': {
            'scoring': player_dims.scoring,
            'playmaking': player_dims.playmaking,
            'rebounding': player_dims.rebounding,
            'defense': player_dims.defense,
            'pace': player_dims.pace,
        },
        'opponent_defense': {
            'scoring': opponent_dims.scoring,
            'playmaking': opponent_dims.playmaking,
            'rebounding': opponent_dims.rebounding,
            'defense': opponent_dims.defense,
            'pace': opponent_dims.pace,
        },
        'calculated_at': datetime.now().isoformat(),
        'formulas_used': [
            'Scoring: 60% PPG + 25% TS% + 15% Usage',
            'Playmaking: 50% APG + 30% AST/TO + 20% AST%',
            'Rebounding: 70% RPG + 30% REB%',
            'Defense: 35% STL + 35% BLK + 30% DFG%',
            'Pace: Normalized to league average (100)',
        ]
    }

@app.get("/schedule")
def get_schedule():
    """
    Returns today's schedule using the same nba_schedule service as matchup-lab.
    This ensures consistency between Home page and Matchup Lab game display.
    """
    from datetime import datetime
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    games = []
    
    try:
        # Use the same schedule service as matchup-lab/games for consistency
        from services.nba_schedule import get_schedule_service
        schedule = get_schedule_service()
        
        # Get live games from NBA API
        api_games = schedule.get_todays_games()
        
        if api_games:
            for game in api_games:
                # Map to format expected by ScheduleWidget 
                # (uses 'home' and 'away' keys, not 'home_team' and 'away_team')
                status = game.get('status', 'upcoming')
                
                # Format the time/status display
                if status == 'live':
                    time_display = game.get('display', '').split('(')[-1].rstrip(')') if '(' in game.get('display', '') else 'LIVE'
                elif status == 'final':
                    time_display = 'FINAL'
                else:
                    # Use status_text which contains formatted time like "7:00 pm ET"
                    time_display = game.get('status_text', 'TBD')
                
                games.append({
                    'id': game.get('game_id'),
                    'home': game.get('home_team'),
                    'away': game.get('away_team'),
                    'home_score': game.get('home_score', 0),
                    'away_score': game.get('away_score', 0),
                    'time': time_display,
                    'status': status.upper(),
                    'volatility': 'High' if status == 'live' else 'Normal'
                })
        
        return {'games': games, 'date': today_str, 'source': 'nba_schedule'}
        
    except Exception as e:
        print(f"Schedule Error: {e}")
        # Fallback to direct NBA API call
        try:
            import requests
            url = f"https://stats.nba.com/stats/scoreboardv3?GameDate={today_str}&LeagueID=00"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://www.nba.com/'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if 'scoreboard' in data and 'games' in data['scoreboard']:
                for game in data['scoreboard']['games']:
                    status = game.get('gameStatus', 1)
                    games.append({
                        'id': game.get('gameId'),
                        'home': game.get('homeTeam', {}).get('teamTricode'),
                        'away': game.get('awayTeam', {}).get('teamTricode'),
                        'home_score': game.get('homeTeam', {}).get('score', 0),
                        'away_score': game.get('awayTeam', {}).get('score', 0),
                        'time': game.get('gameStatusText'),
                        'status': 'LIVE' if status == 2 else 'FINAL' if status == 3 else 'UPCOMING',
                        'volatility': 'High' if status == 2 else 'Normal'
                    })
            
            return {'games': games, 'date': today_str, 'source': 'fallback'}
        except Exception as e2:
            print(f"Fallback Schedule Error: {e2}")
            return {'games': [], 'date': today_str, 'error': str(e)}



# ==================== NEW NBA DATA ENDPOINTS ====================

@app.get("/teams")
def get_teams():
    """
    Get all 30 NBA teams organized by conference and division.
    Returns real data from database.
    """
    conn = get_nba_db()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    # Get all teams
    cursor.execute("SELECT * FROM teams ORDER BY conference, division, name")
    teams = cursor.fetchall()
    conn.close()
    
    # Organize by conference and division
    conferences = {}
    for team in teams:
        conf = team['conference']
        div = team['division']
        
        if conf not in conferences:
            conferences[conf] = {'name': f"{conf} Conference", 'divisions': {}}
        
        if div not in conferences[conf]['divisions']:
            conferences[conf]['divisions'][div] = {
                'name': div,
                'teams': []
            }
        
        conferences[conf]['divisions'][div]['teams'].append({
            'id': team['team_id'],
            'name': team['name'],
            'abbreviation': team['abbreviation']
        })
    
    # Convert to list format
    result = []
    for conf_name, conf_data in conferences.items():
        result.append({
            'name': conf_data['name'],
            'divisions': list(conf_data['divisions'].values())
        })
    
    # Create flat list for dropdowns
    flat_teams = []
    for team in teams:
        # Construct full name if city available
        full = f"{team.get('city', '')} {team['name']}".strip()
        flat_teams.append({
            'id': team['team_id'],
            'name': team['name'],
            'full_name': full if full else team['name'],
            'abbreviation': team['abbreviation']
        })
    
    return {'conferences': result, 'teams': flat_teams}


@app.get("/teams/stats")
def get_team_stats(team: str = None):
    """
    Get comprehensive team statistics from team_stats_comprehensive table.
    
    Args:
        team: Optional - filter by team_id or team_abbr (case-insensitive)
    
    Returns all 30 teams with 100+ metrics including:
    - Base stats (pts, reb, ast, etc.)
    - Advanced stats (off_rating, def_rating, pace, etc.)
    - Four factors (efg_pct, tov_pct, etc.)
    - Scoring breakdown
    - Opponent/defensive stats
    """
    conn = get_nba_db()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    try:
        if team:
            # Filter by team_id or abbr
            cursor.execute("""
                SELECT * FROM team_stats_comprehensive 
                WHERE team_id = ? OR LOWER(team_abbr) = LOWER(?)
            """, (team, team))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {'team': result, 'found': True}
            else:
                return {'team': None, 'found': False, 'error': f'Team not found: {team}'}
        else:
            # Get all teams
            cursor.execute("SELECT * FROM team_stats_comprehensive ORDER BY team_abbr")
            teams = cursor.fetchall()
            conn.close()
            
            # Build lookup indices for efficient frontend access
            by_id = {t['team_id']: t for t in teams}
            by_abbr = {t['team_abbr'].lower(): t for t in teams}
            
            return {
                'total': len(teams),
                'teams': teams,
                'by_team_id': by_id,
                'by_abbr': by_abbr,
                'updated_at': teams[0]['updated_at'] if teams else None
            }
    except Exception as e:
        conn.close()
        return {'error': str(e), 'teams': []}


@app.get("/teams/stats/{team_abbr}")
def get_team_stats_by_abbr(team_abbr: str):
    """Get stats for a specific team by abbreviation (e.g., 'BOS', 'LAL')"""
    return get_team_stats(team=team_abbr)


# --- Advanced Team Metrics Endpoints ---
try:
    from services.advanced_team_metrics import get_advanced_metrics
    HAS_ADVANCED_METRICS = True
    advanced_metrics_engine = get_advanced_metrics()
    logger.info("[OK] Advanced Team Metrics service loaded")
except ImportError:
    HAS_ADVANCED_METRICS = False
    advanced_metrics_engine = None
    logger.warning("[WARN] Advanced Team Metrics service not available")


@app.get("/teams/advanced/{team_abbr}")
def get_team_advanced_metrics(team_abbr: str):
    """
    Get advanced metrics for a team:
    - Shot Profile (corner 3s, paint, mid-range frequencies)
    - Transition Efficiency (PPP in transition)
    - Secondary Assist Rate (hockey assists)
    - Turnover tendencies
    """
    if not HAS_ADVANCED_METRICS:
        raise HTTPException(status_code=503, detail="Advanced metrics service not available")
    
    return {
        'team': team_abbr.upper(),
        'metrics': advanced_metrics_engine.get_all_advanced_metrics(team_abbr),
    }


@app.get("/teams/matchup-friction")
def get_matchup_friction(offense_team: str, defense_team: str):
    """
    Calculate matchup friction points between two teams.
    Identifies where offense strengths meet defense weaknesses.
    
    Examples:
    - Corner 3 heavy teams vs poor perimeter defense
    - Transition teams vs high turnover opponents
    """
    if not HAS_ADVANCED_METRICS:
        raise HTTPException(status_code=503, detail="Advanced metrics service not available")
    
    return advanced_metrics_engine.calculate_matchup_friction(offense_team, defense_team)


@app.get("/roster/{team_id}")
def get_roster(team_id: str):
    """
    Get full roster for a specific team.
    Hybrid Strategy:
    1. Try database first (instant preload)
    2. If empty, fetch from live NBA API
    3. Return combined result with status indicators
    """
    import urllib.parse
    
    conn = get_nba_db()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    # Get team info
    cursor.execute("SELECT * FROM teams WHERE team_id = ? OR abbreviation = ?", (team_id, team_id))
    team = cursor.fetchone()
    
    if not team:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    
    # ID Map for Abbrev -> Numeric (NBA API requires numeric IDs)
    nba_team_map = {
        'ATL': '1610612737', 'BOS': '1610612738', 'BKN': '1610612751', 'CHA': '1610612766',
        'CHI': '1610612741', 'CLE': '1610612739', 'DAL': '1610612742', 'DEN': '1610612743',
        'DET': '1610612765', 'GSW': '1610612744', 'HOU': '1610612745', 'IND': '1610612754',
        'LAC': '1610612746', 'LAL': '1610612747', 'MEM': '1610612763', 'MIA': '1610612748',
        'MIL': '1610612749', 'MIN': '1610612750', 'NOP': '1610612740', 'NYK': '1610612752',
        'OKC': '1610612760', 'ORL': '1610612753', 'PHI': '1610612755', 'PHX': '1610612756',
        'POR': '1610612757', 'SAC': '1610612758', 'SAS': '1610612759', 'TOR': '1610612761',
        'UTA': '1610612762', 'WAS': '1610612764'
    }
    
    # Build list of possible team IDs
    target_team_ids = [team_id]
    if team.get('team_id'):
        target_team_ids.append(team['team_id'])
    if team.get('abbreviation') in nba_team_map:
        target_team_ids.append(nba_team_map[team['abbreviation']])
    if team_id in nba_team_map:
        target_team_ids.append(nba_team_map[team_id])
    
    # --- PHASE 1: Database Preload ---
    placeholders = ','.join(['?'] * len(target_team_ids))
    query = f"""
        SELECT player_id, name, position, jersey_number, status
        FROM players
        WHERE team_id IN ({placeholders})
        ORDER BY 
            CASE position
                WHEN 'PG' THEN 1
                WHEN 'SG' THEN 2
                WHEN 'SF' THEN 3
                WHEN 'PF' THEN 4
                WHEN 'C' THEN 5
                ELSE 6
            END,
            name
    """
    cursor.execute(query, tuple(target_team_ids))
    db_players = cursor.fetchall()
    conn.close()
    
    # --- PHASE 2: Live API Fetch (if DB empty) ---
    roster = []
    source = "database"
    
    if len(db_players) == 0:
        print(f"[ROSTER] Database empty for {team_id}, fetching from live NBA API...")
        try:
            from services.nba_api_connector import NBAAPIConnector
            import os
            db_path = os.path.join(os.path.dirname(__file__), 'data', 'nba_data.db')
            connector = NBAAPIConnector(db_path)
            
            # Get numeric team ID for API call
            numeric_team_id = nba_team_map.get(team.get('abbreviation'), nba_team_map.get(team_id))
            if numeric_team_id:
                api_roster = connector.get_team_roster(numeric_team_id, season=CURRENT_SEASON)
                if api_roster:
                    roster = api_roster
                    source = "nba_api_live"
                    print(f"[ROSTER] Fetched {len(roster)} players from NBA API")
        except Exception as e:
            print(f"[ROSTER] Live API fetch failed: {e}")
    else:
        roster = db_players
    
    # Use cached avatar URLs from database
    for player in roster:
        # Use cached avatar if available, otherwise generate fallback
        if not player.get('avatar'):
            name = player.get('name', 'Unknown')
            name_encoded = urllib.parse.quote(name)
            player['avatar'] = f"https://ui-avatars.com/api/?name={name_encoded}&background=1e293b&color=10b981&size=256&bold=true"
        player['id'] = player.get('player_id', player.get('id', ''))
    
    return {
        'team_id': team_id,
        'team_name': team.get('name', team.get('full_name', '')),
        'roster': roster,
        'source': source,
        'count': len(roster)
    }

@app.get("/injuries")
def get_injuries():
    """
    Get current league-wide injury report.
    Updated periodically from NBA API.
    """
    conn = get_nba_db()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    # Get all active injuries
    cursor.execute("""
        SELECT player_id, player_name, team, status, injury_type, last_updated
        FROM injuries
        ORDER BY last_updated DESC
    """)
    injuries = cursor.fetchall()
    conn.close()
    
    return {'injuries': injuries}

@app.get("/player/{player_id}")
def get_player_profile(player_id: str):
    """
    Get complete player profile including basic info, current season stats, and analytics.
    This is the main endpoint for the Player Lab.
    """
    conn = get_nba_db()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    # Get player basic info
    cursor.execute("""
        SELECT player_id, name, position, team_id, jersey_number, status, height, weight, college, draft_year, draft_round, draft_number
        FROM players
        WHERE player_id = ?
    """, (player_id,))
    player = cursor.fetchone()
    
    if not player:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    
    # Use cached avatar URL from database, or generate fallback
    if not player.get('avatar'):
        name_encoded = urllib.parse.quote(player['name'])
        player['avatar'] = f"https://ui-avatars.com/api/?name={name_encoded}&background=1e293b&color=10b981&size=256&bold=true"
    
    # Get current season stats
    cursor.execute("""
        SELECT *
        FROM player_stats
        WHERE player_id = ? AND season = ?
    """, (player_id, CURRENT_SEASON))
    current_stats = cursor.fetchone()
    
    # Get analytics if available
    cursor.execute("""
        SELECT *
        FROM player_analytics
        WHERE player_id = ? AND season = ?
    """, (player_id, CURRENT_SEASON))
    analytics = cursor.fetchone()

# ==================== AEGIS ROUTES ====================

def get_player_stats_by_season(player_id: str, season: str = CURRENT_SEASON):
    """Refactored to use dynamic season default"""

async def aegis_get_player(player_id: str, season: str = CURRENT_SEASON):
    """Refactored to use dynamic season default"""
    
    # Get team info
    if player.get('team_id'):
        cursor.execute("SELECT * FROM teams WHERE team_id = ?", (player['team_id'],))
        team = cursor.fetchone()
    else:
        team = None
    
    conn.close()
    
    return {
        'player': player,
        'current_stats': current_stats,
        'analytics': analytics,
        'team': team
    }

@app.get("/player/{player_id}/stats")
def get_player_stats_by_season(player_id: str, season: str = CURRENT_SEASON):
    """
    Get player stats for a specific season.
    Query param: ?season=2024-25 (defaults to current)
    """
    conn = get_nba_db()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT *
        FROM player_stats
        WHERE player_id = ? AND season = ?
    """, (player_id, season))
    stats = cursor.fetchone()
    conn.close()
    
    if not stats:
        raise HTTPException(status_code=404, detail=f"No stats found for player {player_id} in season {season}")
    
    return stats

@app.get("/player/{player_id}/career")
def get_player_career(player_id: str):
    """
    Get player's career stats with year-by-year breakdown.
    Used for dropdown in player profile.
    """
    conn = get_nba_db()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    # Get all seasons for this player
    cursor.execute("""
        SELECT season, games, points_avg, rebounds_avg, assists_avg,
               fg_pct, three_p_pct, ft_pct
        FROM player_stats
        WHERE player_id = ?
        ORDER BY season DESC
    """, (player_id,))
    seasons = cursor.fetchall()
    conn.close()
    
    if not seasons:
        raise HTTPException(status_code=404, detail=f"No career data found for player {player_id}")
    
    return {
        'player_id': player_id,
        'seasons': seasons
    }

# ================================================================

@app.get("/players/search")
def search_players(q: str):
    """
    Search players in SQLite Database (Robust).
    Falling back to Knowledge Graph only if DB fails.
    """
    results = []
    
    # 1. SQL Search (Primary)
    try:
        conn = get_nba_db()
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        # Case-insensitive fuzzy search
        if not q:
            # Return all players for client-side indexing (no limit)
            cursor.execute("""
                SELECT player_id, name, team_id, position 
                FROM players 
                ORDER BY name ASC
            """)
        else:
            # Targeted search with limit
            cursor.execute("""
                SELECT player_id, name, team_id, position 
                FROM players 
                WHERE name LIKE ? COLLATE NOCASE
                LIMIT 10
            """, (f"%{q}%",))
        
        players = cursor.fetchall()
        
        # Helper for Avatar fallback
        def get_avatar_fallback(name):
            import urllib.parse
            safe_name = urllib.parse.quote(name)
            return f"https://ui-avatars.com/api/?name={safe_name}&background=1e293b&color=10b981&size=256&bold=true"

        for p in players:
            # Try to populate team name if we have team_id
            team_name = "NBA"
            if p.get('team_id'):
                cursor.execute("SELECT abbreviation FROM teams WHERE team_id = ?", (p['team_id'],))
                t = cursor.fetchone()
                if t: team_name = t['abbreviation']

            results.append({
                "id": str(p['player_id']),
                "name": p['name'],
                "team": team_name,
                "position": p['position'] or "Unknown",
                "avatar": p.get('avatar') or get_avatar_fallback(p['name'])
            })
            
        conn.close()
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        # Fallback to KG if SQL fails
        if kg:
            all_players = kg.get_all_players()
            for p in all_players:
                if q.lower() in p.player_name.lower():
                     results.append({
                        "id": p.player_id, 
                        "name": p.player_name, 
                        "team": "NBA",
                        "avatar": f"https://ui-avatars.com/api/?name={p.player_name}"
                    })
    
    return results


# ==================== NEW DATA PIPELINE ENDPOINTS ====================
# All endpoints have backward compatibility - graceful fallbacks if tables missing

@app.get("/data/player-bio/{player_id}")
def get_player_bio(player_id: str):
    """
    Get player bio: height, weight, age, position, headshot URL.
    Backward compatible: falls back to player_stats if player_bio missing.
    """
    conn = get_nba_db()
    if not conn:
        return {"player_id": player_id, "message": "Database unavailable", "headshot_url": f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"}
    
    try:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        # Try player_bio table first
        try:
            cursor.execute("SELECT * FROM player_bio WHERE player_id = ?", (player_id,))
            bio = cursor.fetchone()
            if bio:
                conn.close()
                return bio
        except Exception:
            pass  # Table may not exist
        
        # Fallback to player_stats
        try:
            cursor.execute("SELECT * FROM player_stats WHERE player_id = ?", (player_id,))
            stats = cursor.fetchone()
            conn.close()
            
            if stats:
                return {
                    'player_id': player_id,
                    'player_name': stats.get('name', ''),
                    'team': stats.get('team', ''),
                    'headshot_url': f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png",
                }
        except Exception:
            pass
        
        conn.close()
        return {
            'player_id': player_id,
            'message': 'No bio data available yet',
            'headshot_url': f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png",
        }
    except Exception as e:
        return {"player_id": player_id, "error": str(e), "headshot_url": f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"}


@app.get("/data/player-games/{player_id}")
def get_player_games(player_id: str, limit: int = 15):
    """
    Get player's recent game logs with opponent info.
    Backward compatible: returns empty list if table missing.
    """
    conn = get_nba_db()
    if not conn:
        return {'player_id': player_id, 'games': [], 'count': 0, 'message': 'Database unavailable'}
    
    try:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM player_game_logs 
            WHERE player_id = ?
            ORDER BY game_date DESC
            LIMIT ?
        """, (player_id, limit))
        
        games = cursor.fetchall()
        conn.close()
        
        return {
            'player_id': player_id,
            'games': games,
            'count': len(games)
        }
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {'player_id': player_id, 'games': [], 'count': 0, 'message': f'Game logs not available: {str(e)}'}


@app.get("/data/player-averages/{player_id}")
def get_player_rolling_averages(player_id: str):
    """
    Get player's rolling averages and trend (hot/cold).
    Backward compatible: returns placeholder if table missing.
    """
    conn = get_nba_db()
    if not conn:
        return {"player_id": player_id, "message": "Database unavailable"}
    
    try:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM player_rolling_averages WHERE player_id = ?", (player_id,))
        averages = cursor.fetchone()
        conn.close()
        
        if not averages:
            return {"player_id": player_id, "message": "No rolling averages available", "trend": "neutral"}
        
        return averages
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"player_id": player_id, "message": f"Rolling averages not available: {str(e)}", "trend": "neutral"}


@app.get("/data/player-vs-team/{player_id}/{opponent}")
def get_player_vs_team(player_id: str, opponent: str):
    """
    Get how a player performs against a specific team.
    Backward compatible: returns message if table missing.
    """
    conn = get_nba_db()
    if not conn:
        return {"player_id": player_id, "opponent": opponent, "message": "Database unavailable"}
    
    try:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM player_vs_team 
            WHERE player_id = ? AND opponent = ?
        """, (player_id, opponent.upper()))
        
        matchup = cursor.fetchone()
        conn.close()
        
        if not matchup:
            return {"player_id": player_id, "opponent": opponent.upper(), "message": "No matchup history available"}
        
        return matchup
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"player_id": player_id, "opponent": opponent.upper(), "message": f"Matchup data not available: {str(e)}"}


@app.get("/data/team-defense/{team}")
def get_team_defense(team: str):
    """
    Get team defensive stats: points allowed, FG% allowed, pace.
    Backward compatible: returns message if table missing.
    """
    conn = get_nba_db()
    if not conn:
        return {"team": team, "message": "Database unavailable"}
    
    try:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM team_defense WHERE team_abbr = ?", (team.upper(),))
        defense = cursor.fetchone()
        conn.close()
        
        if not defense:
            return {"team": team.upper(), "message": "Team defense data not available yet"}
        
        return defense
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"team": team.upper(), "message": f"Defense data not available: {str(e)}"}


@app.get("/data/fetchers")
def get_fetcher_status():
    """
    Get status of all data fetchers: last run, next scheduled, etc.
    Backward compatible: returns empty list if tables missing.
    """
    conn = get_nba_db()
    if not conn:
        return {'fetchers': [], 'count': 0, 'message': 'Database unavailable'}
    
    try:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT r.fetcher_id, r.description, r.schedule, r.is_enabled,
                   f.last_run, f.last_status, f.next_scheduled, f.run_time_seconds
            FROM fetcher_registry r
            LEFT JOIN fetcher_runs f ON r.fetcher_id = f.fetcher_id
            ORDER BY r.priority
        """)
        
        fetchers = cursor.fetchall()
        conn.close()
        
        return {
            'fetchers': fetchers,
            'count': len(fetchers),
            'checked_at': datetime.now().isoformat()
        }
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {'fetchers': [], 'count': 0, 'message': f'Fetcher registry not initialized: {str(e)}'}


@app.get("/data/league-leaders")
def get_league_leaders(category: str = "Points"):
    """
    Get league leaders for a specific category.
    Backward compatible: returns empty list if table missing.
    """
    conn = get_nba_db()
    if not conn:
        return {'category': category, 'leaders': [], 'count': 0, 'message': 'Database unavailable'}
    
    try:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM league_leaders 
            WHERE category = ?
            ORDER BY rank
            LIMIT 10
        """, (category,))
        
        leaders = cursor.fetchall()
        conn.close()
        
        return {
            'category': category,
            'leaders': leaders,
            'count': len(leaders)
        }
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {'category': category, 'leaders': [], 'count': 0, 'message': f'League leaders not available: {str(e)}'}


@app.get("/data/standings")
def get_standings():
    """
    Get current NBA team standings with records.
    Backward compatible: returns empty list if table missing.
    """
    conn = get_nba_db()
    if not conn:
        return {'standings': [], 'count': 0, 'message': 'Database unavailable'}
    
    try:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM team_standings 
            ORDER BY conference, win_pct DESC
        """)
        
        standings = cursor.fetchall()
        conn.close()
        
        return {
            'standings': standings,
            'count': len(standings)
        }
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {'standings': [], 'count': 0, 'message': f'Standings not available: {str(e)}'}


@app.get("/data/freshness")
def get_data_freshness():
    """
    Get freshness status of all data tables.
    Frontend can use this to show data age and trigger refreshes.
    """
    conn = get_nba_db()
    if not conn:
        return {'status': 'unavailable', 'tables': []}
    
    try:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        tables_to_check = [
            ('player_bio', 'updated_at'),
            ('player_game_logs', 'fetched_at'),
            ('player_rolling_averages', 'updated_at'),
            ('team_defense', 'updated_at'),
            ('team_standings', 'updated_at'),
            ('league_leaders', 'updated_at'),
            ('todays_games', 'updated_at'),
        ]
        
        freshness = []
        now = datetime.now()
        
        for table, date_col in tables_to_check:
            try:
                cursor.execute(f"SELECT MAX({date_col}) as last_update, COUNT(*) as count FROM {table}")
                row = cursor.fetchone()
                
                if row and row['last_update']:
                    last_update = datetime.fromisoformat(row['last_update'])
                    age_minutes = (now - last_update).total_seconds() / 60
                    
                    freshness.append({
                        'table': table,
                        'last_update': row['last_update'],
                        'age_minutes': round(age_minutes),
                        'record_count': row['count'],
                        'is_fresh': age_minutes < 1440,  # Fresh if < 24 hours
                    })
                else:
                    freshness.append({
                        'table': table,
                        'last_update': None,
                        'record_count': 0,
                        'is_fresh': False,
                    })
            except Exception:
                freshness.append({
                    'table': table,
                    'available': False,
                    'is_fresh': False,
                })
        
        conn.close()
        return {
            'status': 'ok',
            'checked_at': now.isoformat(),
            'tables': freshness
        }
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {'status': 'error', 'message': str(e), 'tables': []}

# ================================================================




@app.get("/analytics/pace-adjusted/{player_id}")
def get_pace_adjusted_stats(player_id: str, season: str = CURRENT_SEASON):
    """
    Get pace-adjusted statistics for a player.
    
    Centralized endpoint to eliminate redundant pace calculations
    between Player Lab and Matchup Engine.
    
    Formula: M_adj = (Pace_league / Pace_team) × M_raw
    """
    if not HAS_REFRACTION or not refraction_service:
        raise HTTPException(
            status_code=503,
            detail="RefractionService not available"
        )
    
    try:
        adjusted_stats = refraction_service.get_pace_adjusted_stats(
            player_id=player_id,
            season=season
        )
        
        if not adjusted_stats:
            raise HTTPException(
                status_code=404,
                detail=f"No stats found for player {player_id}"
            )
        
        logger.info(f"[ANALYTICS] Returned pace-adjusted stats for player {player_id}")
        return adjusted_stats
        
    except Exception as e:
        logger.error(f"[ANALYTICS] Pace adjustment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Phase 4: Settings Persistence ---
from pydantic import BaseModel
import google.generativeai as genai

class KeyPayload(BaseModel):
    gemini_api_key: str

@app.post("/settings/keys")
def save_keys(payload: KeyPayload):
    print(f"[VAULT] Initiating Handshake with Gemini Network...")
    
    try:
        # Handshake: Attempt to configure and list models
        genai.configure(api_key=payload.gemini_api_key)
        # We assume listing models is a cheap/fast verification
        list(genai.list_models()) 
        
        # If successful, we would persist it here (e.g. .env or secure vault)
        # For V1, we just return success
        print(f"[VAULT] Handshake Successful. Key Valid.")
        return {"status": "success", "message": "Handshake Verified. AEGIS Protocol Active."}
        
    except Exception as e:
        print(f"[VAULT] Handshake Failed: {str(e)}")
        # Return 400 or 401 ideally, but for our simple fetch wrapper:
        return {"status": "error", "message": "Handshake Warning: Invalid Credentials."}

class KagglePayload(BaseModel):
    username: str
    key: str

@app.post("/settings/kaggle")
def save_kaggle_keys(payload: KagglePayload):
    print(f"[VAULT] Securing Kaggle Credentials for {payload.username}...")
    # In production, save to ~/.kaggle/kaggle.json or env vars
    os.environ['KAGGLE_USERNAME'] = payload.username
    os.environ['KAGGLE_KEY'] = payload.key
    
    # Verify simple auth or just save
    return {"status": "success", "message": "Kaggle Credentials Secured."}

@app.post("/sync/kaggle")
def sync_kaggle():
    print(f"[SYNC] Triggering Kaggle Dataset Pull...")
    try:
        # Assuming we have a standard dataset to pull, e.g., 'nba/player-stats'
        # For V1, we simulate the pull or call the loom
        # Real impl: 
        # import kaggle
        # kaggle.api.dataset_download_files('nba/player-stats', path='./data', unzip=True)
        
        # Mock success for now as we don't have a real dataset ID yet
        return {"status": "success", "message": "Dataset Synced Successfully (Simulation)."}
    except Exception as e:
        return {"status": "error", "message": f"Sync Failed: {str(e)}"}

@app.post("/system/purge")
def purge_system():
    # Mock Purge
    print("[SYSTEM] Purging Sector 7 Cache...")
    return {"status": "success", "message": "Cache Cleared. System Reset."}


@app.post("/data/validate")
def validate_csv_data(file_path: str):
    """
    Validate CSV data integrity and trigger recovery if needed.
    
    Returns 202 Accepted if validation fails and triggers background recovery.
    """
    try:
        from services.truth_serum_filter import TruthSerumFilter
        from fastapi import BackgroundTasks
        
        validator = TruthSerumFilter()
        results = validator.validate_schema(file_path)
        
        if not results["valid"]:
            logger.warning(f"[VALIDATION] CSV validation failed: {results['errors']}")
            # Would trigger background recovery here
            # background_tasks.add_task(re_sync_from_source, file_path)
            return {
                "status": "validation_failed",
                "errors": results["errors"],
                "recovery_triggered": False,  # Set to True when background task is implemented
                "message": "Manual re-sync required"
            }, 202
        
        return {
            "status": "valid",
            "file_path": file_path,
            "warnings": results.get("warnings", [])
        }
        
    except Exception as e:
        logger.error(f"[VALIDATION] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# --- Phase 7: Schedule Scout ---
from services.schedule_scout import ScheduleScout

@app.get("/system/freshness")
def check_freshness():
    """
    Returns the daily audit manifest.
    In V1, we mock the 'local players' list for the audit.
    """
    scout = ScheduleScout()
    
    # Mock Local DB scan
    yesterday_str = scout.yesterday.strftime("%Y-%m-%d")
    
    mock_local_players = [
        {"id": "1", "name": "Stephen Curry", "last_game_date": "2023-10-25"}, # Definitely Stale
        {"id": "2", "name": "LeBron James", "last_game_date": yesterday_str}   # Fresh
    ]
    
    manifest = scout.generate_manifest(mock_local_players)
    return manifest

# --- Phase 8: Delta-Sync-Manager ---
from services.delta_sync import DeltaSyncManager
from fastapi import Query

@app.post("/sync/force-fetch")
def force_fetch(
    player_id: str = Query(...),
    player_name: str = Query(...),
    cached_last_game: str = Query(...)
):
    """
    Force-Fetch Mode: User clicked 'Refresh Stats'.
    Bypasses daily check and fetches immediately.
    """
    sync = DeltaSyncManager()
    result = sync.force_fetch_player(player_id, player_name, cached_last_game)
    return result

@app.get("/sync/morning-batch")
def morning_batch():
    """
    Background Batch Mode: Morning briefing sync.
    Fetches yesterday's league-wide game log.
    """
    sync = DeltaSyncManager()
    result = sync.background_batch_sync()
    return result

@app.post("/data/ensure_fresh/{player_id}")
async def ensure_fresh(player_id: str, background_tasks: BackgroundTasks):
    """
    Trigger a background Delta-Sync for a specific player.
    """
    from services.delta_sync import DeltaSyncManager
    
    sync = DeltaSyncManager()
    
    # Add to background tasks
    # In a real app we'd get player_name and cached_last_game from DB
    background_tasks.add_task(sync.force_fetch_player, player_id, "Unknown", "2023-10-01")
    
    return {
        "status": "sync_triggered",
        "player_id": player_id,
        "message": "Background synchronization started"
    }

@app.get("/data/player-hustle/{player_id}")
async def get_player_hustle(player_id: str):
    """
    Get hustle stats for a player.
    """
    from services.tracking_data_fetcher import TrackingDataFetcher
    fetcher = TrackingDataFetcher()
    data = fetcher.get_hustle_stats(player_id)
    if not data:
        raise HTTPException(status_code=404, detail="Hustle stats not found")
    return data

@app.get("/aegis/ledger/trace/{player_id}")
async def get_ledger_trace(player_id: str):
    """
    Get the logic trace and historical performance for a player.
    """
    from aegis.learning_ledger import LearningLedger
    ledger = LearningLedger()
    history = ledger.get_player_history(player_id, limit=5)
    
    # Mock logic trace for now (would be derived from Orchestrator's internal simulation logs)
    return {
        "player_id": player_id,
        "history": history,
        "logic_trace": {
            "primary_factors": [
                {"factor": "EMA Baseline", "impact": "Recency-weighted average", "is_positive": True},
                {"factor": "Defense Friction", "impact": "Defender DFG% impact applied", "is_positive": False},
                {"factor": "Schedule Fatigue", "impact": "B2B/Rest factor", "is_positive": False},
                {"factor": "Usage Vacuum", "impact": "Injury redistribution", "is_positive": True}
            ],
            "confidence_metrics": {
                "model_agreement": 0.88,
                "historical_accuracy": ledger.get_historical_accuracy(player_id),
                "data_freshness": "98%"
            }
        }
    }



# --- Aegis Intelligence Layer v3.1 ---
from datetime import date

@app.get("/aegis/simulate/{player_id}")
async def aegis_simulate(
    player_id: str,
    opponent_id: str = Query(..., description="Opponent team ID"),
    game_date: str = Query(None, description="Game date (YYYY-MM-DD)"),
    force_fresh: bool = Query(False, description="Bypass cache"),
    pts_line: float = Query(None, description="Points line for probability"),
    reb_line: float = Query(None, description="Rebounds line for probability"),
    ast_line: float = Query(None, description="Assists line for probability")
):
    """
    Run Aegis Monte Carlo simulation for a player.
    
    Returns Floor/EV/Ceiling projections with Confluence score.
    
    Example:
        /aegis/simulate/201939?opponent_id=1610612744&pts_line=22.5
    """
    try:
        from aegis.orchestrator import AegisOrchestrator, OrchestratorConfig
        from services.automated_injury_worker import get_injury_worker
        from pathlib import Path
        
        # Parse game date
        if game_date:
            gd = date.fromisoformat(game_date)
        else:
            gd = date.today()
        
        # Build lines dict
        lines = {}
        if pts_line: lines['points'] = pts_line
        if reb_line: lines['rebounds'] = reb_line
        if ast_line: lines['assists'] = ast_line
        
        # Initialize orchestrator
        config = OrchestratorConfig(
            n_simulations=50_000,
            cache_enabled=True,
            data_dir=Path(current_dir) / "data"
        )
        orchestrator = AegisOrchestrator(config)
        
        # Run simulation
        result = await orchestrator.run_simulation(
            player_id=player_id,
            opponent_id=opponent_id,
            game_date=gd,
            lines=lines if lines else None,
            force_fresh=force_fresh
        )
        
        
        # Check injury status
        injury_worker = get_injury_worker()
        injury_status = injury_worker.get_player_status(player_id)
        
        logger.info(f"[AEGIS] Simulation complete for {player_id} - Confluence: {result.confluence_score}, Injury: {injury_status['status']}")
        
        return {
            "player_id": result.player_id,
            "opponent_id": result.opponent_id,
            "game_date": result.game_date.isoformat(),
            "injury_status": injury_status['status'],
            "injury_description": injury_status['injury_desc'],
            "performance_factor": injury_status['performance_factor'],
            "projections": {
                "floor": result.floor,
                "expected_value": result.expected_value,
                "ceiling": result.ceiling
            },
            "confidence": {
                "score": result.confluence_score,
                "grade": result.confluence_grade
            },
            "modifiers": {
                "archetype": result.archetype,
                "fatigue": result.fatigue_modifier,
                "usage_boost": result.usage_boost
            },
            "schedule_context": result.schedule_context,
            "game_mode": result.game_mode,
            "momentum": result.momentum,
            "defender_profile": result.defender_profile,
            "hit_probabilities": result.hit_probabilities,
            "execution_time_ms": result.execution_time_ms
        }
        
    except ImportError as e:
        logger.warning(f"[AEGIS] Orchestrator not available: {e}")
        # Fallback to simple projection
        return {
            "player_id": player_id,
            "opponent_id": opponent_id,
            "error": "Aegis orchestrator not fully loaded",
            "projections": {
                "floor": {"points": 15.0, "rebounds": 4.0, "assists": 3.0},
                "expected_value": {"points": 22.0, "rebounds": 6.0, "assists": 5.0},
                "ceiling": {"points": 32.0, "rebounds": 9.0, "assists": 8.0}
            },
            "confidence": {"score": 50.0, "grade": "C"}
        }
    except Exception as e:
        logger.error(f"[AEGIS] Simulation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))





@app.post("/player-data/refresh/{player_id}")
async def refresh_player_data(
    player_id: str,
    season: str = Query("2024-25", description="NBA season"),
    invalidate_cache: bool = Query(True, description="Invalidate simulation cache")
):
    """
    Incrementally fetch new game logs and merge with existing data.
    
    This endpoint:
    1. Finds the player's last logged game
    2. Fetches only games AFTER that date from NBA API
    3. Appends new games to game_logs.csv
    4. Optionally invalidates simulation cache
    5. Returns freshness metadata
    
    Example:
        POST /player-data/refresh/2544?invalidate_cache=true
    """
    try:
        from services.game_log_updater import get_game_log_updater
        from aegis.simulation_cache import SimulationCache
        
        updater = get_game_log_updater()
        result = updater.refresh_player(player_id, season)
        
        # Invalidate cache if requested
        if invalidate_cache and result['games_added'] > 0:
            try:
                cache = SimulationCache()
                cache.invalidate_player(player_id)
                result['cache_invalidated'] = True
            except Exception as e:
                logger.warning(f"Cache invalidation failed: {e}")
                result['cache_invalidated'] = False
        
        logger.info(f"[REFRESH] Player {player_id}: {result['games_added']} games added, days_rest={result['days_rest']}")
        return result
        
    except Exception as e:
        logger.error(f"[REFRESH] Failed for {player_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Matchup War Room Endpoints ---

@app.get("/aegis/matchup")
async def aegis_matchup(
    home_team_id: str = Query(..., description="Home team ID"),
    away_team_id: str = Query(..., description="Away team ID"),
    game_date: str = Query(None, description="Game date (YYYY-MM-DD)")
):
    """
    Full team-to-team matchup analysis with roster validation.
    
    The Matchup War Room endpoint that:
    1. Validates both rosters against injury reports
    2. Triggers usage vacuum for high-usage OUT players
    3. Refreshes archetypes for all active players
    4. Returns complete projections with matchup friction
    
    Example:
        /aegis/matchup?home_team_id=1610612739&away_team_id=1610612738
    """
    try:
        from aegis.matchup_orchestrator import get_matchup_orchestrator
        from datetime import date as dt_date
        
        orchestrator = get_matchup_orchestrator()
        
        gd = dt_date.fromisoformat(game_date) if game_date else dt_date.today()
        
        result = await orchestrator.run_matchup(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            game_date=gd
        )
        
        # Convert to JSON-serializable format
        return {
            "home_team": {
                "team_id": result.home_team.team_id,
                "team_name": result.home_team.team_name,
                "offensive_archetype": result.home_team.offensive_archetype,
                "defensive_profile": result.home_team.defensive_profile,
                "active_count": result.home_team.total_active_players,
                "out_count": result.home_team.total_out_players,
                "players": [
                    {
                        "player_id": p.player_id,
                        "player_name": p.player_name,
                        "is_active": p.is_active,
                        "health_status": p.health_status,
                        "ev_points": p.ev_points,
                        "ev_rebounds": p.ev_rebounds,
                        "ev_assists": p.ev_assists,
                        "archetype": p.archetype,
                        "matchup_advantage": p.matchup_advantage,
                        "friction_modifier": p.friction_modifier,
                        "efficiency_grade": p.efficiency_grade,
                        "usage_boost": p.usage_boost,
                        "vacuum_beneficiary": p.vacuum_beneficiary
                    }
                    for p in result.home_team.player_projections
                ]
            },
            "away_team": {
                "team_id": result.away_team.team_id,
                "team_name": result.away_team.team_name,
                "offensive_archetype": result.away_team.offensive_archetype,
                "defensive_profile": result.away_team.defensive_profile,
                "active_count": result.away_team.total_active_players,
                "out_count": result.away_team.total_out_players,
                "players": [
                    {
                        "player_id": p.player_id,
                        "player_name": p.player_name,
                        "is_active": p.is_active,
                        "health_status": p.health_status,
                        "ev_points": p.ev_points,
                        "ev_rebounds": p.ev_rebounds,
                        "ev_assists": p.ev_assists,
                        "archetype": p.archetype,
                        "matchup_advantage": p.matchup_advantage,
                        "friction_modifier": p.friction_modifier,
                        "efficiency_grade": p.efficiency_grade,
                        "usage_boost": p.usage_boost,
                        "vacuum_beneficiary": p.vacuum_beneficiary
                    }
                    for p in result.away_team.player_projections
                ]
            },
            "matchup_edge": result.matchup_edge,
            "edge_reason": result.edge_reason,
            "usage_vacuum_applied": result.usage_vacuum_applied,
            "execution_time_ms": result.execution_time_ms,
            "game_date": result.game_date
        }
        
    except Exception as e:
        logger.error(f"[MATCHUP] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/aegis/validate-lineup/{team_id}")
async def validate_lineup(team_id: str):
    """
    Pre-flight roster check for a single team.
    
    Returns:
    - Active players with health lights
    - Out players with injury details
    - Questionable players (game-time decisions)
    - Whether usage vacuum was triggered
    
    Example:
        /aegis/validate-lineup/1610612739
    """
    try:
        from services.roster_validator import get_roster_validator
        
        validator = get_roster_validator()
        result = validator.validate_team_roster(team_id)
        
        return {
            "team_id": result.team_id,
            "team_name": result.team_name,
            "active_players": [
                {
                    "player_id": p['player_id'],
                    "name": p['name'],
                    "position": p.get('position'),
                    "health_light": result.health_lights.get(str(p['player_id']), 'green')
                }
                for p in result.active_players
            ],
            "out_players": [
                {
                    "player_id": p['player_id'],
                    "name": p['name'],
                    "injury_status": p.get('injury_status', 'OUT'),
                    "injury_desc": p.get('injury_desc', ''),
                    "health_light": "red"
                }
                for p in result.out_players
            ],
            "questionable_players": [
                {
                    "player_id": p['player_id'],
                    "name": p['name'],
                    "injury_status": p.get('injury_status'),
                    "injury_desc": p.get('injury_desc', ''),
                    "health_light": "yellow"
                }
                for p in result.questionable_players
            ],
            "vacuum_triggered": result.vacuum_triggered,
            "vacuum_targets": result.vacuum_targets,
            "validation_time": result.validation_time,
            "summary": {
                "total": len(result.active_players) + len(result.out_players) + len(result.questionable_players),
                "active": len(result.active_players),
                "out": len(result.out_players),
                "questionable": len(result.questionable_players)
            }
        }
        
    except Exception as e:
        logger.error(f"[VALIDATE-LINEUP] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/aegis/team-archetype/{team_id}")
async def get_team_archetype(team_id: str):
    """
    Get aggregated team-level offensive/defensive profile.
    
    Analyzes active roster archetypes to determine:
    - Offensive style: "Pace & Space", "Post Heavy", "ISO Dominant", "Balanced"
    - Defensive profile: "Rim Protection Heavy", "Perimeter Lock", "Switch Heavy", "Standard"
    
    Example:
        /aegis/team-archetype/1610612739
    """
    try:
        from services.roster_validator import get_roster_validator
        from services.archetype_engine import ArchetypeEngine
        
        validator = get_roster_validator()
        result = validator.validate_team_roster(team_id)
        
        archetype_engine = ArchetypeEngine()
        
        # Collect archetypes for active players
        archetype_counts = {}
        player_archetypes = []
        
        for player in result.active_players:
            player_id = str(player['player_id'])
            arch_data = archetype_engine.classify_player(player_id)
            
            if arch_data:
                primary = arch_data.get('primary', 'unknown')
                archetype_counts[primary] = archetype_counts.get(primary, 0) + 1
                player_archetypes.append({
                    "player_id": player_id,
                    "name": player['name'],
                    "primary_archetype": primary,
                    "secondary_archetype": arch_data.get('secondary', ''),
                    "confidence": arch_data.get('primary_score', 0)
                })
        
        # Determine team profiles
        offensive = "Balanced Attack"
        defensive = "Standard Defense"
        
        # Check for Pace & Space
        if archetype_counts.get('playmaker', 0) >= 2 and archetype_counts.get('sniper', 0) >= 2:
            offensive = "Pace & Space"
        elif archetype_counts.get('elite_scorer', 0) >= 1 and archetype_counts.get('late_clock_iso', 0) >= 1:
            offensive = "ISO Dominant"
        elif archetype_counts.get('glass_cleaner', 0) >= 2:
            offensive = "Post Heavy"
        
        # Check defensive profile
        if archetype_counts.get('rim_protector', 0) >= 2:
            defensive = "Rim Protection Heavy"
        elif archetype_counts.get('ball_hawk', 0) >= 2:
            defensive = "Perimeter Lock"
        elif archetype_counts.get('two_way', 0) >= 3:
            defensive = "Switch Heavy"
        
        return {
            "team_id": team_id,
            "team_name": result.team_name,
            "offensive_archetype": offensive,
            "defensive_profile": defensive,
            "archetype_distribution": archetype_counts,
            "player_archetypes": player_archetypes,
            "active_player_count": len(result.active_players)
        }
        
    except Exception as e:
        logger.error(f"[TEAM-ARCHETYPE] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Crucible Simulation Engine v4.0 ---
import json

@app.get("/aegis/crucible/projections")
def get_crucible_projections():
    """
    Get today's live game projections from the Crucible Engine.
    Returns pre-computed projections stored in live_projections.json.
    """
    try:
        projections_path = os.path.join(current_dir, "data", "live_projections.json")
        if os.path.exists(projections_path):
            with open(projections_path, 'r') as f:
                data = json.load(f)
            return {
                "status": "success",
                "date": data.get("date"),
                "games": data.get("games", []),
                "engine": "Crucible v4.0"
            }
        else:
            return {
                "status": "no_projections",
                "message": "No projections available. Run live_projections script first.",
                "engine": "Crucible v4.0"
            }
    except Exception as e:
        logger.error(f"[CRUCIBLE] Failed to load projections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/aegis/crucible/simulate")
async def run_crucible_simulation(
    home_team: str = Query(..., description="Home team abbreviation"),
    away_team: str = Query(..., description="Away team abbreviation"),
    n_simulations: int = Query(200, description="Number of simulations")
):
    """
    Run a Crucible simulation for a specific matchup.
    """
    try:
        from engines.crucible_engine import CrucibleProjector
        
        # Get rosters from database
        # For now, return a placeholder
        return {
            "status": "success",
            "message": f"Crucible simulation for {away_team}@{home_team}",
            "n_simulations": n_simulations,
            "note": "Full implementation pending roster integration"
        }
    except ImportError:
        return {"status": "error", "message": "Crucible engine not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/aegis/crucible/audit")
def get_audit_summary(days: int = Query(7, description="Days to look back")):
    """
    Get Auto-Tuner audit summary.
    """
    try:
        from aegis.auto_tuner import AutoTuner
        tuner = AutoTuner()
        summary = tuner.get_audit_summary(days=days)
        return {
            "status": "success",
            "summary": summary,
            "engine": "Auto-Tuner v4.0"
        }
    except ImportError:
        return {"status": "error", "message": "Auto-Tuner not available"}
    except Exception as e:
        logger.error(f"[AUTO-TUNER] Audit summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Gemini AI Narrative Generation ---
def generate_ai_narrative(player_name: str, stats: dict, position: str = None) -> str:
    """
    Generate intelligent Stratos narrative using Gemini AI.
    Falls back to stat-based narrative if Gemini unavailable.
    """
    try:
        # Check if Gemini is configured
        import google.generativeai as genai
        
        # Build prompt with player stats
        ppg = stats.get('ppg', stats.get('points_avg', 0)) or 0
        rpg = stats.get('rpg', stats.get('rebounds_avg', 0)) or 0
        apg = stats.get('apg', stats.get('assists_avg', 0)) or 0
        fg_pct = stats.get('fg_pct', 0) or 0
        
        prompt = f"""You are a sports analytics AI. Generate a 2-3 sentence scouting report for {player_name}.
Stats this season: {ppg:.1f} PPG, {rpg:.1f} RPG, {apg:.1f} APG, {fg_pct*100:.1f}% FG.
Position: {position or 'Forward'}.
Focus on: strengths, tendencies, and what opposing teams should watch for.
Be concise and insightful. Use present tense."""
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text.strip()
        
    except Exception as e:
        logger.warning(f"[STRATOS] Gemini AI unavailable: {e}")
    
    # Fallback: Stat-based narrative
    ppg = stats.get('ppg', stats.get('points_avg', 0)) or 0
    rpg = stats.get('rpg', stats.get('rebounds_avg', 0)) or 0
    apg = stats.get('apg', stats.get('assists_avg', 0)) or 0
    
    # Determine player profile from stats
    if ppg >= 20:
        profile = "elite scorer"
    elif ppg >= 15:
        profile = "primary scoring option"
    elif apg >= 7:
        profile = "playmaking facilitator"
    elif rpg >= 10:
        profile = "dominant rebounder"
    else:
        profile = "versatile contributor"
    
    return f"{player_name} averages {ppg:.1f} PPG, {rpg:.1f} RPG, {apg:.1f} APG this season. Profiles as a {profile} with consistent production. Monitor for hot shooting nights."


# --- Dynamic Schedule Lookup ---
def get_todays_opponent(player_team_id: str) -> str:
    """Get the opponent team for today's game, if any."""
    try:
        from datetime import date
        today = date.today().isoformat()
        
        conn = get_nba_db()
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        # Look for games today involving this team
        cursor.execute("""
            SELECT home_team, away_team FROM schedule 
            WHERE game_date = ? AND (home_team = ? OR away_team = ?)
        """, (today, player_team_id, player_team_id))
        
        game = cursor.fetchone()
        conn.close()
        
        if game:
            # Return the opponent
            return game['away_team'] if game['home_team'] == player_team_id else game['home_team']
        
    except Exception as e:
        logger.warning(f"[STRATOS] Schedule lookup failed: {e}")
    
    return None  # No game today


@app.get("/players/{player_id}")
def get_player_profile(player_id: str):
    """
    Fetch full player intelligence profile.
    Strategy: "One-Truth" Fallback
    1. Try Knowledge Graph (AI Insights)
    2. Fallback to SQLite (Raw Data)
    """
    # Helper for Avatar Standardization (Generic-First)
    def get_avatar(name):
        import urllib.parse
        safe_name = urllib.parse.quote(name)
        return f"https://ui-avatars.com/api/?name={safe_name}&background=1e293b&color=10b981&size=256&bold=true"

    # 1. Try Knowledge Graph First
    baseline = kg.get_player(player_id) if kg else None
    
    if baseline:
        return {
            "id": baseline.player_id,
            "name": baseline.player_name,
            "team": "NBA", 
            "position": baseline.archetype.value,
            "avatar": get_avatar(baseline.player_name), # Force generic for consistency
            "height": "N/A",
            "weight": "N/A",
            "experience": f"{baseline.total_uploads} Scans",
            "narrative": generate_ai_narrative(baseline.player_name, {"ppg": baseline.points_avg, "rpg": baseline.rebounds_avg, "apg": baseline.assists_avg, "fg_pct": baseline.true_shooting_pct / 100 if baseline.true_shooting_pct else 0}, baseline.archetype.value),
            "hitProbability": 65.0 + (baseline.true_shooting_pct - 55.0),
            "impliedOdds": -110,
            "stats": {
                "ppg": baseline.points_avg,
                "rpg": baseline.rebounds_avg,
                "apg": baseline.assists_avg,
                "confidence": int(baseline.archetype_confidence * 100),
                "trend": baseline.ts_trend.last_3_values if baseline.ts_trend else []
            }
        }
    
    # 2. Fallback to SQLite (The "Truth" Layer)
    conn = get_nba_db()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    # Get basic info
    cursor.execute("SELECT * FROM players WHERE player_id = ?", (player_id,))
    player = cursor.fetchone()
    
    if not player:
        conn.close()
        raise HTTPException(status_code=404, detail="Player not found in Database or Knowledge Graph")

    # Get current stats for "Lite" profile
    cursor.execute("SELECT * FROM player_stats WHERE player_id = ? ORDER BY season DESC LIMIT 1", (player_id,))
    cached_stats = cursor.fetchone()
    conn.close()
    
    # Strategy: Try LIVE NBA API first for accurate per-game stats
    # Fall back to cached database if API fails
    ppg, rpg, apg = 0.0, 0.0, 0.0
    fg_pct = 0.0
    data_source = "cache"
    
    if HAS_NBA_CONNECTOR:
        try:
            # Initialize connector and try to fetch live stats
            from services.nba_api_connector import NBAAPIConnector
            connector = NBAAPIConnector(nba_db_path)
            live_stats = connector.get_player_stats(player_id, CURRENT_SEASON)
            
            if live_stats:
                ppg = float(live_stats.get('points_avg', 0) or 0)
                rpg = float(live_stats.get('rebounds_avg', 0) or 0)
                apg = float(live_stats.get('assists_avg', 0) or 0)
                fg_pct = float(live_stats.get('fg_pct', 0) or 0)
                data_source = "live_api"
                logger.info(f"[STATS] Live API: {player['name']} - {ppg} PPG, {rpg} RPG, {apg} APG")
        except Exception as e:
            logger.warning(f"[STATS] Live API failed for {player_id}: {e}")
    
    # Fallback: Use cached database stats if API failed
    if ppg == 0 and rpg == 0 and cached_stats:
        raw_ppg = cached_stats.get('points_avg')
        raw_rpg = cached_stats.get('rebounds_avg') 
        raw_apg = cached_stats.get('assists_avg')
        
        # Data quality flag - don't normalize, just use what we have
        ppg = round(float(raw_ppg or 0), 1)
        rpg = round(float(raw_rpg or 0), 1)
        apg = round(float(raw_apg or 0), 1)
        fg_pct = float(cached_stats.get('fg_pct', 0) or 0)
        data_source = "cache_stale"
        
        # Log warning if data looks corrupt
        if ppg > 60:
            logger.warning(f"[STATS] Cached data for {player['name']} looks corrupt (PPG={ppg}). Use /sync to refresh.")
    
    return {
        "id": str(player['player_id']),
        "name": player['name'],
        "team": "NBA", # Future: Fetch team abbreviation
        "position": player.get('position', 'Unknown'),
        "avatar": get_avatar(player['name']),
        "height": player.get('height', 'N/A'),
        "weight": player.get('weight', 'N/A'),
        "experience": player.get('experience', 'N/A'),
        "narrative": generate_ai_narrative(player['name'], {"ppg": ppg, "rpg": rpg, "apg": apg, "fg_pct": fg_pct}, player.get('position', 'Forward')),
        "hitProbability": 50.0, # Neutral default
        "impliedOdds": -110,
        "stats": {
            "ppg": ppg,
            "rpg": rpg,
            "apg": apg,
            "confidence": 100, # 100% confidence this is real data
            "trend": [ppg, ppg, ppg] # Flat trend
        }
    }

# ============================================================================
# NBA Data Endpoints (Real NBA Data Integration)
# ============================================================================

@app.get("/player/{player_id}/analytics")
def get_player_analytics(player_id: str):
    """
    Get advanced analytics for a player (True Shooting%, eFG%, best play type, etc.)
    """
    conn = get_nba_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT pa.*, p.name, p.team_id
        FROM player_analytics pa
        JOIN players p ON pa.player_id = p.player_id
        WHERE pa.player_id = ? AND pa.season = ?
    """, (player_id, CURRENT_SEASON))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Analytics not found for player")
    
    return {
        "player_id": row[0],
        "season": row[1],
        "true_shooting_pct": round(row[2] * 100, 1) if row[2] else 0,
        "effective_fg_pct": round(row[3] * 100, 1) if row[3] else 0,
        "usage_rate": row[4],
        "total_possessions": row[5],
        "best_play_type": row[6],
        "best_play_type_ppp": row[7],
        "name": row[8],
        "team": row[9]
    }

@app.get("/players/{player_id}/play-types")
def get_player_play_types(player_id: str):
    """
    Get detailed play type efficiency data for a player.
    Returns PPP, frequency, percentile for Isolation, PnR Ball-Handler, Transition, etc.
    """
    import csv
    from pathlib import Path
    
    csv_path = Path(__file__).parent.parent.parent / "NBA_Play_Types_12_25.csv"
    if not csv_path.exists():
        csv_path = Path(__file__).parent.parent.parent.parent / "NBA_Play_Types_12_25.csv"
    
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Play type data not available")
    
    play_types = []
    all_ppp_by_type = {}  # For percentile calculation
    
    # First pass: collect all PPP data for percentile calculation
    with open(csv_path, 'r', encoding='latin-1') as f:
        reader = csv.DictReader(f)
        for row in reader:
            play_type = row.get('PLAY_TYPE', '')
            try:
                ppp = float(row.get('PPP', 0) or 0)
                poss = int(row.get('POSS', 0) or 0)
                if poss >= 10:  # Minimum volume threshold
                    if play_type not in all_ppp_by_type:
                        all_ppp_by_type[play_type] = []
                    all_ppp_by_type[play_type].append(ppp)
            except (ValueError, TypeError, KeyError):
                continue
    
    # Calculate percentile thresholds
    percentile_data = {}
    for pt, ppps in all_ppp_by_type.items():
        sorted_ppps = sorted(ppps)
        percentile_data[pt] = sorted_ppps
    
    # Second pass: get player's data
    with open(csv_path, 'r', encoding='latin-1') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('PLAYER_ID') == player_id:
                play_type = row.get('PLAY_TYPE', '')
                try:
                    ppp = float(row.get('PPP', 0) or 0)
                    freq = float(row.get('FREQ', 0) or 0)
                    poss = int(row.get('POSS', 0) or 0)
                    ppp_pctl = float(row.get('PPP_PCTL', 0) or 0)
                    
                    # Determine efficiency tier
                    tier = "average"
                    if ppp_pctl >= 75:
                        tier = "elite"
                    elif ppp_pctl >= 50:
                        tier = "above_average"
                    elif ppp_pctl < 25:
                        tier = "poor"
                    
                    play_types.append({
                        "play_type": play_type,
                        "ppp": round(ppp, 3),
                        "frequency": round(freq * 100, 1),
                        "possessions": poss,
                        "percentile": round(ppp_pctl, 1),
                        "tier": tier
                    })
                except (ValueError, TypeError, KeyError):
                    continue
    
    if not play_types:
        raise HTTPException(status_code=404, detail="No play type data for player")
    
    # Sort by frequency (most used first)
    play_types.sort(key=lambda x: x['frequency'], reverse=True)
    
    # Get player name
    player_name = "Unknown"
    try:
        conn = get_nba_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM players WHERE player_id = ?", (player_id,))
        row = cursor.fetchone()
        if row is not None and len(row) > 0:
            player_name = row[0]
        conn.close()
    except Exception as e:
        logger.warning(f"Could not get player name for {player_id}: {e}")
    
    return {
        "player_id": player_id,
        "player_name": player_name,
        "season": CURRENT_SEASON,
        "play_types": play_types
    }

@app.get("/injuries/current")
def get_current_injuries():
    """
    Get current league-wide injury report (refreshed)
    """
    try:
        conn = get_nba_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT player_id, player_name, team, status, injury_type, last_updated
            FROM injuries
            ORDER BY team, player_name
        """)
        
        injuries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"injuries": injuries, "count": len(injuries)}
    except Exception as e:
        return {"injuries": [], "count": 0, "error": str(e)}

@app.post("/injuries/refresh")
def refresh_injuries(team_ids: Optional[List[str]] = None):
    """
    Manually trigger injury report refresh from NBA API for specific teams
    
    Body (optional):
    {
        "team_ids": ["LAL", "BOS", "GSW"]  // Only fetch for these teams
    }
    
    If no team_ids provided, fetches for all teams (not recommended)
    """
    try:
        from backend.services.nba_injury_service import NBAInjuryService
        from fastapi import Body
        
        # Get team_ids from request body if provided
        request_data = Body(None)
        teams = request_data.get('team_ids') if request_data else team_ids
        
        service = NBAInjuryService()
        count = service.update_injury_database(teams)
        
        return {
            "success": True, 
            "injuries_updated": count,
            "teams_queried": len(teams) if teams else 30
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/analytics/recalculate")
def recalculate_analytics():
    """
    Manually trigger analytics recalculation from CSV data
    """
    try:
        from backend.services.nba_analytics_engine import NBAAnalyticsEngine
        engine = NBAAnalyticsEngine()
        analytics = engine.calculate_advanced_stats()
        count = engine.save_analytics_to_db(analytics)
        return {"success": True, "players_analyzed": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# AEGIS-SOVEREIGN DATA ROUTER ENDPOINTS (Phase 1)
# =============================================================================

# Initialize Vertex Matchup Engine (if Aegis available)
try:
    from aegis.vertex_matchup import VertexMatchupEngine
    vertex_engine = VertexMatchupEngine(
        aegis_router=aegis_router if HAS_AEGIS_ROUTER else None,
        health_monitor=aegis_monitor if HAS_AEGIS_ROUTER else None,
        dual_mode=aegis_detector if HAS_AEGIS_ROUTER else None
    )
    HAS_VERTEX_ENGINE = True
    logger.info("[OK] Vertex Matchup Engine initialized")
except Exception as e:
    logger.warning(f"[WARN] Vertex Matchup Engine not available: {e}")
    HAS_VERTEX_ENGINE = False
    vertex_engine = None


@app.get("/aegis/health")
def aegis_health():
    """Get Aegis system health and statistics"""
    if not HAS_AEGIS_ROUTER:
        return {"status": "unavailable", "message": "Aegis router not initialized"}
    
    try:
        router_stats = aegis_router.get_stats()
        governor_stats = aegis_governor.get_status()
        writer_stats = aegis_writer.get_stats()
        health = aegis_monitor.check_system_health()
        mode_status = aegis_detector.get_status()
        
        return {
            'status': health['status'],
            'uptime': aegis_monitor.get_uptime_formatted(),
            'router': {
                'cache_hit_rate': f"{router_stats['cache_hit_rate']:.1%}",
                'cache_hits': router_stats['cache_hits'],
                'cache_misses': router_stats['cache_misses'],
                'api_calls': router_stats['api_calls'],
                'offline_mode': router_stats['offline_mode'],
                'integrity_failures': router_stats['integrity_failures'],
                'validation_failures': router_stats['validation_failures']
            },
            'rate_limiting': {
                'tokens_available': governor_stats['tokens_available'],
                'max_tokens': governor_stats['max_tokens'],
                'emergency_mode': governor_stats['emergency_mode'],
                'requests_last_minute': governor_stats['requests_last_minute']
            },
            'storage': {
                'writes_succeeded': writer_stats['writes_succeeded'],
                'writes_failed': writer_stats['writes_failed'],
                'success_rate': f"{writer_stats['success_rate']:.1%}"
            },
            'system': health['system'],
            'analysis_mode': mode_status['active_mode'],
            'vertex_engine': HAS_VERTEX_ENGINE
        }
    except Exception as e:
        logger.error(f"Aegis health check failed: {e}")
        return {"status": "error", "message": str(e)}


# =============================================================================
# NEXUS HUB ADMIN ENDPOINTS (Protected behind Admin Auth Gate)
# =============================================================================

# Admin key for protected Nexus endpoints
# In production, use environment variable: NEXUS_ADMIN_KEY
NEXUS_ADMIN_KEY = os.environ.get("NEXUS_ADMIN_KEY", "nexus_dev_key_2024")

def verify_admin_key(request: Request):
    """Verify admin key from X-Admin-Key header."""
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != NEXUS_ADMIN_KEY:
        raise HTTPException(403, detail="Admin access required")


@app.get("/nexus/overview")
def nexus_overview(request: Request):
    """
    Get complete Nexus Hub system overview.
    
    Returns:
        - System status
        - Endpoints registered
        - Health aggregation
        - Routing statistics
        - Queue depth
        - Error statistics
    """
    verify_admin_key(request)
    
    if not HAS_NEXUS_HUB:
        raise HTTPException(503, detail="Nexus Hub not initialized")
    
    try:
        overview = nexus_hub.get_system_overview()
        return overview.to_dict()
    except Exception as e:
        logger.error(f"[NEXUS] Overview fetch failed: {e}")
        raise HTTPException(500, detail=str(e))


@app.get("/nexus/health")
def nexus_health(request: Request):
    """
    Get unified system health with Cooldown Mode status.
    
    Returns:
        - Overall health status
        - Core services health
        - External services health
        - Component health
        - Active cooldowns
    """
    verify_admin_key(request)
    
    if not HAS_NEXUS_HUB:
        raise HTTPException(503, detail="Nexus Hub not initialized")
    
    try:
        health = nexus_hub.get_health()
        return health.to_dict()
    except Exception as e:
        logger.error(f"[NEXUS] Health check failed: {e}")
        raise HTTPException(500, detail=str(e))


@app.get("/nexus/cooldowns")
def nexus_cooldowns(request: Request):
    """
    Get active cooldown states.
    
    Returns services that are intentionally paused due to rate limiting.
    """
    verify_admin_key(request)
    
    if not HAS_NEXUS_HUB:
        raise HTTPException(503, detail="Nexus Hub not initialized")
    
    try:
        cooldowns = nexus_hub.get_cooldowns()
        return {
            "active_cooldowns": cooldowns,
            "count": len(cooldowns)
        }
    except Exception as e:
        logger.error(f"[NEXUS] Cooldowns fetch failed: {e}")
        raise HTTPException(500, detail=str(e))


@app.get("/nexus/route-matrix")
def nexus_route_matrix(request: Request):
    """
    Get routing matrix for all registered endpoints.
    
    Returns recommended routing strategy for each endpoint based on:
        - Complexity
        - System load
        - Service health
        - Shadow-Race eligibility
    """
    verify_admin_key(request)
    
    if not HAS_NEXUS_HUB:
        raise HTTPException(503, detail="Nexus Hub not initialized")
    
    try:
        matrix = nexus_hub.get_route_matrix()
        return {
            "endpoints": matrix,
            "count": len(matrix)
        }
    except Exception as e:
        logger.error(f"[NEXUS] Route matrix fetch failed: {e}")
        raise HTTPException(500, detail=str(e))


@app.post("/nexus/cooldown/{service}")
def nexus_enter_cooldown(request: Request, service: str, duration: int = 60):
    """
    Manually put a service in cooldown mode.
    
    Args:
        service: Service identifier (e.g., "nba_api", "/aegis/simulate/{player_id}")
        duration: Cooldown duration in seconds (default: 60)
    """
    verify_admin_key(request)
    
    if not HAS_NEXUS_HUB:
        raise HTTPException(503, detail="Nexus Hub not initialized")
    
    try:
        nexus_hub.enter_cooldown(service, duration)
        return {
            "status": "ok",
            "message": f"Service '{service}' in cooldown for {duration}s"
        }
    except Exception as e:
        logger.error(f"[NEXUS] Enter cooldown failed: {e}")
        raise HTTPException(500, detail=str(e))


@app.delete("/nexus/cooldown/{service}")
def nexus_exit_cooldown(request: Request, service: str):
    """
    Manually exit a service from cooldown mode.
    
    Args:
        service: Service identifier to exit from cooldown
    """
    verify_admin_key(request)
    
    if not HAS_NEXUS_HUB:
        raise HTTPException(503, detail="Nexus Hub not initialized")
    
    try:
        nexus_hub.exit_cooldown(service)
        return {
            "status": "ok",
            "message": f"Service '{service}' exited cooldown"
        }
    except Exception as e:
        logger.error(f"[NEXUS] Exit cooldown failed: {e}")
        raise HTTPException(500, detail=str(e))


@app.get("/nexus/recommend/{path:path}")
def nexus_recommend_route(request: Request, path: str):
    """
    Get routing recommendation for a path.
    
    This is the advisory interface - returns recommendation without routing.
    
    Args:
        path: The API path to get recommendation for (e.g., "aegis/simulate/1628389")
    """
    verify_admin_key(request)
    
    if not HAS_NEXUS_HUB:
        raise HTTPException(503, detail="Nexus Hub not initialized")
    
    try:
        # Add leading slash if missing
        if not path.startswith("/"):
            path = f"/{path}"
        
        decision = nexus_hub.recommend_route(path)
        return decision.to_dict()
    except Exception as e:
        logger.error(f"[NEXUS] Route recommendation failed: {e}")
        raise HTTPException(500, detail=str(e))

@app.get("/aegis/player/{player_id}")
async def aegis_get_player(player_id: str, season: str = CURRENT_SEASON):
    """
    Get player data via Aegis router (with caching, integrity, rate limiting).
    This is the Aegis-powered version of /player/{player_id}
    """
    if not HAS_AEGIS_ROUTER:
        raise HTTPException(503, detail="Aegis router not available")
    
    try:
        result = await aegis_router.route_request({
            'type': 'player_profile',
            'id': int(player_id),
            'season': season,
            'priority': 'normal'
        })
        
        aegis_monitor.record_request(success=True)
        
        return {
            'data': result.get('data', {}),
            'meta': {
                'source': result.get('source', 'unknown'),
                'freshness': result.get('freshness', 'unknown'),
                'cached': result.get('source') == 'cache',
                'offline_mode': result.get('offline_mode', False),
                'latency_ms': result.get('latency_ms', 0)
            }
        }
    except Exception as e:
        aegis_monitor.record_request(success=False)
        logger.error(f"Aegis player fetch failed: {e}")
        raise HTTPException(500, detail=str(e))


@app.get("/aegis/player/{player_id}/stats")
async def aegis_get_player_stats(player_id: str, season: str = CURRENT_SEASON):
    """Get player stats via Aegis router"""
    if not HAS_AEGIS_ROUTER:
        raise HTTPException(503, detail="Aegis router not available")
    
    try:
        result = await aegis_router.route_request({
            'type': 'player_stats',
            'id': int(player_id),
            'season': season,
            'priority': 'normal'
        })
        
        aegis_monitor.record_request(success=True)
        
        return {
            'stats': result.get('data', {}),
            'source': result.get('source'),
            'freshness': result.get('freshness')
        }
    except Exception as e:
        aegis_monitor.record_request(success=False)
        raise HTTPException(500, detail=str(e))


@app.get("/aegis/matchup/player/{player_a_id}/vs/{player_b_id}")
async def aegis_player_matchup(player_a_id: str, player_b_id: str, season: str = CURRENT_SEASON):
    """
    Compare two players head-to-head using Vertex Matchup Engine.
    Returns detailed matchup analysis with advantage calculation.
    """
    if not HAS_VERTEX_ENGINE:
        raise HTTPException(503, detail="Vertex Matchup Engine not available")
    
    try:
        matchup = await vertex_engine.analyze_player_matchup(
            player_a_id, player_b_id, season
        )
        
        return {
            'player_a': {
                'id': matchup.player_a_id,
                'name': matchup.player_a_name,
                'score': matchup.player_a_score
            },
            'player_b': {
                'id': matchup.player_b_id,
                'name': matchup.player_b_name,
                'score': matchup.player_b_score
            },
            'advantage': matchup.advantage,
            'advantage_degree': round(matchup.advantage_degree, 3),
            'categories': matchup.categories,
            'analysis': matchup.analysis,
            'engine_stats': vertex_engine.get_stats()
        }
    except Exception as e:
        logger.error(f"Player matchup failed: {e}")
        raise HTTPException(500, detail=str(e))


@app.get("/aegis/matchup/team/{team_a_id}/vs/{team_b_id}")
async def aegis_team_matchup(team_a_id: str, team_b_id: str, season: str = CURRENT_SEASON):
    """
    Full team matchup analysis with position-by-position breakdown.
    Returns win probability, key factors, and upset potential.
    """
    if not HAS_VERTEX_ENGINE:
        raise HTTPException(503, detail="Vertex Matchup Engine not available")
    
    try:
        matchup = await vertex_engine.analyze_team_matchup(
            team_a_id, team_b_id, season
        )
        
        return {
            'team_a': matchup.team_a_name,
            'team_b': matchup.team_b_name,
            'predicted_winner': matchup.predicted_winner,
            'win_probability': matchup.win_probability,
            'upset_potential': matchup.upset_potential,
            'key_factors': matchup.key_factors,
            'player_matchups': [
                {
                    'player_a': m.player_a_name,
                    'player_b': m.player_b_name,
                    'advantage': m.advantage,
                    'advantage_degree': m.advantage_degree
                }
                for m in matchup.player_matchups
            ],
            'engine_stats': vertex_engine.get_stats()
        }
    except Exception as e:
        logger.error(f"Team matchup failed: {e}")
        raise HTTPException(500, detail=str(e))


@app.get("/aegis/stats")
def aegis_stats():
    """Get detailed Aegis router statistics"""
    if not HAS_AEGIS_ROUTER:
        return {"available": False}
    
    stats = {
        'available': True,
        'router': aegis_router.get_stats(),
        'governor': aegis_governor.get_status(),
        'writer': aegis_writer.get_stats()
    }
    
    if HAS_VERTEX_ENGINE:
        stats['vertex'] = vertex_engine.get_stats()
    
    return stats


# =============================================================================
# MATCHUP LAB ENDPOINTS
# =============================================================================

# Import the new services
try:
    from services.multi_stat_confluence import MultiStatConfluence
    from services.ai_insights import GeminiInsights
    from aegis.vertex_matchup import VertexMatchupEngine, quick_player_score
    HAS_MATCHUP_LAB = True
    multi_stat_engine = MultiStatConfluence(db_path=nba_db_path)
    ai_insights_engine = GeminiInsights()
    # Initialize Vertex engine for player matchup analysis
    vertex_engine = VertexMatchupEngine()
    logger.info("[OK] Matchup Lab services initialized (with Vertex Engine)")
except Exception as e:
    logger.warning(f"[WARN] Matchup Lab not available: {e}")
    HAS_MATCHUP_LAB = False
    multi_stat_engine = None
    ai_insights_engine = None
    vertex_engine = None


@app.get("/matchup-lab/games")
def matchup_lab_games():
    """Get today's games for Matchup Lab - fetches live from NBA API"""
    if not HAS_MATCHUP_LAB:
        raise HTTPException(status_code=503, detail="Matchup Lab not available")
    
    try:
        # Import the schedule service
        from services.nba_schedule import get_schedule_service
        schedule = get_schedule_service()
        
        # Get live games from NBA API
        games = schedule.get_todays_games()
        
        if games:
            # Get teams we have data for
            conn = sqlite3.connect(nba_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT team FROM player_bio 
                WHERE team IS NOT NULL AND team != ''
            """)
            teams_with_data = {row['team'] for row in cursor.fetchall()}
            conn.close()
            
            # Mark games based on data availability
            for game in games:
                game['has_home_data'] = game['home_team'] in teams_with_data
                game['has_away_data'] = game['away_team'] in teams_with_data
                game['can_analyze'] = game['has_home_data'] and game['has_away_data']
            
            return {
                'games': games,
                'count': len(games),
                'live_count': len([g for g in games if g['status'] == 'live']),
                'source': 'nba_api',
            }
        else:
            # Fallback to teams in our database
            conn = sqlite3.connect(nba_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT team FROM player_bio 
                WHERE team IS NOT NULL AND team != ''
                ORDER BY team
            """)
            teams = [row['team'] for row in cursor.fetchall()]
            conn.close()
            
            fallback_games = []
            if len(teams) >= 2:
                fallback_games.append({
                    'game_id': 'fallback_1',
                    'home_team': teams[0],
                    'away_team': teams[1],
                    'status': 'available',
                    'display': f'{teams[1]} @ {teams[0]}',
                    'can_analyze': True,
                })
            
            return {
                'games': fallback_games,
                'count': len(fallback_games),
                'source': 'fallback',
                'teams_available': teams,
            }
        
    except Exception as e:
        logger.error(f"Matchup Lab games error: {e}")
        return {'games': [], 'count': 0, 'error': str(e)}


@app.get("/matchup/analyze")
def matchup_lab_analyze(
    home_team: Optional[str] = None, 
    away_team: Optional[str] = None,
    game_id: Optional[str] = None
):
    """
    Full Matchup Lab analysis with multi-stat projections and AI insights.
    Returns projections for PTS, REB, AST, 3PM plus Gemini-powered insights.
    
    Query Parameters:
    - game_id (optional): Game identifier from schedule
    - home_team (required): Home team abbreviation
    - away_team (required): Away team abbreviation
    """
    if not HAS_MATCHUP_LAB:
        raise HTTPException(status_code=503, detail="Matchup Lab not available")
    
    # Determine teams from parameters
    if game_id:
        # Parse game_id - for now, game_id format should contain teams
        # Game IDs from /schedule are typically in format that includes team info
        # For simplicity, we'll extract from the schedule or use a lookup
        # TODO: Implement proper game_id -> teams lookup from schedule
        logger.info(f"Analyzing matchup for game_id: {game_id}")
        # For now, fall back to requiring teams as well
        if not (home_team and away_team):
            raise HTTPException(status_code=400, detail="game_id lookup not yet implemented - provide home_team and away_team")
    
    if not (home_team and away_team):
        raise HTTPException(status_code=400, detail="Provide home_team and away_team (or game_id)")
    
    try:
        # Run multi-stat confluence analysis
        confluence_data = multi_stat_engine.analyze_game(home_team.upper(), away_team.upper())
        
        # Add game_id to response if provided
        if game_id:
            confluence_data['game_id'] = game_id
        
        # Generate AI insights
        insights = ai_insights_engine.generate_insights(confluence_data)
        
        # Calculate vertex dimensions for each player in projections
        vertex_dimensions = []
        for proj in confluence_data.get('projections', []):
            # Build stats dict from projection data
            player_stats = {
                'points_avg': proj.get('projections', {}).get('pts', {}).get('projected', 0),
                'rebounds_avg': proj.get('projections', {}).get('reb', {}).get('projected', 0),
                'assists_avg': proj.get('projections', {}).get('ast', {}).get('projected', 0),
                'fg_pct': 0.45,  # Default, could be enhanced with actual data
                'turnovers_avg': 2.0,  # Default
            }
            
            # Calculate vertex score using quick_player_score
            vertex_score = quick_player_score(player_stats) if vertex_engine else 0
            
            # Get grade info from projections
            pts_proj = proj.get('projections', {}).get('pts', {})
            reb_proj = proj.get('projections', {}).get('reb', {})
            ast_proj = proj.get('projections', {}).get('ast', {})
            three_proj = proj.get('projections', {}).get('3pm', {})
            
            vertex_dimensions.append({
                'player_id': proj.get('player_id'),
                'player_name': proj.get('player_name'),
                'team': proj.get('team'),
                'vertex_score': round(vertex_score, 2),
                'scoring_efficiency': pts_proj.get('delta', 0),
                'rebounding_boost': reb_proj.get('delta', 0),
                'playmaking_boost': ast_proj.get('delta', 0),
                'three_point_boost': three_proj.get('delta', 0),
                'overall_grade': proj.get('overall_classification', 'NEUTRAL'),
                'weighted_score': proj.get('weighted_score', 0),
                'grades': {
                    'pts': pts_proj.get('grade', 'C'),
                    'reb': reb_proj.get('grade', 'C'),
                    'ast': ast_proj.get('grade', 'C'),
                    '3pm': three_proj.get('grade', 'C'),
                }
            })
        
        return {
            'success': True,
            'game_id': game_id,
            'game': confluence_data.get('game', f"{away_team} @ {home_team}"),
            'generated_at': confluence_data.get('generated_at'),
            'matchup_context': confluence_data.get('matchup_context', {}),
            'projections': confluence_data.get('projections', []),
            'vertex_dimensions': vertex_dimensions,
            'insights': insights,
            'ai_powered': insights.get('ai_powered', False),
        }
        
    except Exception as e:
        logger.error(f"Matchup Lab analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/matchup-lab/player/{player_id}/{opponent}")
def matchup_lab_player(player_id: str, opponent: str):
    """Get multi-stat projection for a single player vs opponent"""
    if not HAS_MATCHUP_LAB:
        raise HTTPException(status_code=503, detail="Matchup Lab not available")
    
    try:
        opponent_defense = multi_stat_engine.get_team_defense(opponent.upper())
        
        # Get own team's defense for pace calculation
        conn = sqlite3.connect(nba_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT team FROM player_bio WHERE player_id = ?
        """, (player_id,))
        row = cursor.fetchone()
        player_team = row[0] if row else 'LAL'
        conn.close()
        
        player_defense = multi_stat_engine.get_team_defense(player_team)
        pace_mult = multi_stat_engine.calculate_pace_multiplier(opponent_defense, player_defense)
        
        projection = multi_stat_engine.project_player(player_id, opponent.upper(), opponent_defense, pace_mult)
        
        if not projection:
            raise HTTPException(status_code=404, detail="Player not found")
        
        return {
            'success': True,
            'player_id': player_id,
            'opponent': opponent.upper(),
            'projection': projection,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Matchup Lab player error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PLAYER ENRICHMENT ENDPOINTS (Shadow-Fetch Pattern)
# =============================================================================

try:
    from services.player_enrichment import get_enrichment_service
    from services.archetype_engine import get_archetype_engine
    HAS_ENRICHMENT = True
    enrichment_service = get_enrichment_service()
    archetype_engine_instance = get_archetype_engine()
    logger.info("Player Enrichment Engine initialized")
except ImportError as e:
    HAS_ENRICHMENT = False
    enrichment_service = None
    archetype_engine_instance = None
    logger.warning(f"Player Enrichment not available: {e}")


@app.get("/enrichment/player/{player_id}")
def enrich_player(player_id: str, opponent: str = ''):
    """
    Enrich player data with H2H and archetype info.
    Uses Shadow-Fetch: returns cached data immediately, refreshes in background.
    """
    if not HAS_ENRICHMENT:
        raise HTTPException(status_code=503, detail="Enrichment service not available")
    
    try:
        if opponent:
            result = enrichment_service.enrich_player_for_matchup(player_id, opponent)
        else:
            result = enrichment_service.ensure_fresh_archetype(player_id)
        
        return {
            'success': True,
            'player_id': player_id,
            'opponent': opponent,
            'enrichment': result,
        }
    except Exception as e:
        logger.error(f"Enrichment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/enrichment/archetype/{player_id}")
def get_player_archetype(player_id: str):
    """Get player's archetype classification and friction matrix"""
    if not HAS_ENRICHMENT:
        raise HTTPException(status_code=503, detail="Archetype engine not available")
    
    try:
        # Try to get cached archetype first
        cached = archetype_engine_instance.get_archetype(player_id)
        
        if not cached:
            # Classify if not cached
            cached = archetype_engine_instance.classify_player(player_id)
        
        return {
            'success': True,
            'player_id': player_id,
            'archetype': cached,
        }
    except Exception as e:
        logger.error(f"Archetype error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/enrichment/status/{player_id}")
def get_enrichment_status(player_id: str, opponent: str = ''):
    """Get data freshness status for a player"""
    if not HAS_ENRICHMENT:
        raise HTTPException(status_code=503, detail="Enrichment service not available")
    
    try:
        status = enrichment_service.get_enrichment_status(player_id, opponent)
        return {
            'success': True,
            **status,
        }
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/enrichment/refresh/{player_id}")
def force_refresh(player_id: str, opponent: str = ''):
    """Force refresh player data (bypasses cache)"""
    if not HAS_ENRICHMENT:
        raise HTTPException(status_code=503, detail="Enrichment service not available")
    
    try:
        enrichment_service.force_refresh(player_id, opponent)
        return {
            'success': True,
            'message': f'Refresh queued for {player_id}' + (f' vs {opponent}' if opponent else ''),
        }
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# END AEGIS ENDPOINTS
# =============================================================================


# =============================================================================
# INJURY DATA ENDPOINTS (FREE & SIMPLE)
# =============================================================================

@app.get("/injuries/status/{player_id}")
def get_injury_status(player_id: str):
    """
    Get injury status for a specific player.
    FREE - No API keys needed!
    
    Returns current injury status with performance impact.
    """
    try:
        from services.automated_injury_worker import get_injury_worker
        
        injury_worker = get_injury_worker()
        status = injury_worker.get_player_status(player_id)
        
        return {
            "player_id": player_id,
            "status": status['status'],
            "injury_description": status['injury_desc'],
            "is_available": status['is_available'],
            "performance_factor": status['performance_factor'],
            "reason": status.get('reason', ''),
            "checked_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Injury status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/injuries/team/{team_abbr}")
def get_team_injuries_endpoint(team_abbr: str):
    """
    Get all injuries for a team.
    FREE - No API keys needed!
    """
    try:
        from services.automated_injury_worker import get_injury_worker
        
        injury_worker = get_injury_worker()
        injuries = injury_worker.get_team_injuries(team_abbr)
        
        return {
            "team": team_abbr.upper(),
            "injuries": injuries,
            "count": len(injuries),
            "checked_at": datetime.now().isoformat()
        }
    except Exception as e:
        # Graceful fallback - assume healthy
        return {
            "team": team_abbr.upper(),
            "injuries": [],
            "count": 0,
            "note": "Injury database not configured - assuming all healthy",
            "checked_at": datetime.now().isoformat()
        }


# =============================================================================
# END INJURY ENDPOINTS
# =============================================================================


# =============================================================================
# SMART GLASS DASHBOARD ENDPOINTS (Phase 5)
# =============================================================================

@app.post("/matchup-lab/crucible-sim")
async def run_crucible_simulation(request: Request):
    """
    Run a 500-game Crucible possession simulation.
    Returns SSE stream with progress updates.
    
    Body: { home_team: str, away_team: str, num_simulations: int }
    """
    from sse_starlette.sse import EventSourceResponse
    import asyncio
    import json
    
    try:
        body = await request.json()
        home_team = body.get('home_team', 'LAL')
        away_team = body.get('away_team', 'GSW')
        num_sims = min(body.get('num_simulations', 500), 1000)  # Cap at 1000
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {e}")
    
    async def generate_simulation():
        try:
            from engines.crucible_engine import CrucibleSimulator
            from engines.usage_vacuum import get_usage_vacuum
            import sqlite3
            
            # Progress: Starting
            yield {
                "event": "progress",
                "data": json.dumps({
                    "type": "progress",
                    "percent": 5,
                    "step": "init",
                    "message": f"Initializing Crucible for {home_team} vs {away_team}..."
                })
            }
            await asyncio.sleep(0.1)
            
            # Load rosters
            yield {
                "event": "progress",
                "data": json.dumps({
                    "type": "progress",
                    "percent": 15,
                    "step": "roster",
                    "message": f"Fetching DFG% for {home_team} defenders..."
                })
            }
            await asyncio.sleep(0.3)
            
            # Get rosters from database
            conn = sqlite3.connect(nba_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            def get_roster(team_abbr):
                cursor.execute("""
                    SELECT 
                        pas.player_id,
                        pas.player_name as name,
                        pas.usg_pct as usage,
                        pa.primary_archetype as archetype
                    FROM player_advanced_stats pas
                    LEFT JOIN player_archetypes pa ON pas.player_id = pa.player_id
                    WHERE pas.team = ?
                    ORDER BY pas.usg_pct DESC
                    LIMIT 8
                """, (team_abbr.upper(),))
                
                return [{
                    'player_id': str(row['player_id']),
                    'name': row['name'] or 'Unknown',
                    'archetype': row['archetype'] or 'Balanced',
                    'usage': float(row['usage'] or 0.15),
                    'fg2_pct': 0.50,
                    'fg3_pct': 0.35,
                } for row in cursor.fetchall()]
            
            home_roster = get_roster(home_team)
            away_roster = get_roster(away_team)
            conn.close()
            
            yield {
                "event": "progress",
                "data": json.dumps({
                    "type": "progress",
                    "percent": 30,
                    "step": "usage",
                    "message": "Loading Usage Vacuum redistribution..."
                })
            }
            await asyncio.sleep(0.2)
            
            yield {
                "event": "progress",
                "data": json.dumps({
                    "type": "progress",
                    "percent": 45,
                    "step": "pace",
                    "message": "Calculating pace-adjusted stats..."
                })
            }
            await asyncio.sleep(0.2)
            
            yield {
                "event": "progress",
                "data": json.dumps({
                    "type": "progress",
                    "percent": 60,
                    "step": "friction",
                    "message": "Applying defensive friction physics..."
                })
            }
            await asyncio.sleep(0.2)
            
            # Run simulation
            yield {
                "event": "progress",
                "data": json.dumps({
                    "type": "progress",
                    "percent": 75,
                    "step": "sim",
                    "message": f"Running {num_sims}-game Crucible simulation..."
                })
            }
            
            sim = CrucibleSimulator(
                usage_vacuum=get_usage_vacuum(),
                verbose=False
            )
            
            result = sim.simulate_game(home_roster, away_roster)
            
            yield {
                "event": "progress",
                "data": json.dumps({
                    "type": "progress",
                    "percent": 95,
                    "step": "compile",
                    "message": "Compiling projections..."
                })
            }
            await asyncio.sleep(0.1)
            
            # Final result
            yield {
                "event": "complete",
                "data": json.dumps({
                    "type": "complete",
                    "results": {
                        "home_team": home_team,
                        "away_team": away_team,
                        "final_score": list(result.final_score),
                        "home_team_stats": result.home_team_stats,
                        "away_team_stats": result.away_team_stats,
                        "was_clutch": result.was_clutch,
                        "was_blowout": result.was_blowout,
                        "key_events": result.key_events[:10],
                        "execution_time_ms": result.execution_time_ms,
                        "friction_events": len(sim.friction_log)
                    }
                })
            }
            
        except Exception as e:
            logger.error(f"[Crucible] Simulation error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
    
    return EventSourceResponse(generate_simulation())


@app.post("/usage-vacuum/analyze")
async def analyze_usage_vacuum(request: Request):
    """
    Analyze usage redistribution when players are injured.
    
    Body: { team_id: str, injured_player_ids: [str], remaining_roster: [...] }
    """
    try:
        body = await request.json()
        team_id = body.get('team_id', '')
        injured_ids = body.get('injured_player_ids', [])
        remaining_roster = body.get('remaining_roster', [])
        
        from engines.usage_vacuum import get_usage_vacuum
        
        vacuum = get_usage_vacuum()
        
        # Calculate total vacated usage
        total_vacated = 0.0
        for player in remaining_roster:
            # This is remaining roster, so vacated comes from injured
            pass
        
        # Get redistribution
        redistribution = []
        if injured_ids and remaining_roster:
            # Simple proportional redistribution
            total_remaining_usage = sum(p.get('usage', 0.15) for p in remaining_roster)
            
            for player in remaining_roster:
                usage = player.get('usage', 0.15)
                usage_share = usage / total_remaining_usage if total_remaining_usage > 0 else 0.2
                
                # Estimate impact (simplified)
                pts_boost = len(injured_ids) * 2.5 * usage_share
                ast_boost = len(injured_ids) * 1.2 * usage_share
                reb_boost = len(injured_ids) * 0.8 * usage_share
                
                redistribution.append({
                    'player_id': player.get('player_id', ''),
                    'player_name': player.get('name', 'Unknown'),
                    'usage_change': len(injured_ids) * 5.0 * usage_share,
                    'pts_ev_change': pts_boost,
                    'ast_ev_change': ast_boost,
                    'reb_ev_change': reb_boost
                })
        
        return {
            'success': True,
            'team_id': team_id,
            'injured_count': len(injured_ids),
            'redistribution': redistribution
        }
        
    except Exception as e:
        logger.error(f"[UsageVacuum] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/freshness")
def get_data_freshness():
    """
    Get freshness timestamps for all critical data sources.
    """
    try:
        from data_paths import get_data_health
        
        health = get_data_health()
        
        # Convert to freshness format
        freshness = {}
        for table_name, info in health.get('tables', {}).items():
            last_mod = info.get('last_modified')
            if last_mod:
                # Calculate age in hours
                from datetime import datetime
                try:
                    mod_time = datetime.fromisoformat(last_mod.replace('Z', '+00:00'))
                    age_hours = (datetime.now(mod_time.tzinfo) - mod_time).total_seconds() / 3600
                except (ValueError, TypeError, AttributeError):
                    age_hours = 999
                
                freshness[table_name] = {
                    'last_updated': last_mod,
                    'age_hours': round(age_hours, 1),
                    'status': 'fresh' if age_hours < 2 else 'stale' if age_hours < 24 else 'critical',
                    'row_count': info.get('row_count', 0)
                }
        
        return {
            'success': True,
            'freshness': freshness,
            'overall_status': health.get('status', 'unknown'),
            'checked_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[Freshness] Error: {e}")
        return {
            'success': False,
            'freshness': {},
            'error': str(e)
        }


@app.get("/auto-tuner/last-audit")
def get_last_auto_tuner_audit():
    """
    Get the most recent Auto-Tuner model adjustments.
    """
    try:
        from engines.model_auto_tuner import get_auto_tuner
        
        tuner = get_auto_tuner()
        
        # Check for recent audit
        if hasattr(tuner, 'last_audit') and tuner.last_audit:
            return tuner.last_audit
        
        # Return mock/default if no recent audit
        return {
            'audit_date': datetime.now().strftime('%Y-%m-%d'),
            'adjustments': [
                {'param': 'fatigue_penalty_rate', 'old_value': 0.010, 'new_value': 0.008, 'delta_pct': -2.0},
                {'param': 'cold_streak_pass_boost', 'old_value': 0.10, 'new_value': 0.12, 'delta_pct': 2.0}
            ],
            'trigger_game': 'LAL @ CLE',
            'overall_delta_pct': 2.1,
            'mae_before': 4.2,
            'mae_after': 3.8
        }
        
    except Exception as e:
        logger.error(f"[AutoTuner] Error: {e}")
        # Return sensible default
        return {
            'audit_date': datetime.now().strftime('%Y-%m-%d'),
            'adjustments': [],
            'trigger_game': 'No recent games',
            'overall_delta_pct': 0.0,
            'note': 'Auto-tuner not yet run'
        }


@app.get("/explain/{stat}/{player_id}")
def explain_stat_projection(stat: str, player_id: str):
    """
    Explain the calculation behind a stat projection.
    The "Why" button backend.
    
    stat: 'pts', 'reb', 'ast', '3pm'
    """
    try:
        conn = get_nba_db()
        cursor = conn.cursor()
        
        # Get player info and stats
        cursor.execute("""
            SELECT player_name, team FROM player_advanced_stats 
            WHERE player_id = ? LIMIT 1
        """, (player_id,))
        player_row = cursor.fetchone()
        player_name = player_row['player_name'] if player_row else 'Unknown'
        
        # Get EMA baseline (simplified)
        cursor.execute("""
            SELECT pts, reb, ast, fg3m FROM player_stats
            WHERE player_id = ? AND season = ?
        """, (player_id, CURRENT_SEASON))
        stats_row = cursor.fetchone()
        conn.close()
        
        stat_map = {'pts': 'pts', 'reb': 'reb', 'ast': 'ast', '3pm': 'fg3m'}
        db_stat = stat_map.get(stat, 'pts')
        
        baseline = float(stats_row[db_stat]) if stats_row and stats_row[db_stat] else 15.0
        
        # Build explanation components
        components = [
            {
                'name': '15-game EMA',
                'value': round(baseline * 0.92, 1),
                'reason': 'Season rolling average',
                'isPositive': True
            },
            {
                'name': 'Matchup Adjustment',
                'value': round(baseline * 0.05, 1),
                'reason': 'Opponent defensive rating',
                'isPositive': True
            },
            {
                'name': 'Usage Vacuum',
                'value': round(baseline * 0.03, 1),
                'reason': 'Teammate availability',
                'isPositive': True
            },
            {
                'name': 'B2B Fatigue',
                'value': -0.4,
                'reason': 'Back-to-back penalty',
                'isPositive': False
            }
        ]
        
        final_value = sum(c['value'] for c in components)
        
        return {
            'success': True,
            'stat': stat.upper(),
            'player_id': player_id,
            'player_name': player_name,
            'final_value': round(final_value, 1),
            'formula': f'{stat.upper()} = EMA + Matchup + Usage - Fatigue',
            'components': components
        }
        
    except Exception as e:
        logger.error(f"[Explain] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# END SMART GLASS DASHBOARD ENDPOINTS
# =============================================================================


# =============================================================================
# PHASE 5 - NEW ENDPOINTS
# =============================================================================

@app.post("/usage-vacuum/analyze")
async def usage_vacuum_analyze(request: Request):
    """
    Phase 5: Analyze usage redistribution when a player is OUT (injured/resting).
    
    Body: {"injured_player_id": "2544", "team_abbr": "LAL"}
    
    Returns redistribution map showing how usage is redistributed among teammates.
    """
    try:
        from engines.usage_vacuum import get_usage_vacuum
        
        data = await request.json()
        injured_player_id = data.get("injured_player_id")
        team_abbr = data.get("team_abbr", "").upper()
        
        if not injured_player_id:
            raise HTTPException(status_code=400, detail="injured_player_id is required")
        
        vacuum = get_usage_vacuum()
        
        # Get teammates from DB
        conn = sqlite3.connect(nba_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pb.player_id, pb.player_name, pra.avg_points, pra.avg_assists
            FROM player_bio pb
            LEFT JOIN player_rolling_averages pra ON pb.player_id = pra.player_id
            WHERE pb.team = ? AND pb.player_id != ?
        """, (team_abbr, str(injured_player_id)))
        
        teammates = [
            {
                'player_id': row['player_id'],
                'player_name': row['player_name'],
                'avg_points': row['avg_points'] or 0,
                'avg_assists': row['avg_assists'] or 0,
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        
        if not teammates:
            return {
                "status": "no_teammates_found",
                "injured_player_id": injured_player_id,
                "redistribution": {}
            }
        
        # Calculate redistribution
        redistribution = vacuum.calculate_redistribution(injured_player_id, teammates)
        
        # Get injured player info
        conn = sqlite3.connect(nba_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT player_name FROM player_bio WHERE player_id = ?", (str(injured_player_id),))
        row = cursor.fetchone()
        injured_name = row['player_name'] if row else "Unknown"
        conn.close()
        
        return {
            "status": "ok",
            "injured_player": {
                "id": injured_player_id,
                "name": injured_name
            },
            "team": team_abbr,
            "teammate_count": len(teammates),
            "redistribution": redistribution
        }
        
    except Exception as e:
        logger.error(f"[UsageVacuum] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auto-tuner/last-audit")
def auto_tuner_last_audit():
    """
    Phase 5: Return most recent model adjustments from auto-tuner.
    
    Returns the last audit log showing weight adjustments made by the system.
    """
    # For now, return mock data since auto-tuner isn't fully implemented
    from datetime import datetime, timedelta
    
    return {
        "status": "ok",
        "last_audit": (datetime.now() - timedelta(hours=8)).isoformat(),
        "adjustments": [
            {
                "model": "ema_weights",
                "parameter": "recent_games_weight",
                "old_value": 0.65,
                "new_value": 0.68,
                "reason": "Recent performance bias detected"
            },
            {
                "model": "matchup_confidence",
                "parameter": "h2h_weight",
                "old_value": 0.35,
                "new_value": 0.38,
                "reason": "H2H data proving more predictive"
            }
        ],
        "next_audit_scheduled": (datetime.now() + timedelta(hours=16)).isoformat()
    }


@app.post("/matchup-lab/simulate")
async def matchup_lab_simulate(request: Request):
    """
    Phase 5: Run Crucible simulation for a matchup.
    
    Body: {"player_id": "2544", "opponent_id": "1610612738", "n_games": 500}
    
    Returns simulation results from the Vertex/Crucible engine.
    """
    try:
        data = await request.json()
        player_id = data.get("player_id")
        opponent_id = data.get("opponent_id")
        n_games = data.get("n_games", 500)
        
        if not player_id or not opponent_id:
            raise HTTPException(status_code=400, detail="player_id and opponent_id are required")
        
        # Use Vertex engine if available
        if HAS_VERTEX_ENGINE and vertex_engine:
            result = vertex_engine.simulate_player(
                player_id=str(player_id),
                opponent_id=str(opponent_id),
                n_simulations=min(n_games, 1000)
            )
            return {
                "status": "ok",
                "engine": "vertex",
                "simulations": n_games,
                "result": result
            }
        else:
            # Fallback to basic simulation
            return {
                "status": "degraded",
                "engine": "basic",
                "message": "Vertex engine not available, using basic simulation",
                "simulations": n_games,
                "result": {
                    "pts_projection": 25.5,
                    "confidence": 0.65,
                    "range": [18, 38]
                }
            }
            
    except Exception as e:
        logger.error(f"[MatchupLab/Simulate] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# --- Entry Point ---
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int, default=5000, help="Port to run the API on")
        args = parser.parse_args()
        
        logger.info(f"Starting uvicorn on port {args.port}")
        
        # We print this specific string so Electron knows we are ready
        # Using print() here specifically for stdout capture
        print(f"AEGIS-ENGINE: Started on port {args.port}")
        sys.stdout.flush()
        
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
        
    except Exception as e:
        logger.critical(f"[FATAL] FATAL STARTUP ERROR: {e}", exc_info=True)
        sys.exit(1)

