"""
NBA API Rate Limiter
====================
Shared rate limiting module for all population scripts.
Features exponential backoff and jitter to avoid rate limits.
"""
import time
import random
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# NBA API config
NBA_BASE_URL = "https://stats.nba.com/stats"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
}

TEAM_IDS = {
    'ATL': 1610612737, 'BOS': 1610612738, 'CLE': 1610612739, 'NOP': 1610612740,
    'CHI': 1610612741, 'DAL': 1610612742, 'DEN': 1610612743, 'GSW': 1610612744,
    'HOU': 1610612745, 'LAC': 1610612746, 'LAL': 1610612747, 'MIA': 1610612748,
    'MIL': 1610612749, 'MIN': 1610612750, 'BKN': 1610612751, 'NYK': 1610612752,
    'ORL': 1610612753, 'IND': 1610612754, 'PHI': 1610612755, 'PHX': 1610612756,
    'POR': 1610612757, 'SAC': 1610612758, 'SAS': 1610612759, 'OKC': 1610612760,
    'TOR': 1610612761, 'UTA': 1610612762, 'MEM': 1610612763, 'WAS': 1610612764,
    'DET': 1610612765, 'CHA': 1610612766,
}


class RateLimiter:
    """Smart rate limiter with exponential backoff."""
    
    def __init__(self, base_delay: float = 2.0, max_delay: float = 30.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.current_delay = base_delay
        self.consecutive_failures = 0
        self.last_request_time = 0
    
    def wait(self):
        """Wait before making the next request."""
        now = time.time()
        elapsed = now - self.last_request_time
        jitter = random.uniform(0.1, 0.5)
        wait_time = max(0, self.current_delay + jitter - elapsed)
        
        if wait_time > 0:
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def success(self):
        """Reset delay after successful request."""
        self.consecutive_failures = 0
        self.current_delay = self.base_delay
    
    def failure(self):
        """Increase delay after failed request."""
        self.consecutive_failures += 1
        self.current_delay = min(
            self.base_delay * (2 ** self.consecutive_failures),
            self.max_delay
        )
        logger.warning(f"Rate limit hit, backing off to {self.current_delay:.1f}s")


def make_nba_request(session: requests.Session, url: str, params: dict, 
                     rate_limiter: RateLimiter, max_retries: int = 3) -> Optional[dict]:
    """Make NBA API request with rate limiting and retries."""
    for attempt in range(max_retries):
        rate_limiter.wait()
        
        try:
            response = session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                rate_limiter.success()
                return response.json()
            elif response.status_code == 429:
                rate_limiter.failure()
                logger.warning(f"Rate limited, attempt {attempt + 1}/{max_retries}")
            else:
                logger.error(f"HTTP {response.status_code}")
                rate_limiter.failure()
                
        except requests.Timeout:
            logger.warning(f"Timeout, attempt {attempt + 1}/{max_retries}")
            rate_limiter.failure()
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            rate_limiter.failure()
    
    return None


def create_session() -> requests.Session:
    """Create configured requests session."""
    session = requests.Session()
    session.headers.update(HEADERS)
    return session
