"""Simple test - output to file"""
from services.multi_stat_confluence import MultiStatConfluence
import json

engine = MultiStatConfluence()
result = engine.analyze_game('BOS', 'MIA')

# Count by team
teams = {}
for p in result['projections']:
    team = p.get('team', 'UNKNOWN')
    teams[team] = teams.get(team, 0) + 1

output = {
    'game': result['game'],
    'total_players': len(result['projections']),
    'teams': teams,
    'sample_players': [
        {
            'name': p['player_name'],
            'team': p.get('team'),
            'pos': p.get('position'),
            'class': p.get('classification')
        }
        for p in result['projections'][:10]
    ]
}

with open('backend/team_test_output.json', 'w') as f:
    json.dump(output, f, indent=2)

print("Output written to backend/team_test_output.json")
print(f"Total: {output['total_players']}, Teams: {output['teams']}")
