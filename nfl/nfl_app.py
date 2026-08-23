import streamlit as st
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from nfl.data_loader import (
    load_dk_salaries,
    merge_with_baselines,
    merge_with_dst_baselines,
)

from nfl.nflverse_loader import (
    get_recent_baselines,
    get_recent_dst_baselines,
)

from nfl.projections import (
    add_ll_projections,
    add_optimizer_scores,
    add_strategy_projections,
)

from nfl.odds_loader import (
    load_nfl_odds,
    normalize_odds_teams,
)

from nfl.game_environment import (
    build_game_environment,
    merge_odds_into_environment,
    add_game_script_score,
    build_dst_rb_pairings,
    merge_environment_into_players,
    build_qb_pass_catcher_stacks,
)

from nfl.optimizer import optimize_lineup, optimize_portfolio

st.set_page_config(
    page_title="LineupLab NFL",
    page_icon="🏈",
    layout="wide",
)

st.title("🏈 LineupLab NFL")
st.caption("NFL DFS Projection & Portfolio Lab")

st.divider()

st.subheader("DraftKings Player Pool")

uploaded_file = st.file_uploader(
    "Upload DraftKings NFL salary CSV",
    type=["csv"],
)

if uploaded_file is None:
    st.info("Upload a DraftKings NFL salary CSV to begin.")
    st.stop()

try:
    players = load_dk_salaries(uploaded_file)

    with st.spinner("Loading recent NFL player baselines..."):
        baselines = get_recent_baselines([2025])

    players = merge_with_baselines(players, baselines)
    with st.spinner("Loading recent NFL defense baselines..."):
        dst_baselines = get_recent_dst_baselines([2025])

    players = merge_with_dst_baselines(
        players,
        dst_baselines,
    )
    players = add_ll_projections(players)

except Exception as e:
    st.error(f"Could not load DraftKings salaries: {e}")
    st.stop()

st.success(f"Loaded {len(players)} NFL players.")

# -----------------------------
# Slate summary
# -----------------------------

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("QB", len(players[players["position"] == "QB"]))
col2.metric("RB", len(players[players["position"] == "RB"]))
col3.metric("WR", len(players[players["position"] == "WR"]))
col4.metric("TE", len(players[players["position"] == "TE"]))
col5.metric("DST", len(players[players["position"] == "DST"]))

st.divider()

game_environment = build_game_environment(players)

with st.spinner("Loading NFL Vegas lines..."):
    odds = load_nfl_odds(
        st.secrets["ODDS_API_KEY"],
        "2026-09-13T00:00:00Z",
        "2026-09-14T04:00:00Z",
    )

    odds = normalize_odds_teams(odds)

game_environment = merge_odds_into_environment(
    game_environment,
    odds,
)

game_environment = add_game_script_score(
    game_environment
)

players = merge_environment_into_players(
    players,
    game_environment,
)

players = add_ll_projections(players)
players = add_optimizer_scores(players)
players = add_strategy_projections(players)

st.subheader("Game Environment")

st.dataframe(
    game_environment,
    use_container_width=True,
    hide_index=True,
)

st.subheader("DST / RB Pairings")

pairings = build_dst_rb_pairings(
    players,
    game_environment,
)

pairing_display = pairings[
    [
        "player_dst",
        "player_rb",
        "team",
        "spread_dst",
        "team_implied_total_dst",
        "opponent_implied_total_dst",
        "ll_projection_dst",
        "ll_projection_rb",
        "game_script_score_dst",
        "pair_score",
    ]
].head(20)

st.dataframe(
    pairing_display,
    use_container_width=True,
    hide_index=True,
)

st.subheader("QB / Pass Catcher Stacks")

stacks = build_qb_pass_catcher_stacks(players)

stack_display = stacks[
    [
        "player_qb",
        "player_pc",
        "position_pc",
        "team",
        "game_total_qb",
        "team_implied_total_qb",
        "spread_qb",
        "ll_projection_qb",
        "ll_projection_pc",
        "game_script_score_qb",
        "stack_score",
    ]
].head(25)

st.dataframe(
    stack_display,
    use_container_width=True,
    hide_index=True,
)

# --------------------------
# Filters
# --------------------------

# -----------------------------
# Optimizer Rankings
# -----------------------------

st.subheader("Optimizer Rankings")

ranking_position = st.selectbox(
    "Ranking Position",
    ["QB", "RB", "WR", "TE", "DST"],
    index=1,
)

