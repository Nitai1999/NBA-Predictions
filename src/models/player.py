import pandas as pd

class Player:
    def __init__(self, name, player_id, stats_row):
        self.name = name
        self.id = player_id
        self.mpg = stats_row.get('MIN', 0)
        self.usage_pct = stats_row.get('USG_PCT', 0)
        self.net_rating = stats_row.get('NET_RATING', 0)
        self.efficiency = stats_row.get('PIE', 0) # Player Impact Estimate
        
        # Calculate WIF: Weighted Impact Factor
        # Formula: (Usage * Efficiency * 100) + Net Rating[cite: 3]
        self.wif = (self.usage_pct * self.efficiency * 100) + self.net_rating

    def __repr__(self):
        return f"{self.name} (WIF: {self.wif:.2f})"