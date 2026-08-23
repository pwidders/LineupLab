import nflreadpy as nfl
import pandas as pd

from nfl.projections import (
    build_recent_player_baselines,
    weighted_recent_average,
)


def load_weekly_player_stats(seasons):
    """
    Load nflverse player statistics for one or more NFL seasons.
    Returns a pandas DataFrame for use inside LineupLab.
    """

    df = nfl.load_player_stats(seasons)

    # nflreadpy returns a Polars DataFrame.
    # Convert it to pandas so the rest of LineupLab can use
    # the same dataframe structure as the MLB app.
    if hasattr(df, "to_pandas"):
        df = df.to_pandas()

    return df


def get_available_columns(season=2025):
    """
    Helper for development/debugging.
    Returns the fields currently available from nflverse.
    """

    df = load_weekly_player_stats([season])

    return pd.DataFrame(
        {
            "Column": df.columns,
            "Data Type": [str(df[col].dtype) for col in df.columns],
        }
    )

DFS_POSITIONS = ["QB", "RB", "WR", "TE"]


def get_dfs_player_stats(seasons):
    """
    Return only DFS-relevant offensive players from nflverse.
    """
    df = load_weekly_player_stats(seasons)

    # Exclude preseason/postseason data from player baselines.
    if "season_type" in df.columns:
        df = df[
            df["season_type"]
            .fillna("")
            .astype(str)
            .str.upper()
            .eq("REG")
        ].copy()

    df = df[df["position"].isin(DFS_POSITIONS)].copy()

    return df.reset_index(drop=True)

def get_player_baselines(seasons):
    """
    Build a season-level baseline for DFS-relevant offensive players.

    Uses per-game averages so LineupLab can attach historical
    opportunity and fantasy production to the current DK slate.
    """

    df = get_dfs_player_stats(seasons)

    # Columns we want for our first baseline model
    numeric_cols = [
        "carries",
        "targets",
        "fantasy_points",
        "fantasy_points_ppr",
        "passing_yards",
        "passing_tds",
        "passing_interceptions",
        "rushing_yards",
        "rushing_tds",
        "receptions",
        "receiving_yards",
        "receiving_tds",
    ]

    available_cols = [col for col in numeric_cols if col in df.columns]

    baselines = (
        df.groupby(
            ["player_display_name", "position"],
            as_index=False,
        )[available_cols]
        .mean()
    )

    rename_map = {
        "player_display_name": "player",
        "carries": "avg_carries",
        "targets": "avg_targets",
        "fantasy_points": "avg_fantasy_points",
        "fantasy_points_ppr": "avg_fantasy_points_ppr",
        "passing_yards": "avg_passing_yards",
        "passing_tds": "avg_passing_tds",
        "passing_interceptions": "avg_interceptions",
        "rushing_yards": "avg_rushing_yards",
        "rushing_tds": "avg_rushing_tds",
        "receptions": "avg_receptions",
        "receiving_yards": "avg_receiving_yards",
        "receiving_tds": "avg_receiving_tds",
    }

    baselines = baselines.rename(columns=rename_map)

    return baselines

def get_recent_baselines(seasons):
    """
    Return recent-weighted DFS player baselines.

    Also preserves each player's latest historical team so the
    2026 role layer can detect offseason team changes.
    """

    stats = get_dfs_player_stats(seasons)
    baselines = build_recent_player_baselines(stats)

    team_col = None
    for candidate in ["recent_team", "team"]:
        if candidate in stats.columns:
            team_col = candidate
            break

    if team_col is not None:
        latest_team = (
            stats.sort_values(["player_display_name", "week"])
            .groupby(["player_display_name", "position"], as_index=False)
            .tail(1)[["player_display_name", "position", team_col]]
            .rename(
                columns={
                    "player_display_name": "player",
                    team_col: "historical_team",
                }
            )
        )

        baselines = baselines.merge(
            latest_team,
            on=["player", "position"],
            how="left",
        )

    return baselines

def get_recent_dst_baselines(seasons):
    """
    Build recent-weighted team defense baselines from nflverse.
    """

    df = nfl.load_team_stats(seasons)

    if hasattr(df, "to_pandas"):
        df = df.to_pandas()

    stat_columns = [
        "def_sacks",
        "def_interceptions",
        "fumble_recovery_opp",
        "def_tds",
        "special_teams_tds",
        "def_safeties",
    ]

    df = df.sort_values(["team", "week"])

    rows = []

    for team, group in df.groupby("team"):
        row = {"team": team}

        for col in stat_columns:
            row[f"recent_{col}"] = weighted_recent_average(
                group[col]
            )

        rows.append(row)

    return pd.DataFrame(rows)