import time
from nba_api.stats.static import teams
from fetch_team_data import fetch_team_data 

def refresh_all_teams():
    all_nba_teams = teams.get_teams()
    print(f"Starting Daily League Refresh for {len(all_nba_teams)} teams...")
    
    start_time = time.time()
    for team in all_nba_teams:
        abr = team['abbreviation']
        fetch_team_data(abr)
        # 1-second pause to strictly avoid NBA API rate limiting
        time.sleep(1.0) 

    duration = (time.time() - start_time) / 60
    print(f"\n--- League Refresh Complete! ---")
    print(f"Duration: {duration:.2f} minutes")

if __name__ == "__main__":
    refresh_all_teams()