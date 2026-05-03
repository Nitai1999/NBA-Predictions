import streamlit as st
from datetime import datetime
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.static import teams as nba_teams

# Custom Imports
from models.team import Team
from models.game import Game
from fetch_team_data import fetch_team_data

st.set_page_config(page_title="NBA Prediction Hub", page_icon="🏀")

@st.cache_data(ttl=600) # Faster refresh (10 mins)
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
            
            # BUG FIX: If points exist in LineScore, treat as finished even if status is TBD
            final_score = None
            if not res.empty:
                h_pts = res[res['TEAM_ID'] == h_id]['PTS'].values[0] or 0
                a_pts = res[res['TEAM_ID'] == a_id]['PTS'].values[0] or 0
                if h_pts > 0 or a_pts > 0:
                    final_score = {"home": int(h_pts), "away": int(a_pts)}

            results.append({"home": id_map.get(h_id), "away": id_map.get(a_id), "status": row['GAME_STATUS_TEXT'], "final_score": final_score})
        return results
    except: return []

st.title("🏀 NBA Prediction Hub")
selected_date = st.date_input("Select Date", datetime.now())
date_str = selected_date.strftime('%Y-%m-%d')
games_list = get_actual_games(date_str)

if not games_list:
    st.info("No games scheduled. Mishka says: Time for a walk! 🐕")
else:
    options = [f"{g['away']} @ {g['home']} ({g['status']})" for g in games_list]
    selected_option = st.selectbox("Choose a Game", options)
    game_data = next(g for g in games_list if f"{g['away']} @ {g['home']} ({g['status']})" == selected_option)

    # BUG FIX 1: Automatically show scores for past games[cite: 1]
    if game_data['final_score']:
        st.success("Buzzer Beater! This game is completed.")
        st.subheader("🏟️ Final Game Result")
        sc1, sc2 = st.columns(2)
        sc1.metric(game_data['away'], game_data['final_score']['away'])
        sc2.metric(game_data['home'], game_data['final_score']['home'])
        st.caption("Mishka's dog-wisdom: 'You can't predict the past, only learn from it!'")
    else:
        # Show Injury Selection only for future games[cite: 1]
        with st.spinner("Syncing rosters..."):
            fetch_team_data(game_data['home'])
            fetch_team_data(game_data['away'])
            h_team, a_team = Team(game_data['home']), Team(game_data['away'])

        st.subheader("🏥 Injury Report (Top 12 Rotation)")
        c1, c2 = st.columns(2)
        missing_away = c1.multiselect(f"{game_data['away']} Injuries", [p.name for p in a_team.roster], default=a_team.get_suggested_injuries())
        missing_home = c2.multiselect(f"{game_data['home']} Injuries", [p.name for p in h_team.roster], default=h_team.get_suggested_injuries())

        if st.button("Generate AI Prediction"):
            game_instance = Game(h_team, a_team, date_str)
            res = game_instance.predict(missing_home, missing_away)
            st.divider()
            st.subheader(f"🔮 Prediction: {res['winner']} wins")
            st.write(f"Confidence Level: **{res['probability'] if res['winner'] == game_data['home'] else 1-res['probability']:.1%}**")
            st.markdown(f"### 🤖 AI Narrative Analysis\n{res['narrative']}")

st.divider()
st.caption("🐾 Mishka's dog-wisdom: 'The data is the treat, and logic is the trick!'")