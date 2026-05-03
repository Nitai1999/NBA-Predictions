import streamlit as st
import pandas as pd
import os
from datetime import datetime
from models.game import Game
from models.team import Team

# --- 1. Page Configuration ---
st.set_page_config(
    page_title="NBA Predictor | Nitai Weiss",
    page_icon="🏀",
    layout="centered"
)

# --- 2. Custom CSS for a Professional Look ---
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. Sidebar Configuration ---
st.sidebar.header("⚙️ Settings")
game_date = st.sidebar.date_input("Matchup Date", datetime.now())
h2h_limit = st.sidebar.slider("Head-to-Head History Limit", 5, 20, 10)

# --- 4. Main UI ---
st.title("🏀 NBA Prediction Engine")
st.markdown("Automated AI analysis using Gemini 1.5 Pro & Real-time NBA Statistics.")

# Team Selection
teams = [
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"
]

col1, col2 = st.columns(2)
with col1:
    away_team_code = st.selectbox("Away Team", teams, index=1) # Default to BOS
with col2:
    home_team_code = st.selectbox("Home Team", teams, index=15) # Default to MIA

# --- 5. Prediction Logic ---
if st.button("Generate AI Prediction"):
    # Ensure data directory exists inside the container
    os.makedirs("data/raw", exist_ok=True)
    
    with st.spinner(f"Analyzing {away_team_code} @ {home_team_code}..."):
        try:
            # Initialize Team objects
            h_team = Team(home_team_code)
            a_team = Team(away_team_code)

            # CHECK: Does data exist? If not, fetch it live on Render.
            # This prevents the 'NoneType' error by ensuring files are present.
            for team in [h_team, a_team]:
                # Assuming your Team class has a check for data or you check files manually
                data_path = f"data/raw/{team.team_id}.csv"
                if not os.path.exists(data_path):
                    st.info(f"📥 Data for {team.team_id} not found on server. Fetching fresh stats...")
                    team.fetch_stats() # This triggers your nba_api logic

            # Run Prediction Logic
            game = Game(h_team, a_team, str(game_date), h2h_limit=h2h_limit)
            
            # This is where the 'NoneType' usually happens if calculations fail
            prob = game.calculate_prediction_score()
            
            if prob is None:
                st.error("Error: Prediction engine returned empty results. Try a different matchup.")
            else:
                winner = home_team_code if prob > 0.5 else away_team_code
                confidence = prob if prob > 0.5 else (1 - prob)

                # --- 6. Results Display ---
                st.divider()
                
                res_col1, res_col2 = st.columns(2)
                with res_col1:
                    st.metric("Predicted Winner", winner)
                with res_col2:
                    st.metric("Confidence Level", f"{confidence:.1%}")

                st.subheader("🤖 AI Narrative Analysis")
                # Ensure GEMINI_API_KEY is in Render Environment Variables
                narrative = game.get_ai_explanation(prob, winner)
                st.write(narrative)

                # Optional "Mishka" feature
                st.caption(f"🐾 Mishka's dog-wisdom: 'The {winner} look faster today!'")

        except Exception as e:
            st.error(f"⚠️ Application Error: {e}")
            st.info("Check your Render logs for the full Traceback.")

# --- 7. Footer ---
st.divider()
st.caption("Built for Portfolio - Nitai Weiss | Data powered by NBA_API")