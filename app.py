import streamlit as st

from datetime import date
from io import BytesIO

from cloud_lineup_store import (
    delete_cloud_lineup,
    list_cloud_lineups,
    load_cloud_lineup,
    save_cloud_lineup,
)
from contest_logger import render_contest_logger
from data_loader import load_excel
from late_swap import render_late_swap_assistant
from lineup_manager import (
    clear_saved_lineup,
    get_saved_lineup,
    has_saved_lineup,
    save_lineup,
)
from model import (
    build_multiple_lineups,
    build_real_optimizer_lineup,
    build_stacks,
    compute_hitter_ratings,
    compute_pitcher_ratings,
)
from projection_store import load_projection_file, save_projection_file
from render import render_lineup
from slate_dashboard import render_slate_control_center


DK_SALARY_CAP = 50000

st.set_page_config(page_title="LineupLab", layout="wide")
st.title("⚾ LineupLab")
st.caption("MLB DFS Optimizer")


# -------------------------------------------------------------------
# Lineup Vault
# -------------------------------------------------------------------

st.sidebar.header("Lineup Vault")

vault_slate_date = st.sidebar.date_input(
    "Slate date",
    value=date.today(),
)

vault_slate_name = st.sidebar.text_input(
    "Slate name",
    value="Main",
)

vault_lineup_slot = st.sidebar.number_input(
    "Active lineup slot",
    min_value=1,
    max_value=20,
    value=1,
    step=1,
)

vault_slate_date_str = vault_slate_date.isoformat()
vault_slate_name = vault_slate_name.strip() or "Main"

try:
    saved_vault_lineups = list_cloud_lineups(
        vault_slate_date_str,
        vault_slate_name,
    )
except Exception as exc:
    saved_vault_lineups = []
    st.sidebar.error(f"Could not load Lineup Vault: {exc}")

if saved_vault_lineups:
    st.sidebar.caption("Saved lineups")

    for saved_record in saved_vault_lineups:
        saved_slot = int(saved_record["lineup_slot"])
        saved_name = (
            saved_record.get("lineup_name")
            or f"Lineup #{saved_slot}"
        )
        saved_salary = float(saved_record.get("salary", 0))
        saved_projection = float(
            saved_record.get("projected_score", 0)
        )

        active_marker = (
            " ⭐"
            if saved_slot
            == st.session_state.get("active_cloud_lineup_slot")
            else ""
        )

        st.sidebar.write(
            f"**{saved_name}{active_marker}** — "
            f"${saved_salary:,.0f} | "
            f"{saved_projection:.1f} pts"
        )
else:
    st.sidebar.caption("No cloud-saved lineups for this slate.")

vault_col1, vault_col2 = st.sidebar.columns(2)

with vault_col1:
    if st.button("☁️ Load", key="load_vault_lineup"):
        try:
            (
                cloud_lineup,
                cloud_salary,
                cloud_score,
                _cloud_record,
            ) = load_cloud_lineup(
                vault_slate_date_str,
                vault_slate_name,
                int(vault_lineup_slot),
            )

            st.session_state["current_lineup"] = cloud_lineup.copy()

            save_lineup(
                cloud_lineup,
                cloud_salary,
                cloud_score,
            )

            st.session_state["active_cloud_lineup_slot"] = int(
                vault_lineup_slot
            )

            st.sidebar.success(
                f"Loaded Lineup #{int(vault_lineup_slot)}."
            )
            st.rerun()

        except Exception as exc:
            st.sidebar.error(f"Load failed: {exc}")

with vault_col2:
    if st.button("🗑 Delete", key="delete_vault_lineup"):
        try:
            delete_cloud_lineup(
                vault_slate_date_str,
                vault_slate_name,
                int(vault_lineup_slot),
            )

            if (
                st.session_state.get("active_cloud_lineup_slot")
                == int(vault_lineup_slot)
            ):
                st.session_state.pop(
                    "active_cloud_lineup_slot",
                    None,
                )

            st.sidebar.success(
                f"Deleted Lineup #{int(vault_lineup_slot)}."
            )
            st.rerun()

        except Exception as exc:
            st.sidebar.error(f"Delete failed: {exc}")

st.sidebar.divider()


# -------------------------------------------------------------------
# Projection Library
# -------------------------------------------------------------------

st.sidebar.header("Projection Library")

