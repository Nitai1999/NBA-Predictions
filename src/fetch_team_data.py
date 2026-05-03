import pandas as pd
import os
import time
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.static import teams

def fetch_team_data(team_abr):
    """
    Fetches new data and merges it with existing CSVs to avoid full overwrites.
    """
    raw_data_path = os.path.join('data', 'raw')
    if not os.path.exists(raw_data_path):
        os.makedirs(raw_data_path)

    # Find team ID
    nba_teams = teams.get_teams()
    target_team = [team for team in nba_teams if team['abbreviation'] == team_abr]
    
    if not target_team:
        print(f"Error: Team {team_abr} not found.")
        return False
        
    team_id = target_team[0]['id']
    save_path = os.path.join(raw_data_path, f"{team_abr}_games.csv")

    print(f"Updating data for: {target_team[0]['full_name']}...")

    try:
        # 1. Fetch latest data from API
        time.sleep(0.6) 
        game_finder = leaguegamefinder.LeagueGameFinder(team_id_nullable=team_id)
        new_games_df = game_finder.get_data_frames()[0]

        # Process dates and basic filters
        new_games_df['GAME_DATE'] = pd.to_datetime(new_games_df['GAME_DATE'])
        new_games_df = new_games_df[new_games_df['GAME_DATE'] >= '2021-01-01']
        new_games_df = new_games_df[new_games_df['SEASON_ID'].str.startswith(('2', '4'))]

        # 2. Smart Merge Logic
        if os.path.exists(save_path):
            existing_df = pd.read_csv(save_path)
            existing_df['GAME_DATE'] = pd.to_datetime(existing_df['GAME_DATE'])
            
            # Combine and deduplicate based on GAME_ID
            # We keep 'first' to ensure the most recent API data (with updated stats) is used
            final_df = pd.concat([new_games_df, existing_df]).drop_duplicates(subset=['GAME_ID'], keep='first')
            new_count = len(final_df) - len(existing_df)
            print(f"Merged {new_count} new games into existing record.")
        else:
            final_df = new_games_df
            print(f"No existing file found. Created fresh record.")

        # 3. Sort and Save
        final_df = final_df.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)
        final_df.to_csv(save_path, index=False)
        return True

    except Exception as e:
        print(f"Failed to update {team_abr}: {e}")
        return False

if __name__ == "__main__":
    fetch_team_data("BOS")