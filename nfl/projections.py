import pandas as pd
import numpy as np


RECENT_WEIGHTS = {
    1: 0.10,
    2: 0.15,
    3: 0.20,
    4: 0.25,
    5: 0.30,
}


def weighted_recent_average(values):
    """
    Weighted average where the most recent games receive more weight.
    Expects values ordered oldest -> newest.
    """

    values = pd.Series(values).dropna()

    if values.empty:
        return np.nan

    values = values.tail(5)

    weights = np.array(
        list(RECENT_WEIGHTS.values())[-len(values):]
    )

    weights = weights / weights.sum()

    return np.average(values, weights=weights)


def build_recent_player_baselines(stats):
    """
    Build recent weighted player baselines from nflverse weekly stats.
    """

    stats = stats.copy()

    stat_columns = [
        "attempts",
        "completions",
        "carries",
        "targets",
        "receptions",
        "passing_yards",
        "passing_tds",
        "passing_interceptions",
        "rushing_yards",
        "rushing_tds",
        "receiving_yards",
        "receiving_tds",
        "fantasy_points",
        "fantasy_points_ppr",
    ]

    available = [c for c in stat_columns if c in stats.columns]

    stats = stats.sort_values(
        ["player_display_name", "week"]
    )

    rows = []

    for (player, position), group in stats.groupby(
        ["player_display_name", "position"]
    ):
        row = {
            "player": player,
            "position": position,
        }

        for col in available:
            row[f"recent_{col}"] = weighted_recent_average(
                group[col]
            )

        rows.append(row)

    return pd.DataFrame(rows)

# ---------------------------------------------------------
# Position model constants
# ---------------------------------------------------------

RB_LEAGUE_YPC = 4.3
RB_LEAGUE_CATCH_RATE = 0.75
RB_LEAGUE_YARDS_PER_RECEPTION = 7.5

WR_LEAGUE_CATCH_RATE = 0.65
WR_LEAGUE_YARDS_PER_RECEPTION = 12.0

TE_LEAGUE_CATCH_RATE = 0.70
TE_LEAGUE_YARDS_PER_RECEPTION = 10.5

QB_LEAGUE_COMPLETION_RATE = 0.65
QB_LEAGUE_YARDS_PER_ATTEMPT = 7.2
QB_LEAGUE_TD_RATE = 0.045
QB_LEAGUE_INT_RATE = 0.022

# How much we trust a player's recent efficiency
PLAYER_EFFICIENCY_WEIGHT = 0.65
LEAGUE_EFFICIENCY_WEIGHT = 0.35


def safe_divide(numerator, denominator, fallback=0.0):
    """
    Divide safely while handling blanks and zero denominators.
    """
    try:
        if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
            return fallback
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return fallback


def blend_efficiency(player_rate, league_rate):
    """
    Regress recent player efficiency slightly toward league average.
    """
    return (
        player_rate * PLAYER_EFFICIENCY_WEIGHT
        + league_rate * LEAGUE_EFFICIENCY_WEIGHT
    )


def project_rb(row):
    """
    LineupLab RB Projection v0.2.

    Separates opportunity from efficiency rather than simply
    projecting recent fantasy points forward.
    """

    carries = row.get("recent_carries", 0)
    targets = row.get("recent_targets", 0)
    receptions = row.get("recent_receptions", 0)

    rushing_yards = row.get("recent_rushing_yards", 0)
    receiving_yards = row.get("recent_receiving_yards", 0)

    rushing_tds = row.get("recent_rushing_tds", 0)
    receiving_tds = row.get("recent_receiving_tds", 0)

    # Handle missing history
    if pd.isna(carries):
        return np.nan

    # -----------------------------
    # Rushing efficiency
    # -----------------------------

    player_ypc = safe_divide(
        rushing_yards,
        carries,
        RB_LEAGUE_YPC,
    )

    projected_ypc = blend_efficiency(
        player_ypc,
        RB_LEAGUE_YPC,
    )

    projected_rushing_yards = carries * projected_ypc

    # -----------------------------
    # Receiving efficiency
    # -----------------------------

    player_catch_rate = safe_divide(
        receptions,
        targets,
        RB_LEAGUE_CATCH_RATE,
    )

    projected_catch_rate = blend_efficiency(
        player_catch_rate,
        RB_LEAGUE_CATCH_RATE,
    )

    projected_receptions = targets * projected_catch_rate

    player_ypr = safe_divide(
        receiving_yards,
        receptions,
        RB_LEAGUE_YARDS_PER_RECEPTION,
    )

    projected_ypr = blend_efficiency(
        player_ypr,
        RB_LEAGUE_YARDS_PER_RECEPTION,
    )

    projected_receiving_yards = (
        projected_receptions * projected_ypr
    )

    # -----------------------------
    # TD regression
    # -----------------------------

    rushing_tds = 0 if pd.isna(rushing_tds) else rushing_tds
    receiving_tds = 0 if pd.isna(receiving_tds) else receiving_tds

    # TDs are volatile, so regress them toward modest RB baselines
    projected_rushing_tds = (
        rushing_tds * 0.65
        + 0.35 * 0.30
    )

    projected_receiving_tds = (
        receiving_tds * 0.65
        + 0.35 * 0.06
    )

    # -----------------------------
    # DraftKings scoring
    # -----------------------------

    dk_points = (
        projected_rushing_yards / 10
        + projected_rushing_tds * 6
        + projected_receptions
        + projected_receiving_yards / 10
        + projected_receiving_tds * 6
    )

    return dk_points

