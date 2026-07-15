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

def build_slate_history(history: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate contest history into one row per slate.

    This becomes the foundation for all drill-down analytics.
    """

    if history.empty:
        return pd.DataFrame()

    grouped = (
        history.groupby("slate_date", as_index=False)
        .agg(
            contests=("entry_name", "count"),
            total_fees=("entry_fee", "sum"),
            total_winnings=("winnings", "sum"),
            average_points=("points", "mean"),
        )
    )

    grouped["profit"] = (
        grouped["total_winnings"] - grouped["total_fees"]
    )

    grouped["roi"] = grouped.apply(
        lambda row:
            row["profit"] / row["total_fees"]
            if row["total_fees"] > 0
            else 0,
        axis=1,
    )

    grouped = grouped.sort_values(
        "slate_date",
        ascending=False,
    )

    return grouped


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

    slates = build_slate_history(history)

    if slates.empty:

        st.info("No slates found.")

    else:

        display = slates.copy()

        display["total_fees"] = display["total_fees"].map(
            lambda x: f"${x:.2f}"
        )

        display["total_winnings"] = display["total_winnings"].map(
            lambda x: f"${x:.2f}"
        )

        display["profit"] = display["profit"].map(
            format_profit
        )

        display["roi"] = display["roi"].map(
            lambda x: f"{x:.1%}"
        )

        display["average_points"] = display["average_points"].round(2)

        display["slate_date"] = pd.to_datetime(
            display["slate_date"]
        ).dt.strftime("%Y-%m-%d")

        display = display.rename(
            columns={
                "slate_date": "Slate Date",
                "contests": "Contests",
                "total_fees": "Total Fees",
                "total_winnings": "Total Winnings",
                "average_points": "Average Points",
                "profit": "Profit",
                "roi": "ROI",
            }
        )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Slate Details")

    slate_options = (
        slates["slate_date"]
        .dropna()
        .sort_values(ascending=False)
        .dt.strftime("%Y-%m-%d")
        .tolist()
    )

    selected_slate = st.selectbox(
        "Select a slate",
        options=slate_options,
        key="performance_selected_slate",
    )

    selected_date = pd.to_datetime(selected_slate).date()

    slate_contests = history[
        history["slate_date"].dt.date == selected_date
    ].copy()

    contest_display = slate_contests.copy()

    contest_display["Finish"] = (
        contest_display["rank"].astype(int).astype(str)
        + " / "
        + contest_display["field_size"].astype(int).astype(str)
    )

    contest_display["entry_fee"] = contest_display["entry_fee"].map(
        lambda x: f"${x:.2f}"
    )

    contest_display["winnings"] = contest_display["winnings"].map(
        lambda x: f"${x:.2f}"
    )

    contest_display["profit"] = contest_display["profit"].map(
        format_profit
    )

    contest_display["points"] = contest_display["points"].map(
        lambda x: f"{x:.2f}"
    )

    contest_display = contest_display[
        [
            "contest_type",
            "entry_name",
            "Finish",
            "points",
            "entry_fee",
            "winnings",
            "profit",
        ]
    ].rename(
        columns={
            "contest_type": "Contest",
            "entry_name": "Entry",
            "points": "DK Points",
            "entry_fee": "Fee",
            "winnings": "Winnings",
            "profit": "Profit",
        }
    )

    st.dataframe(
        contest_display,
        use_container_width=True,
        hide_index=True,
    )