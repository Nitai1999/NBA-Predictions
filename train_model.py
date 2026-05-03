import pandas as pd
import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Paths adjusted for your root directory execution
RAW_DATA_PATH = 'data/raw'
MODEL_PATH = 'src/models/nba_model.pkl'

def extract_features_from_history():
    training_rows = []
    if not os.path.exists(RAW_DATA_PATH):
        print(f"❌ Error: {RAW_DATA_PATH} not found.")
        return pd.DataFrame()

    files = [f for f in os.listdir(RAW_DATA_PATH) if f.endswith('_games.csv')]
    
    # Load all data into a dictionary for H2H lookups
    all_teams_data = {f.split('_')[0]: pd.read_csv(os.path.join(RAW_DATA_PATH, f)) for f in files}
    for t in all_teams_data:
        all_teams_data[t]['GAME_DATE'] = pd.to_datetime(all_teams_data[t]['GAME_DATE'], format='mixed')

    for team_abr, df in all_teams_data.items():
        df = df.sort_values('GAME_DATE', ascending=True)

        # Advanced Efficiency Logic (Possessions/Net Rating)
        if 'PLUS_MINUS' in df.columns and 'FGA' in df.columns:
            df['POSS'] = df['FGA'] + (0.44 * df['FTA']) + df['TOV'] - df['OREB']
            df['NET_RTG'] = (df['PLUS_MINUS'] / df['POSS']) * 100
        else: continue

        for i in range(20, len(df)):
            current_game = df.iloc[i]
            past_games = df.iloc[:i]
            
            # H2H Calculation
            matchup_str = str(current_game['MATCHUP'])
            opp_abr = matchup_str.replace('@', '').replace('vs.', '').replace(team_abr, '').strip()
            
            h2h_past = past_games[past_games['MATCHUP'].str.contains(opp_abr)]
            h2h_win_pct = len(h2h_past[h2h_past['WL'] == 'W']) / len(h2h_past) if not h2h_past.empty else 0.5
            
            # Fatigue & Season Stats
            rest_days = (current_game['GAME_DATE'] - past_games['GAME_DATE'].max()).days
            season_data = past_games[past_games['SEASON_ID'] == current_game['SEASON_ID']]
            if season_data.empty: continue
            
            training_rows.append({
                'rest_days': rest_days, 
                'season_net_rtg': season_data['NET_RTG'].mean(),
                'recent_net_rtg': season_data.tail(10)['NET_RTG'].mean(),
                'h2h_win_pct': h2h_win_pct,
                'is_playoff': 1 if str(current_game['SEASON_ID']).startswith('4') else 0,
                'target_win': 1 if current_game['WL'] == 'W' else 0
            })

    return pd.DataFrame(training_rows)

def train_ml_engine():
    print("🚀 Crushing data for all 30 teams...")
    df = extract_features_from_history()
    
    if df.empty:
        print("❌ No data found to train.")
        return
    
    X = df.drop('target_win', axis=1)
    y = df['target_win']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train the Random Forest
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    print("\n✅ Model Accuracy:", f"{accuracy_score(y_test, model.predict(X_test)):.2%}")
    print("\n--- ML DISCOVERED WEIGHTS (Importance) ---")
    importances = sorted(zip(X.columns, model.feature_importances_), key=lambda x: x[1], reverse=True)
    for feature, imp in importances:
        print(f"🔹 {feature:15}: {imp:.4f}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH, compress=3)
    print(f"\n💾 Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_ml_engine()