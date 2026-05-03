import os, joblib
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
        self.final_score = final_score
        
        self.model_path = os.path.join(os.path.dirname(__file__), 'nba_model.pkl')
        self.ml_model = self._load_model()
        
        self.home_rest = self.home_team.get_rest_days(self.date)
        self.away_rest = self.away_team.get_rest_days(self.date)
        self.h2h_win_pct = self._get_h2h_history()

        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None

    def _load_model(self):
        if os.path.exists(self.model_path):
            try: return joblib.load(self.model_path)
            except: return None
        return None

    def _get_h2h_history(self):
        mask = self.home_team.df['MATCHUP'].str.contains(self.away_team.abbreviation)
        history = self.home_team.df[mask].head(self.h2h_limit)
        return (history['WL'] == 'W').mean() if not history.empty else 0.5

    def calculate_prediction_score(self, missing_home=None, missing_away=None):
        if self.final_score:
            return 1.0 if self.final_score['home'] > self.final_score['away'] else 0.0

        base_prob = 0.5
        if self.ml_model:
            try:
                features = pd.DataFrame([{
                    'rest_days': self.home_rest,
                    'season_net_rtg': self.home_team.season_metrics.get('net_rating', 0),
                    'recent_net_rtg': self.home_team.last_10_stats.get('net_rating', 0),
                    'h2h_win_pct': self.h2h_win_pct,
                    'is_playoff': 1 if self.game_type == GameType.PLAYOFF else 0
                }])
                base_prob = self.ml_model.predict_proba(features)[0][1]
            except: pass

        # WIF Adjustment logic[cite: 2]
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
        
        # Build Default Mode injury text[cite: 2]
        injury_txt = ""
        if missing_home or missing_away:
            injury_txt = "\n\n--- INJURY IMPACT ---"
            if missing_home: injury_txt += f"\n{self.home_team.abbreviation} Missing: {', '.join(missing_home)}"
            if missing_away: injury_txt += f"\n{self.away_team.abbreviation} Missing: {', '.join(missing_away)}"
        
        summary = f"--- {status} ---\nResult: {winner_abr} wins\nConfidence: {confidence}\nModel: RF ML + WIF Adjustment{injury_txt}"

        if not self.client: return summary

        context = {"matchup": f"{self.away_team.abbreviation} @ {self.home_team.abbreviation}", "injuries": {"home": missing_home, "away": missing_away}, "final_score": self.final_score}
        prompt = f"As an NBA expert, analyze this: {context}. Factor in injuries and explain the {status.lower()}."
        try:
            response = self.client.models.generate_content(model="gemini-1.5-pro", contents=prompt)
            return f"{summary}\n\n{response.text.strip()}"
        except: return summary

    def predict(self, missing_home=None, missing_away=None):
        prob = self.calculate_prediction_score(missing_home, missing_away)
        if self.final_score:
            winner = self.home_team.abbreviation if self.final_score['home'] > self.final_score['away'] else self.away_team.abbreviation
        else:
            winner = self.home_team.abbreviation if prob > 0.5 else self.away_team.abbreviation
        
        return {"winner": winner, "probability": prob, "narrative": self.get_ai_explanation(prob, winner, missing_home, missing_away), "is_past": self.final_score is not None}