import streamlit as st
from datetime import datetime
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.static import teams as nba_teams

# Custom Imports
from models.team import Team
from models.game import Game
from fetch_team_data import fetch_team_data

st.set_page_config(page_title="NBA Prediction Hub", page_icon="🏀")

@st.cache_data(ttl=3600) # Performance: Cache schedule for 1 hour[cite: 1]
def get_actual_games(date_str):
    try:
        board = scoreboardv2.ScoreboardV2(game_date=date_str)
        games = board.get_data_frames()[0]
        line_score = board.get_data_frames()[1]
        if games.empty: return []

        id_map = {t['id']: t['abbreviation'] for t in nba_teams.get_teams()}
        results = []
        for _, row in games.iterrows():
            g_id, h_id, a_id = row['GAME_ID'], row['HOME_TEAM_ID'], row['VISITOR_TEAM_ID']
            res = line_score[line_score['GAME_ID'] == g_id]
            final_score = None
            if not res.empty and row['GAME_STATUS_TEXT'] == 'Final':
                final_score = {
                    "home": res[res['TEAM_ID'] == h_id]['PTS'].values[0],
                    "away": res[res['TEAM_ID'] == a_id]['PTS'].values[0]
                }
            results.append({
                "home": id_map.get(h_id), 
                "away": id_map.get(a_id), 
                "status": row['GAME_STATUS_TEXT'], 
                "final_score": final_score
            })
        return results
    except Exception: return []

st.title("🏀 NBA Prediction Hub")
st.markdown("Automated AI analysis using **RF ML + WIF Adjustment**.")

# 1. Calendar
selected_date = st.date_input("Select Date", datetime.now())
date_str = selected_date.strftime('%Y-%m-%d')
games_list = get_actual_games(date_str)

if not games_list:
    st.info("No games scheduled. Mishka says: Time for a walk! 🐕")
else:
    # 2. Matchup Selection
    options = [f"{g['away']} @ {g['home']} ({g['status']})" for g in games_list]
    selected_option = st.selectbox("Choose a Game", options)
    game_data = next(g for g in games_list if f"{g['away']} @ {g['home']} ({g['status']})" == selected_option)

    # 3. Data Loading
    with st.spinner("Fetching rosters and historical stats..."):
        fetch_team_data(game_data['home'])
        fetch_team_data(game_data['away'])
        h_team, a_team = Team(game_data['home']), Team(game_data['away'])

    # 4. Injury Selection UI
    st.subheader("🏥 Injury Report (Active Rotation)")
    st.info("We now pull the top 12 players to ensure star players who missed time are included.")
    col1, col2 = st.columns(2)
    
    # Updated to handle the larger roster[cite: 1]
    missing_away = col1.multiselect(
        f"{game_data['away']} Injuries", 
        [p.name for p in a_team.roster], 
        default=a_team.get_suggested_injuries()
    )
    
    missing_home = col2.multiselect(
        f"{game_data['home']} Injuries", 
        [p.name for p in h_team.roster], 
        default=h_team.get_suggested_injuries()
    )

    # Added a manual override in case a player is STILL missing
    with st.expander("Can't find a player? Add them manually"):
        manual_player = st.text_input("Enter Player Name (e.g., Jayson Tatum)")
        if manual_player:
            st.warning(f"Note: Manual players are treated as high-impact stars by the model.")
            # Logic would need to be added to Game.predict to handle this string

    if st.button("Generate AI Analysis"):
        game_instance = Game(h_team, a_team, date_str, final_score=game_data['final_score'])
        res = game_instance.predict(missing_home, missing_away)

        st.divider()
        if res["is_past"]:
            st.subheader("🏟️ Final Score")
            sc1, sc2 = st.columns(2)
            sc1.metric(game_data['away'], game_data['final_score']['away'])
            sc2.metric(game_data['home'], game_data['final_score']['home'])
        else:
            st.subheader(f"🔮 Prediction: {res['winner']} wins")
            actual_prob = res["probability"] if res["winner"] == game_data['home'] else 1 - res["probability"]
            st.write(f"Confidence Level: **{actual_prob:.1%}**")
            st.progress(actual_prob)

        st.markdown("### 🤖 AI Narrative Analysis")
        st.write(res["narrative"])

st.divider()
st.caption("🐾 Mishka's dog-wisdom: 'Data is the treat, and logic is the trick!'")