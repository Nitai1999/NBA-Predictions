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
        
        # Enhanced stat dictionaries[cite: 4]
        self.last_10_stats = {'win_pct': 0, 'net_rating': 0, 'avg_pace': 0}
        self.season_metrics = {'win_pct': 0, 'off_rating': 0, 'def_rating': 0, 'pace': 0, 'net_rating': 0}
        self.splits = {'home_win_pct': 0, 'away_win_pct': 0}
        
        if self.data_exists():
            self.load_and_process()
            self.roster = self._fetch_roster()
        else:
            self.roster = []

    def data_exists(self):
        return os.path.exists(self.file_path)

    def fetch_stats(self):
        """FULL VERSION: Includes API rate limit protection and filtering[cite: 4]."""
        try:
            target_team = [t for t in nba_teams.get_teams() if t['abbreviation'] == self.abbreviation]
            if not target_team: return False
            
            real_id = target_team[0]['id']
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            time.sleep(0.6) 

            game_finder = leaguegamefinder.LeagueGameFinder(team_id_nullable=real_id)
            new_games_df = game_finder.get_data_frames()[0]
            new_games_df['GAME_DATE'] = pd.to_datetime(new_games_df['GAME_DATE'])
            new_games_df = new_games_df[new_games_df['GAME_DATE'] >= '2021-01-01']
            new_games_df = new_games_df[new_games_df['SEASON_ID'].astype(str).str.startswith(('2', '4'))]

            new_games_df.to_csv(self.file_path, index=False)
            self.load_and_process()
            return True
        except Exception as e:
            print(f"Error fetching {self.abbreviation}: {e}")
            return False

    def load_and_process(self):
        if not self.data_exists(): return
        self.df = pd.read_csv(self.file_path)
        if self.df.empty: return

        self.df['GAME_DATE'] = pd.to_datetime(self.df['GAME_DATE'], format='mixed')
        self.df = self.df.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)

        # Advanced Efficiency Logic (POSS, OFF_RTG, PACE)[cite: 4]
        if all(col in self.df.columns for col in ['FGA', 'FTA', 'TOV', 'OREB']):
            self.df['POSS'] = self.df['FGA'] + (0.44 * self.df['FTA']) + self.df['TOV'] - self.df['OREB']
            self.df['OFF_RTG'] = (self.df['PTS'] / self.df['POSS']) * 100
            self.df['DEF_RTG'] = ((self.df['PTS'] - self.df['PLUS_MINUS']) / self.df['POSS']) * 100
            self.df['NET_RTG'] = self.df['OFF_RTG'] - self.df['DEF_RTG']
            self.df['PACE'] = (self.df['POSS'] / (self.df['MIN'] / 5)) * 48
        
        reg_df = self.df[self.df['SEASON_ID'].astype(str).str.startswith('2')]
        if not reg_df.empty:
            self.latest_reg_season_id = reg_df['SEASON_ID'].max()
            self._calculate_advanced_metrics(reg_df)

    def _calculate_advanced_metrics(self, reg_df):
        season_df = reg_df[reg_df['SEASON_ID'] == self.latest_reg_season_id]
        if not season_df.empty:
            self.season_metrics['win_pct'] = len(season_df[season_df['WL'] == 'W']) / len(season_df)
            self.season_metrics['off_rating'] = season_df['OFF_RTG'].mean()
            self.season_metrics['def_rating'] = season_df['DEF_RTG'].mean()
            self.season_metrics['net_rating'] = season_df['NET_RTG'].mean()
            self.season_metrics['pace'] = season_df['PACE'].mean()

        last_10 = season_df.head(10)
        if not last_10.empty:
            self.last_10_stats['win_pct'] = len(last_10[last_10['WL'] == 'W']) / len(last_10)
            self.last_10_stats['net_rating'] = last_10['NET_RTG'].mean()
            self.last_10_stats['avg_pace'] = last_10['PACE'].mean()

        home = season_df[~season_df['MATCHUP'].str.contains('@')]
        away = season_df[season_df['MATCHUP'].str.contains('@')]
        self.splits['home_win_pct'] = len(home[home['WL'] == 'W']) / len(home) if not home.empty else 0.5
        self.splits['away_win_pct'] = len(away[away['WL'] == 'W']) / len(away) if not away.empty else 0.5

    def get_rest_days(self, target_date):
        target_dt = pd.to_datetime(target_date)
        past_games = self.df[self.df['GAME_DATE'] < target_dt]
        if past_games.empty: return 3 
        last_game_date = past_games['GAME_DATE'].max()
        return min((target_dt - last_game_date).days, 7)

    def _fetch_roster(self):
        """Epic 2: Live fetching of top 7 players by MPG."""
        try:
            team_data = [t for t in nba_teams.get_teams() if t['abbreviation'] == self.abbreviation]
            if not team_data: return []
            team_id = team_data[0]['id']
            dash = teamplayerdashboard.TeamPlayerDashboard(team_id=team_id)
            player_stats = dash.get_data_frames()[1]
            top_7 = player_stats.sort_values(by='MIN', ascending=False).head(7)
            return [Player(row['PLAYER_NAME'], row['PLAYER_ID'], row) for _, row in top_7.iterrows()]
        except Exception:
            return []

    def get_suggested_injuries(self):
        """Epic 2: Automation to flag players who missed the last game."""
        try:
            last_game_id = self.df.iloc[0]['GAME_ID']
            box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=last_game_id)
            player_stats = box.get_data_frames()[0]
            suggested = []
            for p in self.roster:
                p_row = player_stats[player_stats['PLAYER_ID'] == p.id]
                if p_row.empty or p_row.iloc[0]['MIN'] is None:
                    suggested.append(p.name)
            return suggested
        except Exception:
            return []