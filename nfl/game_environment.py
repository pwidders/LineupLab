import pandas as pd


def build_game_environment(dk_players):
    """
    Build one row per NFL game from the DraftKings player pool.

    This is the foundation for adding:
      - Vegas game total
      - point spread
      - team implied total
      - opponent implied total
      - favorite / underdog status

    For now, Vegas fields are intentionally left blank.
    """

    if dk_players is None or dk_players.empty:
        return pd.DataFrame()

    required = ["team", "opponent", "home_away", "game_info"]

    missing = [col for col in required if col not in dk_players.columns]
    if missing:
        raise ValueError(
            f"DraftKings player pool is missing columns: {missing}"
        )

    games = (
        dk_players[
            ["team", "opponent", "home_away", "game_info"]
        ]
        .drop_duplicates()
        .copy()
    )

    # Placeholder Vegas fields.
    # We'll populate these in the next step.
    games["game_total"] = None
    games["spread"] = None
    games["team_implied_total"] = None
    games["opponent_implied_total"] = None
    games["is_favorite"] = None

    return games.reset_index(drop=True)

def merge_odds_into_environment(game_environment, odds_df):
    """
    Merge Odds API spreads/totals into LineupLab's team-level
    game environment table.
    """

    env = game_environment.copy()
        # Odds fields must accept numeric values
    numeric_cols = [
        "game_total",
        "spread",
        "team_implied_total",
        "opponent_implied_total",
    ]

    for col in numeric_cols:
        env[col] = pd.to_numeric(env[col], errors="coerce").astype("float64")

    # Boolean favorite flag
    env["is_favorite"] = env["is_favorite"].astype("boolean")

    rows = []

    for _, row in env.iterrows():
        team = row["team"]
        opponent = row["opponent"]

        matchup = odds_df[
            (
                (odds_df["home_team"] == team)
                & (odds_df["away_team"] == opponent)
            )
            |
            (
                (odds_df["away_team"] == team)
                & (odds_df["home_team"] == opponent)
            )
        ]

        new_row = row.to_dict()

        if not matchup.empty:
            odds = matchup.iloc[0]

            if team == odds["home_team"]:
                spread = odds["home_spread"]
            else:
                spread = odds["away_spread"]

            game_total = odds["game_total"]

            new_row["game_total"] = game_total
            new_row["spread"] = spread

            if game_total is not None and spread is not None:
                new_row["team_implied_total"] = (
                    game_total - spread
                ) / 2

                new_row["opponent_implied_total"] = (
                    game_total + spread
                ) / 2

                new_row["is_favorite"] = spread < 0

        rows.append(new_row)

    return pd.DataFrame(rows)

def add_game_script_score(game_environment):
    """
    Add a 0-100 game script score.

    Higher scores favor:
      - favored teams
      - larger negative spreads
      - higher team implied totals
      - lower opponent implied totals
    """

    df = game_environment.copy()

    def scale(series):
        s = pd.to_numeric(series, errors="coerce")

        if s.notna().sum() == 0:
            return pd.Series([50.0] * len(s), index=s.index)

        min_val = s.min()
        max_val = s.max()

        if max_val == min_val:
            return pd.Series([50.0] * len(s), index=s.index)

        return (s - min_val) / (max_val - min_val) * 100

    # More negative spread = better game script
    spread_component = 100 - scale(df["spread"])

    # Higher team total = better
    team_total_component = scale(df["team_implied_total"])

    # Lower opponent total = better for DST
    opponent_total_component = 100 - scale(
        df["opponent_implied_total"]
    )

    df["game_script_score"] = (
        spread_component * 0.45
        + team_total_component * 0.25
        + opponent_total_component * 0.30
    ).round(1)

    return df

def build_dst_rb_pairings(players, game_environment=None):
    """
    Build DST + same-team RB pairing candidates.

    Assumes game-environment fields have already been merged
    onto the player dataframe.
    """

    dst = players[
        players["position"] == "DST"
    ].copy()

    rbs = players[
        (players["position"] == "RB")
        & (players["ll_projection"].fillna(0) >= 8.0)
    ].copy()

    pairings = dst.merge(
        rbs,
        on="team",
        suffixes=("_dst", "_rb"),
    )

    pairings["pair_score"] = (
        pairings["game_script_score_dst"].fillna(0) * 0.55
        + pairings["ll_projection_dst"].fillna(0) * 2.5
        + pairings["ll_projection_rb"].fillna(0) * 1.5
    ).round(1)

    pairings = pairings.sort_values(
        "pair_score",
        ascending=False,
    )

    return pairings

def merge_environment_into_players(players, game_environment):
    """
    Attach team-level Vegas/game environment fields to every player.
    """

    env_cols = [
        "team",
        "game_total",
        "spread",
        "team_implied_total",
        "opponent_implied_total",
        "is_favorite",
        "game_script_score",
    ]

    return players.merge(
        game_environment[env_cols],
        on="team",
        how="left",
    )

def build_qb_pass_catcher_stacks(players):
    """
    Build same-team QB + WR/TE stack candidates.

    Stack score rewards:
      - QB projection
      - pass catcher projection
      - strong game environment
      - higher team implied total
    """

    qb = players[
        players["position"] == "QB"
    ].copy()

    pass_catchers = players[
        players["position"].isin(["WR", "TE"])
    ].copy()

    stacks = qb.merge(
        pass_catchers,
        on="team",
        suffixes=("_qb", "_pc"),
    )

    stacks["stack_score"] = (
        stacks["ll_projection_qb"].fillna(0) * 1.8
        + stacks["ll_projection_pc"].fillna(0) * 1.6
        + stacks["game_script_score_qb"].fillna(0) * 0.25
        + stacks["team_implied_total_qb"].fillna(0) * 0.8
    ).round(1)

    stacks = stacks.sort_values(
        "stack_score",
        ascending=False,
    )

    return stacks