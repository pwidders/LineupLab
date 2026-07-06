import streamlit as st

from data_loader import load_excel
from model import (
    compute_pitcher_ratings,
    compute_hitter_ratings,
    build_stacks,
    build_real_optimizer_lineup,
    build_multiple_lineups,
    late_swap_optimizer,
)
from lineup_manager import (
    save_lineup,
    has_saved_lineup,
    get_saved_lineup,
    clear_saved_lineup,
    get_saved_player_names,
)

DK_SALARY_CAP = 50000

st.set_page_config(page_title="LineupLab", layout="wide")
st.title("⚾ LineupLab")
st.caption("MLB DFS Optimizer")

uploaded_file = st.file_uploader("Upload your Excel sheet", type=["xlsx", "xlsm"])


def render_lineup(lineup, salary, score):
    st.markdown(
        f"### 💰 ${salary:,.0f} | 🔮 {round(score,1)} pts | 💵 ${DK_SALARY_CAP - salary:,.0f} left"
    )

    for _, row in lineup.iterrows():
        st.write(
            f"**{row['Slot']}** — {row['Player']} ({row['Team']}) | "
            f"${int(row['Salary'])} | {round(row['Score'],1)} pts"
        )

    lineup_text = "\n".join(
        f"{row['Slot']} - {row['Player']}" for _, row in lineup.iterrows()
    )
    st.code(lineup_text, language="text")

def render_slate_control_center(hitters_live, pitchers_live, stacks_live, combined_excluded_players, weather_risk_teams):
    top_stack = stacks_live.iloc[0]["Team"] if not stacks_live.empty else "N/A"

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Active Hitters", len(hitters_live))
    col2.metric("Active Pitchers", len(pitchers_live))
    col3.metric("Excluded Players", len(combined_excluded_players))
    col4.metric("Weather Teams", len(weather_risk_teams))

    st.markdown(
        f"""
        ### Slate Status
        - 🔥 **Top Stack:** {top_stack}
        - 🌧 **Weather-risk teams removed:** {", ".join(weather_risk_teams) if weather_risk_teams else "None"}
        - 🚑 **Unavailable / excluded players:** {len(combined_excluded_players)}
        """
    )

def filter_unavailable(df, unavailable_players):
    unavailable_set = {str(p).strip() for p in unavailable_players if str(p).strip()}

    if not unavailable_set:
        return df.copy()

    return df[
        ~df["Players"].astype(str).str.strip().isin(unavailable_set)
    ].copy()


def parse_pasted_lineup(text):
    players = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if " - " in line:
            name = line.split(" - ", 1)[1]
        elif "—" in line:
            name = line.split("—", 1)[1]
        else:
            name = line

        name = name.split("(")[0].strip()
        name = name.split("|")[0].strip()

        if name:
            players.append(name)

    return players


