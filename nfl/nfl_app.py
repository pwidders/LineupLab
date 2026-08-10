import streamlit as st

from data_loader import load_dk_salaries


st.set_page_config(
    page_title="LineupLab NFL",
    page_icon="🏈",
    layout="wide",
)

st.title("🏈 LineupLab NFL")
st.caption("NFL DFS Projection & Portfolio Lab")

st.divider()

st.subheader("DraftKings Player Pool")

uploaded_file = st.file_uploader(
    "Upload DraftKings NFL salary CSV",
    type=["csv"],
)

if uploaded_file is None:
    st.info("Upload a DraftKings NFL salary CSV to begin.")
    st.stop()

try:
    players = load_dk_salaries(uploaded_file)

except Exception as e:
    st.error(f"Could not load DraftKings salaries: {e}")
    st.stop()

st.success(f"Loaded {len(players)} NFL players.")

# -----------------------------
# Slate summary
# -----------------------------

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("QB", len(players[players["position"] == "QB"]))
col2.metric("RB", len(players[players["position"] == "RB"]))
col3.metric("WR", len(players[players["position"] == "WR"]))
col4.metric("TE", len(players[players["position"] == "TE"]))
col5.metric("DST", len(players[players["position"] == "DST"]))

st.divider()

# -----------------------------
# Filters
# -----------------------------

st.subheader("Player Pool")

position_filter = st.multiselect(
    "Position",
    ["QB", "RB", "WR", "TE", "DST"],
    default=["QB", "RB", "WR", "TE", "DST"],
)

filtered = players[
    players["position"].isin(position_filter)
].copy()

st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True,
    column_config={
        "dk_id": None,
        "player": "Player",
        "position": "Pos",
        "team": "Team",
        "opponent": "Opp",
        "home_away": "H/A",
        "salary": st.column_config.NumberColumn(
            "Salary",
            format="$%d",
        ),
        "dk_avg_points": st.column_config.NumberColumn(
            "DK Avg",
            format="%.1f",
        ),
        "status": "Status",
        "game_info": "Game",
    },
)