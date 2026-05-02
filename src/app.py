import streamlit as st
import pandas as pd
from models.game import Game, GameType
from models.team import Team
import os

st.set_page_config(page_title="NBA Predictor", page_icon="🏀")

st.title("🏀 Nitai's NBA Prediction Engine")
st.markdown("Automated AI analysis using Gemini & NBA Stats.")

# Sidebar for configuration
st.sidebar.header("Settings")
game_date = st.sidebar.date_input("Matchup Date")

col1, col2 = st.columns(2)

with col1:
    away_team = st.selectbox("Away Team", ["BOS", "MIA", "LAL", "GSW", "DEN"]) # Add all teams later

with col2:
    home_team = st.selectbox("Home Team", ["BOS", "MIA", "LAL", "GSW", "DEN"], index=1)

if st.button("Generate AI Prediction"):
    with st.spinner("Analyzing data and calling Gemini..."):
        try:
            # Initialize our objects
            h_team = Team(home_team)
            a_team = Team(away_team)
            
            # Run the prediction
            game = Game(h_team, a_team, str(game_date), h2h_limit=10)
            prob = game.calculate_prediction_score()
            winner = home_team if prob > 0.5 else away_team
            
            # Display results
            st.success(f"Prediction: {winner} is favored to win!")
            
            # Get and display the AI narrative
            narrative = game.get_ai_explanation(prob, winner)
            st.info(narrative)
            
        except Exception as e:
            st.error(f"Error: {e}")
            st.write("Make sure you have fetched data for these teams first!")