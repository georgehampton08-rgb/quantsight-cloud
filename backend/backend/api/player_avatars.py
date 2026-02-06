"""
Player Avatar Proxy Service
Proxies and caches NBA player headshots to bypass CSP restrictions
"""
import os
import requests
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
import urllib.parse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache directory for avatars
AVATAR_CACHE_DIR = Path(os.getenv('APPDATA') or os.path.expanduser('~')) / 'QuantSight' / 'cache' / 'avatars'
AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# NBA headshot URLs
NBA_HEADSHOT_URL = "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
NBA_HEADSHOT_SMALL_URL = "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/{player_id}.png"

@router.get("/player-avatar/{player_id}")
async def get_player_avatar(player_id: str, size: str = "large"):
    """
    Proxy endpoint for player avatars that caches images locally.
    This bypasses CSP restrictions by serving from localhost.
    
    Args:
        player_id: NBA player ID
        size: 'large' (1040x760) or 'small' (260x190)
    
    Returns:
        Image file (PNG)
    """
    # Sanitize player_id to prevent path traversal
    clean_id = "".join(c for c in player_id if c.isalnum() or c in ('-', '_'))
    cache_filename = f"{clean_id}_{size}.png"
    cache_path = AVATAR_CACHE_DIR / cache_filename
    
    # Return cached file if it exists and is recent (less than 7 days old)
    if cache_path.exists():
        age_days = (Path(cache_path).stat().st_mtime - os.path.getmtime(cache_path)) / 86400
        if age_days < 7:
            return FileResponse(cache_path, media_type="image/png")
    
    # Try to download from NBA CDN
    url = NBA_HEADSHOT_URL.format(player_id=player_id) if size == "large" else NBA_HEADSHOT_SMALL_URL.format(player_id=player_id)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.nba.com/',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('image'):
            # Cache the image
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Cached avatar for player {player_id}")
            return Response(content=response.content, media_type="image/png")
        else:
            logger.warning(f"NBA CDN returned {response.status_code} for player {player_id}")
            
    except Exception as e:
        logger.error(f"Failed to fetch avatar for {player_id}: {e}")
    
    # Fallback: Generate UI Avatar
    try:
        from sqlite3 import connect
        from pathlib import Path
        
        # Try to get player name from database
        db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        if not db_path.exists():
            # Try AppData location
            db_path = Path(os.getenv('APPDATA') or os.path.expanduser('~')) / 'QuantSight' / 'data' / 'nba_data.db'
        
        player_name = None
        if db_path.exists():
            conn = connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM players WHERE player_id = ?", (player_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                player_name = row[0]
        
        if not player_name:
            player_name = f"Player {player_id}"
        
        # Generate fallback avatar
        name_encoded = urllib.parse.quote(player_name)
        fallback_url = f"https://ui-avatars.com/api/?name={name_encoded}&background=1e293b&color=10b981&size=512&bold=true&format=png"
        
        fallback_response = requests.get(fallback_url, timeout=5)
        if fallback_response.status_code == 200:
            # Cache fallback too
            with open(cache_path, 'wb') as f:
                f.write(fallback_response.content)
            return Response(content=fallback_response.content, media_type="image/png")
            
    except Exception as e:
        logger.error(f"Fallback avatar generation failed: {e}")
    
    # Ultimate fallback: 404
    raise HTTPException(status_code=404, detail="Avatar not available")


@router.delete("/player-avatar/cache/clear")
async def clear_avatar_cache():
    """Clear all cached avatars (admin endpoint)"""
    try:
        import shutil
        if AVATAR_CACHE_DIR.exists():
            shutil.rmtree(AVATAR_CACHE_DIR)
            AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "message": "Avatar cache cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
