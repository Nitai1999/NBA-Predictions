import os
from enum import Enum
from google import genai

class GameType(Enum):
    REGULAR_SEASON = 1
    PLAYOFF = 2
    CUP = 3 

class Game:
    def __init__(self, home_team, away_team, date, game_type=GameType.REGULAR_SEASON, is_neutral=False, h2h_limit=5):
        self.home_team = home_team
        self.away_team = away_team
        self.date = date
        self.game_type = game_type
        self.is_neutral = is_neutral
        self.h2h_limit = h2h_limit
        
        # Core Stats
        self.h2h_history = self._get_h2h_history()
        
        # Streak Logic
        self.home_h2h_streak = self._check_h2h_streak(self.home_team, self.away_team)
        self.away_h2h_streak = self._check_h2h_streak(self.away_team, self.home_team)
        self.home_hot_streak = self._check_recent_streak(self.home_team)
        self.away_hot_streak = self._check_recent_streak(self.away_team)
        
        # Initialize Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None

    def _get_h2h_history(self):
        mask = self.home_team.df['MATCHUP'].str.contains(self.away_team.abbreviation)
        history = self.home_team.df[mask].head(self.h2h_limit)
        if history.empty: return 0.5 
        wins = len(history[history['WL'] == 'W'])
        return wins / len(history)

    def _check_h2h_streak(self, team, opponent):
        """Checks if 'team' has won the last 4 games against 'opponent'."""
        mask = team.df['MATCHUP'].str.contains(opponent.abbreviation)
        last_4 = team.df[mask].head(4)
        if len(last_4) < 4: return False
        return (last_4['WL'] == 'W').all()

    def _check_recent_streak(self, team):
        """Checks if a team has won its last 5 games overall."""
        last_5 = team.df.head(5)
        if len(last_5) < 5: return False
        return (last_5['WL'] == 'W').all()

    def _get_playoff_experience(self, team):
        playoff_games = team.df[team.df['SEASON_ID'].astype(str).str.startswith('4')]
        return len(playoff_games)

    def calculate_prediction_score(self):
        # 1. BASE WEIGHTS
        weights = {'season_win_pct': 0.30, 'last_10': 0.25, 'splits': 0.20, 'h2h': 0.15, 'experience': 0.10}
        
        if self.game_type == GameType.PLAYOFF:
            weights = {'last_10': 0.05, 'experience': 0.35, 'h2h': 0.25, 'season_win_pct': 0.15, 'splits': 0.20}
        
        home_perf = self.home_team.splits['home_win_pct'] if not self.is_neutral else (self.home_team.splits['home_win_pct'] + self.home_team.splits['away_win_pct'])/2
        away_perf = self.away_team.splits['away_win_pct'] if not self.is_neutral else (self.away_team.splits['home_win_pct'] + self.away_team.splits['away_win_pct'])/2

        # 2. CALCULATE BASE SCORES
        home_exp = min(self._get_playoff_experience(self.home_team) / 100, 1.0)
        away_exp = min(self._get_playoff_experience(self.away_team) / 100, 1.0)

        home_final = (self.home_team.season_metrics['win_pct'] * weights['season_win_pct']) + \
                     (self.home_team.last_10_stats['win_pct'] * weights['last_10']) + \
                     (home_perf * weights['splits']) + \
                     (self.h2h_history * weights['h2h']) + \
                     (home_exp * weights['experience'])

        away_final = (self.away_team.season_metrics['win_pct'] * weights['season_win_pct']) + \
                     (self.away_team.last_10_stats['win_pct'] * weights['last_10']) + \
                     (away_perf * weights['splits']) + \
                     ((1 - self.h2h_history) * weights['h2h']) + \
                     (away_exp * weights['experience'])

        # 3. APPLY STREAK BONUSES (+0.05 for each active streak)
        if self.home_h2h_streak: home_final += 0.05
        if self.home_hot_streak: home_final += 0.05
        if self.away_h2h_streak: away_final += 0.05
        if self.away_hot_streak: away_final += 0.05

        return home_final / (home_final + away_final)

    def get_ai_explanation(self, prob, winner_abr):
        confidence = f"{prob if prob > 0.5 else (1 - prob):.1%}"
        
        # Streak Dashboard data
        h_streak = "🔥 ACTIVE (5+ WINS)" if self.home_hot_streak else "None"
        a_streak = "🔥 ACTIVE (5+ WINS)" if self.away_hot_streak else "None"
        h2h_s = f"Dominant (4-0)" if (self.home_h2h_streak or self.away_h2h_streak) else "Competitive"

        fallback_msg = (
            f"--- STATISTICAL MODEL SUMMARY ---\n"
            f"Result: {winner_abr} wins\n"
            f"Confidence: {confidence}\n"
            f"----------------------------------\n"
            f"STREAKS: Home: {h_streak} | Away: {a_streak}\n"
            f"H2H Vibe: {h2h_s}\n"
            f"----------------------------------\n"
            f"(AI Narrative Unavailable: Quota Exceeded)"
        )

        if not self.client: return fallback_msg

        stats_brief = {
            "matchup": f"{self.away_team.abbreviation} vs {self.home_team.abbreviation}",
            "prediction": f"{winner_abr} wins",
            "confidence": confidence,
            "streaks": {"home_hot": self.home_hot_streak, "away_hot": self.away_hot_streak, "h2h_streak": (self.home_h2h_streak or self.away_h2h_streak)}
        }

        prompt = f"As an NBA expert, explain why {winner_abr} is favored based on: {stats_brief}. Mention streaks if they exist."

        try:
            response = self.client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            return response.text.strip()
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower(): return fallback_msg
            return f"{fallback_msg}\n[Note: {e}]"

    def predict(self):
        prob = self.calculate_prediction_score()
        winner_abr = self.home_team.abbreviation if prob > 0.5 else self.away_team.abbreviation
        ai_narrative = self.get_ai_explanation(prob, winner_abr)
        
        print(f"\n" + "="*60)
        print(f"   PREDICTION: {self.away_team.abbreviation} @ {self.home_team.abbreviation}")
        print(f"   Context: {self.game_type.name} | H2H Window: {self.h2h_limit}")
        print(f"="*60)
        print(f"\n{ai_narrative}\n")
        
        return winner_abr