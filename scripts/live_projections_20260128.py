"""
Live NBA Game Projections - January 28, 2026
=============================================
Crucible Engine projections for tonight's slate.
"""

import sys
import os
from datetime import date
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from engines.crucible_engine import CrucibleProjector
from aegis.auto_tuner import AutoTuner


# -------------------------------------------------------------------
# TONIGHT'S GAMES - January 28, 2026
# -------------------------------------------------------------------

GAMES = [
    {"game_id": "LAL_CLE_20260128", "home": "CLE", "away": "LAL", "time": "7:00 PM ET"},
    {"game_id": "CHI_IND_20260128", "home": "IND", "away": "CHI", "time": "7:00 PM ET"},
    {"game_id": "ATL_BOS_20260128", "home": "BOS", "away": "ATL", "time": "7:30 PM ET"},
    {"game_id": "ORL_MIA_20260128", "home": "MIA", "away": "ORL", "time": "7:30 PM ET"},
    {"game_id": "NYK_TOR_20260128", "home": "TOR", "away": "NYK", "time": "7:30 PM ET"},
    {"game_id": "CHA_MEM_20260128", "home": "MEM", "away": "CHA", "time": "8:00 PM ET"},
    {"game_id": "MIN_DAL_20260128", "home": "DAL", "away": "MIN", "time": "8:30 PM ET"},
    {"game_id": "GSW_UTA_20260128", "home": "UTA", "away": "GSW", "time": "9:00 PM ET"},
    {"game_id": "SAS_HOU_20260128", "home": "HOU", "away": "SAS", "time": "9:30 PM ET"},
]

# -------------------------------------------------------------------
# TEAM ROSTERS (from local data + estimated stats)
# -------------------------------------------------------------------

