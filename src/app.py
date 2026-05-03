import streamlit as st
import os
from datetime import datetime
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.static import teams

# Custom Imports
from models.team import Team
from models.game import Game, GameType
from fetch_team_data import fetch_team_data

st.set_page_config(page_title="NBA Prediction Hub", page_icon="🏀")

# --- Utility Functions ---
@st.cache_data(ttl=3600) # Cache schedule for 1 hour
def get_actual_games(date_str):
    try:
        board = scoreboardv2.ScoreboardV2(game_date=date_str)
        games = board.get_data_frames()[0]
        line_score = board.get_data_frames()[1] # Results
        
        if games.empty:
            return []

        nba_teams = teams.get_teams()
        id_to_abr = {t['id']: t['abbreviation'] for t in nba_teams}

        results = []
        for _, row in games.iterrows():
            game_id = row['GAME_ID']
            home_id = row['HOME_TEAM_ID']
            away_id = row['VISITOR_TEAM_ID']
            
            # Check for existing scores
            game_results = line_score[line_score['GAME_ID'] == game_id]
            final_score = None
            if not game_results.empty and row['GAME_STATUS_TEXT'] == 'Final':
                home_pts = game_results[game_results['TEAM_ID'] == home_id]['PTS'].values[0]
                away_pts = game_results[game_results['TEAM_ID'] == away_id]['PTS'].values[0]
                final_score = {"home": home_pts, "away": away_pts}

            results.append({
                "game_id": game_id,
                "home": id_to_abr.get(home_id),
                "away": id_to_abr.get(away_id),
                "status": row['GAME_STATUS_TEXT'],
                "final_score": final_score
            })
        return results
    except Exception:
        return []

# --- UI Layout ---
st.title("🏀 NBA Prediction Hub")
st.markdown("Automated AI analysis using **Random Forest ML** & **Gemini 1.5 Pro**.")

# 1. Calendar Selection
selected_date = st.date_input("Select Date", datetime.now())
date_str = selected_date.strftime('%Y-%m-%d')

# 2. Fetch Actual Games
with st.spinner("Checking NBA Schedule..."):
    games_list = get_actual_games(date_str)

if not games_list:
    st.info(f"No games scheduled for {date_str}. Mishka says: Time for a walk! 🐕")
else:
    # 3. Game Selection
    options = [f"{g['away']} @ {g['home']} ({g['status']})" for g in games_list]
    selected_option = st.selectbox("Choose a Game", options)
    
    # Identify the selected game object
    game_data = next(g for g in games_list if f"{g['away']} @ {g['home']} ({g['status']})" == selected_option)

    if st.button("Generate AI Analysis"):
        # Data Integrity Check: Ensure we have the CSVs[cite: 2]
        with st.status("Data Sync in Progress...", expanded=False) as status:
            st.write(f"Checking {game_data['home']} records...")
            fetch_team_data(game_data['home'])
            st.write(f"Checking {game_data['away']} records...")
            fetch_team_data(game_data['away'])
            status.update(label="Data Synchronized!", state="complete")

        # Initialize Analysis
        home_team = Team(game_data['home'])
        away_team = Team(game_data['away'])
        
        game_instance = Game(
            home_team=home_team,
            away_team=away_team,
            date=date_str,
            final_score=game_data['final_score']
        )

        # Output Results
        st.divider()
        if game_data['final_score']:
            st.subheader("🏟️ Game Result")
            c1, c2 = st.columns(2)
            c1.metric(game_data['away'], game_data['final_score']['away'])
            c2.metric(game_data['home'], game_data['final_score']['home'])
        else:
            prob = game_instance.calculate_prediction_score()
            winner = game_data['home'] if prob > 0.5 else game_data['away']
            conf = f"{prob if prob > 0.5 else (1 - prob):.1%}"
            
            st.subheader(f"🔮 Prediction: {winner} wins")
            st.write(f"Confidence Level: **{conf}**")

        st.markdown("### 🤖 AI Narrative Analysis")
        narrative = game_instance.get_ai_explanation(
            prob if not game_data['final_score'] else 0, 
            game_data['home']
        )
        st.write(narrative)

st.divider()
st.caption(f"🐾 Mishka's dog-wisdom: 'The schedule is my favorite bone to chew on!'")