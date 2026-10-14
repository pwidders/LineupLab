from io import BytesIO
from datetime import datetime

import pandas as pd


REPORT_VERSION = "NFL Algorithm Review Report v1.0"


def _safe_numeric(df, columns):
    df = df.copy()

    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            ).fillna(0)

    return df


def _profit_summary(df):
    if df.empty:
        return pd.DataFrame()

    entries = len(df)
    fees = float(df.get("entry_fee", pd.Series(dtype=float)).sum())
    winnings = float(df.get("winnings", pd.Series(dtype=float)).sum())
    profit = winnings - fees

    roi = profit / fees if fees > 0 else 0.0

    cash_rate = (
        float((df["winnings"] > 0).mean())
        if "winnings" in df.columns and entries
        else 0.0
    )

    avg_points = (
        float(df["points"].mean())
        if "points" in df.columns and entries
        else 0.0
    )

    return pd.DataFrame(
        [
            {
                "Entries": entries,
                "Entry Fees": fees,
                "Winnings": winnings,
                "Profit": profit,
                "ROI": roi,
                "Cash Rate": cash_rate,
                "Avg DK Points": avg_points,
            }
        ]
    )


def _group_performance(df, group_col):
    if df.empty or group_col not in df.columns:
        return pd.DataFrame()

    work = df.copy()

    work[group_col] = (
        work[group_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "Unknown")
    )

    rows = []

    for value, group in work.groupby(group_col):
        summary = _profit_summary(group)

        if summary.empty:
            continue

        row = summary.iloc[0].to_dict()
        row[group_col] = value
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)

    ordered_cols = [
        group_col,
        "Entries",
        "Entry Fees",
        "Winnings",
        "Profit",
        "ROI",
        "Cash Rate",
        "Avg DK Points",
    ]

    return result[ordered_cols].sort_values(
        ["Profit", "Avg DK Points"],
        ascending=[False, False],
    )


def _weekly_results(df):
    if df.empty or "slate_date" not in df.columns:
        return pd.DataFrame()

    work = df.copy()

    work["slate_date"] = pd.to_datetime(
        work["slate_date"],
        errors="coerce",
    )

    work = work.dropna(subset=["slate_date"])

    if work.empty:
        return pd.DataFrame()

    # NFL DFS week = Tuesday through Monday.
    work["Week Start"] = (
        work["slate_date"]
        - pd.to_timedelta(
            (work["slate_date"].dt.weekday - 1) % 7,
            unit="D",
        )
    ).dt.normalize()

    work["Week End"] = (
        work["Week Start"]
        + pd.Timedelta(days=6)
    )

    rows = []

    for (week_start, week_end), group in work.groupby(
        ["Week Start", "Week End"]
    ):
        summary = _profit_summary(group)

        if summary.empty:
            continue

        row = summary.iloc[0].to_dict()
        row["Week Start"] = week_start
        row["Week End"] = week_end
        rows.append(row)

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    ordered_cols = [
        "Week Start",
        "Week End",
        "Entries",
        "Entry Fees",
        "Winnings",
        "Profit",
        "ROI",
        "Cash Rate",
        "Avg DK Points",
    ]

    return result[ordered_cols].sort_values(
        "Week Start"
    )


def _explode_player_results(df):
    if df.empty or "player_results" not in df.columns:
        return pd.DataFrame()

    rows = []

    for contest_row, contest in df.iterrows():
        player_results = contest.get("player_results")

        if not isinstance(player_results, list):
            continue

        for player in player_results:
            if not isinstance(player, dict):
                continue

            rows.append(
                {
                    "Contest Row": contest_row,
                    "Slate Date": contest.get("slate_date"),
                    "Contest Type": contest.get("contest_type", ""),
                    "Strategy": contest.get("strategy", ""),
                    "Lineup Slot": contest.get("lineup_slot", ""),
                    "Lineup Points": contest.get("points", 0),
                    "Rank": contest.get("rank", 0),
                    "Field Size": contest.get("field_size", 0),
                    "Lineup Profit": contest.get("profit", 0),
                    "Player": player.get("player", ""),
                    "Slot": player.get("slot", ""),
                    "Position": player.get("position", ""),
                    "Team": player.get("team", ""),
                    "Opponent": player.get("opponent", ""),
                    "Salary": player.get("salary", 0),
                    "Projection": player.get("projection", 0),
                    "Cash Score": player.get("cash_score", 0),
                    "GPP Score": player.get("gpp_score", 0),
                }
            )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _player_exposure(player_df, total_lineups=None):
    if player_df.empty:
        return pd.DataFrame()

    work = player_df.copy()

    for col in [
        "Lineup Points",
        "Lineup Profit",
        "Salary",
        "Projection",
        "Cash Score",
        "GPP Score",
    ]:
        if col in work.columns:
            work[col] = pd.to_numeric(
                work[col],
                errors="coerce",
            ).fillna(0)

    result = (
        work.groupby(
            ["Player", "Position", "Team"],
            dropna=False,
        )
        .agg(
            Lineups=("Player", "size"),
            Avg_Lineup_Points=("Lineup Points", "mean"),
            Total_Lineup_Profit=("Lineup Profit", "sum"),
            Avg_Salary=("Salary", "mean"),
            Avg_Projection=("Projection", "mean"),
            Avg_Cash_Score=("Cash Score", "mean"),
            Avg_GPP_Score=("GPP Score", "mean"),
        )
        .reset_index()
    )

    if total_lineups is None:
        total_lineups = max(
            work["Contest Row"].nunique(),
            1,
        )

    result["Exposure"] = (
        result["Lineups"] / total_lineups
    )

    return result.sort_values(
        ["Lineups", "Avg_Lineup_Points"],
        ascending=[False, False],
    )


