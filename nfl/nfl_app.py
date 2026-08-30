import streamlit as st
from pathlib import Path
import sys
import pandas as pd
from io import BytesIO

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from nfl.data_loader import (
    load_dk_salaries,
    merge_with_baselines,
    merge_with_dst_baselines,
)

from nfl.salary_store import (
    load_latest_salary_file,
    save_latest_salary_file,
)

from nfl.nflverse_loader import (
    get_recent_baselines,
    get_recent_dst_baselines,
)

from nfl.role_adjustments import apply_role_adjustments

from nfl.projections import (
    add_ll_projections,
    add_optimizer_scores,
    add_strategy_projections,
)

from nfl.odds_loader import (
    load_nfl_odds,
    normalize_odds_teams,
    load_manual_test_odds,
)

from nfl.odds_store import (
    save_latest_odds,
    load_latest_odds,
    load_latest_odds_with_meta,
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

from nfl.final_lineup_store import (
    save_nfl_final_lineup,
    list_nfl_final_lineups,
)

st.set_page_config(
    page_title="LineupLab NFL",
    page_icon="🏈",
    layout="wide",
)

# -----------------------------
# LineupLab NFL visual theme
# -----------------------------
st.markdown(
    """
    <style>
    :root {
        --ll-bg: #07111f;
        --ll-panel: #0d1a2a;
        --ll-panel-2: #122235;
        --ll-border: #23384f;
        --ll-green: #76d400;
        --ll-green-2: #9be329;
        --ll-text: #f5f7fa;
        --ll-muted: #9eabb9;
    }

    .stApp {
        background:
            radial-gradient(circle at top right, rgba(118,212,0,0.06), transparent 28%),
            linear-gradient(180deg, #07111f 0%, #091522 100%);
        color: var(--ll-text);
    }

    [data-testid="stHeader"] {
        background: rgba(7,17,31,0.88);
        backdrop-filter: blur(8px);
    }

    [data-testid="stToolbar"] {
        right: 1rem;
    }

    .block-container {
        max-width: 1550px;
        padding-top: 1.4rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3, h4 {
        color: var(--ll-text) !important;
        letter-spacing: -0.01em;
    }

    p, label, .stCaption {
        color: var(--ll-muted);
    }

    [data-testid="stMetric"] {
        background: linear-gradient(180deg, rgba(18,34,53,.96), rgba(13,26,42,.96));
        border: 1px solid var(--ll-border);
        border-radius: 12px;
        padding: 0.85rem 1rem;
        box-shadow: 0 8px 24px rgba(0,0,0,.15);
    }

    [data-testid="stMetricLabel"] {
        color: var(--ll-muted);
    }

    [data-testid="stMetricValue"] {
        color: var(--ll-text);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--ll-border);
        border-radius: 12px;
        overflow: hidden;
        background: var(--ll-panel);
    }

    .stSelectbox > div > div,
    .stNumberInput > div > div,
    .stMultiSelect > div > div,
    .stFileUploader section {
        background: var(--ll-panel-2);
        border-color: var(--ll-border);
        border-radius: 9px;
    }

    .stButton > button {
        border-radius: 8px;
        border: 1px solid #75d300;
        background: linear-gradient(180deg, #5daf00, #3f8500);
        color: white;
        font-weight: 700;
        min-height: 2.7rem;
        box-shadow: 0 4px 14px rgba(118,212,0,.16);
    }

    .stButton > button:hover {
        border-color: #a3ef38;
        background: linear-gradient(180deg, #6bc400, #4d9800);
        color: white;
    }

    div[data-testid="stAlert"] {
        border-radius: 10px;
        border: 1px solid var(--ll-border);
    }

    hr {
        border-color: var(--ll-border) !important;
    }

    .ll-hero {
        padding: 0.4rem 0 0.9rem 0;
        border-bottom: 1px solid var(--ll-border);
        margin-bottom: 1.6rem;
    }

    .ll-kicker {
        color: var(--ll-muted);
        font-size: 0.82rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        margin-top: -0.2rem;
    }

    .ll-section-rule {
        height: 3px;
        width: 56px;
        background: linear-gradient(90deg, var(--ll-green), transparent);
        margin: -0.25rem 0 0.9rem 0;
        border-radius: 999px;
    }

    .ll-ready {
        border: 1px solid rgba(118,212,0,.35);
        background: rgba(118,212,0,.07);
        border-radius: 10px;
        padding: .75rem 1rem;
        color: #dfffb3;
        margin-top: .75rem;
    }
        /* =========================================================
    LINEUPLAB NFL — INPUT / DROPDOWN READABILITY
    ========================================================= */

    /* Selectbox / dropdown selected value */
    div[data-baseweb="select"] > div {
        background-color: #12263a !important;
        border-color: #29445f !important;
        color: #f5f7fa !important;
    }

    div[data-baseweb="select"] span {
        color: #f5f7fa !important;
        -webkit-text-fill-color: #f5f7fa !important;
    }

    /* Dropdown arrow */
    div[data-baseweb="select"] svg {
        fill: #76d600 !important;
        color: #76d600 !important;
    }

    /* Number inputs */
    div[data-testid="stNumberInput"] input {
        background-color: #12263a !important;
        color: #f5f7fa !important;
        -webkit-text-fill-color: #f5f7fa !important;
        opacity: 1 !important;
    }

    /* +/- controls */
    div[data-testid="stNumberInput"] button {
        background-color: #12263a !important;
        color: #76d600 !important;
    }

    div[data-testid="stNumberInput"] button svg {
        fill: #76d600 !important;
    }

    /* Multiselect text */
    div[data-baseweb="select"] input {
        color: #f5f7fa !important;
        -webkit-text-fill-color: #f5f7fa !important;
    }

    /* Placeholder text */
    div[data-baseweb="select"] input::placeholder {
        color: #aebdca !important;
        opacity: 1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

logo_path = ROOT_DIR / "assets" / "lineuplab_nfl_logo.png"

st.markdown('<div class="ll-hero">', unsafe_allow_html=True)
if logo_path.exists():
    st.image(str(logo_path), width=500)
else:
    st.markdown("## 🏈 LineupLab NFL")
st.markdown(
    '<div class="ll-kicker">NFL DFS Projection & Portfolio Lab</div></div>',
    unsafe_allow_html=True,
)

st.subheader("DraftKings Player Pool")
st.markdown('<div class="ll-section-rule"></div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Upload DraftKings NFL salary CSV",
    type=["csv"],
)

# Save every manually uploaded DK salary file to Supabase so the same
# slate is available from another device/session.
if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    st.session_state["active_nfl_salary_bytes"] = file_bytes
    st.session_state["active_nfl_salary_name"] = uploaded_file.name

    try:
        save_latest_salary_file(
            file_bytes=file_bytes,
            filename=uploaded_file.name,
        )
        st.caption("☁️ DraftKings salary sheet saved for cross-device use.")
    except Exception as exc:
        st.warning(f"Could not save salary sheet to cloud: {exc}")

# If this browser/session has no upload, restore the latest cloud-saved file.
if uploaded_file is None and "active_nfl_salary_bytes" not in st.session_state:
    try:
        saved_bytes, saved_name = load_latest_salary_file()
        st.session_state["active_nfl_salary_bytes"] = saved_bytes
        st.session_state["active_nfl_salary_name"] = saved_name
    except Exception:
        pass

# Convert the persisted bytes back into a file-like object expected by
# the existing DraftKings loader.
if uploaded_file is None and "active_nfl_salary_bytes" in st.session_state:
    uploaded_file = BytesIO(st.session_state["active_nfl_salary_bytes"])
    uploaded_file.name = st.session_state.get(
        "active_nfl_salary_name",
        "latest_nfl_dk_salaries.csv",
    )
    st.info(
        f"📲 Loaded saved DraftKings salary sheet: "
        f"{uploaded_file.name}"
    )

if uploaded_file is None:
    st.info("Upload a DraftKings NFL salary CSV to begin.")
    st.stop()

try:
    players = load_dk_salaries(uploaded_file)

    # Remove players who have already been ruled out before any projections,
    # rankings, stacks, or optimizer logic are built.
    if "status" in players.columns:
        normalized_status = (
            players["status"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )
        out_mask = normalized_status.isin({"OUT", "O"})
        out_count = int(out_mask.sum())
        players = players.loc[~out_mask].copy()

        if out_count:
            st.caption(f"🚫 Removed {out_count} player(s) ruled OUT from the active slate.")

    with st.spinner("Loading recent NFL player baselines..."):
        baselines = get_recent_baselines([2025])

    players = merge_with_baselines(players, baselines)

    # Week 1 / early-season 2026 role-transition layer
    players = apply_role_adjustments(players)
    with st.spinner("Loading recent NFL defense baselines..."):
        dst_baselines = get_recent_dst_baselines([2025])

    players = merge_with_dst_baselines(
        players,
        dst_baselines,
    )
    # Projection is calculated after Vegas/game environment is merged.

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

odds = None
odds_source = None
odds_refreshed_at = None

st.subheader("Vegas Odds")
st.markdown('<div class="ll-section-rule"></div>', unsafe_allow_html=True)

st.caption(
    "LineupLab uses the most recently saved Vegas snapshot by default. "
    "The Odds API is called only when you click Refresh Vegas Odds."
)

refresh_odds = st.button(
    "🔄 Refresh Vegas Odds",
    key="refresh_nfl_vegas_odds",
    help=(
        "Makes one live Odds API request for the configured NFL slate, "
        "then saves that snapshot for reuse across reruns and devices."
    ),
)

if refresh_odds:
    with st.spinner("Refreshing NFL Vegas lines..."):
        try:
            fresh_odds = load_nfl_odds(
                st.secrets["ODDS_API_KEY"],
                "2026-09-13T00:00:00Z",
                "2026-09-14T04:00:00Z",
            )

            fresh_odds = normalize_odds_teams(fresh_odds)

            if fresh_odds is None or fresh_odds.empty:
                st.warning(
                    "The Odds API returned no games. "
                    "Keeping the previously saved snapshot."
                )
            else:
                save_latest_odds(fresh_odds)
                odds = fresh_odds
                odds_source = "fresh"

                try:
                    _, odds_refreshed_at = load_latest_odds_with_meta()
                except Exception:
                    odds_refreshed_at = None

                st.success(
                    "🟢 Vegas odds refreshed and saved. "
                    "No additional API calls will occur until you "
                    "press Refresh Vegas Odds again."
                )

        except Exception as exc:
            st.error(
                "Could not refresh Vegas odds. "
                f"The saved snapshot will be used instead. ({exc})"
            )

# Normal Streamlit reruns only read the saved snapshot.
if odds is None or odds.empty:
    try:
        odds, odds_refreshed_at = load_latest_odds_with_meta()

        if odds is not None and not odds.empty:
            odds_source = "saved"

    except Exception:
        odds = None

# Development fallback only when no saved snapshot exists.
if odds is None or odds.empty:
    odds = load_manual_test_odds()

    if odds is not None and not odds.empty:
        odds_source = "manual"
    else:
        odds = None
        odds_source = None

if odds_source in {"fresh", "saved"}:
    if odds_refreshed_at:
        try:
            refreshed_dt = pd.to_datetime(
                odds_refreshed_at,
                utc=True,
            ).tz_convert("America/Los_Angeles")

            refreshed_label = refreshed_dt.strftime(
                "%b %d, %Y • %I:%M %p PT"
            )
        except Exception:
            refreshed_label = str(odds_refreshed_at)

        st.info(
            f"🟡 Using saved Vegas snapshot • Last refreshed: "
            f"**{refreshed_label}**"
        )
    else:
        st.info(
            "🟡 Using saved Vegas snapshot. "
            "Refresh timestamp is unavailable for this legacy snapshot."
        )

elif odds_source == "manual":
    st.info(
        "🧪 No saved Vegas snapshot found — using manually entered "
        "Week 1 test lines."
    )

else:
    st.warning(
        "🔴 No Vegas odds are currently available. "
        "LineupLab will continue without Vegas adjustments."
    )

if odds is not None and not odds.empty:
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
st.markdown('<div class="ll-section-rule"></div>', unsafe_allow_html=True)

st.dataframe(
    game_environment,
    use_container_width=True,
    hide_index=True,
)

st.subheader("DST / RB Pairings")
st.markdown('<div class="ll-section-rule"></div>', unsafe_allow_html=True)

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
st.markdown('<div class="ll-section-rule"></div>', unsafe_allow_html=True)

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
st.markdown('<div class="ll-section-rule"></div>', unsafe_allow_html=True)

ranking_position = st.selectbox(
    "Ranking Position",
    ["QB", "RB", "WR", "TE", "DST"],
    index=1,
    help=(
        "Choose which position to rank using LineupLab's projection, value, "
        "floor, ceiling, Cash score, and GPP score."
    ),
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
st.markdown('<div class="ll-section-rule"></div>', unsafe_allow_html=True)

strategy = st.selectbox(
    "Strategy",
    ["Cash", "Hybrid", "GPP"],
    help=(
        "Controls how LineupLab evaluates players. Cash emphasizes floor and "
        "consistency, Hybrid balances safety and upside, and GPP emphasizes "
        "ceiling and tournament potential."
    ),
)

strategy_help = {
    "Cash": "Prioritizes stability, floor, and high-probability scoring for double-ups and cash games.",
    "Hybrid": "Balances cash-game safety with GPP upside — ideal for a lineup being entered in both a double-up and GPP.",
    "GPP": "Prioritizes ceiling, correlation, and tournament upside over pure consistency.",
}

st.caption(strategy_help[strategy])
st.caption(
    "FLEX preference: LineupLab slightly favors RB/WR over a second TE, "
    "but will still use TE at FLEX when the projection edge is strong enough."
)

min_salary = st.number_input(
    "Minimum Salary",
    min_value=0,
    max_value=50000,
    value=49000,
    step=100,
    help=(
        "Minimum total salary the optimizer must spend. Lowering this gives "
        "LineupLab more flexibility and may uncover stronger value combinations."
    ),
)

require_qb_stack = False
qb_stack_size = 1
min_stack_partner_gpp_score = 0.0
require_dst_rb = False

if strategy in ["Hybrid", "GPP"]:

    require_qb_stack = st.checkbox(
        "Require QB + WR/TE stack",
        value=True,
        help=(
            "Requires the quarterback to be paired with at least one same-team "
            "WR or TE to capture correlated scoring."
        ),
    )

    qb_stack_size = st.selectbox(
        "Portfolio QB Stack Size",
        options=[1, 2],
        index=0,
        format_func=lambda value: (
            "QB + 1 pass catcher"
            if value == 1
            else "QB + 2 pass catchers"
        ),
        help=(
            "Choose whether each quarterback must be paired with one or two "
            "same-team WR/TE pass catchers."
        ),
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
        value=(strategy == "GPP"),
        help=(
            "Pairs a defense with a running back from the same team, targeting "
            "favorable game scripts where the team leads and runs more. "
            "Defaults on for GPP and off for Hybrid."
        ),
    )

if st.button("Build Lineup", type="primary", use_container_width=False):

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

        # Preserve the most recently built single lineup across Streamlit reruns
        # so it can be selected and saved as an official Final Lineup.
        st.session_state["nfl_single_lineup"] = lineup.copy()
        st.session_state["nfl_single_lineup_strategy"] = strategy

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
st.markdown('<div class="ll-section-rule"></div>', unsafe_allow_html=True)
st.caption(
    "Build three related lineups while controlling overlap, exposure, and stacking."
)

portfolio_strategy = st.selectbox(
    "Portfolio Strategy",
    ["Cash", "Hybrid", "GPP"],
    index=1,
    key="portfolio_strategy",
    help=(
        "Controls how all three portfolio lineups are optimized. Cash emphasizes "
        "stability, Hybrid balances safety and upside, and GPP emphasizes ceiling "
        "and tournament potential."
    ),
)

portfolio_strategy_help = {
    "Cash": (
        "Three stability-first lineups designed around floor, consistency, "
        "and high-probability scoring."
    ),
    "Hybrid": (
        "Three balanced lineups designed to pull double duty in both double-ups "
        "and small-field / 3-max GPPs."
    ),
    "GPP": (
        "Three tournament-focused lineups emphasizing ceiling, correlation, "
        "and differentiated upside."
    ),
}

st.caption(portfolio_strategy_help[portfolio_strategy])

portfolio_col1, portfolio_col2, portfolio_col3 = st.columns(3)

with portfolio_col1:
    portfolio_min_salary = st.number_input(
        "Portfolio Minimum Salary",
        min_value=0,
        max_value=50000,
        value=49000,
        step=100,
        key="portfolio_min_salary",
        help=(
            "Minimum total salary each portfolio lineup must spend. Lowering "
            "this gives the optimizer more flexibility and can create more diversity."
        ),
    )

with portfolio_col2:
    portfolio_max_overlap = st.number_input(
        "Max Shared Players",
        min_value=0,
        max_value=8,
        value=6,
        step=1,
        key="portfolio_max_overlap",
        help=(
            "Maximum number of players any two portfolio lineups may share. "
            "Lower values create more diversity; higher values preserve more of "
            "your strongest core."
        ),
    )

with portfolio_col3:
    portfolio_max_qb_exposure = st.number_input(
        "Max QB Exposure",
        min_value=1,
        max_value=3,
        value=2,
        step=1,
        key="portfolio_max_qb_exposure",
        help=(
            "Maximum number of the three portfolio lineups that may use the same "
            "quarterback. A value of 2 prevents one QB from appearing in all three."
        ),
    )

st.markdown("#### Automatic Exposure Tiers")

use_auto_exposure_tiers = st.checkbox(
    "Use automatic player exposure tiers",
    value=True,
    key="portfolio_auto_exposure",
    help=(
        "Automatically manages exposure across the three-lineup portfolio. "
        "Only designated Auto Core players may appear in all 3 lineups; "
        "all other players are capped at 2. Manual overrides take priority."
    ),
)

if use_auto_exposure_tiers:
    st.caption(
        "Balanced auto tiers: only the top non-QB Auto Core plays may reach 100%; "
        "all other players are capped at 67%. QB exposure is controlled separately. "
        "Manual overrides supersede these caps."
    )

    max_auto_core_players = st.number_input(
        "Max Auto Core Players",
        min_value=0,
        max_value=3,
        value=2,
        step=1,
        key="portfolio_max_auto_core_players",
        help=(
            "Maximum number of elite non-QB players LineupLab may designate as "
            "automatic core plays that are allowed to appear in all three lineups. "
            "QB exposure is handled separately."
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
    "Players to cap",
    list(exposure_options.keys()),
    key="portfolio_exposure_players",
    help=(
        "Manually control exposure for specific players. After selecting a player, "
        "set 100% = 3 lineups, 67% = 2, 33% = 1, or 0% = exclude."
    ),
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
    help=(
        "Requires every portfolio QB to be paired with at least one same-team "
        "WR or TE so the lineup captures correlated passing-game scoring."
    ),
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
    value=(portfolio_strategy == "GPP"),
    key="portfolio_dst_rb",
    help=(
        "Requires each defense to be paired with a running back from the same team. "
        "This targets positive game-script correlation. Defaults on for GPP and "
        "off for Cash/Hybrid."
    ),
)

st.markdown(
    '<div class="ll-ready">Ready to optimize — review the portfolio controls, then build your three-lineup set.</div>',
    unsafe_allow_html=True,
)

if st.button(
    "Build 3-Lineup Portfolio",
    type="primary",
):

    with st.spinner(f"Building 3-lineup {portfolio_strategy} portfolio..."):

        portfolio = optimize_portfolio(
            players,
            num_lineups=3,
            strategy=portfolio_strategy,
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
            st.success(f"3-lineup {portfolio_strategy} portfolio built!")

        # Preserve the latest portfolio across Streamlit reruns so any of the
        # three lineups can be saved as official Final Lineups.
        st.session_state["nfl_portfolio"] = [
            lineup.copy() for lineup in portfolio
        ]
        st.session_state["nfl_portfolio_strategy"] = portfolio_strategy

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
                f"{portfolio_strategy} Strategy Projection",
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

# -------------------------
# Final Lineups
# -------------------------

st.subheader("🏁 NFL Final Lineups")
st.markdown('<div class="ll-section-rule"></div>', unsafe_allow_html=True)
st.caption(
    "Save the exact lineup you actually plan to enter. "
    "These records will become the source of truth for NFL Contest Review "
    "and Performance Center."
)

final_meta_col1, final_meta_col2 = st.columns(2)

with final_meta_col1:
    nfl_final_slate_date = st.date_input(
        "Final Lineup Slate Date",
        key="nfl_final_slate_date",
    )

with final_meta_col2:
    nfl_final_slate_name = st.text_input(
        "Slate Name",
        value="Main",
        key="nfl_final_slate_name",
    )

available_final_sources = {}

single_saved = st.session_state.get("nfl_single_lineup")
if isinstance(single_saved, pd.DataFrame) and not single_saved.empty:
    single_strategy = st.session_state.get(
        "nfl_single_lineup_strategy",
        single_saved.attrs.get("strategy", "Unknown"),
    )
    available_final_sources[
        f"Single Build — {single_strategy}"
    ] = (
        single_saved,
        single_strategy,
    )

portfolio_saved = st.session_state.get("nfl_portfolio", [])
portfolio_strategy_saved = st.session_state.get(
    "nfl_portfolio_strategy",
    "Unknown",
)

if isinstance(portfolio_saved, list):
    for index, saved_lineup in enumerate(portfolio_saved, start=1):
        if isinstance(saved_lineup, pd.DataFrame) and not saved_lineup.empty:
            available_final_sources[
                f"Portfolio Lineup {index} — {portfolio_strategy_saved}"
            ] = (
                saved_lineup,
                portfolio_strategy_saved,
            )

if not available_final_sources:
    st.info(
        "Build a single lineup or 3-lineup portfolio first. "
        "The lineup(s) will then appear here for Final Lineup saving."
    )
else:
    final_source_label = st.selectbox(
        "Lineup to Save",
        options=list(available_final_sources.keys()),
        key="nfl_final_source",
    )

    final_lineup, final_strategy = available_final_sources[
        final_source_label
    ]

    final_slot = st.selectbox(
        "Final Lineup Slot",
        options=[
            "Lineup 1",
            "Lineup 2",
            "Lineup 3",
            "Cash",
            "GPP",
        ],
        key="nfl_final_slot",
        help=(
            "Each slot can hold one official lineup for the selected slate. "
            "Saving the same slot again overwrites that slot only."
        ),
    )

    final_preview_cols = [
        "slot",
        "player",
        "position",
        "team",
        "opponent",
        "salary",
        "ll_projection",
    ]

    st.dataframe(
        final_lineup[final_preview_cols],
        use_container_width=True,
        hide_index=True,
    )

    preview_col1, preview_col2, preview_col3 = st.columns(3)

    preview_salary = float(
        final_lineup.attrs.get(
            "total_salary",
            pd.to_numeric(
                final_lineup["salary"],
                errors="coerce",
            ).fillna(0).sum(),
        )
    )

    preview_projection = float(
        final_lineup.attrs.get(
            "total_projection",
            pd.to_numeric(
                final_lineup["ll_projection"],
                errors="coerce",
            ).fillna(0).sum(),
        )
    )

    preview_col1.metric(
        "Salary",
        f"${preview_salary:,.0f}",
    )
    preview_col2.metric(
        "Raw Projection",
        f"{preview_projection:.1f}",
    )
    preview_col3.metric(
        "Strategy",
        final_strategy,
    )

    if st.button(
        "💾 Save NFL Final Lineup",
        type="primary",
        key="save_nfl_final_lineup",
    ):
        try:
            saved_record = save_nfl_final_lineup(
                lineup=final_lineup,
                slate_date=nfl_final_slate_date.isoformat(),
                slate_name=nfl_final_slate_name,
                lineup_slot=final_slot,
                strategy=final_strategy,
            )

            st.session_state[
                "nfl_final_lineup_notice"
            ] = (
                f"Saved {final_slot} — "
                f"{saved_record.get('lineup_id', '')}"
            )
            st.rerun()

        except Exception as exc:
            st.error(
                f"Could not save NFL Final Lineup: {exc}"
            )

final_notice = st.session_state.pop(
    "nfl_final_lineup_notice",
    None,
)

if final_notice:
    st.success(f"🏁 {final_notice}")

st.markdown("#### Saved NFL Final Lineups")

try:
    saved_nfl_finals = list_nfl_final_lineups(
        slate_date=nfl_final_slate_date.isoformat(),
        slate_name=nfl_final_slate_name,
    )
except Exception as exc:
    saved_nfl_finals = []
    st.caption(
        f"Saved Final Lineups are not available yet: {exc}"
    )

if saved_nfl_finals:
    saved_final_df = pd.DataFrame(saved_nfl_finals)

    saved_display_cols = [
        col for col in [
            "lineup_slot",
            "strategy",
            "salary",
            "projected_score",
            "optimizer_score",
            "lineup_id",
            "updated_at",
        ]
        if col in saved_final_df.columns
    ]

    st.dataframe(
        saved_final_df[saved_display_cols],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption(
        "No NFL Final Lineups are saved for this slate yet."
    )

st.divider()

st.subheader("Player Pool")

position_filter = st.multiselect(
    "Position",
    ["QB", "RB", "WR", "TE", "DST"],
    default=["QB", "RB", "WR", "TE", "DST"],
    help="Filter the player-pool table by position. This does not exclude players from the optimizer.",
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