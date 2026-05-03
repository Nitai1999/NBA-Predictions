import os, joblib
import pandas as pd
from google import genai

class Game:
    def __init__(self, home_team, away_team, date, final_score=None):
        self.home_team = home_team
        self.away_team = away_team
        self.date = date
        self.final_score = final_score
        
        self.model_path = os.path.join(os.path.dirname(__file__), 'nba_model.pkl')
        self.ml_model = self._load_model()
        self.home_rest = self.home_team.get_rest_days(self.date)
        
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None

    def _load_model(self):
        if os.path.exists(self.model_path):
            try: return joblib.load(self.model_path)
            except: return None
        return None

    def calculate_prediction_score(self, missing_home=None, missing_away=None):
        if self.final_score:
            return 1.0 if self.final_score['home'] > self.final_score['away'] else 0.0

        base_prob = 0.5
        if self.ml_model:
            try:
                features = pd.DataFrame([{
                    'rest_days': self.home_rest,
                    'season_net_rtg': self.home_team.season_metrics.get('net_rating', 0),
                    'recent_net_rtg': 0,
                    'h2h_win_pct': 0.5,
                    'is_playoff': 1
                }])
                base_prob = self.ml_model.predict_proba(features)[0][1]
            except: pass

        h_full = sum(p.wif for p in self.home_team.roster)
        a_full = sum(p.wif for p in self.away_team.roster)
        h_miss = sum(p.wif for p in self.home_team.roster if p.name in (missing_home or []))
        a_miss = sum(p.wif for p in self.away_team.roster if p.name in (missing_away or []))
        
        h_ratio = (h_full - h_miss) / h_full if h_full > 0 else 1
        a_ratio = (a_full - a_miss) / a_full if a_full > 0 else 1
        
        return max(0.01, min(0.99, base_prob * (h_ratio / a_ratio)))

    def get_ai_explanation(self, prob, winner_abr, missing_home, missing_away):
        confidence = f"{prob if prob > 0.5 else (1 - prob):.1%}"
        status = "COMPLETED" if self.final_score else "PREDICTION"
        
        injury_txt = ""
        if missing_home or missing_away:
            injury_txt = f"\n\n--- INJURY IMPACT ---\nHome Missing: {missing_home}\nAway Missing: {missing_away}"
            
        summary = f"--- {status} ---\nResult: {winner_abr} wins\nConfidence: {confidence}\nModel: RF ML + WIF Adjustment{injury_txt}"

        if not self.client: return summary

        prompt = f"Explain the {status} for {self.away_team.abbreviation} @ {self.home_team.abbreviation}. Favored: {winner_abr}. Injuries: Home {missing_home}, Away {missing_away}. Keep it professional."
        try:
            response = self.client.models.generate_content(model="gemini-1.5-pro", contents=prompt)
            return f"{summary}\n\n{response.text.strip()}"
        except: return summary

    def predict(self, missing_home=None, missing_away=None):
        """Unified prediction logic for both past and future games[cite: 14]."""
        if self.final_score:
            winner = self.home_team.abbreviation if self.final_score['home'] > self.final_score['away'] else self.away_team.abbreviation
            return {"winner": winner, "probability": 1.0 if winner == self.home_team.abbreviation else 0.0, "narrative": "Game Finished. Result recorded.", "is_past": True}
            
        prob = self.calculate_prediction_score(missing_home, missing_away)
        winner = self.home_team.abbreviation if prob > 0.5 else self.away_team.abbreviation
        return {"winner": winner, "probability": prob, "narrative": self.get_ai_explanation(prob, winner, missing_home, missing_away), "is_past": False}