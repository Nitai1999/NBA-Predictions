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
        """
        Initializes the Game instance, pulls situational data (rest/streaks), 
        and attempts to load the trained ML model.
        """
        self.home_team = home_team
        self.away_team = away_team
        self.date = date
        self.game_type = game_type
        self.is_neutral = is_neutral
        self.h2h_limit = h2h_limit
        
        # Determine paths relative to this file inside src/models/[cite: 4]
        self.model_path = os.path.join(os.path.dirname(__file__), 'nba_model.pkl')
        self.ml_model = self._load_model()
        
        # Calculate situational factors for the model
        self.home_rest = self.home_team.get_rest_days(self.date)[cite: 8]
        self.away_rest = self.away_team.get_rest_days(self.date)[cite: 8]
        
        # Performance history[cite: 5, 7]
        self.h2h_history = self._get_h2h_history()[cite: 5]
        self.home_hot_streak = self._check_recent_streak(self.home_team)[cite: 5]
        self.away_hot_streak = self._check_recent_streak(self.away_team)[cite: 5]

        # AI Narrative Setup[cite: 5]
        api_key = os.getenv("GEMINI_API_KEY")[cite: 5]
        self.client = genai.Client(api_key=api_key) if api_key else None[cite: 5]

    def _load_model(self):
        """Loads the serialized Random Forest model if it exists in the models directory."""
        if os.path.exists(self.model_path):
            try:
                return joblib.load(self.model_path)
            except Exception:
                return None
        return None

    def _get_h2h_history(self):
        """Calculates win percentage of the home team against the away team in recent meetings."""
        mask = self.home_team.df['MATCHUP'].str.contains(self.away_team.abbreviation)[cite: 5]
        history = self.home_team.df[mask].head(self.h2h_limit)[cite: 5]
        if history.empty: return 0.5[cite: 5]
        wins = len(history[history['WL'] == 'W'])[cite: 5]
        return wins / len(history)[cite: 5]

    def _check_recent_streak(self, team):
        """Checks if a team is currently on a 5-game winning streak."""
        last_5 = team.df.head(5)[cite: 5]
        if len(last_5) < 5: return False[cite: 5]
        return (last_5['WL'] == 'W').all()[cite: 5]

    def calculate_prediction_score(self):
        """
        Calculates the win probability. Prioritizes the ML model's 'Feature Importance' 
        weights, falling back to manual weights if the model is missing.
        """
        # 1. ATTEMPT MACHINE LEARNING PREDICTION[cite: 7]
        if self.ml_model:
            try:
                # Features must exactly match the list in train_model.py[cite: 7]
                features = pd.DataFrame([{
                    'rest_days': self.home_rest,
                    'season_net_rtg': self.home_team.season_metrics.get('net_rating', 0),
                    'recent_net_rtg': self.home_team.last_10_stats.get('net_rating', 0),
                    'h2h_win_pct': self.h2h_history,
                    'is_playoff': 1 if self.game_type == GameType.PLAYOFF else 0
                }])
                
                # predict_proba returns [[prob_loss, prob_win]][cite: 7]
                return self.ml_model.predict_proba(features)[0][1] 
            except Exception:
                pass # Use manual fallback if model structure has changed

        # 2. MANUAL FALLBACK LOGIC[cite: 7]
        def normalize(val): return (val + 15) / 30 
        
        h_net = self.home_team.season_metrics.get('net_rating', 0)
        a_net = self.away_team.season_metrics.get('net_rating', 0)
        
        # Manual distribution: Efficiency (35%), Recent Form (30%), H2H (15%), Splits (20%)
        h_score = (normalize(h_net) * 0.35) + \
                  (normalize(self.home_team.last_10_stats.get('net_rating', 0)) * 0.30) + \
                  (self.h2h_history * 0.15) + \
                  (self.home_team.splits.get('home_win_pct', 0) * 0.20)
        
        a_score = (normalize(a_net) * 0.35) + \
                  (normalize(self.away_team.last_10_stats.get('net_rating', 0)) * 0.30) + \
                  ((1 - self.h2h_history) * 0.15) + \
                  (self.away_team.splits.get('away_win_pct', 0) * 0.20)

        # Fatigue Adjustment[cite: 7]
        if self.home_rest <= 1: h_score -= 0.04
        if self.away_rest <= 1: a_score -= 0.04

        return h_score / (h_score + a_score)

    def get_ai_explanation(self, prob, winner_abr):
        """Uses Gemini 1.5 Pro to provide a narrative analysis based on the stats."""
        confidence = f"{prob if prob > 0.5 else (1 - prob):.1%}"[cite: 5]
        
        fallback_msg = (
            f"--- STATISTICAL MODEL SUMMARY ---\n"
            f"Result: {winner_abr} wins\n"
            f"Confidence: {confidence}\n"
            f"Model Type: {'Random Forest ML' if self.ml_model else 'Weighted Manual'}\n"
            f"----------------------------------\n"
            f"Home Rest: {self.home_rest} days | Away Rest: {self.away_rest} days\n"
            f"H2H Win%: {self.h2h_history:.1%}\n"
            f"----------------------------------"
        )[cite: 5]

        if not self.client: return fallback_msg[cite: 5]

        stats_brief = {
            "matchup": f"{self.away_team.abbreviation} vs {self.home_team.abbreviation}",[cite: 5]
            "prediction": f"{winner_abr} wins",[cite: 5]
            "confidence": confidence,[cite: 5]
            "fatigue_factor": {"home_rest": self.home_rest, "away_rest": self.away_rest},
            "recent_streaks": {"home_hot": self.home_hot_streak, "away_hot": self.away_hot_streak}[cite: 5]
        }

        prompt = f"As an NBA expert, explain why {winner_abr} is favored: {stats_brief}. Highlight if rest or H2H history played a role."[cite: 5]

        try:
            response = self.client.models.generate_content(model="gemini-1.5-pro", contents=prompt)[cite: 5]
            return response.text.strip()[cite: 5]
        except Exception:
            return fallback_msg[cite: 5]

    def predict(self):
        """CLI method for generating and printing a full prediction report."""
        prob = self.calculate_prediction_score()[cite: 5]
        winner_abr = self.home_team.abbreviation if prob > 0.5 else self.away_team.abbreviation[cite: 5]
        ai_narrative = self.get_ai_explanation(prob, winner_abr)[cite: 5]
        
        print(f"\n" + "="*60)
        print(f"   NBA PREDICTION: {self.away_team.abbreviation} @ {self.home_team.abbreviation}")
        print(f"   Model Confidence: {prob:.1%}")
        print(f"="*60)
        print(f"\n{ai_narrative}\n")
        
        return winner_abr[cite: 5]