uploaded_file = st.file_uploader(
    "Upload your Excel sheet",
    type=["xlsx", "xlsm"],
)

# Keep manually uploaded projections available through Streamlit reruns.
if uploaded_file is not None:
    st.session_state["active_projection_bytes"] = uploaded_file.getvalue()
    st.session_state["active_projection_name"] = uploaded_file.name

if uploaded_file and st.sidebar.button("💾 Save Uploaded Sheet"):
    try:
        save_projection_file(uploaded_file)
        st.sidebar.success("Saved latest projection sheet.")
    except Exception as exc:
        st.sidebar.error(f"Save failed: {exc}")

if st.sidebar.button("📲 Load Latest Saved Sheet"):
    try:
        saved_bytes = load_projection_file()


        st.session_state["saved_projection_bytes"] = saved_bytes
        st.session_state["active_projection_bytes"] = saved_bytes
        st.session_state["active_projection_name"] = (
            "latest_projection_sheet.xlsx"
        )
        
        st.sidebar.success("Loaded latest saved sheet.")
    except Exception as exc:
        st.sidebar.error(f"Load failed: {exc}")

if uploaded_file is None:
    if "active_projection_bytes" in st.session_state:
        uploaded_file = BytesIO(
            st.session_state["active_projection_bytes"]
        )
        uploaded_file.name = st.session_state.get(
            "active_projection_name",
            "uploaded_projection_sheet.xlsx",
        )

    elif "saved_projection_bytes" in st.session_state:
        uploaded_file = BytesIO(
            st.session_state["saved_projection_bytes"]
        )
        uploaded_file.name = "latest_projection_sheet.xlsx"


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def filter_unavailable(df, unavailable_players):
    unavailable_set = {
        str(player).strip()
        for player in unavailable_players
        if str(player).strip()
    }

    if not unavailable_set:
        return df.copy()

    return df[
        ~df["Players"]
        .astype(str)
        .str.strip()
        .isin(unavailable_set)
    ].copy()


def render_saved_lineup_card():
    if not has_saved_lineup():
        return

    saved_lineup, saved_salary, saved_score, saved_at = (
        get_saved_lineup()
    )

    with st.expander(
        "💾 Saved Starting Lineup",
        expanded=False,
    ):
        st.write(f"Saved at: **{saved_at}**")
        st.write(f"Salary: **${saved_salary:,.0f}**")
        st.write(
            f"Projection: **{saved_score:.1f} pts**"
        )

        for _, row in saved_lineup.iterrows():
            st.write(
                f"**{row['Slot']}** — "
                f"{row['Player']} ({row['Team']})"
            )

        if st.button(
            "🗑 Clear Saved Starting Lineup",
            key="clear_saved_starting_lineup",
        ):
            clear_saved_lineup()
            st.rerun()


def render_cloud_save_controls():
    if not has_saved_lineup():
        return

    st.markdown("#### Save to Lineup Vault")

    cloud_save_name = st.text_input(
        "Cloud lineup name",
        value=f"Lineup #{int(vault_lineup_slot)}",
        key="cloud_lineup_name",
    )

    if st.button(
        "💾 Save Current Lineup to Cloud",
        key="save_current_lineup_to_cloud",
    ):
        try:
            (
                lineup_to_save,
                salary_to_save,
                score_to_save,
                _saved_at,
            ) = get_saved_lineup()

            save_cloud_lineup(
                lineup=lineup_to_save,
                salary=salary_to_save,
                projected_score=score_to_save,
                slate_date=vault_slate_date_str,
                slate_name=vault_slate_name,
                lineup_slot=int(vault_lineup_slot),
                lineup_name=cloud_save_name,
            )

            st.session_state["active_cloud_lineup_slot"] = int(
                vault_lineup_slot
            )

            st.success(
                f"Saved Lineup #{int(vault_lineup_slot)} "
                "to the cloud ✅"
            )
            st.rerun()

        except Exception as exc:
            st.error(f"Cloud lineup save failed: {exc}")


# -------------------------------------------------------------------
# Main tabs
# -------------------------------------------------------------------

(
    tab_pitchers,
    tab_hitters,
    tab_stacks,
    tab_builder,
    tab_review,
    tab_health,
) = st.tabs(
    [
        "Pitchers",
        "Hitters",
        "Stacks",
        "Lineup Builder",
        "Contest Review",
        "Health Check",
    ]
)

