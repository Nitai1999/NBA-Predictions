import pandas as pd
import os
from nba_api.stats.endpoints import leaguegamelog # Switched for better data coverage
from nba_api.stats.static import teams as nba_teams

class Team:
    def __init__(self, abbreviation):
        self.abbreviation = abbreviation
        self.team_id = abbreviation 
        self.file_path = os.path.join('data', 'raw', f"{self.abbreviation}.csv")
        self.df = None
        
        # Default stats to prevent UI crashes
        self.last_10_stats = {'win_pct': 0, 'avg_pts': 0, 'avg_opp_pts': 0}
        self.season_metrics = {'win_pct': 0, 'games_played': 0, 'off_rating': 0, 'def_rating': 0, 'net_rating': 0}
        self.splits = {'home_win_pct': 0, 'away_win_pct': 0}
        
        if self.data_exists():
            self.load_and_process()

    def data_exists(self):
        return os.path.exists(self.file_path)

    def fetch_stats(self):
        """Fetches stats using LeagueGameLog which reliably includes PLUS_MINUS."""
        try:
            nba_team_search = [t for t in nba_teams.get_teams() if t['abbreviation'] == self.abbreviation]
            if not nba_team_search:
                return False
            
            real_id = nba_team_search[0]['id']

            # Using LeagueGameLog filtered for this team - this contains PLUS_MINUS
            log_request = leaguegamelog.LeagueGameLog(
                team_id_nullable=real_id, 
                season='2025-26', 
                player_or_team_abbreviation='T'
            )
            gamelog = log_request.get_data_frames()[0]

            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            gamelog.to_csv(self.file_path, index=False)
            
            self.load_and_process()
            return True
        except Exception as e:
            # This will now give you a more specific error if the API blocks you
            print(f"Error fetching {self.abbreviation}: {e}")
            return False

    def load_and_process(self):
        if not self.data_exists():
            return

        self.df = pd.read_csv(self.file_path)
        if self.df.empty:
            return

        # FIX: Added format='mixed' to silence the UserWarning
        self.df['GAME_DATE'] = pd.to_datetime(self.df['GAME_DATE'], format='mixed', errors='coerce')
        self.df = self.df.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)

        # Check if PLUS_MINUS exists before calculating to avoid KeyError
        if 'PLUS_MINUS' in self.df.columns:
            self.df['OPP_PTS'] = self.df['PTS'] - self.df['PLUS_MINUS']
        else:
            # Fallback logic: if it's missing, we just treat OPP_PTS as unknown or 0
            self.df['OPP_PTS'] = 0
        
        reg_season_df = self.df[self.df['SEASON_ID'].astype(str).str.startswith('2')]
        
        if not reg_season_df.empty:
            self.latest_reg_season_id = reg_season_df['SEASON_ID'].max()
            self._calculate_season_record()
            self._calculate_last_10()
            self._calculate_splits()
            self._calculate_efficiency_ratings()

    def _calculate_season_record(self):
        season_df = self.df[self.df['SEASON_ID'] == self.latest_reg_season_id]
        total = len(season_df)
        wins = len(season_df[season_df['WL'] == 'W'])
        self.season_metrics['win_pct'] = wins / total if total > 0 else 0
        self.season_metrics['games_played'] = total

    def _calculate_last_10(self):
        reg_df = self.df[self.df['SEASON_ID'].astype(str).str.startswith('2')].head(10)
        if not reg_df.empty:
            wins = len(reg_df[reg_df['WL'] == 'W'])
            self.last_10_stats['win_pct'] = wins / len(reg_df)
            self.last_10_stats['avg_pts'] = reg_df['PTS'].mean()
            self.last_10_stats['avg_opp_pts'] = reg_df['OPP_PTS'].mean()

    def _calculate_splits(self):
        reg_df = self.df[self.df['SEASON_ID'] == self.latest_reg_season_id]
        home_df = reg_df[~reg_df['MATCHUP'].str.contains('@')]
        away_df = reg_df[reg_df['MATCHUP'].str.contains('@')]
        
        self.splits['home_win_pct'] = len(home_df[home_df['WL'] == 'W']) / len(home_df) if not home_df.empty else 0
        self.splits['away_win_pct'] = len(away_df[away_df['WL'] == 'W']) / len(away_df) if not away_df.empty else 0

    def _calculate_efficiency_ratings(self):
        season_df = self.df[self.df['SEASON_ID'] == self.latest_reg_season_id]
        if not season_df.empty:
            self.season_metrics['off_rating'] = season_df['PTS'].mean()
            self.season_metrics['def_rating'] = season_df['OPP_PTS'].mean()
            self.season_metrics['net_rating'] = self.season_metrics['off_rating'] - self.season_metrics['def_rating']