def adjust_rb_for_game_environment(row, base_projection):
    """
    Adjust RB projection for Vegas/game-script environment.

    Positive factors:
      - favored team
      - larger negative spread
      - higher team implied total

    Kept intentionally modest for v0.3.
    """

    if pd.isna(base_projection):
        return np.nan

    spread = row.get("spread", np.nan)
    team_total = row.get("team_implied_total", np.nan)

    adjustment = 1.0

    # Favorite / underdog adjustment
    if not pd.isna(spread):
        if spread <= -7:
            adjustment += 0.08
        elif spread <= -3:
            adjustment += 0.04
        elif spread >= 7:
            adjustment -= 0.07
        elif spread >= 3:
            adjustment -= 0.03

    # Team scoring environment
    if not pd.isna(team_total):
        if team_total >= 28:
            adjustment += 0.06
        elif team_total >= 25:
            adjustment += 0.03
        elif team_total <= 18:
            adjustment -= 0.05
        elif team_total <= 21:
            adjustment -= 0.02

    # Cap so Vegas doesn't overwhelm the player baseline
    adjustment = min(max(adjustment, 0.85), 1.15)

    return base_projection * adjustment

def adjust_qb_for_game_environment(row, base_projection):
    """
    Adjust QB projection for game environment.

    QB benefits most from:
      - high team implied total
      - high overall game total
      - competitive spread

    Large-favorite blowout risk slightly reduces the bump.
    """

    if pd.isna(base_projection):
        return np.nan

    team_total = row.get("team_implied_total", np.nan)
    game_total = row.get("game_total", np.nan)
    spread = row.get("spread", np.nan)

    adjustment = 1.0

    # Team scoring expectation
    if not pd.isna(team_total):
        if team_total >= 28:
            adjustment += 0.06
        elif team_total >= 25:
            adjustment += 0.03
        elif team_total <= 18:
            adjustment -= 0.06
        elif team_total <= 21:
            adjustment -= 0.03

    # Overall shootout environment
    if not pd.isna(game_total):
        if game_total >= 50:
            adjustment += 0.05
        elif game_total >= 47:
            adjustment += 0.03
        elif game_total <= 40:
            adjustment -= 0.04
        elif game_total <= 43:
            adjustment -= 0.02

    # Competitive games are generally better for sustained passing.
    if not pd.isna(spread):
        if abs(spread) <= 3:
            adjustment += 0.02
        elif spread <= -10:
            adjustment -= 0.03

    adjustment = min(max(adjustment, 0.85), 1.15)

    return base_projection * adjustment


def adjust_receiver_for_game_environment(row, base_projection):
    """
    Adjust WR/TE projection for passing-game environment.
    """

    if pd.isna(base_projection):
        return np.nan

    team_total = row.get("team_implied_total", np.nan)
    game_total = row.get("game_total", np.nan)
    spread = row.get("spread", np.nan)

    adjustment = 1.0

    if not pd.isna(team_total):
        if team_total >= 28:
            adjustment += 0.05
        elif team_total >= 25:
            adjustment += 0.03
        elif team_total <= 18:
            adjustment -= 0.05
        elif team_total <= 21:
            adjustment -= 0.02

    if not pd.isna(game_total):
        if game_total >= 50:
            adjustment += 0.06
        elif game_total >= 47:
            adjustment += 0.03
        elif game_total <= 40:
            adjustment -= 0.04

    # Mild passing-volume bump for underdogs.
    if not pd.isna(spread):
        if spread >= 7:
            adjustment += 0.03
        elif spread >= 3:
            adjustment += 0.01

    adjustment = min(max(adjustment, 0.85), 1.15)

    return base_projection * adjustment

