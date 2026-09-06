import pandas as pd
import streamlit as st

from nfl.contest_history_store import (
    load_nfl_contest_history,
)


def _format_profit(value: float) -> str:
    if value > 0:
        return f"+${value:,.2f}"
    if value < 0:
        return f"-${abs(value):,.2f}"
    return "$0.00"


def render_nfl_performance_center():
    st.subheader("📊 NFL Performance Center")
    st.markdown(
        '<div class="ll-section-rule"></div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "NFL Performance Center is connected to the dedicated "
        "nfl_contest_history table. Permanent contest saving will be enabled "
        "after the Week 1 DraftKings export format is validated."
    )

    try:
        history = load_nfl_contest_history()
    except Exception as exc:
        st.info(
            "NFL Performance Center is ready, but the contest-history "
            f"table is not available yet: {exc}"
        )
        return

    if history.empty:
        st.info(
            "No NFL contest history has been saved yet. "
            "This is expected before the first validated Week 1 import."
        )

        st.markdown("#### Planned v1 Analytics")
        st.write(
            "• Profit / ROI / Cash Rate\n"
            "• Contest performance\n"
            "• Strategy performance: Cash / Hybrid / GPP\n"
            "• Player and position performance\n"
            "• Projection vs actual DK points\n"
            "• QB stack performance\n"
            "• DST + RB correlation\n"
            "• Salary utilization and lineup construction"
        )
        return

    history = history.copy()

    for col in ["entry_fee", "winnings", "profit", "points"]:
        if col not in history.columns:
            history[col] = 0.0
        history[col] = pd.to_numeric(
            history[col],
            errors="coerce",
        ).fillna(0)

    total_entries = len(history)
    total_fees = float(history["entry_fee"].sum())
    total_winnings = float(history["winnings"].sum())
    net_profit = total_winnings - total_fees

    roi = (
        net_profit / total_fees
        if total_fees > 0
        else 0.0
    )

    cash_rate = (
        float((history["winnings"] > 0).mean())
        if total_entries > 0
        else 0.0
    )

    cards = st.columns(5)

    cards[0].metric(
        "Profit",
        _format_profit(net_profit),
    )
    cards[1].metric(
        "ROI",
        f"{roi:.1%}",
    )
    cards[2].metric(
        "Cash Rate",
        f"{cash_rate:.1%}",
    )
    cards[3].metric(
        "Entries",
        f"{total_entries:,}",
    )
    cards[4].metric(
        "Avg DK Points",
        f"{history['points'].mean():.2f}",
    )

    st.markdown("#### Saved NFL Contest History")

    display_cols = [
        col for col in [
            "slate_date",
            "contest_type",
            "entry_name",
            "strategy",
            "lineup_slot",
            "entry_fee",
            "winnings",
            "profit",
            "points",
            "rank",
            "field_size",
        ]
        if col in history.columns
    ]

    st.dataframe(
        history[display_cols],
        use_container_width=True,
        hide_index=True,
    )
