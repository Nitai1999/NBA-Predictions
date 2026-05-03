import pandas as pd
import os
from nba_api.stats.endpoints import teamgamelog
from nba_api.stats.static import teams as nba_teams

class Team:
    def __init__(self, abbreviation):
        """
        Initializes the Team object and calculates core metrics.
        :param abbreviation: 3-letter team code (e.g., 'BOS')
        """
        # FIX: Added team_id so app.py can find it
        self.abbreviation = abbreviation
        self.team_id = abbreviation 
        
        # Ensure path matches the 'data/raw' structure used in app.py and Docker
        self.file_path = os.path.join('data', 'raw', f"{self.abbreviation}_games.csv")
        self.df = None
        
        # Performance Fields
        self.last_10_stats = {}
        self.season_metrics = {}
        self.splits = {}
        
        # Only process if data exists; otherwise app.py will call fetch_stats()
        if self.data_exists():
            self.load_and_process()

    def data_exists(self):
        """Checks if the CSV file for this team exists."""
        return os.path.exists(self.file_path)

    def fetch_stats(self):
        """
        Fetches official NBA stats live and saves to CSV.
        Required for cloud deployment where local files are missing.
        """
        try:
            # 1. Find the numerical NBA Team ID from the abbreviation
            nba_team = [t for t in nba_teams.get_teams() if t['abbreviation'] == self.abbreviation][0]
            real_id = nba_team['id']

            # 2. Call the NBA API
            # Fetching the last 2 seasons to ensure we have enough data for 'Last 10'
            gamelog = teamgamelog.TeamGameLog(team_id=real_id, season='2025-26').get_data_frames()[0]
            prev_log = teamgamelog.TeamGameLog(team_id=real_id, season='2024-25').get_data_frames()[0]
            
            full_log = pd.concat([gamelog, prev_log], ignore_index=True)

            # 3. Save to the path expected by the app
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            full_log.to_csv(self.file_path, index=False)
            
            # 4. Load the newly saved data into the object
            self.load_and_process()
            return True
        except Exception as e:
            print(f"Failed to fetch stats for {self.abbreviation}: {e}")
            return False

    def load_and_process(self):
        """Loads the CSV and prepares necessary columns for calculation."""
        if not self.data_exists():
            return

        self.df = pd.read_csv(self.file_path)
        self.df['GAME_DATE'] = pd.to_datetime(self.df['GAME_DATE'])
        
        # Keep everything sorted newest first for easy slicing
        self.df = self.df.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)

        # Derive Opponent Points: PTS - PLUS_MINUS = OPP_PTS
        self.df['OPP_PTS'] = self.df['PTS'] - self.df['PLUS_MINUS']
        
        # Identify the latest REGULAR season (ID starts with '2')
        reg_season_df = self.df[self.df['SEASON_ID'].astype(str).str.startswith('2')]
        if not reg_season_df.empty:
            self.latest_reg_season_id = reg_season_df['SEASON_ID'].max()
            # Run calculations
            self._calculate_season_record()
            self._calculate_last_10()
            self._calculate_splits()
            self._calculate_efficiency_ratings()

    def _calculate_season_record(self):
        """Calculates Win % for the most recent Regular Season."""
        season_df = self.df[self.df['SEASON_ID'] == self.latest_reg_season_id]
        wins = len(season_df[season_df['WL'] == 'W'])
        total = len(season_df)
        self.season_metrics['win_pct'] = wins / total if total > 0 else 0
        self.season_metrics['games_played'] = total

    def _calculate_last_10(self):
        """Calculates stats for the last 10 Regular Season games."""
        reg_df = self.df[self.df['SEASON_ID'].astype(str).str.startswith('2')].head(10)
        wins = len(reg_df[reg_df['WL'] == 'W'])
        self.last_10_stats['win_pct'] = wins / len(reg_df) if not reg_df.empty else 0
        self.last_10_stats['avg_pts'] = reg_df['PTS'].mean()
        self.last_10_stats['avg_opp_pts'] = reg_df['OPP_PTS'].mean()

    def _calculate_splits(self):
        """Calculates Home vs Away win percentages."""
        reg_df = self.df[self.df['SEASON_ID'] == self.latest_reg_season_id]
        home_df = reg_df[~reg_df['MATCHUP'].str.contains('@')]
        away_df = reg_df[reg_df['MATCHUP'].str.contains('@')]
        
        def get_pct(df):
            if df.empty: return 0
            return len(df[df['WL'] == 'W']) / len(df)

        self.splits['home_win_pct'] = get_pct(home_df)
        self.splits['away_win_pct'] = get_pct(away_df)

    def _calculate_efficiency_ratings(self):
        """Calculates proxy Offensive and Defensive ratings."""
        season_df = self.df[self.df['SEASON_ID'] == self.latest_reg_season_id]
        if not season_df.empty:
            self.season_metrics['off_rating'] = season_df['PTS'].mean()
            self.season_metrics['def_rating'] = season_df['OPP_PTS'].mean()
            self.season_metrics['net_rating'] = self.season_metrics['off_rating'] - self.season_metrics['def_rating']

    def __repr__(self):
        return f"<Team {self.abbreviation} | Win%: {self.season_metrics.get('win_pct', 0):.2f}>"