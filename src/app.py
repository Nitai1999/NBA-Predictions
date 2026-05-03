import streamlit as st
from datetime import datetime, date
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.static import teams as nba_teams
from models.team import Team
from models.game import Game
from fetch_team_data import fetch_team_data

st.set_page_config(page_title="NBA Prediction Hub", page_icon="🏀")

@st.cache_data(ttl=600)
def get_actual_games(date_str):
    try:
        board = scoreboardv2.ScoreboardV2(game_date=date_str)
        games = board.get_data_frames()[0]
        line_score = board.get_data_frames()[1]
        if games.empty: return []

        id_map = {t['id']: t['abbreviation'] for t in nba_teams.get_teams()}
        results = []
        is_past = datetime.strptime(date_str, '%Y-%m-%d').date() <= date.today()

        for _, row in games.iterrows():
            g_id, h_id, a_id = row['GAME_ID'], row['HOME_TEAM_ID'], row['VISITOR_TEAM_ID']
            h_abr, a_abr = id_map.get(h_id), id_map.get(a_id)
            
            final_score = None
            res = line_score[line_score['GAME_ID'] == g_id]
            if not res.empty:
                h_pts = res[res['TEAM_ID'] == h_id]['PTS'].values[0] or 0
                a_pts = res[res['TEAM_ID'] == a_id]['PTS'].values[0] or 0
                if h_pts > 0 or a_pts > 0:
                    final_score = {"home": int(h_pts), "away": int(a_pts)}

            # BUG FIX: If API has no points, check local CSV to see if the game actually happened[cite: 12, 13]
            if final_score is None and is_past:
                temp_team = Team(h_abr)
                final_score = temp_team.get_score_from_csv(date_str)

            # PHANTOM FILTER: Only skip if status is TBD and no score found anywhere[cite: 12, 13]
            if row['GAME_STATUS_TEXT'] == 'TBD' and final_score is None and is_past:
                continue

            results.append({"home": h_abr, "away": a_abr, "status": row['GAME_STATUS_TEXT'], "final_score": final_score})
        return results
    except: return []

st.title("🏀 NBA Prediction Hub")
selected_date = st.date_input("Select Date", date.today())
date_str = selected_date.strftime('%Y-%m-%d')
games_list = get_actual_games(date_str)

if not games_list:
    st.info("No active games. The series might be over! 🐕")
else:
    options = [f"{g['away']} @ {g['home']} ({'FINAL' if g['final_score'] else g['status']})" for g in games_list]
    selected_option = st.selectbox("Choose a Matchup", options)
    game_data = next(g for g in games_list if f"{g['away']} @ {g['home']} ({'FINAL' if g['final_score'] else g['status']})" == selected_option)

    # BUG FIX: Automatically show results for past games[cite: 12, 13]
    if game_data['final_score']:
        st.success("🏟️ GAME COMPLETED")
        c1, c2 = st.columns(2)
        c1.metric(game_data['away'], game_data['final_score']['away'])
        c2.metric(game_data['home'], game_data['final_score']['home'])
    else:
        with st.spinner("Syncing rosters..."):
            fetch_team_data(game_data['home'])
            fetch_team_data(game_data['away'])
            h_team, a_team = Team(game_data['home']), Team(game_data['away'])

        st.subheader("🏥 Injury Report")
        missing_away = st.multiselect(f"{game_data['away']} Injuries", [p.name for p in a_team.roster], default=a_team.get_suggested_injuries())
        missing_home = st.multiselect(f"{game_data['home']} Injuries", [p.name for p in h_team.roster], default=h_team.get_suggested_injuries())

        if st.button("Generate AI Prediction"):
            game_instance = Game(h_team, a_team, date_str)
            res = game_instance.predict(missing_home, missing_away)
            st.divider()
            st.subheader(f"🔮 Prediction: {res['winner']} wins")
            st.write(f"Confidence: **{res['probability'] if res['winner'] == game_data['home'] else 1-res['probability']:.1%}**")
            st.markdown(f"### 🤖 AI Analysis\n{res['narrative']}")