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
    def __init__(self, home_team, away_team, date, game_type=GameType.REGULAR_SEASON, is_neutral=False, h2h_limit=5, final_score=None):
        self.home_team = home_team
        self.away_team = away_team
        self.date = date
        self.game_type = game_type
        self.is_neutral = is_neutral
        self.h2h_limit = h2h_limit
        self.final_score = final_score # Format: {"home": 110, "away": 105}
        
        # Path to the ML model in the same folder
        self.model_path = os.path.join(os.path.dirname(__file__), 'nba_model.pkl')
        self.ml_model = self._load_model()
        
        # Situational Attributes
        self.home_rest = self.home_team.get_rest_days(self.date)
        self.away_rest = self.away_team.get_rest_days(self.date)
        self.h2h_history = self._get_h2h_history()
        self.home_hot_streak = self._check_recent_streak(self.home_team)
        self.away_hot_streak = self._check_recent_streak(self.away_team)

        # AI Client setup
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
        # If the game is already finished, probability is 100% for the actual winner
        if self.final_score:
            return 1.0 if self.final_score['home'] > self.final_score['away'] else 0.0

        if self.ml_model:
            try:
                features = pd.DataFrame([{
                    'rest_days': self.home_rest,
                    'season_net_rtg': self.home_team.season_metrics.get('net_rating', 0),
                    'recent_net_rtg': self.home_team.last_10_stats.get('net_rating', 0),
                    'h2h_win_pct': self.h2h_history,
                    'is_playoff': 1 if self.game_type == GameType.PLAYOFF else 0
                }])
                # Returns probability of Home Team winning
                return self.ml_model.predict_proba(features)[0][1] 
            except Exception:
                pass

        # Manual Fallback Logic if ML fails
        def normalize(val): return (val + 15) / 30 
        h_net = self.home_team.season_metrics.get('net_rating', 0)
        a_net = self.away_team.season_metrics.get('net_rating', 0)
        
        h_score = (normalize(h_net) * 0.35) + (self.h2h_history * 0.15)
        a_score = (normalize(a_net) * 0.35) + ((1 - self.h2h_history) * 0.15)
        return h_score / (h_score + a_score)

    def get_ai_explanation(self, prob, winner_abr):
        confidence = f"{prob if prob > 0.5 else (1 - prob):.1%}"
        
        if self.final_score:
            status_summary = (
                f"--- GAME RECAP ---\n"
                f"Result: {self.away_team.abbreviation} {self.final_score['away']} - "
                f"{self.home_team.abbreviation} {self.final_score['home']}\n"
                f"Status: COMPLETED\n"
                f"-------------------"
            )
        else:
            status_summary = (
                f"--- STATISTICAL MODEL SUMMARY ---\n"
                f"Result: {winner_abr} wins\n"
                f"Confidence: {confidence}\n"
                f"Model Type: {'Random Forest ML' if self.ml_model else 'Weighted Manual'}\n"
                f"----------------------------------"
            )

        if not self.client:
            return f"{status_summary}\nHome Rest: {self.home_rest}d | Away Rest: {self.away_rest}d | H2H: {self.h2h_history:.1%}"

        # Dynamic prompt based on whether the game is past or future
        context = "completed game result" if self.final_score else "upcoming prediction"
        stats_data = {
            "matchup": f"{self.away_team.abbreviation} vs {self.home_team.abbreviation}",
            "winner": winner_abr,
            "metrics": {
                "h2h_pct": f"{self.h2h_history:.1%}",
                "home_rest": self.home_rest,
                "away_rest": self.away_rest
            }
        }

        prompt = f"As an NBA expert analyst, explain the {context} for {stats_data}. Keep it concise and insightful."

        try:
            response = self.client.models.generate_content(model="gemini-1.5-pro", contents=prompt)
            return f"{status_summary}\n\n{response.text.strip()}"
        except Exception:
            return status_summary

    def predict(self):
        """
        The main execution method for Epic 1.
        Calculates the outcome, identifies the winner, and returns the narrative.
        """
        prob = self.calculate_prediction_score()
        
        # Determine winner based on actual score (past) or probability (future)
        if self.final_score:
            home_won = self.final_score['home'] > self.final_score['away']
            winner_abr = self.home_team.abbreviation if home_won else self.away_team.abbreviation
        else:
            winner_abr = self.home_team.abbreviation if prob > 0.5 else self.away_team.abbreviation
        
        # Fetch the narrative
        narrative = self.get_ai_explanation(prob, winner_abr)
        
        return {
            "winner": winner_abr,
            "probability": prob,
            "narrative": narrative,
            "is_past": self.final_score is not None
        }