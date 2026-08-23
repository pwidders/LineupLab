import pandas as pd


NAME_ALIASES = {
    "James Cook III": "James Cook",
}


def normalize_player_name(name):
    """
    Normalize player names for cross-source matching.

    Removes punctuation and common suffixes so DraftKings names such as
    'James Cook III' can match historical sources using 'James Cook'.
    """
    if pd.isna(name):
        return ""

    value = str(name).strip()
    value = NAME_ALIASES.get(value, value)

    value = (
        value.replace(".", "")
        .replace("'", "")
        .replace("’", "")
        .replace("-", " ")
    )

    parts = value.split()
    suffixes = {"JR", "SR", "II", "III", "IV", "V"}

    while parts and parts[-1].upper() in suffixes:
        parts = parts[:-1]

    return " ".join(parts).upper()


REQUIRED_DK_COLUMNS = {
    "Position",
    "Name",
    "ID",
    "Salary",
    "Game Info",
    "TeamAbbrev",
    "AvgPointsPerGame",
    "Status",
}


def load_dk_salaries(uploaded_file):
    """
    Load and normalize a DraftKings NFL salary CSV.
    """

    df = pd.read_csv(uploaded_file)

    missing = REQUIRED_DK_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            "DraftKings CSV is missing required columns: "
            + ", ".join(sorted(missing))
        )

    df = df.copy()

    # Rename DK columns into LineupLab's internal format
    df = df.rename(
        columns={
            "Name": "player",
            "ID": "dk_id",
            "Position": "position",
            "Salary": "salary",
            "Game Info": "game_info",
            "TeamAbbrev": "team",
            "AvgPointsPerGame": "dk_avg_points",
            "Status": "status",
        }
    )

    # Clean basic fields
    df["player"] = df["player"].astype(str).str.strip()
    df["player_match_key"] = df["player"].map(normalize_player_name)
    df["position"] = df["position"].astype(str).str.strip().str.upper()
    df["team"] = df["team"].astype(str).str.strip().str.upper()

    df["salary"] = pd.to_numeric(df["salary"], errors="coerce")
    df["dk_avg_points"] = pd.to_numeric(
        df["dk_avg_points"], errors="coerce"
    )

    df["status"] = df["status"].fillna("").astype(str).str.strip().str.upper()

    # Parse matchup from strings such as:
    # DET@CIN 08/13/2026 07:00PM ET
    matchup = df["game_info"].str.extract(
        r"(?P<away>[A-Z]+)@(?P<home>[A-Z]+)"
    )

    df["away_team"] = matchup["away"]
    df["home_team"] = matchup["home"]

    # Determine opponent
    df["opponent"] = df.apply(
        lambda row: (
            row["home_team"]
            if row["team"] == row["away_team"]
            else row["away_team"]
        ),
        axis=1,
    )

    # Home / Away indicator
    df["home_away"] = df.apply(
        lambda row: "HOME"
        if row["team"] == row["home_team"]
        else "AWAY",
        axis=1,
    )

    # Keep only NFL Classic positions
    valid_positions = ["QB", "RB", "WR", "TE", "DST"]
    df = df[df["position"].isin(valid_positions)].copy()

    # LineupLab's standard NFL player-pool order
    columns = [
        "dk_id",
        "player",
        "position",
        "team",
        "opponent",
        "home_away",
        "salary",
        "dk_avg_points",
        "status",
        "game_info",
    ]

    return df[columns].reset_index(drop=True)

def merge_with_dst_baselines(players, dst_baselines):
    """
    Merge team-defense baselines onto current DK DST rows.
    """

    merged = players.merge(
        dst_baselines,
        on="team",
        how="left",
    )

    return merged

def merge_with_baselines(dk_players, baselines):
    """
    Merge current DraftKings slate players with historical/recent NFL baselines.

    Matching order:
      1. exact player + position match
      2. normalized name + position fallback
    """

    # Reset indices because the app may have filtered OUT players before this
    # merge, leaving gaps in the DraftKings dataframe index. Boolean masks built
    # from the merged dataframe must align positionally with this dataframe.
    left = dk_players.copy().reset_index(drop=True)
    right = baselines.copy().reset_index(drop=True)

    if "player_match_key" not in left.columns:
        left["player_match_key"] = left["player"].map(normalize_player_name)

    right["player_match_key"] = right["player"].map(normalize_player_name)

    merged = left.merge(
        right,
        on=["player", "position"],
        how="left",
        suffixes=("", "_baseline"),
    )

    baseline_value_cols = [
        c for c in right.columns
        if c not in {"player", "position", "player_match_key"}
    ]

    if baseline_value_cols:
        missing_mask = merged[baseline_value_cols].isna().all(axis=1)
    else:
        missing_mask = pd.Series(False, index=merged.index)

    if missing_mask.any():
        fallback_left = left.iloc[
            missing_mask.to_numpy().nonzero()[0]
        ][["player_match_key", "position"]].copy()

        fallback = fallback_left.merge(
            right.drop(columns=["player"]),
            on=["player_match_key", "position"],
            how="left",
        )

        for col in baseline_value_cols:
            if col in fallback.columns:
                merged.loc[missing_mask, col] = fallback[col].values

    return merged.drop(columns=["player_match_key"], errors="ignore")