ROSTERS = {
    "CLE": [
        {"player_id": "1629630", "name": "Donovan Mitchell", "archetype": "Scorer", "fg2_pct": 0.52, "fg3_pct": 0.371, "usage": 0.28},
        {"player_id": "1628978", "name": "Darius Garland", "archetype": "Playmaker", "fg2_pct": 0.54, "fg3_pct": 0.416, "usage": 0.24},
        {"player_id": "1630544", "name": "Evan Mobley", "archetype": "Rim Protector", "fg2_pct": 0.58, "fg3_pct": 0.354, "usage": 0.22},
        {"player_id": "1628398", "name": "Jarrett Allen", "archetype": "Rim Protector", "fg2_pct": 0.68, "fg3_pct": 0.00, "usage": 0.16},
        {"player_id": "cle5", "name": "Max Strus", "archetype": "Three-and-D", "fg2_pct": 0.45, "fg3_pct": 0.38, "usage": 0.14},
        {"player_id": "cle6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "cle7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "LAL": [
        {"player_id": "2544", "name": "LeBron James", "archetype": "Scorer", "fg2_pct": 0.56, "fg3_pct": 0.358, "usage": 0.30},
        {"player_id": "203076", "name": "Anthony Davis", "archetype": "Rim Protector", "fg2_pct": 0.58, "fg3_pct": 0.236, "usage": 0.28},
        {"player_id": "lal3", "name": "D'Angelo Russell", "archetype": "Playmaker", "fg2_pct": 0.48, "fg3_pct": 0.36, "usage": 0.22},
        {"player_id": "lal4", "name": "Austin Reaves", "archetype": "Balanced", "fg2_pct": 0.50, "fg3_pct": 0.40, "usage": 0.16},
        {"player_id": "lal5", "name": "Rui Hachimura", "archetype": "Balanced", "fg2_pct": 0.52, "fg3_pct": 0.35, "usage": 0.12},
        {"player_id": "lal6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "lal7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "BOS": [
        {"player_id": "1628369", "name": "Jayson Tatum", "archetype": "Scorer", "fg2_pct": 0.52, "fg3_pct": 0.374, "usage": 0.30},
        {"player_id": "1628370", "name": "Jaylen Brown", "archetype": "Slasher", "fg2_pct": 0.54, "fg3_pct": 0.371, "usage": 0.28},
        {"player_id": "bos3", "name": "Derrick White", "archetype": "Three-and-D", "fg2_pct": 0.50, "fg3_pct": 0.38, "usage": 0.18},
        {"player_id": "bos4", "name": "Jrue Holiday", "archetype": "Playmaker", "fg2_pct": 0.52, "fg3_pct": 0.36, "usage": 0.15},
        {"player_id": "bos5", "name": "Al Horford", "archetype": "Rim Protector", "fg2_pct": 0.55, "fg3_pct": 0.35, "usage": 0.12},
        {"player_id": "bos6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "bos7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "ATL": [
        {"player_id": "203897", "name": "Trae Young", "archetype": "Playmaker", "fg2_pct": 0.48, "fg3_pct": 0.371, "usage": 0.32},
        {"player_id": "1629632", "name": "De'Andre Hunter", "archetype": "Three-and-D", "fg2_pct": 0.50, "fg3_pct": 0.391, "usage": 0.18},
        {"player_id": "atl3", "name": "Jalen Johnson", "archetype": "Slasher", "fg2_pct": 0.54, "fg3_pct": 0.32, "usage": 0.22},
        {"player_id": "atl4", "name": "Clint Capela", "archetype": "Rim Protector", "fg2_pct": 0.65, "fg3_pct": 0.00, "usage": 0.14},
        {"player_id": "atl5", "name": "Dyson Daniels", "archetype": "Balanced", "fg2_pct": 0.48, "fg3_pct": 0.34, "usage": 0.16},
        {"player_id": "atl6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "atl7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "MIA": [
        {"player_id": "1629636", "name": "Tyler Herro", "archetype": "Scorer", "fg2_pct": 0.50, "fg3_pct": 0.418, "usage": 0.28},
        {"player_id": "1628389", "name": "Bam Adebayo", "archetype": "Rim Protector", "fg2_pct": 0.52, "fg3_pct": 0.00, "usage": 0.24},
        {"player_id": "mia3", "name": "Jimmy Butler", "archetype": "Playmaker", "fg2_pct": 0.50, "fg3_pct": 0.32, "usage": 0.26},
        {"player_id": "mia4", "name": "Terry Rozier", "archetype": "Three-and-D", "fg2_pct": 0.46, "fg3_pct": 0.38, "usage": 0.18},
        {"player_id": "mia5", "name": "Nikola Jovic", "archetype": "Balanced", "fg2_pct": 0.48, "fg3_pct": 0.36, "usage": 0.12},
        {"player_id": "mia6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "mia7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "ORL": [
        {"player_id": "1630559", "name": "Franz Wagner", "archetype": "Scorer", "fg2_pct": 0.52, "fg3_pct": 0.351, "usage": 0.28},
        {"player_id": "1630567", "name": "Jalen Suggs", "archetype": "Three-and-D", "fg2_pct": 0.48, "fg3_pct": 0.362, "usage": 0.20},
        {"player_id": "1630178", "name": "Cole Anthony", "archetype": "Playmaker", "fg2_pct": 0.46, "fg3_pct": 0.362, "usage": 0.18},
        {"player_id": "orl4", "name": "Wendell Carter Jr", "archetype": "Rim Protector", "fg2_pct": 0.55, "fg3_pct": 0.32, "usage": 0.16},
        {"player_id": "orl5", "name": "Kentavious Caldwell-Pope", "archetype": "Three-and-D", "fg2_pct": 0.48, "fg3_pct": 0.40, "usage": 0.14},
        {"player_id": "orl6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "orl7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "NYK": [
        {"player_id": "1628973", "name": "Jalen Brunson", "archetype": "Scorer", "fg2_pct": 0.52, "fg3_pct": 0.382, "usage": 0.32},
        {"player_id": "nyk2", "name": "OG Anunoby", "archetype": "Three-and-D", "fg2_pct": 0.50, "fg3_pct": 0.38, "usage": 0.18},
        {"player_id": "nyk3", "name": "Mikal Bridges", "archetype": "Balanced", "fg2_pct": 0.48, "fg3_pct": 0.36, "usage": 0.20},
        {"player_id": "nyk4", "name": "Josh Hart", "archetype": "Balanced", "fg2_pct": 0.50, "fg3_pct": 0.32, "usage": 0.16},
        {"player_id": "1628386", "name": "Mitchell Robinson", "archetype": "Rim Protector", "fg2_pct": 0.64, "fg3_pct": 0.00, "usage": 0.10},
        {"player_id": "nyk6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "nyk7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "TOR": [
        {"player_id": "1630224", "name": "Scottie Barnes", "archetype": "Playmaker", "fg2_pct": 0.52, "fg3_pct": 0.311, "usage": 0.26},
        {"player_id": "1629631", "name": "RJ Barrett", "archetype": "Slasher", "fg2_pct": 0.58, "fg3_pct": 0.378, "usage": 0.26},
        {"player_id": "tor3", "name": "Immanuel Quickley", "archetype": "Scorer", "fg2_pct": 0.46, "fg3_pct": 0.38, "usage": 0.22},
        {"player_id": "tor4", "name": "Gradey Dick", "archetype": "Three-and-D", "fg2_pct": 0.48, "fg3_pct": 0.42, "usage": 0.16},
        {"player_id": "tor5", "name": "Jakob Poeltl", "archetype": "Rim Protector", "fg2_pct": 0.62, "fg3_pct": 0.00, "usage": 0.14},
        {"player_id": "tor6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "tor7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "MEM": [
        {"player_id": "1629627", "name": "Ja Morant", "archetype": "Slasher", "fg2_pct": 0.52, "fg3_pct": 0.321, "usage": 0.30},
        {"player_id": "1628977", "name": "Jaren Jackson Jr.", "archetype": "Rim Protector", "fg2_pct": 0.52, "fg3_pct": 0.354, "usage": 0.26},
        {"player_id": "1630195", "name": "Desmond Bane", "archetype": "Three-and-D", "fg2_pct": 0.48, "fg3_pct": 0.372, "usage": 0.22},
        {"player_id": "203935", "name": "Marcus Smart", "archetype": "Playmaker", "fg2_pct": 0.42, "fg3_pct": 0.367, "usage": 0.16},
        {"player_id": "mem5", "name": "Santi Aldama", "archetype": "Balanced", "fg2_pct": 0.50, "fg3_pct": 0.38, "usage": 0.14},
        {"player_id": "mem6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "mem7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "CHA": [
        {"player_id": "cha1", "name": "LaMelo Ball", "archetype": "Playmaker", "fg2_pct": 0.46, "fg3_pct": 0.36, "usage": 0.30},
        {"player_id": "cha2", "name": "Brandon Miller", "archetype": "Scorer", "fg2_pct": 0.50, "fg3_pct": 0.38, "usage": 0.24},
        {"player_id": "cha3", "name": "Miles Bridges", "archetype": "Slasher", "fg2_pct": 0.52, "fg3_pct": 0.34, "usage": 0.22},
        {"player_id": "cha4", "name": "Mark Williams", "archetype": "Rim Protector", "fg2_pct": 0.60, "fg3_pct": 0.00, "usage": 0.14},
        {"player_id": "cha5", "name": "Grant Williams", "archetype": "Balanced", "fg2_pct": 0.48, "fg3_pct": 0.36, "usage": 0.12},
        {"player_id": "cha6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "cha7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "DAL": [
        {"player_id": "1629029", "name": "Luka Doncic", "archetype": "Scorer", "fg2_pct": 0.52, "fg3_pct": 0.345, "usage": 0.34},
        {"player_id": "dal2", "name": "Kyrie Irving", "archetype": "Playmaker", "fg2_pct": 0.54, "fg3_pct": 0.40, "usage": 0.26},
        {"player_id": "1629639", "name": "PJ Washington", "archetype": "Balanced", "fg2_pct": 0.52, "fg3_pct": 0.371, "usage": 0.16},
        {"player_id": "dal4", "name": "Daniel Gafford", "archetype": "Rim Protector", "fg2_pct": 0.70, "fg3_pct": 0.00, "usage": 0.12},
        {"player_id": "dal5", "name": "Klay Thompson", "archetype": "Three-and-D", "fg2_pct": 0.46, "fg3_pct": 0.38, "usage": 0.18},
        {"player_id": "dal6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "dal7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "MIN": [
        {"player_id": "1630162", "name": "Anthony Edwards", "archetype": "Scorer", "fg2_pct": 0.52, "fg3_pct": 0.397, "usage": 0.32},
        {"player_id": "min2", "name": "Julius Randle", "archetype": "Balanced", "fg2_pct": 0.54, "fg3_pct": 0.32, "usage": 0.24},
        {"player_id": "min3", "name": "Rudy Gobert", "archetype": "Rim Protector", "fg2_pct": 0.68, "fg3_pct": 0.00, "usage": 0.14},
        {"player_id": "min4", "name": "Jaden McDaniels", "archetype": "Three-and-D", "fg2_pct": 0.48, "fg3_pct": 0.36, "usage": 0.16},
        {"player_id": "min5", "name": "Mike Conley", "archetype": "Playmaker", "fg2_pct": 0.48, "fg3_pct": 0.40, "usage": 0.14},
        {"player_id": "min6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "min7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "GSW": [
        {"player_id": "201939", "name": "Stephen Curry", "archetype": "Scorer", "fg2_pct": 0.52, "fg3_pct": 0.409, "usage": 0.32},
        {"player_id": "203110", "name": "Draymond Green", "archetype": "Playmaker", "fg2_pct": 0.48, "fg3_pct": 0.341, "usage": 0.14},
        {"player_id": "gsw3", "name": "Andrew Wiggins", "archetype": "Balanced", "fg2_pct": 0.50, "fg3_pct": 0.38, "usage": 0.20},
        {"player_id": "gsw4", "name": "Kevon Looney", "archetype": "Rim Protector", "fg2_pct": 0.62, "fg3_pct": 0.00, "usage": 0.10},
        {"player_id": "gsw5", "name": "Jonathan Kuminga", "archetype": "Slasher", "fg2_pct": 0.54, "fg3_pct": 0.32, "usage": 0.18},
        {"player_id": "gsw6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "gsw7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "UTA": [
        {"player_id": "uta1", "name": "Lauri Markkanen", "archetype": "Scorer", "fg2_pct": 0.52, "fg3_pct": 0.36, "usage": 0.28},
        {"player_id": "uta2", "name": "Collin Sexton", "archetype": "Scorer", "fg2_pct": 0.50, "fg3_pct": 0.34, "usage": 0.24},
        {"player_id": "uta3", "name": "Jordan Clarkson", "archetype": "Scorer", "fg2_pct": 0.48, "fg3_pct": 0.36, "usage": 0.22},
        {"player_id": "uta4", "name": "Walker Kessler", "archetype": "Rim Protector", "fg2_pct": 0.65, "fg3_pct": 0.00, "usage": 0.14},
        {"player_id": "uta5", "name": "John Collins", "archetype": "Balanced", "fg2_pct": 0.54, "fg3_pct": 0.34, "usage": 0.16},
        {"player_id": "uta6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "uta7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "SAS": [
        {"player_id": "1631094", "name": "Victor Wembanyama", "archetype": "Rim Protector", "fg2_pct": 0.52, "fg3_pct": 0.354, "usage": 0.30},
        {"player_id": "sas2", "name": "Devin Vassell", "archetype": "Three-and-D", "fg2_pct": 0.48, "fg3_pct": 0.38, "usage": 0.22},
        {"player_id": "sas3", "name": "Keldon Johnson", "archetype": "Slasher", "fg2_pct": 0.50, "fg3_pct": 0.34, "usage": 0.20},
        {"player_id": "sas4", "name": "Chris Paul", "archetype": "Playmaker", "fg2_pct": 0.48, "fg3_pct": 0.36, "usage": 0.18},
        {"player_id": "sas5", "name": "Jeremy Sochan", "archetype": "Balanced", "fg2_pct": 0.52, "fg3_pct": 0.28, "usage": 0.14},
        {"player_id": "sas6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "sas7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "HOU": [
        {"player_id": "1630552", "name": "Alperen Sengun", "archetype": "Playmaker", "fg2_pct": 0.56, "fg3_pct": 0.291, "usage": 0.26},
        {"player_id": "hou2", "name": "Jalen Green", "archetype": "Scorer", "fg2_pct": 0.48, "fg3_pct": 0.36, "usage": 0.28},
        {"player_id": "hou3", "name": "Fred VanVleet", "archetype": "Playmaker", "fg2_pct": 0.46, "fg3_pct": 0.38, "usage": 0.20},
        {"player_id": "hou4", "name": "Dillon Brooks", "archetype": "Three-and-D", "fg2_pct": 0.46, "fg3_pct": 0.36, "usage": 0.18},
        {"player_id": "hou5", "name": "Tari Eason", "archetype": "Slasher", "fg2_pct": 0.52, "fg3_pct": 0.32, "usage": 0.14},
        {"player_id": "hou6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "hou7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "IND": [
        {"player_id": "1630169", "name": "Tyrese Haliburton", "archetype": "Playmaker", "fg2_pct": 0.48, "fg3_pct": 0.361, "usage": 0.26},
        {"player_id": "ind2", "name": "Pascal Siakam", "archetype": "Slasher", "fg2_pct": 0.54, "fg3_pct": 0.32, "usage": 0.24},
        {"player_id": "ind3", "name": "Myles Turner", "archetype": "Rim Protector", "fg2_pct": 0.54, "fg3_pct": 0.36, "usage": 0.18},
        {"player_id": "ind4", "name": "Andrew Nembhard", "archetype": "Balanced", "fg2_pct": 0.50, "fg3_pct": 0.38, "usage": 0.16},
        {"player_id": "ind5", "name": "Bennedict Mathurin", "archetype": "Scorer", "fg2_pct": 0.48, "fg3_pct": 0.36, "usage": 0.18},
        {"player_id": "ind6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "ind7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
    "CHI": [
        {"player_id": "1629638", "name": "Coby White", "archetype": "Scorer", "fg2_pct": 0.50, "fg3_pct": 0.381, "usage": 0.24},
        {"player_id": "chi2", "name": "Zach LaVine", "archetype": "Scorer", "fg2_pct": 0.52, "fg3_pct": 0.38, "usage": 0.26},
        {"player_id": "chi3", "name": "Nikola Vucevic", "archetype": "Balanced", "fg2_pct": 0.54, "fg3_pct": 0.38, "usage": 0.22},
        {"player_id": "chi4", "name": "Patrick Williams", "archetype": "Three-and-D", "fg2_pct": 0.48, "fg3_pct": 0.34, "usage": 0.14},
        {"player_id": "chi5", "name": "Josh Giddey", "archetype": "Playmaker", "fg2_pct": 0.50, "fg3_pct": 0.32, "usage": 0.18},
        {"player_id": "chi6", "name": "Reserve 1", "archetype": "Balanced", "usage": 0.08},
        {"player_id": "chi7", "name": "Reserve 2", "archetype": "Balanced", "usage": 0.08},
    ],
}


def run_live_projections():
    """Run projections for tonight's games"""
    print("=" * 70)
    print(" 🏀 CRUCIBLE ENGINE - LIVE PROJECTIONS")
    print(" January 28, 2026")
    print("=" * 70)
    
    tuner = AutoTuner()
    projector = CrucibleProjector(n_simulations=300, verbose=False)
    
    all_projections = {}
    
    for game in GAMES:
        home = game["home"]
        away = game["away"]
        
        home_roster = ROSTERS.get(home, [])
        away_roster = ROSTERS.get(away, [])
        
        if not home_roster or not away_roster:
            print(f"\n⚠️  Missing roster data for {away}@{home}")
            continue
        
        print(f"\n{'─' * 50}")
        print(f"🎯 {away} @ {home} ({game['time']})")
        print(f"{'─' * 50}")
        
        # Run projection
        proj = projector.project(home_roster, away_roster)
        
        # Display results
        print(f"\n📊 Game Score Projection:")
        
        # Safe access
        game_proj = proj.get('game', {})
        h_score = game_proj.get('home_score', {})
        a_score = game_proj.get('away_score', {})
        
        print(f"   {home}: {h_score.get('floor',0):.0f} / {h_score.get('ev',0):.0f} / {h_score.get('ceiling',0):.0f}")
        print(f"   {away}: {a_score.get('floor',0):.0f} / {a_score.get('ev',0):.0f} / {a_score.get('ceiling',0):.0f}")
        print(f"   Blowout Probability: {game_proj.get('blowout_pct',0):.1%}")
        
        # Top performers
        print(f"\n🔥 Top Performers (EV Points):")
        
        all_players = []
        home_team_data = proj.get('home', {})
        away_team_data = proj.get('away', {})
        
        for pid, data in home_team_data.items():
            ev = data.get('ev', {})
            all_players.append((data.get('name', 'Unknown'), ev.get('points', 0), home))
            
        for pid, data in away_team_data.items():
            ev = data.get('ev', {})
            all_players.append((data.get('name', 'Unknown'), ev.get('points', 0), away))
        
        top_3 = sorted(all_players, key=lambda x: x[1], reverse=True)[:3]
        for name, pts, team in top_3:
            print(f"   {name} ({team}): {pts:.1f} pts")
        
        # Log to Auto-Tuner
        tuner.log_game_script(
            game_id=game["game_id"],
            game_date=date.today(),
            home_team=home,
            away_team=away,
            home_score_pred=(
                h_score.get('floor', 0),
                h_score.get('ev', 0),
                h_score.get('ceiling', 0)
            ),
            away_score_pred=(
                a_score.get('floor', 0),
                a_score.get('ev', 0),
                a_score.get('ceiling', 0)
            ),
            blowout_pct=game_proj.get('blowout_pct', 0),
            clutch_pct=game_proj.get('clutch_pct', 0),
            key_events=[f"Top scorer: {top_3[0][0]}" if top_3 else "Top scorer: N/A"]
        )
        
        all_projections[game["game_id"]] = proj
        print(f"   ✅ Logged to Auto-Tuner")
    
    print("\n" + "=" * 70)
    print(" PROJECTIONS COMPLETE - LOGGED FOR NEXT-DAY AUDIT")
    print("=" * 70)
    
    # Save to JSON for frontend
    output_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'data', 'live_projections.json')
    with open(output_path, 'w') as f:
        json.dump({
            'date': date.today().isoformat(),
            'games': [
                {
                    'game_id': g['game_id'],
                    'home': g['home'],
                    'away': g['away'],
                    'time': g['time'],
                    'home_score': all_projections.get(g['game_id'], {}).get('game', {}).get('home_score', {}),
                    'away_score': all_projections.get(g['game_id'], {}).get('game', {}).get('away_score', {}),
                    'blowout_pct': all_projections.get(g['game_id'], {}).get('game', {}).get('blowout_pct', 0),
                }
                for g in GAMES if g['game_id'] in all_projections
            ]
        }, f, indent=2)
    
    print(f"\n📁 Saved to {output_path}")


if __name__ == "__main__":
    run_live_projections()
