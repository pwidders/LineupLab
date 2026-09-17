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

    # Weekly Recap
    st.markdown("#### 🏈 Weekly Recap")

    recap = history.copy()
    if "slate_date" in recap.columns:
        recap["slate_date"] = pd.to_datetime(recap["slate_date"], errors="coerce")
        recap = recap.dropna(subset=["slate_date"])

        if not recap.empty:
            # NFL DFS week = Tuesday through Monday
            recap["week_start"] = (
                recap["slate_date"]
                - pd.to_timedelta(
                    (recap["slate_date"].dt.weekday - 1) % 7,
                    unit="D",
                )
            ).dt.normalize()

            recap["week_end"] = (
                recap["week_start"]
                + pd.Timedelta(days=6)
            )

            available_weeks = (
                recap[["week_start", "week_end"]]
                .drop_duplicates()
                .sort_values("week_start", ascending=False)
            )
            week_options = {
                f"{row.week_start.strftime('%b %d')}–{row.week_end.strftime('%b %d, %Y')}": row.week_start
                for row in available_weeks.itertuples(index=False)
            }
            selected_label = st.selectbox(
                "Recap Week", list(week_options.keys()), key="nfl_performance_recap_week"
            )
            selected_start = week_options[selected_label]
            selected_end = selected_start + pd.Timedelta(days=6)
            weekly = recap[
                (recap["slate_date"] >= selected_start)
                & (recap["slate_date"] <= selected_end)
            ].copy()

            weekly_entries = len(weekly)
            weekly_fees = float(weekly["entry_fee"].sum())
            weekly_winnings = float(weekly["winnings"].sum())
            weekly_profit = weekly_winnings - weekly_fees
            weekly_roi = weekly_profit / weekly_fees if weekly_fees > 0 else 0.0
            weekly_cash_rate = float((weekly["winnings"] > 0).mean()) if weekly_entries else 0.0
            weekly_avg_points = float(weekly["points"].mean()) if weekly_entries else 0.0

            recap_cards = st.columns(5)
            recap_cards[0].metric("Weekly Profit", _format_profit(weekly_profit))
            recap_cards[1].metric("Weekly ROI", f"{weekly_roi:.1%}")
            recap_cards[2].metric("Cash Rate", f"{weekly_cash_rate:.1%}")
            recap_cards[3].metric("Entries", f"{weekly_entries:,}")
            recap_cards[4].metric("Avg DK Points", f"{weekly_avg_points:.2f}")

            best_row = None
            if "rank" in weekly.columns and "field_size" in weekly.columns:
                weekly["rank"] = pd.to_numeric(weekly["rank"], errors="coerce")
                weekly["field_size"] = pd.to_numeric(weekly["field_size"], errors="coerce")
                valid = weekly[
                    weekly["rank"].notna()
                    & weekly["field_size"].notna()
                    & (weekly["field_size"] > 0)
                ].copy()
                if not valid.empty:
                    valid["finish_pct"] = valid["rank"] / valid["field_size"]
                    best_row = valid.sort_values("finish_pct").iloc[0]

            summary = [f"{weekly_entries} contest {'entry was' if weekly_entries == 1 else 'entries were'} tracked."]
            if weekly_fees > 0:
                summary.append(
                    f"Weekly result: {_format_profit(weekly_profit)} with a {weekly_roi:.1%} ROI."
                )
            else:
                summary.append(
                    "Entry fees and winnings have not been recorded yet, so profit and ROI are not meaningful for this week."
                )
            if best_row is not None:
                rank = int(best_row["rank"]); field_size = int(best_row["field_size"])
                top_pct = rank / field_size * 100
                detail = f"Best finish: {rank:,} of {field_size:,} (top {top_pct:.1f}%)"
                contest = str(best_row.get("contest_type", "") or "").strip()
                strategy = str(best_row.get("strategy", "") or "").strip()
                if contest: detail += f" in {contest}"
                if strategy: detail += f" using {strategy}"
                summary.append(detail + ".")
            st.info(" ".join(summary))

            weekly_cols = [c for c in [
                "slate_date", "contest_type", "strategy", "lineup_slot",
                "entry_fee", "winnings", "points", "rank", "field_size"
            ] if c in weekly.columns]
            st.caption("Weekly entries")
            st.dataframe(weekly[weekly_cols].sort_values("slate_date"), use_container_width=True, hide_index=True)
        else:
            st.caption("No dated NFL contest results are available for Weekly Recap.")
    else:
        st.caption("Weekly Recap requires slate_date in NFL contest history.")

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

