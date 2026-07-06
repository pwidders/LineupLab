import streamlit as st


def render_slate_control_center(
    hitters_live,
    pitchers_live,
    stacks_live,
    combined_excluded_players,
    weather_risk_teams,
):
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