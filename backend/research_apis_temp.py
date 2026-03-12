import sys
import json
import requests
import datetime
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.endpoints import playbyplayv2
from nba_api.live.nba.endpoints import playbyplay as live_playbyplay

def main():
    print("--- ESPN API (Finished Game) ---")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y%m%d')
    espn_sb_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={yesterday}"
    espn_sb = requests.get(espn_sb_url).json()
    
    events = espn_sb.get("events", [])
    if events:
        espn_event = events[0]
        espn_game_id = espn_event["id"]
        print(f"ESPN Game ID: {espn_game_id}, Name: {espn_event['name']}, Status: {espn_event['status']['type']['description']}")
        
        espn_summary_url = f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={espn_game_id}"
        espn_summary = requests.get(espn_summary_url).json()
        
        with open("espn_pbp_sample.json", "w", encoding="utf-8") as f:
            plays = espn_summary.get("plays", [])
            json.dump({
                "play_count": len(plays),
                "plays_sample": plays[:5],
                "boxscore_keys": list(espn_summary.get("boxscore", {}).keys()),
                "header_status": espn_summary.get("header", {}).get("competitions", [{}])[0].get("status", {})
            }, f, indent=2)
        print("Saved ESPN PBP sample to espn_pbp_sample.json")
    
    print("\n--- NBA API (Finished Game) ---")
    try:
        from nba_api.stats.endpoints import scoreboardv2
        custom_headers = {
            'Host': 'stats.nba.com',
            'Connection': 'keep-alive',
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Referer': 'https://www.nba.com/',
            'Origin': 'https://www.nba.com',
        }
        board = scoreboardv2.ScoreboardV2(game_date="2024-03-01", headers=custom_headers, timeout=10)
        nba_games = board.get_data_frames()[0]
        if nba_games.empty:
            print("No NBA API games found.")
        else:
            nba_game_id = str(nba_games.iloc[0]['GAME_ID']).zfill(10)
            print(f"NBA API Game ID: {nba_game_id}")
            
            pbp = playbyplayv2.PlayByPlayV2(game_id=nba_game_id, headers=custom_headers, timeout=10)
            nba_pbp_df = pbp.get_data_frames()[0]
            
            with open("nba_pbp_sample.json", "w", encoding="utf-8") as f:
                records = nba_pbp_df.head(5).to_dict('records')
                json.dump(records, f, indent=2)
            print("Saved NBA PBP sample to nba_pbp_sample.json")
            
            # test live endpoint with past game (might fail but let's try)
            try:
                live_pbp = live_playbyplay.PlayByPlay(nba_game_id)
                live_pbp_dict = live_pbp.get_dict()
                with open("nba_live_pbp_sample.json", "w", encoding="utf-8") as f:
                    actions = live_pbp_dict.get("game", {}).get("actions", [])
                    json.dump(actions[:5], f, indent=2)
                print("Saved NBA LIVE PBP sample to nba_live_pbp_sample.json")
            except Exception as e:
                print(f"live.nba.endpoints.playbyplay failed (expected for non-live games): {e}")

    except Exception as e:
        print(f"NBA API failed: {e}")

if __name__ == "__main__":
    main()
