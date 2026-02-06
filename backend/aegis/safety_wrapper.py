"""
Integration Safety Wrapper
Ensures router data flows don't interfere with existing calculations
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class CalculationSafetyWrapper:
    """
    Safety wrapper that ensures the Aegis router provides data
    to existing calculation functions without modifying them.
    
    Acts as a read-only data provider - calculations remain unchanged.
    """
    
    def __init__(self, aegis_router):
        """
        Initialize with Aegis router instance.
        
        Args:
            aegis_router: AegisBrain instance
        """
        self.router = aegis_router
        logger.info("CalculationSafetyWrapper initialized")
    
    async def get_data_for_calculation(self, query: dict) -> dict:
        """
        Provides data to calculation functions without modifying them.
        
        The router's job ends here - calculations use the same data format
        they always have, just retrieved more intelligently.
        
        Args:
            query: Data request (type, id, etc.)
            
        Returns:
            Normalized data in legacy format
        """
        # Get data through smart router
        raw_result = await self.router.route_request(query)
        
        # Extract just the data portion
        data = raw_result.get('data', {})
        
        # Transform to existing expected format (backward compatible)
        normalized = self._normalize_to_legacy_format(data, query.get('type'))
        
        logger.debug(f"Provided data for calculation: {query.get('type')}:{query.get('id')}")
        
        return normalized
    
    def _normalize_to_legacy_format(self, data: dict, entity_type: str) -> dict:
        """
        Ensure data matches what existing calculations expect.
        
        No changes to data structure - just smart retrieval.
        The calculations receive the exact same format they always did.
        """
        # For now, pass through as-is
        # Can add format transformations here if needed
        return data
    
    async def get_player_stats(self, player_id: int) -> dict:
        """Convenience method for player stats"""
        return await self.get_data_for_calculation({
            'type': 'player_stats',
            'id': player_id
        })
    
    async def get_team_stats(self, team_id: int) -> dict:
        """Convenience method for team stats"""
        return await self.get_data_for_calculation({
            'type': 'team_stats',
            'id': team_id
        })
    
    async def get_schedule(self) -> dict:
        """Convenience method for schedule data"""
        return await self.get_data_for_calculation({
            'type': 'schedule',
            'id': 0  # Global schedule
        })
