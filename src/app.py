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
        target_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        is_past_date = target_date_obj < date.today()

        for _, row in games.iterrows():
            g_id, h_id, a_id = row['GAME_ID'], row['HOME_TEAM_ID'], row['VISITOR_TEAM_ID']
            h_abr, a_abr = id_map.get(h_id), id_map.get(a_id)
            
            final_score = None
            # Check API Scoreboard
            res = line_score[line_score['GAME_ID'] == g_id]
            if not res.empty:
                h_pts = res[res['TEAM_ID'] == h_id]['PTS'].values[0] or 0
                a_pts = res[res['TEAM_ID'] == a_id]['PTS'].values[0] or 0
                if h_pts > 0 or a_pts > 0:
                    final_score = {"home": int(h_pts), "away": int(a_pts)}

            # BUG FIX: If it's a past date, check local CSV as a secondary source[cite: 13, 16]
            if final_score is None and is_past_date:
                final_score = Team(h_abr).get_score_from_csv(date_str)

            # PHANTOM LOGIC REMOVED: All games returned by API are shown.
            results.append({
                "home": h_abr, 
                "away": a_abr, 
                "status": row['GAME_STATUS_TEXT'], 
                "final_score": final_score,
                "is_past_date": is_past_date
            })
        return results
    except: return []

st.title("🏀 NBA Prediction Hub")
selected_date = st.date_input("Select Date", date.today())
date_str = selected_date.strftime('%Y-%m-%d')
games_list = get_actual_games(date_str)

if not games_list:
    st.info("No games found for this date. 🐕")
else:
    options = [f"{g['away']} @ {g['home']} ({'FINAL' if g['final_score'] else g['status']})" for g in games_list]
    selected_option = st.selectbox("Choose a Game", options)
    game_data = next(g for g in games_list if f"{g['away']} @ {g['home']} ({'FINAL' if g['final_score'] else g['status']})" == selected_option)

    # UI LOGIC FIX: If it's a past date OR we have a score, show result ONLY
    if game_data['final_score'] or game_data['is_past_date']:
        st.success("🏟️ GAME COMPLETED")
        if game_data['final_score']:
            c1, c2 = st.columns(2)
            c1.metric(game_data['away'], game_data['final_score']['away'])
            c2.metric(game_data['home'], game_data['final_score']['home'])
        else:
            st.warning("Score data not found in API or local database. Series placeholder or data lag.")
    else:
        # Prediction UI for today/future
        with st.spinner("Syncing rosters..."):
            fetch_team_data(game_data['home'])
            fetch_team_data(game_data['away'])
            h_team, a_team = Team(game_data['home']), Team(game_data['away'])

        st.subheader("🏥 Injury Report")
        col1, col2 = st.columns(2)
        missing_away = col1.multiselect(f"{game_data['away']} Injuries", [p.name for p in a_team.roster], default=a_team.get_suggested_injuries())
        missing_home = col2.multiselect(f"{game_data['home']} Injuries", [p.name for p in h_team.roster], default=h_team.get_suggested_injuries())

        if st.button("Generate AI Prediction"):
            game_instance = Game(h_team, a_team, date_str)
            res = game_instance.predict(missing_home, missing_away)
            st.divider()
            st.subheader(f"🔮 Prediction: {res['winner']} wins")
            st.write(f"Confidence Level: **{res['probability'] if res['winner'] == game_data['home'] else 1-res['probability']:.1%}**")
            st.markdown(f"### 🤖 Analysis\n{res['narrative']}")

st.divider()
st.caption("🐾 Mishka's dog-wisdom: 'Consistency is better than a squirrel on a fence!'")