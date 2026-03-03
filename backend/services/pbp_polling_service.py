import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from services.nba_pbp_service import pbp_client, PlayEvent
from services.firebase_pbp_service import firebase_pbp_service

logger = logging.getLogger(__name__)

class PBPPollingService:
    def __init__(self):
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.game_metadata_cache: Dict[str, Dict[str, Any]] = {}
        # In-memory broker for SSE routes. game_id -> asyncio.Queue
        self.sse_queues: Dict[str, List[asyncio.Queue]] = {}

    def get_tracked_games(self) -> List[str]:
        return list(self.active_tasks.keys())

    async def start_tracking(self, game_id: str):
        if game_id in self.active_tasks:
            logger.info(f"Already tracking game {game_id}")
            return

        logger.info(f"Starting tracking for game {game_id}")
        self.active_tasks[game_id] = asyncio.create_task(self._poll_loop(game_id))

    def stop_tracking(self, game_id: str):
        task = self.active_tasks.pop(game_id, None)
        if task:
            task.cancel()
            logger.info(f"Stopped tracking game {game_id}")

    async def _poll_loop(self, game_id: str):
        poll_interval = 10 # seconds
        consecutive_errors = 0
        last_sequence_num = -1

        try:
            while True:
                try:
                    # 1. Fetch from primary ESPN
                    plays = pbp_client.fetch_espn_plays(game_id)
                    consecutive_errors = 0
                    
                except Exception as e:
                    logger.error(f"ESPN failed for {game_id}: {e}")
                    consecutive_errors += 1
                    plays = []
                    
                # NOTE: In a real failover, we'd need to map ESPN game_id to NBA game_id, 
                # but they are physically different IDs. If ESPN fails continuously,
                # we'd rely on a manual or lookup mapping to switch to CDN.
                # For this MVP phase, we retry ESPN with backoff.
                
                if not plays and consecutive_errors > 0:
                    try:
                        # Optional: attempt CDN fallback if we knew the NBA ID
                        # plays = pbp_client.fetch_nba_cdn_plays(nba_game_id)
                        pass
                    except:
                        pass

                # Filter newly unseen plays
                new_plays = []
                for p in plays:
                    if p.sequenceNumber > last_sequence_num:
                        new_plays.append(p)

                if new_plays:
                    # Async push to Firebase (run in threadpool since Firebase Admin is sync)
                    await asyncio.to_thread(firebase_pbp_service.save_plays_batch, game_id, new_plays)
                    
                    # Update local state
                    last_sequence_num = max([p.sequenceNumber for p in new_plays])
                    
                    # Async update metadata/snapshot
                    await asyncio.to_thread(
                        firebase_pbp_service.update_cache_snapshot,
                        game_id,
                        len(plays),
                        datetime.utcnow().isoformat() + "Z"
                    )

                    # Push to any active SSE listeners
                    if game_id in self.sse_queues:
                        for q in self.sse_queues[game_id]:
                            # Push the list of new plays as JSON to the queue
                            json_payload = [p.model_dump() for p in new_plays]
                            try:
                                q.put_nowait(json_payload)
                            except asyncio.QueueFull:
                                pass

                    logger.info(f"Polled {len(new_plays)} new plays for game {game_id}. Last Seq: {last_sequence_num}")

                # If game reached 'End Game' sequence, stop polling
                if plays and any((p.eventType.lower() == "end game" or p.description.lower() == "end of game") for p in plays):
                    logger.info(f"Game {game_id} has ended. Stopping poller.")
                    self.active_tasks.pop(game_id, None)
                    break

                # Backoff if errors
                sleep_time = min(poll_interval * (2 ** consecutive_errors), 60) if consecutive_errors > 0 else poll_interval
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info(f"Poller for {game_id} was cancelled.")
        except Exception as e:
            logger.error(f"Fatal error in poller loop for {game_id}: {e}")
            self.active_tasks.pop(game_id, None)

    # --- SSE Broker Methods ---
    def subscribe_sse(self, game_id: str) -> asyncio.Queue:
        if game_id not in self.sse_queues:
            self.sse_queues[game_id] = []
        q = asyncio.Queue(maxsize=100)
        self.sse_queues[game_id].append(q)
        return q

    def unsubscribe_sse(self, game_id: str, q: asyncio.Queue):
        if game_id in self.sse_queues and q in self.sse_queues[game_id]:
            self.sse_queues[game_id].remove(q)
            if not self.sse_queues[game_id]:
                del self.sse_queues[game_id]

pbp_polling_manager = PBPPollingService()
