import os
from enum import Enum
from google import genai

class GameType(Enum):
    REGULAR_SEASON = 1
    PLAYOFF = 2
    CUP = 3 

class Game:
    def __init__(self, home_team, away_team, date, game_type=GameType.REGULAR_SEASON, is_neutral=False, h2h_limit=5):
        """
        Initializes the Game with advanced logic for fatigue and possession-based efficiency.
        """
        self.home_team = home_team
        self.away_team = away_team
        self.date = date
        self.game_type = game_type
        self.is_neutral = is_neutral
        self.h2h_limit = h2h_limit
        
        # 1. Fatigue Analysis
        # Calculates days since the last game for both teams
        self.home_rest = self.home_team.get_rest_days(self.date)[cite: 7]
        self.away_rest = self.away_team.get_rest_days(self.date)[cite: 7]
        
        # 2. History & Streaks[cite: 5]
        self.h2h_history = self._get_h2h_history()[cite: 5]
        self.home_h2h_streak = self._check_h2h_streak(self.home_team, self.away_team)[cite: 5]
        self.away_h2h_streak = self._check_h2h_streak(self.away_team, self.home_team)[cite: 5]
        self.home_hot_streak = self._check_recent_streak(self.home_team)[cite: 5]
        self.away_hot_streak = self._check_recent_streak(self.away_team)[cite: 5]
        
        # 3. AI Client Setup[cite: 5]
        api_key = os.getenv("GEMINI_API_KEY")[cite: 5]
        self.client = genai.Client(api_key=api_key) if api_key else None[cite: 5]

    def _get_h2h_history(self):
        """Calculates win percentage in the last N matchups."""
        mask = self.home_team.df['MATCHUP'].str.contains(self.away_team.abbreviation)[cite: 5]
        history = self.home_team.df[mask].head(self.h2h_limit)[cite: 5]
        if history.empty: return 0.5[cite: 5]
        wins = len(history[history['WL'] == 'W'])[cite: 5]
        return wins / len(history)[cite: 5]

    def _check_h2h_streak(self, team, opponent):
        """Checks for a 4-0 sweep in recent head-to-head games."""
        mask = team.df['MATCHUP'].str.contains(opponent.abbreviation)[cite: 5]
        last_4 = team.df[mask].head(4)[cite: 5]
        if len(last_4) < 4: return False[cite: 5]
        return (last_4['WL'] == 'W').all()[cite: 5]

    def _check_recent_streak(self, team):
        """Checks if a team has won its last 5 games overall."""
        last_5 = team.df.head(5)[cite: 5]
        if len(last_5) < 5: return False[cite: 5]
        return (last_5['WL'] == 'W').all()[cite: 5]

    def _get_playoff_experience(self, team):
        """Counts total career playoff games in the current dataset."""
        playoff_games = team.df[team.df['SEASON_ID'].astype(str).str.startswith('4')][cite: 5]
        return len(playoff_games)[cite: 5]

    def calculate_prediction_score(self):
        """
        Main algorithm: Weights season-long efficiency, recent form (Net Rating), 
        head-to-head history, and applies fatigue/streak modifiers.
        """
        # 1. Base Weights
        weights = {
            'season_efficiency': 0.35, # Long-term Off/Def Rating
            'recent_net_rtg': 0.30,    # Recent point differential dominance
            'splits': 0.15,            # Home/Away performance[cite: 7]
            'h2h': 0.10,               # Rivalry history[cite: 7]
            'experience': 0.10         # Veteran/Playoff presence[cite: 7]
        }

        # 2. Normalization Function[cite: 7]
        # Maps a Net Rating (usually -15 to +15) to a 0.0 - 1.0 scale
        def normalize_rtg(val): return (val + 15) / 30[cite: 7]

        # 3. Calculate Home and Away Base Scores
        home_net = self.home_team.season_metrics['off_rating'] - self.home_team.season_metrics['def_rating'][cite: 7]
        away_net = self.away_team.season_metrics['off_rating'] - self.away_team.season_metrics['def_rating'][cite: 7]

        home_final = (normalize_rtg(home_net) * weights['season_efficiency']) + \
                     (normalize_rtg(self.home_team.last_10_stats['net_rating']) * weights['recent_net_rtg']) + \
                     (self.home_team.splits['home_win_pct'] * weights['splits']) + \
                     (self.h2h_history * weights['h2h'])[cite: 7]

        away_final = (normalize_rtg(away_net) * weights['season_efficiency']) + \
                     (normalize_rtg(self.away_team.last_10_stats['net_rating']) * weights['recent_net_rtg']) + \
                     (self.away_team.splits['away_win_pct'] * weights['splits']) + \
                     ((1 - self.h2h_history) * weights['h2h'])[cite: 7]

        # 4. Apply Fatigue Penalties[cite: 7]
        if self.home_rest <= 1: home_final -= 0.04 # Penalty for Back-to-Back[cite: 7]
        if self.away_rest <= 1: away_final -= 0.04[cite: 7]
        
        # 5. Apply Streak Bonuses[cite: 7]
        if self.home_hot_streak: home_final += 0.03[cite: 7]
        if self.away_hot_streak: away_final += 0.03[cite: 7]

        return home_final / (home_final + away_final)[cite: 7]

    def get_ai_explanation(self, prob, winner_abr):
        """Generates a narrative analysis using the Gemini API."""
        confidence = f"{prob if prob > 0.5 else (1 - prob):.1%}"[cite: 5]
        
        h_streak = "🔥 ACTIVE (5+ WINS)" if self.home_hot_streak else "None"[cite: 5]
        a_streak = "🔥 ACTIVE (5+ WINS)" if self.away_hot_streak else "None"[cite: 5]
        h2h_s = "Dominant (4-0)" if (self.home_h2h_streak or self.away_h2h_streak) else "Competitive"[cite: 5]

        fallback_msg = (
            f"--- STATISTICAL MODEL SUMMARY ---\n"
            f"Result: {winner_abr} wins\n"
            f"Confidence: {confidence}\n"
            f"Rest Advantage: {'Home' if self.home_rest > self.away_rest else 'Away' if self.away_rest > self.home_rest else 'Equal'}\n"
            f"----------------------------------\n"
            f"STREAKS: Home: {h_streak} | Away: {a_streak}\n"
            f"H2H Vibe: {h2h_s}\n"
            f"----------------------------------"
        )[cite: 5]

        if not self.client: return fallback_msg[cite: 5]

        stats_brief = {
            "matchup": f"{self.away_team.abbreviation} vs {self.home_team.abbreviation}",[cite: 5]
            "prediction": f"{winner_abr} wins",[cite: 5]
            "confidence": confidence,[cite: 5]
            "home_rest": self.home_rest,
            "away_rest": self.away_rest,
            "streaks": {"home_hot": self.home_hot_streak, "away_hot": self.away_hot_streak}[cite: 5]
        }

        prompt = f"As an NBA expert, explain why {winner_abr} is favored based on: {stats_brief}. Mention fatigue/rest if one team is on a back-to-back."[cite: 5]

        try:
            response = self.client.models.generate_content(model="gemini-2.0-flash", contents=prompt)[cite: 5]
            return response.text.strip()[cite: 5]
        except Exception:
            return fallback_msg[cite: 5]

    def predict(self):
        """CLI helper to run a prediction and print results."""
        prob = self.calculate_prediction_score()[cite: 5]
        winner_abr = self.home_team.abbreviation if prob > 0.5 else self.away_team.abbreviation[cite: 5]
        ai_narrative = self.get_ai_explanation(prob, winner_abr)[cite: 5]
        
        print(f"\n" + "="*60)
        print(f"   PREDICTION: {self.away_team.abbreviation} @ {self.home_team.abbreviation}")
        print(f"   Context: {self.game_type.name} | Confidence: {prob:.1%}")
        print(f"="*60)
        print(f"\n{ai_narrative}\n")
        
        return winner_abr[cite: 5]