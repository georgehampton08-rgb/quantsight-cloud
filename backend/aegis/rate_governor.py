"""
Token Bucket Rate Governor
Strict rate-limiting to respect API quotas and mimic human behavior
"""

import asyncio
import time
from collections import deque
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TokenBucketGovernor:
    """
    Token bucket algorithm for rate limiting API requests.
    
    Rules:
    - Maximum 1 request per 0.75 seconds (human-like pacing)
    - Burst mode: 5 simultaneous for Morning Briefing, then 5s cooldown
    - Emergency brake at 10% remaining quota
    
    This prevents hitting API rate limits and mimics human browsing patterns.
    """
    
    def __init__(self, max_tokens=10, refill_rate=0.75):
        """
        Initialize token bucket governor.
        
        Args:
            max_tokens: Maximum tokens in bucket
            refill_rate: Seconds per token refill
        """
        self.tokens = max_tokens
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate  # Seconds per token
        self.last_refill = time.time()
        self.request_history = deque(maxlen=100)
        self.lock = asyncio.Lock()
        
        # API quota tracking
        self.rate_limit_remaining = 100
        self.rate_limit_total = 100
        self.rate_limit_reset = None
        self.emergency_mode = False
        self.historical_paused = False
        
        # Burst mode for batch operations
        self.burst_mode_active = False
        self.burst_requests_remaining = 5
        self.cooldown_until = None
        
        logger.info(f"TokenBucketGovernor initialized: {max_tokens} tokens, {refill_rate}s refill")
    
    async def acquire_token(self, priority: str = 'normal') -> bool:
        """
        Request permission to make an API call.
        
        Args:
            priority: 'normal', 'high', or 'critical'
            
        Returns:
            True if allowed, False if rate-limited
        """
        async with self.lock:
            # Check if in cooldown
            if self.cooldown_until and time.time() < self.cooldown_until:
                logger.debug("Request denied: In cooldown period")
                return False
            
            # Emergency brake check - only critical requests allowed
            if self.emergency_mode and priority != 'critical':
                logger.warning(f"Emergency mode active - denying {priority} priority request")
                return False
            
            # Refill tokens based on elapsed time
            self._refill_tokens()
            
            # Burst mode handling
            if self.burst_mode_active:
                if self.burst_requests_remaining > 0:
                    self.burst_requests_remaining -= 1
                    self._log_request(priority)
                    logger.info(f"Burst token acquired ({self.burst_requests_remaining} remaining)")
                    return True
                else:
                    # Burst exhausted, enter cooldown
                    self.cooldown_until = time.time() + 5  # 5 second cooldown
                    self.burst_mode_active = False
                    logger.info("Burst mode exhausted - entering 5s cooldown")
                    return False
            
            # Normal token consumption
            if self.tokens >= 1:
                self.tokens -= 1
                self._log_request(priority)
                logger.debug(f"Token acquired ({self.tokens:.1f} remaining)")
                return True
            
            logger.debug("Request denied: No tokens available")
            return False
    
    def _refill_tokens(self):
        """Refill tokens based on time elapsed"""
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed / self.refill_rate
        
        if new_tokens >= 1:
            # Add at least 1 token
            tokens_to_add = int(new_tokens)
            self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
            self.last_refill = now
            logger.debug(f"Refilled {tokens_to_add} tokens → {self.tokens:.1f} total")
    
    def _log_request(self, priority: str):
        """Log request for monitoring"""
        self.request_history.append({
            'timestamp': time.time(),
            'priority': priority
        })
    
    def update_from_headers(self, headers: dict):
        """
        Monitor API response headers for rate limit status.
        
        Args:
            headers: HTTP response headers
        """
        remaining = headers.get('X-RateLimit-Remaining')
        limit = headers.get('X-RateLimit-Limit')
        reset_time = headers.get('X-RateLimit-Reset')
        
        if remaining is not None:
            self.rate_limit_remaining = int(remaining)
            
        if limit is not None:
            self.rate_limit_total = int(limit)
        
        # Calculate percentage remaining
        if self.rate_limit_total > 0:
            percentage = (self.rate_limit_remaining / self.rate_limit_total) * 100
            
            if percentage < 10:
                if not self.emergency_mode:
                    logger.warning(f"⚠️ Rate limit critical: {percentage:.1f}% remaining - activating emergency brake")
                    self.emergency_mode = True
                    self._pause_historical_fetches()
            elif self.emergency_mode and percentage > 20:
                # Exit emergency mode when quota recovers
                logger.info(f"✓ Rate limit recovered: {percentage:.1f}% - deactivating emergency brake")
                self.emergency_mode = False
                self.historical_paused = False
        
        if reset_time:
            try:
                self.rate_limit_reset = datetime.fromtimestamp(int(reset_time))
            except (ValueError, TypeError):
                pass
    
    def activate_burst_mode(self, reason: str = 'morning_briefing'):
        """
        Enable burst mode for batch operations.
        
        Args:
            reason: Reason for burst mode (for logging)
        """
        self.burst_mode_active = True
        self.burst_requests_remaining = 5
        logger.info(f"🚀 Burst mode activated: {reason}")
    
    def _pause_historical_fetches(self):
        """Put historical (non-essential) fetches on hold"""
        self.historical_paused = True
        logger.warning("⏸️ Historical fetches paused due to low quota")
    
    def get_status(self) -> dict:
        """Return current governor status for monitoring"""
        # Count requests in last minute
        now = time.time()
        recent_requests = len([
            r for r in self.request_history 
            if r['timestamp'] > now - 60
        ])
        
        return {
            'tokens_available': round(self.tokens, 2),
            'max_tokens': self.max_tokens,
            'rate_limit_remaining': self.rate_limit_remaining,
            'rate_limit_total': self.rate_limit_total,
            'rate_limit_percentage': round(
                (self.rate_limit_remaining / self.rate_limit_total * 100) 
                if self.rate_limit_total > 0 else 0, 
                1
            ),
            'emergency_mode': self.emergency_mode,
            'burst_mode': self.burst_mode_active,
            'in_cooldown': self.cooldown_until is not None and time.time() < self.cooldown_until,
            'requests_last_minute': recent_requests,
            'historical_paused': self.historical_paused
        }
    
    def reset(self):
        """Reset governor state (for testing)"""
        self.tokens = self.max_tokens
        self.emergency_mode = False
        self.burst_mode_active = False
        self.cooldown_until = None
        self.historical_paused = False
        logger.info("Governor reset to default state")
