from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

WORKING_LINEUP_KEY = "current_lineup"
WORKING_SALARY_KEY = "current_salary"
WORKING_SCORE_KEY = "current_score"
WORKING_UPDATED_KEY = "current_updated_at"
WORKING_ACTION_KEY = "current_last_action"
WORKING_SYNC_STATUS_KEY = "working_lineup_sync_status"
WORKING_SYNC_ERROR_KEY = "working_lineup_sync_error"
WORKING_SLATE_DATE_KEY = "working_lineup_slate_date"
WORKING_SLATE_NAME_KEY = "working_lineup_slate_name"


def configure_working_lineup_cloud(slate_date: str, slate_name: str) -> None:
    """Tell the manager which slate should receive automatic cloud saves."""
    st.session_state[WORKING_SLATE_DATE_KEY] = str(slate_date)
    st.session_state[WORKING_SLATE_NAME_KEY] = str(slate_name).strip() or "Main"


def _local_timestamp() -> str:
    return (
        datetime.now(ZoneInfo("America/Los_Angeles"))
        .strftime("%b %d • %I:%M %p")
    )


def set_working_lineup(
    lineup: pd.DataFrame,
    salary: float,
    score: float,
    last_action: str = "Working Lineup Update",
    sync_to_cloud: bool = True,
) -> None:
    """Set the live lineup locally and automatically persist it to Supabase."""
    if lineup is None or lineup.empty:
        raise ValueError("Cannot set an empty working lineup.")

    st.session_state[WORKING_LINEUP_KEY] = lineup.copy()
    st.session_state[WORKING_SALARY_KEY] = float(salary)
    st.session_state[WORKING_SCORE_KEY] = float(score)
    st.session_state[WORKING_UPDATED_KEY] = _local_timestamp()
    st.session_state[WORKING_ACTION_KEY] = (
        str(last_action).strip() or "Working Lineup Update"
    )

    if not sync_to_cloud:
        return

    slate_date = st.session_state.get(WORKING_SLATE_DATE_KEY)
    slate_name = st.session_state.get(WORKING_SLATE_NAME_KEY)
    if not slate_date or not slate_name:
        st.session_state[WORKING_SYNC_STATUS_KEY] = "local_only"
        return

    st.session_state[WORKING_SYNC_STATUS_KEY] = "saving"
    st.session_state.pop(WORKING_SYNC_ERROR_KEY, None)

    try:
        from cloud_lineup_store import save_cloud_working_lineup

        save_cloud_working_lineup(
            lineup=lineup,
            salary=salary,
            projected_score=score,
            slate_date=slate_date,
            slate_name=slate_name,
            last_action=last_action,
        )
        st.session_state[WORKING_SYNC_STATUS_KEY] = "synced"
    except Exception as exc:
        # Keep the local lineup usable even if Supabase is temporarily unavailable.
        st.session_state[WORKING_SYNC_STATUS_KEY] = "error"
        st.session_state[WORKING_SYNC_ERROR_KEY] = str(exc)


def restore_working_lineup_from_cloud(
    slate_date: str,
    slate_name: str,
) -> bool:
    """Restore a slate's live working lineup into Streamlit session state."""
    from cloud_lineup_store import load_cloud_working_lineup

    try:
        lineup, salary, score, record = load_cloud_working_lineup(
            slate_date,
            slate_name,
        )
    except FileNotFoundError:
        return False

    set_working_lineup(
        lineup,
        salary,
        score,
        last_action=record.get("last_action") or "Restored from Cloud",
        sync_to_cloud=False,
    )
    st.session_state[WORKING_SYNC_STATUS_KEY] = "synced"
    st.session_state[WORKING_ACTION_KEY] = (
        record.get("last_action") or "Restored from Cloud"
    )
    return True


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


def get_working_lineup_status() -> tuple[str, str, str | None]:
    return (
        st.session_state.get(WORKING_SYNC_STATUS_KEY, "local_only"),
        st.session_state.get(WORKING_ACTION_KEY, "Working Lineup Update"),
        st.session_state.get(WORKING_SYNC_ERROR_KEY),
    )


def clear_working_lineup(clear_cloud: bool = False) -> None:
    slate_date = st.session_state.get(WORKING_SLATE_DATE_KEY)
    slate_name = st.session_state.get(WORKING_SLATE_NAME_KEY)

    for key in [
        WORKING_LINEUP_KEY,
        WORKING_SALARY_KEY,
        WORKING_SCORE_KEY,
        WORKING_UPDATED_KEY,
        WORKING_ACTION_KEY,
        WORKING_SYNC_STATUS_KEY,
        WORKING_SYNC_ERROR_KEY,
    ]:
        st.session_state.pop(key, None)

    if clear_cloud and slate_date and slate_name:
        from cloud_lineup_store import delete_cloud_working_lineup
        delete_cloud_working_lineup(slate_date, slate_name)


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