with tab_review:
    render_contest_logger()


if uploaded_file:
    hitters_raw, pitchers_raw, _ = load_excel(uploaded_file)

    hitters = compute_hitter_ratings(hitters_raw)
    pitchers = compute_pitcher_ratings(pitchers_raw)

    all_players = sorted(
        list(
            hitters["Players"]
            .dropna()
            .astype(str)
            .unique()
        )
        + list(
            pitchers["Players"]
            .dropna()
            .astype(str)
            .unique()
        )
    )

    all_teams = sorted(
        list(
            hitters["Team"]
            .dropna()
            .astype(str)
            .unique()
        )
        + list(
            pitchers["Team"]
            .dropna()
            .astype(str)
            .unique()
        )
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

        weather_risk_teams = st.multiselect(
            "Exclude teams due to weather",
            options=all_teams,
            help=(
                "Removes all hitters and pitchers from "
                "selected weather-risk teams."
            ),
        )

        st.write("### IL / Bench / Scratched")

        unavailable_players = st.multiselect(
            "Select unavailable players",
            options=all_players,
            help=(
                "Tap players to remove them from "
                "the player pool."
            ),
        )

        with st.expander(
            "Or paste player names (desktop)"
        ):
            unavailable_text = st.text_area(
                "Paste one player per line",
                placeholder="One player per line",
            )

            unavailable_players.extend(
                [
                    player.strip()
                    for player in unavailable_text.splitlines()
                    if player.strip()
                ]
            )

        unavailable_players = sorted(
            set(unavailable_players)
        )

        weather_excluded_players = []

        if weather_risk_teams:
            weather_excluded_players += (
                hitters[
                    hitters["Team"]
                    .astype(str)
                    .isin(weather_risk_teams)
                ]["Players"]
                .dropna()
                .astype(str)
                .tolist()
            )

            weather_excluded_players += (
                pitchers[
                    pitchers["Team"]
                    .astype(str)
                    .isin(weather_risk_teams)
                ]["Players"]
                .dropna()
                .astype(str)
                .tolist()
            )

        combined_excluded_players = sorted(
            set(
                excluded_players
                + unavailable_players
                + weather_excluded_players
            )
        )

        hitters_live = filter_unavailable(
            hitters,
            combined_excluded_players,
        )
        pitchers_live = filter_unavailable(
            pitchers,
            combined_excluded_players,
        )
        stacks_live = build_stacks(hitters_live)

        render_slate_control_center(
            hitters_live,
            pitchers_live,
            stacks_live,
            combined_excluded_players,
            weather_risk_teams,
        )

        render_saved_lineup_card()

        if stacks_live.empty:
            st.error(
                "No valid stacks found after filtering "
                "unavailable players."
            )
        else:
            stack_options = (
                stacks_live["Team"]
                .dropna()
                .astype(str)
                .tolist()
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                primary_stack = st.selectbox(
                    "Primary stack",
                    stack_options,
                    index=0,
                )

            with col2:
                secondary_stack = st.selectbox(
                    "Secondary stack",
                    stack_options,
                    index=(
                        1
                        if len(stack_options) > 1
                        else 0
                    ),
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
                lineup, salary, score = (
                    build_real_optimizer_lineup(
                        hitters_live,
                        pitchers_live,
                        stacks_live,
                        locked_players=locked_players,
                        excluded_players=(
                            combined_excluded_players
                        ),
                        primary_stack=primary_stack,
                        secondary_stack=secondary_stack,
                        min_salary=min_salary,
                    )
                )

                if lineup.empty:
                    st.error(
                        "No optimized lineup found. Try "
                        "lowering minimum salary, changing "
                        "stacks, or relaxing locks/excludes."
                    )
                else:
                    st.session_state[
                        "current_lineup"
                    ] = lineup.copy()

                    save_lineup(
                        lineup,
                        salary,
                        score,
                    )

                    render_lineup(
                        lineup,
                        salary,
                        score,
                    )
                    st.success(
                        "Lineup saved for Late Swap ✅"
                    )

            # This renders immediately after a successful build
            # and also remains available on later reruns.
            render_cloud_save_controls()

            st.divider()

            render_late_swap_assistant(
                hitters_live=hitters_live,
                pitchers_live=pitchers_live,
                stacks_live=stacks_live,
                unavailable_players=unavailable_players,
                combined_excluded_players=(
                    combined_excluded_players
                ),
                manual_locked_players=locked_players,
            )

            st.divider()

            if st.button("Build Multiple Lineups"):
                multi = build_multiple_lineups(
                    hitters_live,
                    pitchers_live,
                    stacks_live,
                    num_lineups=num_lineups,
                    locked_players=locked_players,
                    excluded_players=(
                        combined_excluded_players
                    ),
                    primary_stack=primary_stack,
                    secondary_stack=secondary_stack,
                    min_salary=min_salary,
                )

                if multi.empty:
                    st.error(
                        "No multiple lineups found. Try "
                        "lowering minimum salary or relaxing "
                        "locks/excludes."
                    )
                else:
                    for lineup_num, lineup_df in multi.groupby(
                        "Lineup #"
                    ):
                        st.subheader(
                            f"Lineup {lineup_num}"
                        )

                        lineup_clean = lineup_df.drop(
                            columns=["Lineup #"],
                            errors="ignore",
                        )

                        lineup_salary = (
                            lineup_clean["Salary"].sum()
                        )
                        lineup_score = (
                            lineup_clean["Score"].sum()
                        )

                        render_lineup(
                            lineup_clean,
                            lineup_salary,
                            lineup_score,
                        )
                        st.divider()

    if "hitters_live" not in locals():
        hitters_live = hitters

    if "pitchers_live" not in locals():
        pitchers_live = pitchers

    if "stacks_live" not in locals():
        stacks_live = build_stacks(hitters_live)

    with tab_pitchers:
        st.subheader("Pitchers")

        sorted_pitchers = pitchers_live.sort_values(
            "Overall",
            ascending=False,
        )

        st.write("Top Pitchers")
        st.dataframe(
            sorted_pitchers.head(10),
            use_container_width=True,
        )

        with st.expander("View Full Pitcher Pool"):
            st.dataframe(
                sorted_pitchers,
                use_container_width=True,
            )

    with tab_hitters:
        st.subheader("Hitters")

        sorted_hitters = hitters_live.sort_values(
            "Overall",
            ascending=False,
        )

        st.write("Top Hitters")
        st.dataframe(
            sorted_hitters.head(15),
            use_container_width=True,
        )

        with st.expander("View Full Hitter Pool"):
            st.dataframe(
                sorted_hitters,
                use_container_width=True,
            )

    with tab_stacks:
        st.subheader("Live Recalculated Stacks")
        st.write("Top Live Stacks")

        st.dataframe(
            stacks_live.head(10),
            use_container_width=True,
        )

        with st.expander("View All Live Stacks"):
            st.dataframe(
                stacks_live,
                use_container_width=True,
            )

    with tab_health:
        st.subheader("Health Check")

        issues = []

        if "Salary" not in hitters_live.columns:
            issues.append(
                "Hitters sheet is missing Salary column"
            )
        elif hitters_live["Salary"].isna().sum() > 0:
            issues.append("Missing hitter salaries")

        if "Salary" not in pitchers_live.columns:
            issues.append(
                "Pitchers sheet is missing Salary column"
            )
        elif pitchers_live["Salary"].isna().sum() > 0:
            issues.append("Missing pitcher salaries")

        if (
            "DK Projection" in hitters_live.columns
            and hitters_live["DK Projection"]
            .isna()
            .sum()
            > 0
        ):
            issues.append(
                "Missing hitter DK projections"
            )

        if (
            "DK Projection" in pitchers_live.columns
            and pitchers_live["DK Projection"]
            .isna()
            .sum()
            > 0
        ):
            issues.append(
                "Missing pitcher DK projections"
            )

        if stacks_live.empty:
            issues.append("No valid stacks found")

        if not issues:
            st.success("All live data looks good ✅")
        else:
            for issue in issues:
                st.warning(issue)

else:
    with tab_pitchers:
        st.info("Upload projections to view pitchers.")

    with tab_hitters:
        st.info("Upload projections to view hitters.")

    with tab_stacks:
        st.info("Upload projections to view stacks.")

    with tab_builder:
        st.info(
            "Upload your Excel projection sheet "
            "to use the lineup builder."
        )

    with tab_health:
        st.info(
            "Upload projections to run health check."
        )