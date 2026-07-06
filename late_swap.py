import streamlit as st

from model import late_swap_optimizer
from lineup_manager import save_lineup
from render import render_lineup


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
):
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

    if not current_players:
        st.info("Build a lineup first or paste your current DK lineup to use Late Swap.")
        return

    unavailable_set = set(unavailable_players)

    kept_players = [p for p in current_players if p not in unavailable_set]
    scratched_from_lineup = [p for p in current_players if p in unavailable_set]

    st.write(f"Current lineup detected: **{len(current_players)} players**")
    st.write(f"Keeping: **{len(kept_players)}**")
    st.write(f"Replacing: **{len(scratched_from_lineup)}**")

    if scratched_from_lineup:
        st.warning(
            "Scratched/unavailable from current lineup: "
            + ", ".join(scratched_from_lineup)
        )

    if st.button("🔄 Late Swap Rebuild"):
        late_swap_salary_floor = st.number_input(
            "Minimum salary after late swap",
            min_value=0,
            max_value=50000,
            value=49000,
            step=100,
        )

        lineup, salary, score = late_swap_optimizer(
            hitters_live,
            pitchers_live,
            stacks_live,
            current_players,
            combined_excluded_players,
            min_salary=late_swap_salary_floor,
        )

        if lineup.empty:
            st.error(
                "No valid late swap found. Try unlocking one more player or relaxing constraints."
            )
            return

        st.success("Late swap completed ✅")
        render_lineup(lineup, salary, score)

        st.session_state["current_lineup"] = lineup.copy()
        save_lineup(lineup, salary, score)