ranking_cols = [
    "player",
    "position",
    "team",
    "opponent",
    "salary",
    "ll_projection",
    "ll_floor",
    "ll_ceiling",
    "ll_value",
    "cash_score",
    "gpp_score",
]

ranking_display = (
    players[
        players["position"] == ranking_position
    ][ranking_cols]
    .sort_values(
        "cash_score",
        ascending=False,
    )
    .head(20)
)

st.dataframe(
    ranking_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "player": "Player",
        "position": "Pos",
        "team": "Team",
        "opponent": "Opp",

        "salary": st.column_config.NumberColumn(
            "Salary",
            format="$%d",
        ),

        "ll_projection": st.column_config.NumberColumn(
            "LL Proj",
            format="%.1f",
        ),

        "ll_floor": st.column_config.NumberColumn(
            "Floor",
            format="%.1f",
        ),

        "ll_ceiling": st.column_config.NumberColumn(
            "Ceiling",
            format="%.1f",
        ),

        "ll_value": st.column_config.NumberColumn(
            "Value",
            format="%.2f",
        ),

        "cash_score": st.column_config.NumberColumn(
            "Cash",
            format="%.1f",
        ),

        "gpp_score": st.column_config.NumberColumn(
            "GPP",
            format="%.1f",
        ),
    },
)

# -------------------------
# Lineup Optimizer
# -------------------------

st.subheader("Lineup Optimizer")

strategy = st.selectbox(
    "Strategy",
    ["Cash", "GPP"],
)

min_salary = st.number_input(
    "Minimum Salary",
    min_value=0,
    max_value=50000,
    value=49000,
    step=100,
)

require_qb_stack = False
qb_stack_size = 1
min_stack_partner_gpp_score = 0.0
require_dst_rb = False

if strategy == "GPP":

    require_qb_stack = st.checkbox(
        "Require QB + WR/TE stack",
        value=True,
    )

    qb_stack_size = st.selectbox(
        "QB Stack Size",
        options=[1, 2],
        index=0,
        format_func=lambda value: (
            "QB + 1 pass catcher"
            if value == 1
            else "QB + 2 pass catchers"
        ),
        help="Minimum number of same-team WR/TE players required with the QB.",
        disabled=not require_qb_stack,
    )

    min_stack_partner_gpp_score = st.number_input(
        "Minimum Stack Partner GPP Score",
        min_value=0.0,
        max_value=100.0,
        value=80.0,
        step=1.0,
        help=(
            "Same-team WR/TE players used to satisfy the QB stack must meet "
            "at least this GPP score. Set to 0 to disable."
        ),
        disabled=not require_qb_stack,
    )

    require_dst_rb = st.checkbox(
        "Pair DST with same-team RB",
        value=True,
    )

if st.button("Build Lineup"):

    with st.spinner(
        f"Building {strategy} lineup..."
    ):

        lineup = optimize_lineup(
            players,
            strategy=strategy,
            min_salary=min_salary,
            require_qb_stack=require_qb_stack,
            qb_stack_size=int(qb_stack_size),
            require_dst_rb=require_dst_rb,
            min_stack_partner_gpp_score=float(min_stack_partner_gpp_score),
        )

    if lineup is None:

        st.error(
            "No valid lineup found. Try lowering the minimum salary "
            "or relaxing correlation rules."
        )

    else:

        st.success(
            f"{strategy} lineup built!"
        )

        lineup_display = lineup[
            [
                "slot",
                "player",
                "position",
                "team",
                "opponent",
                "salary",
                "ll_projection",
                "cash_projection",
                "gpp_projection",
                "cash_score",
                "gpp_score",
            ]
        ].copy()

        st.dataframe(
            lineup_display,
            width="stretch",
            hide_index=True,
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Salary",
            f"${lineup.attrs['total_salary']:,.0f}",
        )

        col2.metric(
            "Projected Points",
            f"{lineup.attrs['total_projection']:.1f}",
        )

        col3.metric(
            "Salary Remaining",
            f"${50000 - lineup.attrs['total_salary']:,.0f}",
        )

        col4.metric(
            "Strategy Projection",
            f"{lineup.attrs['optimizer_score']:.1f}",
        )


# -------------------------
# 3-Lineup Portfolio Builder
# -------------------------

st.subheader("3-Lineup Portfolio Builder")
st.caption(
    "Build three correlated GPP lineups while limiting player overlap "
    "between every pair of lineups."
)

