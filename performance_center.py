import pandas as pd
import streamlit as st

from contest_history_store import load_contest_history


def calculate_overall_metrics(history: pd.DataFrame) -> dict:
    """
    Calculate portfolio-level DFS performance metrics.

    Keeping calculations separate from Streamlit rendering allows
    this function to be reused later for filters, exports, and tests.
    """
    total_contests = len(history)

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
        if total_contests > 0
        else 0.0
    )

    average_points = (
        float(history["points"].mean())
        if "points" in history.columns
        else 0.0
    )

    # rank_percentile is stored as rank / field_size.
    # Subtracting from 1 converts it into a finish score:
    # 100% = best possible finish, 0% = last place.
    average_finish_percentile = (
        float((1 - history["rank_percentile"]).mean())
        if "rank_percentile" in history.columns
        else 0.0
    )

    return {
        "total_fees": total_fees,
        "total_winnings": total_winnings,
        "net_profit": net_profit,
        "roi": roi,
        "cash_rate": cash_rate,
        "total_contests": total_contests,
        "average_points": average_points,
        "average_finish_percentile": (
            average_finish_percentile
        ),
    }


def format_profit(value: float) -> str:
    if value > 0:
        return f"+${value:,.2f}"

    if value < 0:
        return f"-${abs(value):,.2f}"

    return "$0.00"


def render_performance_center():
    st.header("📊 Performance Center")

    try:
        history = load_contest_history()
    except Exception as exc:
        st.error(
            "Performance Center could not load your "
            f"contest history: {exc}"
        )
        return

    if history.empty:
        st.info(
            "No contest history has been saved yet. "
            "Upload a DraftKings contest export in "
            "Contest Review and save it to Contest History."
        )
        return

    metrics = calculate_overall_metrics(history)

    st.subheader("Overall Performance")

    row1 = st.columns(4)

    row1[0].metric(
        "Total Entry Fees",
        f"${metrics['total_fees']:,.2f}",
    )

    row1[1].metric(
        "Total Winnings",
        f"${metrics['total_winnings']:,.2f}",
    )

    row1[2].metric(
        "Net Profit",
        format_profit(metrics["net_profit"]),
    )

    row1[3].metric(
        "ROI",
        f"{metrics['roi']:.1%}",
    )

    row2 = st.columns(4)

    row2[0].metric(
        "Cash Rate",
        f"{metrics['cash_rate']:.1%}",
    )

    row2[1].metric(
        "Total Contests",
        f"{metrics['total_contests']:,}",
    )

    row2[2].metric(
        "Average DK Points",
        f"{metrics['average_points']:.2f}",
    )

    row2[3].metric(
        "Average Finish Percentile",
        f"{metrics['average_finish_percentile']:.1%}",
    )

    st.divider()

    st.subheader("Slate History")

    st.caption(
        "Slate-level results will be added in the next step."
    )