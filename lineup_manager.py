import streamlit as st
import pandas as pd
from datetime import datetime

WORKING_LINEUP_KEY = "current_lineup"
WORKING_SALARY_KEY = "current_salary"
WORKING_SCORE_KEY = "current_score"
WORKING_UPDATED_KEY = "current_updated_at"


def set_working_lineup(lineup: pd.DataFrame, salary: float, score: float) -> None:
    if lineup is None or lineup.empty:
        raise ValueError("Cannot set an empty working lineup.")

    st.session_state[WORKING_LINEUP_KEY] = lineup.copy()
    st.session_state[WORKING_SALARY_KEY] = float(salary)
    st.session_state[WORKING_SCORE_KEY] = float(score)
    st.session_state[WORKING_UPDATED_KEY] = datetime.now().strftime("%I:%M %p")


def has_working_lineup() -> bool:
    lineup = st.session_state.get(WORKING_LINEUP_KEY)
    return lineup is not None and not lineup.empty


def get_working_lineup():
    return (
        st.session_state.get(WORKING_LINEUP_KEY),
        float(st.session_state.get(WORKING_SALARY_KEY, 0)),
        float(st.session_state.get(WORKING_SCORE_KEY, 0)),
        st.session_state.get(WORKING_UPDATED_KEY, "Unknown"),
    )


def clear_working_lineup() -> None:
    for key in [
        WORKING_LINEUP_KEY,
        WORKING_SALARY_KEY,
        WORKING_SCORE_KEY,
        WORKING_UPDATED_KEY,
    ]:
        st.session_state.pop(key, None)


def get_working_player_names() -> list[str]:
    if not has_working_lineup():
        return []

    lineup = st.session_state[WORKING_LINEUP_KEY]
    return lineup["Player"].dropna().astype(str).tolist()


# Backward-compatible aliases for older modules.
save_lineup = set_working_lineup
has_saved_lineup = has_working_lineup
get_saved_lineup = get_working_lineup
clear_saved_lineup = clear_working_lineup
get_saved_player_names = get_working_player_names