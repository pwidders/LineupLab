import streamlit as st
from supabase import create_client


TABLE_NAME = "slate_settings"

LOADED_SLATE_KEY = "_loaded_slate_settings_key"


def _client():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_KEY"],
    )


def load_settings(slate_date: str, slate_name: str) -> dict:
    result = (
        _client()
        .table(TABLE_NAME)
        .select("*")
        .eq("slate_date", slate_date)
        .eq("slate_name", slate_name)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return {
        "weather_teams": [],
        "unavailable_players": [],
        "locked_players": [],
        "excluded_players": [],
    }


def save_settings(
    slate_date: str,
    slate_name: str,
    weather_teams: list[str],
    unavailable_players: list[str],
    locked_players: list[str],
    excluded_players: list[str],
) -> None:
    record = {
        "slate_date": slate_date,
        "slate_name": slate_name,
        "weather_teams": list(weather_teams),
        "unavailable_players": list(unavailable_players),
        "locked_players": list(locked_players),
        "excluded_players": list(excluded_players),
    }

    (
        _client()
        .table(TABLE_NAME)
        .upsert(
            record,
            on_conflict="slate_date,slate_name",
        )
        .execute()
    )


def initialize_slate_settings(
    slate_date: str,
    slate_name: str,
    all_players: list[str],
    all_teams: list[str],
) -> None:
    """
    Load Supabase settings into Streamlit session state.

    This runs only when the selected slate changes. It must be called
    after the projection sheet has created all_players and all_teams,
    but before the multiselect widgets are rendered.
    """
    current_slate_key = f"{slate_date}|{slate_name}"

    if (
        st.session_state.get(LOADED_SLATE_KEY)
        == current_slate_key
    ):
        return

    settings = load_settings(
        slate_date,
        slate_name,
    )

    player_options = set(all_players)
    team_options = set(all_teams)

    st.session_state["locked_players"] = [
        player
        for player in settings.get("locked_players", [])
        if player in player_options
    ]

    st.session_state["excluded_players"] = [
        player
        for player in settings.get("excluded_players", [])
        if player in player_options
    ]

    st.session_state["unavailable_players"] = [
        player
        for player in settings.get("unavailable_players", [])
        if player in player_options
    ]

    st.session_state["weather_risk_teams"] = [
        team
        for team in settings.get("weather_teams", [])
        if team in team_options
    ]

    st.session_state[LOADED_SLATE_KEY] = current_slate_key


def persist_slate_settings(
    slate_date: str,
    slate_name: str,
) -> None:
    """
    Save the current Streamlit widget selections to Supabase.
    """
    save_settings(
        slate_date=slate_date,
        slate_name=slate_name,
        weather_teams=st.session_state.get(
            "weather_risk_teams",
            [],
        ),
        unavailable_players=st.session_state.get(
            "unavailable_players",
            [],
        ),
        locked_players=st.session_state.get(
            "locked_players",
            [],
        ),
        excluded_players=st.session_state.get(
            "excluded_players",
            [],
        ),
    )