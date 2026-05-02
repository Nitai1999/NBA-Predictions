import pandas as pd
import os

class Team:
    def __init__(self, abbreviation):
        """
        Initializes the Team object and calculates core metrics.
        :param abbreviation: 3-letter team code (e.g., 'BOS')
        """
        self.abbreviation = abbreviation
        self.file_path = os.path.join('data', 'raw', f"{self.abbreviation}_games.csv")
        self.df = None
        
        # Performance Fields
        self.last_10_stats = {}
        self.season_metrics = {}
        self.splits = {}
        
        self.load_and_process()

    def load_and_process(self):
        """Loads the CSV and prepares necessary columns for calculation."""
        if not os.path.exists(self.file_path):
            print(f"Error: No data found for {self.abbreviation}")
            return

        self.df = pd.read_csv(self.file_path)
        self.df['GAME_DATE'] = pd.to_datetime(self.df['GAME_DATE'])
        
        # Keep everything sorted newest first for easy slicing
        self.df = self.df.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)

        # Derive Opponent Points: PTS - PLUS_MINUS = OPP_PTS
        self.df['OPP_PTS'] = self.df['PTS'] - self.df['PLUS_MINUS']
        
        # Identify the latest REGULAR season (ID starts with '2')
        # This prevents the logic from accidentally using Playoff data ('4') for season stats
        reg_season_df = self.df[self.df['SEASON_ID'].astype(str).str.startswith('2')]
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
        """
        Calculates stats for the last 10 Regular Season games.
        This will look across seasons if the current one has fewer than 10 games.
        """
        reg_df = self.df[self.df['SEASON_ID'].astype(str).str.startswith('2')].head(10)
        
        wins = len(reg_df[reg_df['WL'] == 'W'])
        self.last_10_stats['win_pct'] = wins / len(reg_df) if not reg_df.empty else 0
        self.last_10_stats['avg_pts'] = reg_df['PTS'].mean()
        self.last_10_stats['avg_opp_pts'] = reg_df['OPP_PTS'].mean()

    def _calculate_splits(self):
        """Calculates Home vs Away win percentages (Regular Season only)."""
        reg_df = self.df[self.df['SEASON_ID'] == self.latest_reg_season_id]
        
        home_df = reg_df[~reg_df['MATCHUP'].str.contains('@')]
        away_df = reg_df[reg_df['MATCHUP'].str.contains('@')]
        
        def get_pct(df):
            if df.empty: return 0
            return len(df[df['WL'] == 'W']) / len(df)

        self.splits['home_win_pct'] = get_pct(home_df)
        self.splits['away_win_pct'] = get_pct(away_df)

    def _calculate_efficiency_ratings(self):
        """Calculates proxy Offensive and Defensive ratings for the latest Regular Season."""
        season_df = self.df[self.df['SEASON_ID'] == self.latest_reg_season_id]
        
        if not season_df.empty:
            self.season_metrics['off_rating'] = season_df['PTS'].mean()
            self.season_metrics['def_rating'] = season_df['OPP_PTS'].mean()
            self.season_metrics['net_rating'] = self.season_metrics['off_rating'] - self.season_metrics['def_rating']

    def __repr__(self):
        return f"<Team {self.abbreviation} | Season {self.latest_reg_season_id} | Win%: {self.season_metrics.get('win_pct', 0):.2f}>"

if __name__ == "__main__":
    # Test with the Celtics data
    team = Team("BOS")
    print(f"--- {team.abbreviation} Stats (Season {team.latest_reg_season_id}) ---")
    print(f"Overall Win %: {team.season_metrics['win_pct']:.3f}")
    print(f"Last 10 Win %: {team.last_10_stats['win_pct']:.3f}")
    print(f"Home Split: {team.splits['home_win_pct']:.3f} | Away Split: {team.splits['away_win_pct']:.3f}")
    print(f"Offensive Rating (Avg Pts): {team.season_metrics['off_rating']:.1f}")
    print(f"Defensive Rating (Avg Opp Pts): {team.season_metrics['def_rating']:.1f}")