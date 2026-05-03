import pandas as pd
import os
import time
from nba_api.stats.endpoints import leaguegamefinder, teamplayerdashboard, boxscoretraditionalv2
from nba_api.stats.static import teams as nba_teams
from .player import Player

class Team:
    def __init__(self, abbreviation):
        self.abbreviation = abbreviation
        self.team_id = abbreviation 
        self.file_path = os.path.join('data', 'raw', f"{self.abbreviation}_games.csv")
        self.df = None
        
        self.last_10_stats = {'win_pct': 0, 'net_rating': 0, 'avg_pace': 0}
        self.season_metrics = {'win_pct': 0, 'off_rating': 0, 'def_rating': 0, 'pace': 0, 'net_rating': 0}
        
        if self.data_exists():
            self.load_and_process()
            self.roster = self._fetch_roster()
        else:
            self.roster = []

    def data_exists(self):
        return os.path.exists(self.file_path)

    def fetch_stats(self):
        try:
            target_team = [t for t in nba_teams.get_teams() if t['abbreviation'] == self.abbreviation]
            if not target_team: return False
            real_id = target_team[0]['id']
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            time.sleep(0.6) 

            game_finder = leaguegamefinder.LeagueGameFinder(team_id_nullable=real_id)
            new_games_df = game_finder.get_data_frames()[0]
            new_games_df.to_csv(self.file_path, index=False)
            self.load_and_process()
            return True
        except: return False

    def load_and_process(self):
        if not self.data_exists(): return
        self.df = pd.read_csv(self.file_path)
        if self.df.empty: return
        self.df['GAME_DATE'] = pd.to_datetime(self.df['GAME_DATE'], format='mixed')
        self.df = self.df.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)

        if all(col in self.df.columns for col in ['FGA', 'FTA', 'TOV', 'OREB']):
            self.df['POSS'] = self.df['FGA'] + (0.44 * self.df['FTA']) + self.df['TOV'] - self.df['OREB']
            self.df['OFF_RTG'] = (self.df['PTS'] / self.df['POSS']) * 100
            self.df['DEF_RTG'] = ((self.df['PTS'] - self.df['PLUS_MINUS']) / self.df['POSS']) * 100
            self.df['NET_RTG'] = self.df['OFF_RTG'] - self.df['DEF_RTG']
            self.df['PACE'] = (self.df['POSS'] / (self.df['MIN'] / 5)) * 48
        
        reg_df = self.df[self.df['SEASON_ID'].astype(str).str.startswith('2')]
        if not reg_df.empty:
            self.latest_reg_season_id = reg_df['SEASON_ID'].max()
            season_df = reg_df[reg_df['SEASON_ID'] == self.latest_reg_season_id]
            self.season_metrics['win_pct'] = (season_df['WL'] == 'W').mean()
            self.season_metrics['net_rating'] = season_df['NET_RTG'].mean()

    def get_rest_days(self, target_date):
        past = self.df[self.df['GAME_DATE'] < pd.to_datetime(target_date)]
        if past.empty: return 3
        return min((pd.to_datetime(target_date) - past['GAME_DATE'].max()).days, 7)

    def get_score_from_csv(self, game_date):
        """Hard check for scores in local data[cite: 16]."""
        if self.df is None: return None
        try:
            target_dt_str = pd.to_datetime(game_date).strftime('%Y-%m-%d')
            game_row = self.df[self.df['GAME_DATE'].dt.strftime('%Y-%m-%d') == target_dt_str]
            if not game_row.empty:
                row = game_row.iloc[0]
                is_home = 'vs.' in row['MATCHUP']
                pts = int(row['PTS'])
                opp_pts = int(pts - row['PLUS_MINUS'])
                return {"home": pts, "away": opp_pts} if is_home else {"home": opp_pts, "away": pts}
        except: pass
        return None

    def _fetch_roster(self):
        try:
            team_id = [t for t in nba_teams.get_teams() if t['abbreviation'] == self.abbreviation][0]['id']
            dash = teamplayerdashboard.TeamPlayerDashboard(team_id=team_id)
            player_stats = dash.get_data_frames()[1]
            top_12 = player_stats.sort_values(by='MIN', ascending=False).head(12)
            return [Player(row['PLAYER_NAME'], row['PLAYER_ID'], row) for _, row in top_12.iterrows()]
        except: return []

    def get_suggested_injuries(self):
        try:
            last_game_id = self.df.iloc[0]['GAME_ID']
            box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=last_game_id)
            p_stats = box.get_data_frames()[0]
            return [p.name for p in self.roster if p_stats[p_stats['PLAYER_ID'] == p.id].empty]
        except: return []