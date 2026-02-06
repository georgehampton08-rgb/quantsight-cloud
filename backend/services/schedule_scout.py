from datetime import datetime, timedelta
import json
import random

class ScheduleScout:
    def __init__(self):
        self.today = datetime.now().date()
        self.yesterday = self.today - timedelta(days=1)
        
    def get_active_teams_mock(self):
        """
        Mock: Returns a list of teams playing today.
        In prod, this would hit the NBA Schedule API.
        """
        all_teams = ["LAL", "GSW", "BOS", "MIA", "NYK", "PHI", "DEN", "PHX"]
        # Randomly select 4 teams playing today
        return random.sample(all_teams, 4)

    def check_freshness(self, stored_date_str: str, expected_last_game_str: str = None) -> str:
        """
        Logic Refined (User Feedback): 
        - Compare 'stored_date' vs 'expected_last_game_date' (from Schedule API).
        - If stored == expected: FRESH (Data is up to date with reality).
        - If stored < expected: STALE (We are missing the latest game).
        
        Fallback: If no expected date provided, use Yesterday as loose baseline.
        """
        try:
            stored_date = datetime.strptime(stored_date_str, "%Y-%m-%d").date()
            
            if expected_last_game_str:
                expected_date = datetime.strptime(expected_last_game_str, "%Y-%m-%d").date()
                if stored_date >= expected_date:
                    return "FRESH"
                else:
                    return f"STALE (Exp: {expected_last_game_str})"
            
            # Fallback (Legacy)
            if stored_date >= self.yesterday:
                return "FRESH"
            else:
                return "STALE"
        except ValueError:
            return "UNKNOWN_DATE_FORMAT"

    def generate_manifest(self, players: list) -> dict:
        """
        Generates the status_manifest.json for the frontend.
        failed_last_game_date can be mocked or passed in.
        """
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "scout_version": "AEGIS-V2 (Smart Audit)",
            "active_teams_today": self.get_active_teams_mock(),
            "freshness_audit": []
        }

        for p in players:
            # In Prod, we would fetch 'expected_last_game' from an external Schedule API here.
            # For V1, we simply check if the player dict has an 'expected_date' field, 
            # otherwise we default to None (Yesterday fallback).
            expected = p.get('expected_active_date') 
            status = self.check_freshness(p['last_game_date'], expected)
            
            entry = {
                "player_id": p['id'],
                "name": p['name'],
                "last_game_processed": p['last_game_date'],
                "status": status,
                "data_source": "Local Cache"
            }
            manifest['freshness_audit'].append(entry)

        return manifest
