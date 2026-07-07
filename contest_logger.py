import streamlit as st
import pandas as pd
from datetime import datetime


def parse_percent(x):
    try:
        return float(str(x).replace("%", "").strip())
    except Exception:
        return 0.0


def render_contest_logger():
    st.subheader("Contest Stat Collector")

    uploaded = st.file_uploader(
        "Upload DraftKings contest standings CSV",
        type=["csv"],
        key="contest_csv_upload",
    )

    if uploaded is None:
        st.info("Upload a DraftKings contest export to review and log results.")
        return

    df = pd.read_csv(uploaded)

    standings = df[df["EntryName"].notna()].copy()
    player_rows = df[df["Player"].notna()].copy()

    entry_names = standings["EntryName"].dropna().astype(str).unique().tolist()

    default_index = 0
    for i, name in enumerate(entry_names):
        if name.lower() == "rentisdue":
            default_index = i
            break

    selected_entry = st.selectbox(
        "Select your entry",
        entry_names,
        index=default_index,
    )

    my_row = standings[standings["EntryName"].astype(str) == selected_entry].iloc[0]

    rank = int(my_row["Rank"])
    field_size = int(standings["Rank"].max())
    points = float(my_row["Points"])
    lineup_text = str(my_row["Lineup"])

    rank_pct = rank / field_size if field_size else 0

    st.metric("Entry", selected_entry)
    st.metric("Rank", f"{rank} / {field_size}")
    st.metric("Points", round(points, 2))
    st.metric("Rank Percentile", f"{rank_pct:.1%}")

    st.markdown("### Lineup")
    st.write(lineup_text)

    player_rows["Ownership %"] = player_rows["%Drafted"].apply(parse_percent)

    st.markdown("### Player Ownership / Results")
    st.dataframe(
        player_rows[["Player", "Roster Position", "Ownership %", "FPTS"]]
        .sort_values("Ownership %", ascending=False),
        use_container_width=True,
    )

    avg_ownership = player_rows["Ownership %"].mean()
    total_player_fpts = player_rows["FPTS"].sum()

    summary = pd.DataFrame(
        [
            {
                "Logged At": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Entry Name": selected_entry,
                "Rank": rank,
                "Field Size": field_size,
                "Points": points,
                "Rank Percentile": rank_pct,
                "Average Ownership": avg_ownership,
                "Player FPTS Total": total_player_fpts,
                "Lineup": lineup_text,
            }
        ]
    )

    st.markdown("### Log Row")
    st.dataframe(summary, use_container_width=True)

    csv = summary.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Contest Log Row",
        data=csv,
        file_name="lineuplab_contest_log_row.csv",
        mime="text/csv",
    )