"""
Leader Election
===============
Redis-based distributed lock for multi-instance coordination.
"""

import asyncio
import uuid
from typing import Optional

from ..bootstrap.redis_client import get_redis
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LeaderElection:
    """
    Distributed leader election using Redis SET NX.
    
    Only the Lead Sovereign executes remediation actions.
    Followers observe and monitor leader's heartbeat.
    """
    
    def __init__(self):
        self.instance_id = str(uuid.uuid4())
        self.is_leader = False
        self.heartbeat_task: Optional[asyncio.Task] = None
    
    async def run_election(self) -> bool:
        """
        Attempt to become the Lead Sovereign.
        
        Returns:
            True if elected leader, False if follower
        """
        try:
            redis_client = await get_redis()
            
            # Attempt to acquire lock (30s TTL)
            acquired = await redis_client.set(
                "vanguard:sovereign:leader",
                self.instance_id,
                nx=True,  # Only set if not exists
                ex=30     # Expire in 30 seconds
            )
            
            if acquired:
                self.is_leader = True
                logger.info("leader_elected", instance_id=self.instance_id, role="LEAD_SOVEREIGN")
                
                # Start heartbeat to maintain leadership
                self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                return True
            else:
                self.is_leader = False
                logger.info("follower_role", instance_id=self.instance_id, role="FOLLOWER")
                return False
        
        except Exception as e:
            logger.error("leader_election_failed", error=str(e))
            self.is_leader = False
            return False
    
    async def _heartbeat_loop(self) -> None:
        """Maintain leadership by renewing lock every 10s."""
        while self.is_leader:
            try:
                await asyncio.sleep(10)
                
                redis_client = await get_redis()
                
                # Renew lock if still leader
                current_leader = await redis_client.get("vanguard:sovereign:leader")
                if current_leader == self.instance_id:
                    await redis_client.expire("vanguard:sovereign:leader", 30)
                    logger.debug("leader_heartbeat", instance_id=self.instance_id)
                else:
                    # Lost leadership
                    self.is_leader = False
                    logger.warning("leadership_lost", instance_id=self.instance_id)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("heartbeat_error", error=str(e))
    
    async def stop(self) -> None:
        """Stop heartbeat and release leadership."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.is_leader:
            try:
                redis_client = await get_redis()
                await redis_client.delete("vanguard:sovereign:leader")
                logger.info("leadership_released", instance_id=self.instance_id)
            except Exception as e:
                logger.error("leadership_release_error", error=str(e))
        
        self.is_leader = False


# Global leader election
_leader_election: LeaderElection | None = None


def get_leader_election() -> LeaderElection:
    """Get or create the global leader election."""
    global _leader_election
    if _leader_election is None:
        _leader_election = LeaderElection()
    return _leader_election
