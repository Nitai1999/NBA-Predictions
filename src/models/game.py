import os
import joblib
import pandas as pd
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
        
        self.model_path = os.path.join(os.path.dirname(__file__), 'nba_model.pkl')
        self.ml_model = self._load_model()
        
        self.home_rest = self.home_team.get_rest_days(self.date)
        self.away_rest = self.away_team.get_rest_days(self.date)
        
        self.h2h_history = self._get_h2h_history()
        self.home_hot_streak = self._check_recent_streak(self.home_team)
        self.away_hot_streak = self._check_recent_streak(self.away_team)

        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                return joblib.load(self.model_path)
            except Exception:
                return None
        return None

    def _get_h2h_history(self):
        mask = self.home_team.df['MATCHUP'].str.contains(self.away_team.abbreviation)
        history = self.home_team.df[mask].head(self.h2h_limit)
        if history.empty: return 0.5
        wins = len(history[history['WL'] == 'W'])
        return wins / len(history)

    def _check_recent_streak(self, team):
        last_5 = team.df.head(5)
        if len(last_5) < 5: return False
        return (last_5['WL'] == 'W').all()

    def calculate_prediction_score(self):
        if self.ml_model:
            try:
                features = pd.DataFrame([{
                    'rest_days': self.home_rest,
                    'season_net_rtg': self.home_team.season_metrics.get('net_rating', 0),
                    'recent_net_rtg': self.home_team.last_10_stats.get('net_rating', 0),
                    'h2h_win_pct': self.h2h_history,
                    'is_playoff': 1 if self.game_type == GameType.PLAYOFF else 0
                }])
                return self.ml_model.predict_proba(features)[0][1] 
            except Exception:
                pass

        def normalize(val): return (val + 15) / 30 
        h_net = self.home_team.season_metrics.get('net_rating', 0)
        a_net = self.away_team.season_metrics.get('net_rating', 0)
        
        h_score = (normalize(h_net) * 0.35) + \
                  (normalize(self.home_team.last_10_stats.get('net_rating', 0)) * 0.30) + \
                  (self.h2h_history * 0.15) + \
                  (self.home_team.splits.get('home_win_pct', 0) * 0.20)
        
        a_score = (normalize(a_net) * 0.35) + \
                  (normalize(self.away_team.last_10_stats.get('net_rating', 0)) * 0.30) + \
                  ((1 - self.h2h_history) * 0.15) + \
                  (self.away_team.splits.get('away_win_pct', 0) * 0.20)

        if self.home_rest <= 1: h_score -= 0.04
        if self.away_rest <= 1: a_score -= 0.04

        return h_score / (h_score + a_score)

    def get_ai_explanation(self, prob, winner_abr):
        confidence = f"{prob if prob > 0.5 else (1 - prob):.1%}"
        
        fallback_msg = (
            f"--- STATISTICAL MODEL SUMMARY ---\n"
            f"Result: {winner_abr} wins\n"
            f"Confidence: {confidence}\n"
            f"Model Type: {'Random Forest ML' if self.ml_model else 'Weighted Manual'}\n"
            f"----------------------------------\n"
            f"Home Rest: {self.home_rest} days | Away Rest: {self.away_rest} days\n"
            f"H2H Win%: {self.h2h_history:.1%}\n"
            f"----------------------------------"
        )

        if not self.client: return fallback_msg

        stats_brief = {
            "matchup": f"{self.away_team.abbreviation} vs {self.home_team.abbreviation}",
            "prediction": f"{winner_abr} wins",
            "confidence": confidence,
            "fatigue_factor": {"home_rest": self.home_rest, "away_rest": self.away_rest},
            "recent_streaks": {"home_hot": self.home_hot_streak, "away_hot": self.away_hot_streak}
        }

        prompt = f"As an NBA expert, explain why {winner_abr} is favored: {stats_brief}. Highlight if rest or H2H history played a role."

        try:
            response = self.client.models.generate_content(model="gemini-1.5-pro", contents=prompt)
            return response.text.strip()
        except Exception:
            return fallback_msg

    def predict(self):
        prob = self.calculate_prediction_score()
        winner_abr = self.home_team.abbreviation if prob > 0.5 else self.away_team.abbreviation
        ai_narrative = self.get_ai_explanation(prob, winner_abr)
        
        print(f"\n" + "="*60)
        print(f"   NBA PREDICTION: {self.away_team.abbreviation} @ {self.home_team.abbreviation}")
        print(f"   Model Confidence: {prob:.1%}")
        print(f"="*60)
        print(f"\n{ai_narrative}\n")
        
        return winner_abr