portfolio_col1, portfolio_col2, portfolio_col3 = st.columns(3)

with portfolio_col1:
    portfolio_min_salary = st.number_input(
        "Portfolio Minimum Salary",
        min_value=0,
        max_value=50000,
        value=49000,
        step=100,
        key="portfolio_min_salary",
    )

with portfolio_col2:
    portfolio_max_overlap = st.number_input(
        "Max Shared Players",
        min_value=0,
        max_value=8,
        value=6,
        step=1,
        key="portfolio_max_overlap",
        help="Maximum number of players any two portfolio lineups may share.",
    )

with portfolio_col3:
    portfolio_max_qb_exposure = st.number_input(
        "Max QB Exposure",
        min_value=1,
        max_value=3,
        value=2,
        step=1,
        key="portfolio_max_qb_exposure",
        help="Maximum number of the 3 portfolio lineups that may use the same QB.",
    )

st.markdown("#### Automatic Exposure Tiers")

use_auto_exposure_tiers = st.checkbox(
    "Use automatic player exposure tiers",
    value=True,
    key="portfolio_auto_exposure",
    help=(
        "Elite/Core (GPP score 95+) may appear in 3 lineups; "
        "Strong (90-94.9) in up to 2; Secondary (<90) in up to 1. "
        "Manual player overrides below take priority."
    ),
)

if use_auto_exposure_tiers:
    st.caption(
        "Balanced auto tiers: top non-QB Auto Core plays may reach 100%; "
        "other 90+ plays may also reach 100%; under-90 plays are capped at 67%. "
        "QB exposure is controlled separately. Manual overrides supersede these caps."
    )

    max_auto_core_players = st.number_input(
        "Max Auto Core Players",
        min_value=0,
        max_value=3,
        value=2,
        step=1,
        key="portfolio_max_auto_core_players",
        help=(
            "Maximum number of top 95+ non-QB plays labeled as Auto Core. "
            "QB exposure is handled separately. Manual 100% overrides are unaffected."
        ),
    )
else:
    max_auto_core_players = 0

st.markdown("#### Player Exposure Overrides")
st.caption("Optional: 100% = 3 lineups, 67% = 2, 33% = 1, 0% = exclude.")

exposure_candidates = (
    players[players["position"].isin(["QB", "RB", "WR", "TE", "DST"])]
    [["dk_id", "player", "position", "team"]]
    .drop_duplicates(subset=["dk_id"])
    .sort_values(["position", "player"])
)
exposure_options = {
    f'{r["player"]} ({r["position"]}, {r["team"]})': str(r["dk_id"])
    for _, r in exposure_candidates.iterrows()
}
selected_exposure_players = st.multiselect(
    "Players to cap", list(exposure_options.keys()), key="portfolio_exposure_players"
)
player_exposure_limits = {}
for label in selected_exposure_players:
    pct = st.selectbox(
        label, [100, 67, 33, 0], index=1,
        format_func=lambda x: f"{x}%",
        key=f"exposure_{exposure_options[label]}"
    )
    player_exposure_limits[exposure_options[label]] = {100:3, 67:2, 33:1, 0:0}[pct]

portfolio_qb_stack = st.checkbox(
    "Require QB + WR/TE stack in every portfolio lineup",
    value=True,
    key="portfolio_qb_stack",
)

portfolio_qb_stack_size = st.selectbox(
    "Portfolio QB Stack Size",
    options=[1, 2],
    index=0,
    format_func=lambda value: (
        "QB + 1 pass catcher"
        if value == 1
        else "QB + 2 pass catchers"
    ),
    key="portfolio_qb_stack_size",
    help="Minimum number of same-team WR/TE players required with each portfolio QB.",
    disabled=not portfolio_qb_stack,
)

portfolio_min_stack_partner_gpp_score = st.number_input(
    "Minimum Stack Partner GPP Score",
    min_value=0.0,
    max_value=100.0,
    value=80.0,
    step=1.0,
    key="portfolio_min_stack_partner_gpp_score",
    help=(
        "WR/TE players used to satisfy a portfolio QB stack must meet this "
        "minimum GPP score. Set to 0 to disable."
    ),
    disabled=not portfolio_qb_stack,
)

portfolio_diversify_qb_stacks = st.checkbox(
    "Diversify repeated QB stacks",
    value=True,
    key="portfolio_diversify_qb_stacks",
    help=(
        "If the same QB appears in multiple portfolio lineups, "
        "require at least one of his stacked WR/TE pass catchers to change."
    ),
    disabled=not portfolio_qb_stack,
)