def project_receiver(row):
    """
    LineupLab WR/TE Projection v0.2.

    Projects receiving production from recent target volume
    with regressed catch and yardage efficiency.
    """

    position = row.get("position")

    targets = row.get("recent_targets", 0)
    receptions = row.get("recent_receptions", 0)
    receiving_yards = row.get("recent_receiving_yards", 0)
    receiving_tds = row.get("recent_receiving_tds", 0)

    if pd.isna(targets):
        return np.nan

    if position == "TE":
        league_catch_rate = TE_LEAGUE_CATCH_RATE
        league_ypr = TE_LEAGUE_YARDS_PER_RECEPTION
    else:
        league_catch_rate = WR_LEAGUE_CATCH_RATE
        league_ypr = WR_LEAGUE_YARDS_PER_RECEPTION

    # Catch efficiency
    player_catch_rate = safe_divide(
        receptions,
        targets,
        league_catch_rate,
    )

    projected_catch_rate = blend_efficiency(
        player_catch_rate,
        league_catch_rate,
    )

    projected_receptions = targets * projected_catch_rate

    # Yardage efficiency
    player_ypr = safe_divide(
        receiving_yards,
        receptions,
        league_ypr,
    )

    projected_ypr = blend_efficiency(
        player_ypr,
        league_ypr,
    )

    projected_receiving_yards = (
        projected_receptions * projected_ypr
    )

    # TD regression
    receiving_tds = (
        0 if pd.isna(receiving_tds)
        else receiving_tds
    )

    baseline_td_rate = 0.25 if position == "WR" else 0.20

    projected_receiving_tds = (
        receiving_tds * 0.65
        + baseline_td_rate * 0.35
    )

    # Include occasional rushing production
    rushing_yards = row.get("recent_rushing_yards", 0)
    rushing_tds = row.get("recent_rushing_tds", 0)

    rushing_yards = (
        0 if pd.isna(rushing_yards)
        else rushing_yards
    )

    rushing_tds = (
        0 if pd.isna(rushing_tds)
        else rushing_tds
    )

    dk_points = (
        projected_receptions
        + projected_receiving_yards / 10
        + projected_receiving_tds * 6
        + rushing_yards / 10
        + rushing_tds * 6
    )

    return dk_points

def project_qb(row):
    """
    LineupLab QB Projection v0.3.

    Opportunity-first QB model:
    attempts -> passing efficiency -> TD/INT rates
    plus rushing production.
    """

    attempts = row.get("recent_attempts", np.nan)
    completions = row.get("recent_completions", np.nan)
    passing_yards = row.get("recent_passing_yards", np.nan)
    passing_tds = row.get("recent_passing_tds", np.nan)
    interceptions = row.get("recent_passing_interceptions", np.nan)

    rushing_yards = row.get("recent_rushing_yards", 0)
    rushing_tds = row.get("recent_rushing_tds", 0)

    if pd.isna(attempts) or attempts <= 0:
        return np.nan

    # -----------------------------
    # Passing efficiency
    # -----------------------------

    player_completion_rate = safe_divide(
        completions,
        attempts,
        QB_LEAGUE_COMPLETION_RATE,
    )

    projected_completion_rate = blend_efficiency(
        player_completion_rate,
        QB_LEAGUE_COMPLETION_RATE,
    )

    player_ypa = safe_divide(
        passing_yards,
        attempts,
        QB_LEAGUE_YARDS_PER_ATTEMPT,
    )

    projected_ypa = blend_efficiency(
        player_ypa,
        QB_LEAGUE_YARDS_PER_ATTEMPT,
    )

    projected_passing_yards = attempts * projected_ypa

    # -----------------------------
    # TD / INT rates
    # -----------------------------

    player_td_rate = safe_divide(
        passing_tds,
        attempts,
        QB_LEAGUE_TD_RATE,
    )

    projected_td_rate = blend_efficiency(
        player_td_rate,
        QB_LEAGUE_TD_RATE,
    )

    projected_passing_tds = attempts * projected_td_rate

    player_int_rate = safe_divide(
        interceptions,
        attempts,
        QB_LEAGUE_INT_RATE,
    )

    projected_int_rate = blend_efficiency(
        player_int_rate,
        QB_LEAGUE_INT_RATE,
    )

    projected_interceptions = attempts * projected_int_rate

    # -----------------------------
    # Rushing
    # -----------------------------

    rushing_yards = (
        0 if pd.isna(rushing_yards)
        else rushing_yards
    )

    rushing_tds = (
        0 if pd.isna(rushing_tds)
        else rushing_tds
    )

    # -----------------------------
    # DraftKings scoring
    # -----------------------------

    dk_points = (
        projected_passing_yards / 25
        + projected_passing_tds * 4
        - projected_interceptions
        + rushing_yards / 10
        + rushing_tds * 6
    )

    if projected_passing_yards >= 300:
        dk_points += 3

    return dk_points


