import streamlit as st
import pandas as pd
from datetime import datetime


DEFAULT_ENTRY_NAME = "rentisdue"


def parse_percent(x):
    try:
        return float(str(x).replace("%", "").strip())
    except Exception:
        return 0.0


def _required_columns_present(df, required_cols):
    missing = [col for col in required_cols if col not in df.columns]
    return missing


def _safe_num(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _render_single_contest(file, file_index):
    try:
        df = pd.read_csv(file)
    except Exception as e:
        st.error(f"Could not read {file.name}: {e}")
        return None

    required_cols = ["EntryName", "Rank", "Points", "Lineup", "Player", "Roster Position", "%Drafted", "FPTS"]
    missing = _required_columns_present(df, required_cols)

    if missing:
        st.error(f"{file.name} is missing required columns: {', '.join(missing)}")
        return None

    standings = df[df["EntryName"].notna()].copy()
    player_rows = df[df["Player"].notna()].copy()

    if standings.empty:
        st.warning(f"No standings rows found in {file.name}.")
        return None

    entry_names = standings["EntryName"].dropna().astype(str).unique().tolist()

    default_index = 0
    for i, name in enumerate(entry_names):
        if name.lower() == DEFAULT_ENTRY_NAME:
            default_index = i
            break

    selected_entry = st.selectbox(
        "Select your entry",
        entry_names,
        index=default_index,
        key=f"contest_entry_select_{file_index}_{file.name}",
    )

    my_row = standings[standings["EntryName"].astype(str) == selected_entry].iloc[0]

    rank = int(_safe_num(my_row["Rank"], 0))
    field_size = int(pd.to_numeric(standings["Rank"], errors="coerce").max())
    points = _safe_num(my_row["Points"], 0.0)
    lineup_text = str(my_row["Lineup"])
    rank_pct = rank / field_size if field_size else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Entry", selected_entry)
    col2.metric("Rank", f"{rank} / {field_size}")
    col3.metric("Points", round(points, 2))
    col4.metric("Rank Percentile", f"{rank_pct:.1%}")

    st.markdown("### Lineup")
    st.write(lineup_text)

    player_rows["Ownership %"] = player_rows["%Drafted"].apply(parse_percent)
    player_rows["FPTS"] = pd.to_numeric(player_rows["FPTS"], errors="coerce").fillna(0)

    st.markdown("### Player Ownership / Results")
    visible_cols = ["Player", "Roster Position", "Ownership %", "FPTS"]
    st.dataframe(
        player_rows[visible_cols].sort_values("Ownership %", ascending=False),
        use_container_width=True,
    )

    avg_ownership = player_rows["Ownership %"].mean()
    total_player_fpts = player_rows["FPTS"].sum()

    best_player = ""
    worst_player = ""
    if not player_rows.empty:
        best_player_row = player_rows.sort_values("FPTS", ascending=False).iloc[0]
        worst_player_row = player_rows.sort_values("FPTS", ascending=True).iloc[0]
        best_player = f"{best_player_row['Player']} ({best_player_row['FPTS']})"
        worst_player = f"{worst_player_row['Player']} ({worst_player_row['FPTS']})"

    summary = pd.DataFrame(
        [
            {
                "Logged At": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Source File": file.name,
                "Entry Name": selected_entry,
                "Rank": rank,
                "Field Size": field_size,
                "Points": points,
                "Rank Percentile": rank_pct,
                "Average Ownership": avg_ownership,
                "Player FPTS Total": total_player_fpts,
                "Best Player": best_player,
                "Worst Player": worst_player,
                "Lineup": lineup_text,
            }
        ]
    )

    st.markdown("### Log Row")
    st.dataframe(summary, use_container_width=True)

    st.download_button(
        "Download This Contest Log Row",
        data=summary.to_csv(index=False).encode("utf-8"),
        file_name=f"lineuplab_contest_log_{file_index + 1}.csv",
        mime="text/csv",
        key=f"contest_log_download_{file_index}_{file.name}",
    )

    return summary


def render_contest_logger():
    st.subheader("Contest Stat Collector")

    uploaded_files = st.file_uploader(
        "Upload DraftKings contest standings CSV",
        type=["csv"],
        key="contest_csv_upload",
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload one or more DraftKings contest exports to review and log results.")
        return

    all_summaries = []

    for i, file in enumerate(uploaded_files):
        with st.expander(f"{file.name}", expanded=(i == 0)):
            summary = _render_single_contest(file, i)
            if summary is not None:
                all_summaries.append(summary)

    if all_summaries:
        combined = pd.concat(all_summaries, ignore_index=True)

        st.divider()
        st.markdown("### Combined Contest Log")
        st.dataframe(combined, use_container_width=True)

        st.download_button(
            "Download Combined Contest Log",
            data=combined.to_csv(index=False).encode("utf-8"),
            file_name="lineuplab_combined_contest_log.csv",
            mime="text/csv",
            key="combined_contest_log_download",
        )