portfolio_dst_rb = st.checkbox(
    "Pair DST with same-team RB in every portfolio lineup",
    value=True,
    key="portfolio_dst_rb",
)

if st.button(
    "Build 3-Lineup Portfolio",
    type="primary",
):

    with st.spinner("Building 3-lineup GPP portfolio..."):

        portfolio = optimize_portfolio(
            players,
            num_lineups=3,
            strategy="GPP",
            min_salary=portfolio_min_salary,
            require_qb_stack=portfolio_qb_stack,
            qb_stack_size=int(portfolio_qb_stack_size),
            require_dst_rb=portfolio_dst_rb,
            max_overlap=int(portfolio_max_overlap),
            max_qb_exposure=int(portfolio_max_qb_exposure),
            player_exposure_limits=player_exposure_limits,
            use_auto_exposure_tiers=use_auto_exposure_tiers,
            max_auto_core_players=int(max_auto_core_players),
            diversify_qb_stacks=portfolio_diversify_qb_stacks,
            min_stack_partner_gpp_score=float(
                portfolio_min_stack_partner_gpp_score
            ),
        )

    if not portfolio:
        st.error(
            "No valid portfolio could be built. Try lowering the minimum "
            "salary or increasing Max Shared Players."
        )

    else:
        if len(portfolio) < 3:
            st.warning(
                f"Only {len(portfolio)} valid lineup(s) could be built "
                "with the current constraints."
            )
        else:
            st.success("3-lineup GPP portfolio built!")

        portfolio_ids = []

        for lineup_number, portfolio_lineup in enumerate(portfolio, start=1):

            st.markdown(f"### Lineup {lineup_number}")

            portfolio_display = portfolio_lineup[
                [
                    "slot",
                    "player",
                    "position",
                    "team",
                    "opponent",
                    "salary",
                    "ll_projection",
                    "gpp_projection",
                    "gpp_score",
                ]
            ].copy()

            st.dataframe(
                portfolio_display,
                width="stretch",
                hide_index=True,
            )

            metric1, metric2, metric3, metric4 = st.columns(4)

            metric1.metric(
                "Salary",
                f"${portfolio_lineup.attrs['total_salary']:,.0f}",
            )

            metric2.metric(
                "Projected Points",
                f"{portfolio_lineup.attrs['total_projection']:.1f}",
            )

            metric3.metric(
                "Salary Remaining",
                f"${50000 - portfolio_lineup.attrs['total_salary']:,.0f}",
            )

            metric4.metric(
                "GPP Projection",
                f"{portfolio_lineup.attrs['optimizer_score']:.1f}",
            )

            portfolio_ids.append(
                set(
                    portfolio_lineup["dk_id"]
                    .dropna()
                    .astype(str)
                )
            )

        if len(portfolio_ids) > 1:
            st.markdown("### Portfolio Overlap")

            overlap_rows = []

            for i in range(len(portfolio_ids)):
                for j in range(i + 1, len(portfolio_ids)):
                    overlap_rows.append(
                        {
                            "Lineups": f"{i + 1} vs {j + 1}",
                            "Shared Players": len(
                                portfolio_ids[i] & portfolio_ids[j]
                            ),
                        }
                    )

            import pandas as pd

            st.dataframe(
                pd.DataFrame(overlap_rows),
                width="stretch",
                hide_index=True,
            )

        if portfolio:
            st.markdown("### QB Exposure")

            qb_exposure = {}

            for portfolio_lineup in portfolio:
                qb_rows = portfolio_lineup[
                    portfolio_lineup["position"] == "QB"
                ]

                if qb_rows.empty:
                    continue

                qb_name = qb_rows.iloc[0]["player"]
                qb_exposure[qb_name] = qb_exposure.get(qb_name, 0) + 1

            qb_exposure_rows = [
                {
                    "QB": qb_name,
                    "Lineups": count,
                    "Exposure": f"{count / len(portfolio):.0%}",
                }
                for qb_name, count in sorted(
                    qb_exposure.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ]

            if qb_exposure_rows:
                st.dataframe(
                    pd.DataFrame(qb_exposure_rows),
                    width="stretch",
                    hide_index=True,
                )

        if portfolio:
            st.markdown("### QB Stack Exposure")

            qb_stack_rows = []
            for lineup_number, portfolio_lineup in enumerate(portfolio, start=1):
                qb_rows = portfolio_lineup[
                    portfolio_lineup["position"] == "QB"
                ]
                if qb_rows.empty:
                    continue

                qb_row = qb_rows.iloc[0]
                qb_team = qb_row["team"]

                stack_rows = portfolio_lineup[
                    (portfolio_lineup["team"] == qb_team)
                    & (portfolio_lineup["position"].isin(["WR", "TE"]))
                ][["player", "gpp_score"]].copy()

                pass_catchers = stack_rows["player"].tolist()
                stack_scores = [
                    f'{row["player"]}: {float(row["gpp_score"]):.1f}'
                    for _, row in stack_rows.iterrows()
                ]

                qb_stack_rows.append({
                    "Lineup": lineup_number,
                    "QB": qb_row["player"],
                    "Pass Catchers": " + ".join(pass_catchers),
                    "Stack Partner Scores": " | ".join(stack_scores),
                })

            if qb_stack_rows:
                st.dataframe(
                    pd.DataFrame(qb_stack_rows),
                    width="stretch",
                    hide_index=True,
                )

        if portfolio:
            st.markdown("### Portfolio Player Exposure")
            counts = {}
            for lineup in portfolio:
                for _, row in lineup.iterrows():
                    pid = str(row["dk_id"])
                    counts.setdefault(pid, {
                        "Player": row["player"], "Pos": row["position"],
                        "Team": row["team"], "Lineups": 0
                    })
                    counts[pid]["Lineups"] += 1

            effective_limits = portfolio[0].attrs.get(
                "effective_exposure_limits",
                {},
            )
            manual_limits = portfolio[0].attrs.get(
                "manual_exposure_limits",
                {},
            )
            auto_limits = portfolio[0].attrs.get(
                "auto_exposure_limits",
                {},
            )
            auto_core_ids = portfolio[0].attrs.get(
                "auto_core_ids",
                set(),
            )

            rows = []
            for pid, info in counts.items():
                cap = effective_limits.get(pid, 3)

                if pid in manual_limits:
                    cap_source = "Manual"
                elif pid in auto_core_ids:
                    cap_source = "Auto Core"
                elif pid in auto_limits:
                    cap_source = "Auto"
                else:
                    cap_source = "Default"

                rows.append({
                    **info,
                    "Exposure": f'{info["Lineups"]/len(portfolio):.0%}',
                    "Cap": f"{cap/3:.0%}",
                    "Cap Source": cap_source,
                })

            exposure_df = pd.DataFrame(rows).sort_values(
                ["Lineups", "Player"], ascending=[False, True]
            )
            st.dataframe(exposure_df, width="stretch", hide_index=True)

st.divider()

st.subheader("Player Pool")

position_filter = st.multiselect(
    "Position",
    ["QB", "RB", "WR", "TE", "DST"],
    default=["QB", "RB", "WR", "TE", "DST"],
)

filtered = players[
    players["position"].isin(position_filter)
].copy()

st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True,
    column_config={
        "dk_id": None,
        "player": "Player",
        "position": "Pos",
        "team": "Team",
        "opponent": "Opp",
        "home_away": "H/A",
        "salary": st.column_config.NumberColumn(
            "Salary",
            format="$%d",
        ),
        "dk_avg_points": st.column_config.NumberColumn(
            "DK Avg",
            format="%.1f",
        ),
        "status": "Status",
        "game_info": "Game",
        "avg_carries": st.column_config.NumberColumn(
            "Carries/G",
            format="%.1f",
        ),
        "avg_targets": st.column_config.NumberColumn(
            "Targets/G",
            format="%.1f",
        ),
        "avg_fantasy_points_ppr": st.column_config.NumberColumn(
            "2025 PPR/G",
            format="%.1f",
        ),
        "ll_projection": st.column_config.NumberColumn(
            "LL Proj",
            format="%.1f",
        ),
        "ll_floor": st.column_config.NumberColumn(
            "Floor",
            format="%.1f",
        ),
        "ll_ceiling": st.column_config.NumberColumn(
            "Ceiling",
            format="%.1f",
        ),
        "ll_value": st.column_config.NumberColumn(
            "Value",
            format="%.2f",
        ),
        "cash_score": st.column_config.NumberColumn(
            "Cash",
            format="%.1f",
        ),

        "gpp_score": st.column_config.NumberColumn(
            "GPP",
            format="%.1f",
        ),
    },
)