def calculate_ll_projection(row):
    """
    LineupLab NFL Projection v0.2.
    """

    position = row.get("position")

    if position == "QB":
        base_projection = project_qb(row)

        return adjust_qb_for_game_environment(
            row,
            base_projection,
        )

    if position == "RB":
        base_projection = project_rb(row)

        return adjust_rb_for_game_environment(
            row,
            base_projection,
        )

    if position in ["WR", "TE"]:
        base_projection = project_receiver(row)

        return adjust_receiver_for_game_environment(
            row,
            base_projection,
        )

    if position == "DST":
        base_projection = project_dst(row)

        return adjust_dst_for_game_environment(
            row,
            base_projection,
        )

        return row.get(
            "recent_fantasy_points_ppr",
            np.nan,
        )


def _opportunity_stability_score(row):
    """
    Return a 0-1 estimate of workload stability.

    This is not a separate projection. It only helps shape the expected
    floor/ceiling range around the median LineupLab projection.

    Higher-volume players get a stronger floor. Lower-volume roles retain
    more boom/bust behavior.
    """

    position = row.get("position")

    def num(key):
        value = pd.to_numeric(
            pd.Series([row.get(key, np.nan)]),
            errors="coerce",
        ).iloc[0]

        return 0.0 if pd.isna(value) else float(value)

    if position == "QB":
        score = num("recent_attempts") / 36.0

    elif position == "RB":
        weighted_opportunity = (
            num("recent_carries")
            + num("recent_targets") * 0.75
        )
        score = weighted_opportunity / 20.0

    elif position == "WR":
        score = num("recent_targets") / 10.0

    elif position == "TE":
        score = num("recent_targets") / 8.0

    elif position == "DST":
        # DST remains intrinsically volatile even with a strong matchup.
        score = 0.45

    else:
        score = 0.50

    return float(min(max(score, 0.0), 1.0))


def _projection_range_multipliers(row):
    """
    Build position- and role-aware floor/ceiling multipliers.

    The range is intentionally wider for volatile positions and uncertain
    early-season roles, while established high-volume players receive a
    stronger floor.

    role_prior_weight comes from role_adjustments.py:
      lower value = more trusted historical role
      higher value = more uncertain/current-role prior influence
    """

    position = row.get("position")

    base_floor = {
        "QB": 0.74,
        "RB": 0.66,
        "WR": 0.58,
        "TE": 0.56,
        "DST": 0.42,
    }.get(position, 0.65)

    base_ceiling = {
        "QB": 1.30,
        "RB": 1.47,
        "WR": 1.58,
        "TE": 1.55,
        "DST": 1.78,
    }.get(position, 1.45)

    stability = _opportunity_stability_score(row)

    prior_weight = pd.to_numeric(
        pd.Series([row.get("role_prior_weight", 0.15)]),
        errors="coerce",
    ).iloc[0]

    if pd.isna(prior_weight):
        prior_weight = 0.15

    prior_weight = float(
        min(max(prior_weight, 0.0), 1.0)
    )

    # Higher workload stability lifts the floor.
    floor_multiplier = (
        base_floor
        + stability * 0.10
        - prior_weight * 0.10
    )

    # Role uncertainty and lower-volume roles create more upside spread.
    ceiling_multiplier = (
        base_ceiling
        + (1.0 - stability) * 0.08
        + prior_weight * 0.12
    )

    floor_multiplier = min(
        max(floor_multiplier, 0.35),
        0.88,
    )

    ceiling_multiplier = min(
        max(ceiling_multiplier, 1.18),
        1.95,
    )

    return floor_multiplier, ceiling_multiplier