def _position_exposure(
    player_df,
    position,
    total_lineups,
):
    if player_df.empty or "Position" not in player_df.columns:
        return pd.DataFrame()

    subset = player_df[
        player_df["Position"]
        .fillna("")
        .astype(str)
        .str.upper()
        .eq(position.upper())
    ].copy()

    return _player_exposure(
        subset,
        total_lineups=total_lineups,
    )


def _lineup_analysis(df):
    if df.empty:
        return pd.DataFrame()

    preferred_cols = [
        "slate_date",
        "contest_type",
        "entry_name",
        "strategy",
        "lineup_slot",
        "salary",
        "projected_score",
        "optimizer_score",
        "points",
        "rank",
        "field_size",
        "rank_percentile",
        "entry_fee",
        "winnings",
        "profit",
        "lineup",
        "lineup_id",
    ]

    cols = [
        col
        for col in preferred_cols
        if col in df.columns
    ]

    result = df[cols].copy()

    if (
        "points" in result.columns
        and "projected_score" in result.columns
    ):
        result["Projection Error"] = (
            result["points"]
            - result["projected_score"]
        )

    return result


def build_nfl_algorithm_review_report(
    history: pd.DataFrame,
) -> bytes:
    """
    Build the NFL Algorithm Review Report as an in-memory XLSX file.
    """

    if history is None or history.empty:
        raise ValueError(
            "NFL contest history is empty. "
            "There is nothing to include in the report."
        )

    history = _safe_numeric(
        history,
        [
            "rank",
            "field_size",
            "points",
            "rank_percentile",
            "salary",
            "projected_score",
            "optimizer_score",
            "entry_fee",
            "winnings",
            "profit",
        ],
    )

    player_df = _explode_player_results(history)

    tracked_lineups = max(
        player_df["Contest Row"].nunique(),
        1,
    )

    summary = _profit_summary(history)
    weekly = _weekly_results(history)
    strategy = _group_performance(history, "strategy")
    contest_type = _group_performance(
        history,
        "contest_type",
    )
    
    player_exposure = _player_exposure(
        player_df,
        total_lineups=tracked_lineups,
    )

    qb_exposure = _position_exposure(
        player_df,
        "QB",
        total_lineups=tracked_lineups,
    )

    dst_exposure = _position_exposure(
        player_df,
        "DST",
        total_lineups=tracked_lineups,
    )
    lineup_analysis = _lineup_analysis(history)

    version = pd.DataFrame(
        [
            {
                "Report": REPORT_VERSION,
                "Generated At": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "Contest Records": len(history),
                "Player Result Rows": len(player_df),
                "Notes": (
                    "Player/QB/DST sheets measure exposure and the "
                    "performance of lineups containing those players. "
                    "Individual player FPTS and ownership are not analyzed "
                    "because those fields are not yet populated reliably "
                    "in NFL contest history."
                ),
            }
        ]
    )

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:
        summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )

        weekly.to_excel(
            writer,
            sheet_name="Weekly Results",
            index=False,
        )

        lineup_analysis.to_excel(
            writer,
            sheet_name="Contest Results",
            index=False,
        )

        strategy.to_excel(
            writer,
            sheet_name="Strategy Results",
            index=False,
        )

        contest_type.to_excel(
            writer,
            sheet_name="Contest Type Results",
            index=False,
        )

        player_exposure.to_excel(
            writer,
            sheet_name="Player Exposure",
            index=False,
        )

        qb_exposure.to_excel(
            writer,
            sheet_name="QB Exposure",
            index=False,
        )

        dst_exposure.to_excel(
            writer,
            sheet_name="DST Exposure",
            index=False,
        )

        lineup_analysis.to_excel(
            writer,
            sheet_name="Lineup Analysis",
            index=False,
        )

        history.to_excel(
            writer,
            sheet_name="Raw History",
            index=False,
        )

        version.to_excel(
            writer,
            sheet_name="Version",
            index=False,
        )

    output.seek(0)
    return output.getvalue()