import os
import time
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.static import teams

# Custom Imports
from models.team import Team
from models.game import Game, GameType
from fetch_nba_data import fetch_team_data 

# Environment Setup
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
load_dotenv(dotenv_path=project_root / '.env')

CONFERENCES = {
    'ATL': 'East', 'BOS': 'East', 'BKN': 'East', 'CHA': 'East', 'CHI': 'East',
    'CLE': 'East', 'DET': 'East', 'IND': 'East', 'MIA': 'East', 'MIL': 'East',
    'NYK': 'East', 'ORL': 'East', 'PHI': 'East', 'TOR': 'East', 'WAS': 'East',
    'DAL': 'West', 'DEN': 'West', 'GSW': 'West', 'HOU': 'West', 'LAC': 'West',
    'LAL': 'West', 'MEM': 'West', 'MIN': 'West', 'NOP': 'West', 'OKC': 'West',
    'PHX': 'West', 'POR': 'West', 'SAC': 'West', 'SAS': 'West', 'UTA': 'West'
}

def get_game_type(game_id):
    prefix = str(game_id)[:3]
    if prefix == '004': return GameType.PLAYOFF
    if prefix == '006': return GameType.CUP
    return GameType.REGULAR_SEASON

def run_daily_predictions():
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime('%Y-%m-%d')
    
    print(f"--- NBA Daily Prediction Pipeline ---")
    print(f"Target Date: {tomorrow_str}\n")

    try:
        board = scoreboardv2.ScoreboardV2(game_date=tomorrow_str)
        games_df = board.get_data_frames()[0]
        
        if games_df.empty:
            print("No games scheduled. Mishka says: Time for a walk! 🐕")
            return

        nba_teams = teams.get_teams()
        id_to_abr = {t['id']: t['abbreviation'] for t in nba_teams}

        for _, row in games_df.iterrows():
            home_abr = id_to_abr.get(row['HOME_TEAM_ID'])
            away_abr = id_to_abr.get(row['VISITOR_TEAM_ID'])
            
            # Determine 10 vs 6 rule
            same_conf = CONFERENCES.get(home_abr) == CONFERENCES.get(away_abr)
            h2h_limit = 10 if same_conf else 6

            print(f"Preparing: {away_abr} vs {home_abr}...")
            fetch_team_data(home_abr)
            fetch_team_data(away_abr)

            try:
                game_instance = Game(
                    home_team=Team(home_abr),
                    away_team=Team(away_abr),
                    date=tomorrow_str,
                    game_type=get_game_type(row['GAME_ID']),
                    is_neutral=(row['ARENA_NAME'] in ["T-Mobile Arena", "Accor Arena"]),
                    h2h_limit=h2h_limit
                )
                game_instance.predict()

                print("Cooling down API (2s)...")
                time.sleep(2)
            except Exception as e:
                print(f"Error predicting matchup: {e}")

    except Exception as e:
        print(f"Pipeline Error: {e}")

if __name__ == "__main__":
    run_daily_predictions()