def add_ll_projections(players):
    """
    Add LineupLab projection outputs.

    Floor and ceiling are player-specific rather than fixed percentages:
      - position sets the base volatility profile;
      - recent workload affects stability;
      - early-season role uncertainty widens the range.
    """

    players = players.copy()

    players["ll_projection"] = players.apply(
        calculate_ll_projection,
        axis=1,
    )

    range_multipliers = players.apply(
        _projection_range_multipliers,
        axis=1,
        result_type="expand",
    )

    range_multipliers.columns = [
        "_floor_multiplier",
        "_ceiling_multiplier",
    ]

    players = pd.concat(
        [players, range_multipliers],
        axis=1,
    )

    players["ll_floor"] = (
        players["ll_projection"]
        * players["_floor_multiplier"]
    )

    players["ll_ceiling"] = (
        players["ll_projection"]
        * players["_ceiling_multiplier"]
    )

    players["ll_value"] = (
        players["ll_projection"]
        / players["salary"]
        * 1000
    )

    players = players.drop(
        columns=[
            "_floor_multiplier",
            "_ceiling_multiplier",
        ],
        errors="ignore",
    )

    return players

def add_optimizer_scores(players):
    """
    Add LineupLab Cash and GPP optimizer scores.

    Scores are normalized within each position so QB, RB, WR,
    TE and DST are evaluated relative to their own player pools.

    Cash emphasizes:
      - median projection
      - value
      - floor

    GPP emphasizes:
      - ceiling
      - median projection
      - value

    Ownership/leverage will be added later if we obtain
    reliable ownership projections.
    """

    players = players.copy()

    score_cols = [
        "ll_projection",
        "ll_floor",
        "ll_ceiling",
        "ll_value",
        "game_script_score"
    ]

    for col in score_cols:
        players[f"{col}_pct"] = (
            players.groupby("position")[col]
            .rank(
                pct=True,
                method="average",
            )
            * 100
        )

    players["cash_score"] = (
        players["ll_projection_pct"] * 0.45
        + players["ll_value_pct"] * 0.30
        + players["ll_floor_pct"] * 0.15
        + players["game_script_score_pct"] * 0.10
    ).round(1)

    players["gpp_score"] = (
        players["ll_ceiling_pct"] * 0.35
        + players["ll_projection_pct"] * 0.30
        + players["ll_value_pct"] * 0.20
        + players["game_script_score_pct"] * 0.15
    ).round(1)

    # Remove temporary percentile columns.
    temp_cols = [
        f"{col}_pct"
        for col in score_cols
    ]

    players = players.drop(
        columns=temp_cols,
        errors="ignore",
    )

    return players

def add_strategy_projections(players):
    """
    Add strategy-specific optimizer projections in DK-point units.

    CASH:
      - heavily anchored to median projection
      - modest floor/stability influence
      - modest value influence

    GPP:
      - anchored to median projection
      - rewards ceiling
      - rewards game environment
      - rewards salary efficiency/value

    Correlation itself remains handled by optimizer constraints.
    """

    players = players.copy()

    # ---------------------------------
    # Make sure inputs are numeric
    # ---------------------------------

    numeric_cols = [
        "ll_projection",
        "ll_floor",
        "ll_ceiling",
        "ll_value",
        "game_script_score",
    ]

    for col in numeric_cols:
        players[col] = pd.to_numeric(
            players[col],
            errors="coerce",
        )

    # ---------------------------------
    # Position-relative VALUE percentile
    # ---------------------------------

    players["strategy_value_pct"] = (
        players.groupby("position")["ll_value"]
        .rank(
            pct=True,
            method="average",
        )
        .fillna(0.5)
    )

    # ---------------------------------
    # Normalize game environment
    # 0.0 to 1.0
    # ---------------------------------

    players["strategy_environment"] = (
        players["game_script_score"]
        .fillna(50)
        .clip(0, 100)
        / 100
    )

    # ---------------------------------
    # CASH PROJECTION
    # ---------------------------------

    # Base stays very close to expected points.
    cash_base = (
        players["ll_projection"] * 0.85
        + players["ll_floor"] * 0.15
    )

    # Small value bump/penalty:
    # approximately -3% to +3%
    cash_value_multiplier = (
        0.97
        + players["strategy_value_pct"] * 0.06
    )

    players["cash_projection"] = (
        cash_base
        * cash_value_multiplier
    ).round(3)

    # ---------------------------------
    # GPP PROJECTION v2
    # ---------------------------------

    # Ceiling component provides upside emphasis.
    gpp_base = (
        players["ll_projection"] * 0.70
        + players["ll_ceiling"] * 0.30
    )

    # Environment:
    # poor environments can lose ~5%;
    # elite environments can gain ~5%.
    environment_multiplier = (
        0.95
        + players["strategy_environment"] * 0.10
    )

    # Value:
    # cheap upside can move roughly -4% to +4%.
    gpp_value_multiplier = (
        0.96
        + players["strategy_value_pct"] * 0.08
    )

    players["gpp_projection"] = (
        gpp_base
        * environment_multiplier
        * gpp_value_multiplier
    ).round(3)

    # ---------------------------------
    # Clean temporary columns
    # ---------------------------------

    players = players.drop(
        columns=[
            "strategy_value_pct",
            "strategy_environment",
        ],
        errors="ignore",
    )

    return players

