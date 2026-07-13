import streamlit as st

from lineup_manager import (
    get_working_lineup,
    has_working_lineup,
    set_working_lineup,
)
from model import late_swap_optimizer


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


def render_late_swap_assistant(
    hitters_live,
    pitchers_live,
    stacks_live,
    unavailable_players,
    combined_excluded_players,
    manual_locked_players=None,
):
    st.subheader("Late Swap Assistant")

    pasted_lineup = st.text_area(
        "Optional: paste current DK lineup here",
        placeholder="P - Player Name\nP - Player Name\nC - Player Name...",
    )

    if pasted_lineup.strip():
        current_players = parse_pasted_lineup(pasted_lineup)
    elif has_working_lineup():
        working_lineup, _, _, _ = get_working_lineup()
        current_players = (
            working_lineup["Player"]
            .dropna()
            .astype(str)
            .tolist()
        )
    else:
        current_players = []

    if not current_players:
        st.info(
            "Load a lineup from the Vault, build a lineup, "
            "or paste a current DK lineup to use Late Swap."
        )
        return

    unavailable_set = {
        str(player).strip()
        for player in unavailable_players
        if str(player).strip()
    }

    kept_players = [
        player
        for player in current_players
        if player not in unavailable_set
    ]
    scratched_from_lineup = [
        player
        for player in current_players
        if player in unavailable_set
    ]

    st.write(f"Current lineup detected: **{len(current_players)} players**")
    st.write(f"Keeping: **{len(kept_players)}**")
    st.write(f"Replacing: **{len(scratched_from_lineup)}**")

    if scratched_from_lineup:
        st.warning(
            "Scratched/unavailable from current lineup: "
            + ", ".join(scratched_from_lineup)
        )

    late_swap_salary_floor = st.number_input(
        "Minimum salary after late swap",
        min_value=0,
        max_value=50000,
        value=49000,
        step=100,
        key="late_swap_salary_floor",
    )

    if st.button("🔄 Late Swap Rebuild", key="late_swap_rebuild"):
        lineup, salary, score = late_swap_optimizer(
            hitters_live,
            pitchers_live,
            stacks_live,
            current_players,
            combined_excluded_players,
            min_salary=late_swap_salary_floor,
            manual_locked_players=manual_locked_players,
        )

        if lineup.empty:
            st.error(
                "No valid late swap found. Try unlocking one more player "
                "or relaxing constraints."
            )
            return

        set_working_lineup(lineup, salary, score)
        st.session_state["working_lineup_notice"] = "Late swap completed ✅"
        st.rerun()