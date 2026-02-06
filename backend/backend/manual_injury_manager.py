"""
Manual Injury Database Manager
================================
Option 3: Simple interface to manually add/update injuries.
"""
import sys
import os
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from services.automated_injury_worker import get_injury_worker
from datetime import datetime


class ManualInjuryManager:
    """Simple interface for manual injury management"""
    
    def __init__(self):
        self.worker = get_injury_worker()
    
    def add_injury(self, player_name: str, player_id: str, team: str, 
                   status: str, injury_desc: str):
        """Add or update an injury"""
        self.worker.mark_injured(player_id, player_name, team, status, injury_desc)
        print(f"✅ Added: {player_name} ({team}) - {status}")
    
    def remove_injury(self, player_id: str):
        """Remove an injury (mark as healthy)"""
        self.worker.mark_healthy(player_id)
        print(f"✅ Removed injury for player {player_id}")
    
    def bulk_update_from_list(self, injuries: list):
        """Update multiple injuries at once"""
        for inj in injuries:
            self.add_injury(
                inj['player_name'],
                inj['player_id'],
                inj['team'],
                inj['status'],
                inj['injury_desc']
            )
    
    def get_team_status(self, team: str):
        """View current injuries for a team"""
        injuries = self.worker.get_team_injuries(team)
        if injuries:
            print(f"\n{team} Injuries ({len(injuries)}):")
            for inj in injuries:
                print(f"  - {inj['player_name']}: {inj['status']} ({inj['injury_desc']})")
        else:
            print(f"\n{team}: All players healthy")


# Example usage / test
if __name__ == "__main__":
    print("="*70)
    print("MANUAL INJURY DATABASE MANAGER")
    print("="*70)
    
    manager = ManualInjuryManager()
    
    # Add today's real injuries from web search
    print("\n📝 Adding real injuries from Jan 28, 2026 reports...")
    
    real_injuries = [
        # Lakers
        {'player_name': 'Austin Reaves', 'player_id': '1628983', 'team': 'LAL',
         'status': 'OUT', 'injury_desc': 'Left calf strain'},
        
        # Cavaliers
        {'player_name': 'Darius Garland', 'player_id': '203507', 'team': 'CLE',
         'status': 'OUT', 'injury_desc': 'Right great toe sprain'},
        {'player_name': 'Evan Mobley', 'player_id': '1630596', 'team': 'CLE',
         'status': 'OUT', 'injury_desc': 'Left calf strain'},
        
        # Celtics
        {'player_name': 'Jayson Tatum', 'player_id': '1628369', 'team': 'BOS',
         'status': 'OUT', 'injury_desc': 'Right Achilles repair'},
        {'player_name': 'Kristaps Porzingis', 'player_id': '204001', 'team': 'BOS',
         'status': 'OUT', 'injury_desc': 'Left Achilles tendinitis'},
    ]
    
    manager.bulk_update_from_list(real_injuries)
    
    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70)
    
    # Check each team
    for team in ['LAL', 'CLE', 'BOS']:
        manager.get_team_status(team)
    
    print("\n" + "="*70)
    print("✅ Manual update system working!")
    print("\n💡 To use in production:")
    print("   1. Create a simple web form or admin panel")
    print("   2. Call manager.add_injury() with player data")
    print("   3. Injuries auto-apply to all simulations")
    print("="*70)
