import requests, json

def main():
    url = "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_0022500858.json"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers)
        data = r.json()
        actions = data.get("game", {}).get("actions", [])
        if actions:
            with open("nba_pbp_cdn_sample.json", "w") as f:
                json.dump(actions[:3], f, indent=2)
            print("Wrote nba_pbp_cdn_sample.json")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