def expected_dst_points_allowed_score(opponent_implied_total):
    """
    Convert the opponent's Vegas implied total into the DraftKings
    DST points-allowed scoring component.

    DraftKings NFL DST points allowed:
      0 points      -> +10
      1-6 points    -> +7
      7-13 points   -> +4
      14-20 points  -> +1
      21-27 points  ->  0
      28-34 points  -> -1
      35+ points    -> -4

    For v0.2 we use the opponent implied total as the expected scoring
    outcome and assign the corresponding DK scoring bucket.
    """

    try:
        points = float(opponent_implied_total)
    except (TypeError, ValueError):
        return 0.0

    if pd.isna(points):
        return 0.0

    if points <= 0:
        return 10.0
    if points <= 6:
        return 7.0
    if points <= 13:
        return 4.0
    if points <= 20:
        return 1.0
    if points <= 27:
        return 0.0
    if points <= 34:
        return -1.0

    return -4.0


def project_dst(row):
    """
    LineupLab DST Projection v0.2.

    Combines recent defensive production with the DraftKings
    points-allowed scoring component estimated from the opponent's
    Vegas implied total.
    """

    sacks = row.get("recent_def_sacks", 0)
    interceptions = row.get("recent_def_interceptions", 0)
    fumble_recoveries = row.get(
        "recent_fumble_recovery_opp",
        0,
    )
    defensive_tds = row.get("recent_def_tds", 0)
    special_teams_tds = row.get(
        "recent_special_teams_tds",
        0,
    )
    safeties = row.get("recent_def_safeties", 0)

    values = [
        sacks,
        interceptions,
        fumble_recoveries,
        defensive_tds,
        special_teams_tds,
        safeties,
    ]

    values = [
        0 if pd.isna(v) else v
        for v in values
    ]

    (
        sacks,
        interceptions,
        fumble_recoveries,
        defensive_tds,
        special_teams_tds,
        safeties,
    ) = values

    points_allowed_score = expected_dst_points_allowed_score(
        row.get("opponent_implied_total", np.nan)
    )

    dk_points = (
        sacks * 1
        + interceptions * 2
        + fumble_recoveries * 2
        + defensive_tds * 6
        + special_teams_tds * 6
        + safeties * 2
        + points_allowed_score
    )

    return dk_points

def adjust_dst_for_game_environment(row, base_projection):
    """
    Apply a modest DST game-script adjustment after the DraftKings
    points-allowed component has already been incorporated.

    Opponent implied total is intentionally NOT used again here;
    doing so would double-count the same Vegas information.

    DST still benefits from being favored because favorable game scripts
    can create more obvious passing situations and turnover/sack chances.
    """

    if pd.isna(base_projection):
        return np.nan

    spread = row.get("spread", np.nan)

    adjustment = 1.0

    if not pd.isna(spread):
        if spread <= -7:
            adjustment += 0.08
        elif spread <= -3:
            adjustment += 0.04
        elif spread >= 7:
            adjustment -= 0.08
        elif spread >= 3:
            adjustment -= 0.04

    adjustment = min(max(adjustment, 0.90), 1.10)

    return base_projection * adjustment