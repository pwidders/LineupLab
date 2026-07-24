import altair as alt
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


def build_player_history(history: pd.DataFrame) -> pd.DataFrame:
    """
    Flatten player_results JSON from contest history into
    one row per player appearance.
    """

    if history.empty or "player_results" not in history.columns:
        return pd.DataFrame()

    player_rows = []

    for _, contest in history.iterrows():
        results = contest.get("player_results")

        if not isinstance(results, list):
            continue

        for player in results:
            if not isinstance(player, dict):
                continue

            player_rows.append(
                {
                    "player": player.get("player", ""),
                    "roster_position": player.get(
                        "roster_position",
                        "",
                    ),
                    "ownership": player.get("ownership", 0),
                    "fpts": player.get("fpts", 0),
                    "slate_date": contest.get("slate_date"),
                    "contest_type": contest.get("contest_type"),
                    "entry_fee": contest.get("entry_fee", 0),
                    "winnings": contest.get("winnings", 0),
                    "profit": contest.get("profit", 0),
                    "lineup_id": contest.get("lineup_id"),
                }
            )

    if not player_rows:
        return pd.DataFrame()

    players = pd.DataFrame(player_rows)

    players["ownership"] = pd.to_numeric(
        players["ownership"],
        errors="coerce",
    ).fillna(0)

    players["fpts"] = pd.to_numeric(
        players["fpts"],
        errors="coerce",
    ).fillna(0)

    players["player_key"] = (
        players["player"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    players = players.drop_duplicates(
        subset=[
            "slate_date",
            "contest_type",
            "lineup_id",
            "player_key",
        ],
        keep="first",
    )

    players = players.drop(columns=["player_key"])

    return players

def format_profit(value: float) -> str:
    if value > 0:
        return f"+${value:,.2f}"

    if value < 0:
        return f"-${abs(value):,.2f}"

    return "$0.00"


def render_performance_center():
    st.header("📊 Performance Dashboard")

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

    st.subheader("At a Glance")

    cards = st.columns(5)

    cards[0].metric(
        "Lifetime Profit",
        format_profit(metrics["net_profit"]),
    )

    cards[1].metric(
        "ROI",
        f"{metrics['roi']:.1%}",
    )

    cards[2].metric(
        "Cash Rate",
        f"{metrics['cash_rate']:.1%}",
    )

    cards[3].metric(
        "Entries",
        f"{metrics['total_contests']:,}",
    )

    cards[4].metric(
        "Average DK Points",
        f"{metrics['average_points']:.2f}",
    )

    st.divider()

    st.subheader("📈 Bankroll Curve")

    slates = build_slate_history(history)

    if slates.empty:
        st.info("No slates found.")
    else:
        profit_curve = (
            slates[
                ["slate_date", "profit"]
            ]
            .copy()
            .sort_values("slate_date")
        )

        profit_curve["slate_date"] = pd.to_datetime(
            profit_curve["slate_date"],
            errors="coerce",
        )

        profit_curve = profit_curve.dropna(
            subset=["slate_date"]
        )

        profit_curve["cumulative_profit"] = (
            profit_curve["profit"].cumsum()
        )

        bankroll_chart = (
            alt.Chart(profit_curve)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "slate_date:T",
                    title="Slate Date",
                    axis=alt.Axis(
                        format="%b %d",
                        labelAngle=0,
                    ),
                ),
                y=alt.Y(
                    "cumulative_profit:Q",
                    title="Profit ($)",
                ),
                tooltip=[
                    alt.Tooltip(
                        "slate_date:T",
                        title="Slate",
                        format="%b %d, %Y",
                    ),
                    alt.Tooltip(
                        "profit:Q",
                        title="Slate Profit",
                        format="$.2f",
                    ),
                    alt.Tooltip(
                        "cumulative_profit:Q",
                        title="Running Profit",
                        format="$.2f",
                    ),
                ],
            )
            .properties(height=280)
        )

        st.altair_chart(
            bankroll_chart,
            use_container_width=True,
        )

        st.caption(
            "Each point reflects your running lifetime profit "
            "after all contests from that slate are included."
        )

    st.markdown("### 🏟 Contest Performance")

    contest_performance = history.copy()

    contest_performance["roi"] = contest_performance.apply(
        lambda row: (
            row["profit"] / row["entry_fee"]
            if row["entry_fee"] > 0
            else 0.0
        ),
        axis=1,
    )

    contest_performance["finish"] = (
        contest_performance["rank"].astype(int).astype(str)
        + " / "
        + contest_performance["field_size"].astype(int).astype(str)
    )

    contest_performance["cash_result"] = (
        contest_performance["winnings"] > 0
    ).map(
        {
            True: "✅",
            False: "❌",
        }
    )

    contest_performance = contest_performance.sort_values(
        ["slate_date", "contest_type"],
        ascending=[False, True],
    )

    contest_display = contest_performance[
        [
            "slate_date",
            "contest_type",
            "entry_name",
            "entry_fee",
            "winnings",
            "profit",
            "roi",
            "points",
            "finish",
            "cash_result",
        ]
    ].copy()

    contest_display["slate_date"] = pd.to_datetime(
        contest_display["slate_date"]
    ).dt.strftime("%Y-%m-%d")

    contest_display["entry_fee"] = contest_display["entry_fee"].map(
        lambda value: f"${value:.2f}"
    )

    contest_display["winnings"] = contest_display["winnings"].map(
        lambda value: f"${value:.2f}"
    )

    contest_display["profit"] = contest_display["profit"].map(
        format_profit
    )

    contest_display["roi"] = contest_display["roi"].map(
        lambda value: f"{value:.1%}"
    )

    contest_display["points"] = contest_display["points"].map(
        lambda value: f"{value:.2f}"
    )

    contest_display = contest_display.rename(
        columns={
            "slate_date": "Slate",
            "contest_type": "Contest",
            "entry_name": "Entry",
            "entry_fee": "Fee",
            "winnings": "Won",
            "profit": "Profit",
            "roi": "ROI",
            "points": "DK Points",
            "finish": "Finish",
            "cash_result": "Cash",
        }
    )

    st.dataframe(
        contest_display,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Player Analytics")

    players = build_player_history(history)

    if players.empty:
        st.info(
            "Player analytics will appear after contests "
            "with player-results data are saved."
        )
        return

    player_summary = (
        players.groupby("player", as_index=False)
        .agg(
            times_used=("player", "size"),
            average_fpts=("fpts", "mean"),
            average_ownership=("ownership", "mean"),
        )
    )

    player_summary = player_summary[
        player_summary["player"].astype(str).str.strip() != ""
    ]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### Most Used Players")

        most_used = (
            player_summary.sort_values(
                ["times_used", "average_fpts"],
                ascending=[False, False],
            )
            .head(10)
            .rename(
                columns={
                    "player": "Player",
                    "times_used": "Uses",
                }
            )
        )

        st.dataframe(
            most_used[["Player", "Uses"]],
            use_container_width=True,
            hide_index=True,
        )

    with col2:
        st.markdown("#### Highest Average DK Points")

        best_fpts = (
            player_summary.sort_values(
                "average_fpts",
                ascending=False,
            )
            .head(10)
            .copy()
        )

        best_fpts["average_fpts"] = (
            best_fpts["average_fpts"].round(2)
        )

        best_fpts = best_fpts.rename(
            columns={
                "player": "Player",
                "average_fpts": "Avg DK Points",
            }
        )

        st.dataframe(
            best_fpts[["Player", "Avg DK Points"]],
            use_container_width=True,
            hide_index=True,
        )

    with col3:
        st.markdown("#### Highest Average Ownership")

        highest_owned = (
            player_summary.sort_values(
                "average_ownership",
                ascending=False,
            )
            .head(10)
            .copy()
        )

        highest_owned["average_ownership"] = (
            highest_owned["average_ownership"].map(
                lambda value: f"{value:.1f}%"
            )
        )

        highest_owned = highest_owned.rename(
            columns={
                "player": "Player",
                "average_ownership": "Avg Ownership",
            }
        )

        st.dataframe(
            highest_owned[
                ["Player", "Avg Ownership"]
            ],
            use_container_width=True,
            hide_index=True,
        )