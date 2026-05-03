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
        
        # Schedule Analysis
        self.home_rest = self.home_team.get_rest_days(self.date)
        self.away_rest = self.away_team.get_rest_days(self.date)
        
        # Core History
        self.h2h_history = self._get_h2h_history()
        self.home_h2h_streak = self._check_h2h_streak(self.home_team, self.away_team)
        self.away_h2h_streak = self._check_h2h_streak(self.away_team, self.home_team)
        self.home_hot_streak = self._check_recent_streak(self.home_team)
        self.away_hot_streak = self._check_recent_streak(self.away_team)
        
        # Gemini setup
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None

    def _get_h2h_history(self):
        mask = self.home_team.df['MATCHUP'].str.contains(self.away_team.abbreviation)
        history = self.home_team.df[mask].head(self.h2h_limit)
        if history.empty: return 0.5 
        return len(history[history['WL'] == 'W']) / len(history)

    def _check_h2h_streak(self, team, opponent):
        mask = team.df['MATCHUP'].str.contains(opponent.abbreviation)
        last_4 = team.df[mask].head(4)
        return (last_4['WL'] == 'W').all() if len(last_4) >= 4 else False

    def _check_recent_streak(self, team):
        last_5 = team.df.head(5)
        return (last_5['WL'] == 'W').all() if len(last_5) >= 5 else False

    def _get_playoff_experience(self, team):
        return len(team.df[team.df['SEASON_ID'].astype(str).str.startswith('4')])

    def calculate_prediction_score(self):
        weights = {
            'season_efficiency': 0.35, 
            'recent_net_rtg': 0.30,   
            'splits': 0.15,
            'h2h': 0.10,
            'experience': 0.10
        }

        def normalize(val): return (val + 15) / 30

        home_net = self.home_team.season_metrics['off_rating'] - self.home_team.season_metrics['def_rating']
        away_net = self.away_team.season_metrics['off_rating'] - self.away_team.season_metrics['def_rating']

        home_final = (normalize(home_net) * weights['season_efficiency']) + \
                     (normalize(self.home_team.last_10_stats['net_rating']) * weights['recent_net_rtg']) + \
                     (self.home_team.splits['home_win_pct'] * weights['splits']) + \
                     (self.h2h_history * weights['h2h'])

        away_final = (normalize(away_net) * weights['season_efficiency']) + \
                     (normalize(self.away_team.last_10_stats['net_rating']) * weights['recent_net_rtg']) + \
                     (self.away_team.splits['away_win_pct'] * weights['splits']) + \
                     ((1 - self.h2h_history) * weights['h2h'])

        if self.home_rest <= 1: home_final -= 0.04
        if self.away_rest <= 1: away_final -= 0.04
        
        if self.home_hot_streak: home_final += 0.03
        if self.away_hot_streak: away_final += 0.03

        return home_final / (home_final + away_final)

    def get_ai_explanation(self, prob, winner_abr):
        confidence = f"{prob if prob > 0.5 else (1 - prob):.1%}"
        
        h_streak = "🔥 ACTIVE (5+ WINS)" if self.home_hot_streak else "None"
        a_streak = "🔥 ACTIVE (5+ WINS)" if self.away_hot_streak else "None"
        h2h_s = "Dominant (4-0)" if (self.home_h2h_streak or self.away_h2h_streak) else "Competitive"

        fallback_msg = (
            f"--- STATISTICAL MODEL SUMMARY ---\n"
            f"Result: {winner_abr} wins\n"
            f"Confidence: {confidence}\n"
            f"----------------------------------\n"
            f"STREAKS: Home: {h_streak} | Away: {a_streak}\n"
            f"H2H Vibe: {h2h_s}\n"
            f"----------------------------------"
        )

        if not self.client: return fallback_msg

        stats_brief = {
            "matchup": f"{self.away_team.abbreviation} vs {self.home_team.abbreviation}",
            "prediction": f"{winner_abr} wins",
            "confidence": confidence,
            "home_rest": self.home_rest,
            "away_rest": self.away_rest,
            "streaks": {"home_hot": self.home_hot_streak, "away_hot": self.away_hot_streak}
        }

        prompt = f"As an NBA expert, explain why {winner_abr} is favored based on: {stats_brief}. Mention fatigue/rest if one team is on a back-to-back."

        try:
            response = self.client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            return response.text.strip()
        except Exception:
            return fallback_msg

    def predict(self):
        prob = self.calculate_prediction_score()
        winner_abr = self.home_team.abbreviation if prob > 0.5 else self.away_team.abbreviation
        ai_narrative = self.get_ai_explanation(prob, winner_abr)
        return winner_abr