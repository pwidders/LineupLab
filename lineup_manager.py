import streamlit as st
import pandas as pd
from datetime import datetime


def save_lineup(lineup: pd.DataFrame, salary: float, score: float) -> None:
    st.session_state["saved_lineup"] = lineup.copy()
    st.session_state["saved_salary"] = salary
    st.session_state["saved_score"] = score
    st.session_state["saved_at"] = datetime.now().strftime("%I:%M %p")


def has_saved_lineup() -> bool:
    return "saved_lineup" in st.session_state


def get_saved_lineup():
    return (
        st.session_state.get("saved_lineup"),
        st.session_state.get("saved_salary", 0),
        st.session_state.get("saved_score", 0),
        st.session_state.get("saved_at", "Unknown"),
    )


def clear_saved_lineup() -> None:
    for key in ["saved_lineup", "saved_salary", "saved_score", "saved_at"]:
        if key in st.session_state:
            del st.session_state[key]


def get_saved_player_names() -> list[str]:
    if not has_saved_lineup():
        return []

    lineup = st.session_state["saved_lineup"]
    return lineup["Player"].dropna().astype(str).tolist()