if uploaded_file:
    hitters_raw, pitchers_raw, _ = load_excel(uploaded_file)

    hitters = compute_hitter_ratings(hitters_raw)
    pitchers = compute_pitcher_ratings(pitchers_raw)

    all_players = sorted(
        list(hitters["Players"].dropna().astype(str).unique())
        + list(pitchers["Players"].dropna().astype(str).unique())
    )

    tab_pitchers, tab_hitters, tab_stacks, tab_builder, tab_health = st.tabs(
        ["Pitchers", "Hitters", "Stacks", "Lineup Builder", "Health Check"]
    )

    with tab_builder:
        st.subheader("Lineup Builder")

        locked_players = st.multiselect(
            "Lock players",
            options=all_players,
            help="Optimizer must include these players.",
        )

        excluded_players = st.multiselect(
            "Exclude players",
            options=all_players,
            help="Optimizer cannot include these players.",
        )

        all_teams = sorted(
            list(hitters["Team"].dropna().astype(str).unique())
            + list(pitchers["Team"].dropna().astype(str).unique())
        )

        weather_risk_teams = st.multiselect(
            "Exclude teams due to weather",
            options=all_teams,
            help="Removes all hitters and pitchers from selected weather-risk teams.",
        )
        
        unavailable_text = st.text_area(
            "IL / bench / scratched players",
            placeholder="Paste one player per line",
        )

        unavailable_players = [
            p.strip()
            for p in unavailable_text.splitlines()
            if p.strip()
        ]

        weather_excluded_players = []

        if weather_risk_teams:
            weather_excluded_players += hitters[
                hitters["Team"].astype(str).isin(weather_risk_teams)
            ]["Players"].dropna().astype(str).tolist()

            weather_excluded_players += pitchers[
                pitchers["Team"].astype(str).isin(weather_risk_teams)
            ]["Players"].dropna().astype(str).tolist()

        combined_excluded_players = sorted(
            set(excluded_players + unavailable_players + weather_excluded_players)
        )

        hitters_live = filter_unavailable(hitters, combined_excluded_players)
        pitchers_live = filter_unavailable(pitchers, combined_excluded_players)
        stacks_live = build_stacks(hitters_live)

        render_slate_control_center(
            hitters_live,
            pitchers_live,
            stacks_live,
            combined_excluded_players,
            weather_risk_teams,
        )

        if stacks_live.empty:
            st.error("No valid stacks found after filtering unavailable players.")
        else:
            stack_options = stacks_live["Team"].dropna().astype(str).tolist()

            col1, col2, col3 = st.columns(3)

            with col1:
                primary_stack = st.selectbox("Primary stack", stack_options, index=0)

            with col2:
                secondary_stack = st.selectbox(
                    "Secondary stack",
                    stack_options,
                    index=1 if len(stack_options) > 1 else 0,
                )

            with col3:
                min_salary = st.number_input(
                    "Minimum salary",
                    min_value=0,
                    max_value=DK_SALARY_CAP,
                    value=49500,
                    step=100,
                )

            num_lineups = st.number_input(
                "Number of lineups",
                min_value=1,
                max_value=20,
                value=3,
                step=1,
            )

            if st.button("Build Real Optimizer Lineup"):
                lineup, salary, score = build_real_optimizer_lineup(
                    hitters_live,
                    pitchers_live,
                    stacks_live,
                    locked_players=locked_players,
                    excluded_players=combined_excluded_players,
                    primary_stack=primary_stack,
                    secondary_stack=secondary_stack,
                    min_salary=min_salary,
                )

                if lineup.empty:
                    st.error(
                        "No optimized lineup found. Try lowering minimum salary, changing stacks, or relaxing locks/excludes."
                    )
                else:
                    st.session_state["current_lineup"] = lineup.copy()
                    render_lineup(lineup, salary, score)
                    st.success("Lineup saved for Late Swap ✅")
                    
                    if has_saved_lineup():
                        saved_lineup, saved_salary, saved_score, saved_at = get_saved_lineup()

                        with st.expander("💾 Saved Morning Lineup", expanded=False):
                            st.write(f"Saved at: **{saved_at}**")
                            st.write(f"Salary: **${saved_salary:,.0f}**")
                            st.write(f"Projection: **{saved_score:.1f} pts**")

                            for _, row in saved_lineup.iterrows():
                                st.write(f"**{row['Slot']}** — {row['Player']} ({row['Team']})")

                            if st.button("🗑 Clear Saved Lineup"):
                                clear_saved_lineup()
                                st.rerun()

            st.divider()

            st.subheader("Late Swap Assistant")

            pasted_lineup = st.text_area(
                "Optional: paste current DK lineup here",
                placeholder="P - Player Name\nP - Player Name\nC - Player Name...",
            )

            if pasted_lineup.strip():
                current_players = parse_pasted_lineup(pasted_lineup)
            elif "current_lineup" in st.session_state:
                current_players = (
                    st.session_state["current_lineup"]["Player"]
                    .dropna()
                    .astype(str)
                    .tolist()
                )
            else:
                current_players = []

            if current_players:
                st.write(f"Current lineup detected: **{len(current_players)} players**")

                unavailable_set = set(unavailable_players)
                kept_players = [
                    p for p in current_players
                    if p not in unavailable_set
                ]
                scratched_from_lineup = [
                    p for p in current_players
                    if p in unavailable_set
                ]

                st.write(f"Keeping: **{len(kept_players)}**")
                st.write(f"Replacing: **{len(scratched_from_lineup)}**")

                if scratched_from_lineup:
                    st.warning("Scratched/unavailable from current lineup: " + ", ".join(scratched_from_lineup))

                if st.button("🔄 Late Swap Rebuild"):
                    lineup, salary, score = late_swap_optimizer(
                        hitters_live,
                        pitchers_live,
                        stacks_live,
                        current_players,
                        combined_excluded_players,
                    )

                if lineup.empty:
                    st.error("No valid late swap found. Try unlocking one more player or relaxing constraints.")
                else:
                    st.success("Late swap completed ✅")

                    render_lineup(lineup, salary, score)

                    st.session_state["current_lineup"] = lineup.copy()
                    save_lineup(lineup, salary, score)

            else:
                st.info("Build a lineup first or paste your current DK lineup to use Late Swap.")

            st.divider()

            if st.button("Build Multiple Lineups"):
                multi = build_multiple_lineups(
                    hitters_live,
                    pitchers_live,
                    stacks_live,
                    num_lineups=num_lineups,
                    locked_players=locked_players,
                    excluded_players=combined_excluded_players,
                    primary_stack=primary_stack,
                    secondary_stack=secondary_stack,
                    min_salary=min_salary,
                )

                if multi.empty:
                    st.error(
                        "No multiple lineups found. Try lowering minimum salary or relaxing locks/excludes."
                    )
                else:
                    for lineup_num, lineup_df in multi.groupby("Lineup #"):
                        st.subheader(f"Lineup {lineup_num}")
                        lineup_clean = lineup_df.drop(columns=["Lineup #"], errors="ignore")
                        salary = lineup_clean["Salary"].sum()
                        score = lineup_clean["Score"].sum()
                        render_lineup(lineup_clean, salary, score)
                        st.divider()

    if "hitters_live" not in locals():
        hitters_live = hitters
    if "pitchers_live" not in locals():
        pitchers_live = pitchers
    if "stacks_live" not in locals():
        stacks_live = build_stacks(hitters_live)

    with tab_pitchers:
        st.subheader("Pitchers")
        sorted_pitchers = pitchers_live.sort_values("Overall", ascending=False)
        st.write("Top Pitchers")
        st.dataframe(sorted_pitchers.head(10), use_container_width=True)

        with st.expander("View Full Pitcher Pool"):
            st.dataframe(sorted_pitchers, use_container_width=True)

    with tab_hitters:
        st.subheader("Hitters")
        sorted_hitters = hitters_live.sort_values("Overall", ascending=False)
        st.write("Top Hitters")
        st.dataframe(sorted_hitters.head(15), use_container_width=True)

        with st.expander("View Full Hitter Pool"):
            st.dataframe(sorted_hitters, use_container_width=True)

    with tab_stacks:
        st.subheader("Live Recalculated Stacks")
        st.write("Top Live Stacks")
        st.dataframe(stacks_live.head(10), use_container_width=True)

        with st.expander("View All Live Stacks"):
            st.dataframe(stacks_live, use_container_width=True)

    with tab_health:
        st.subheader("Health Check")

        issues = []

        if "Salary" not in hitters_live.columns:
            issues.append("Hitters sheet is missing Salary column")
        elif hitters_live["Salary"].isna().sum() > 0:
            issues.append("Missing hitter salaries")

        if "Salary" not in pitchers_live.columns:
            issues.append("Pitchers sheet is missing Salary column")
        elif pitchers_live["Salary"].isna().sum() > 0:
            issues.append("Missing pitcher salaries")

        if "DK Projection" in hitters_live.columns and hitters_live["DK Projection"].isna().sum() > 0:
            issues.append("Missing hitter DK projections")

        if "DK Projection" in pitchers_live.columns and pitchers_live["DK Projection"].isna().sum() > 0:
            issues.append("Missing pitcher DK projections")

        if stacks_live.empty:
            issues.append("No valid stacks found")

        if not issues:
            st.success("All live data looks good ✅")
        else:
            for issue in issues:
                st.warning(issue)

else:
    st.info("Upload your Excel projection sheet to begin.")