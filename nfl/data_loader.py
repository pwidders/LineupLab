import pandas as pd


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