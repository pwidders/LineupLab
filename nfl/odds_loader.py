import requests
import pandas as pd


NFL_ODDS_URL = (
    "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
)


def load_nfl_odds(
    api_key,
    commence_time_from=None,
    commence_time_to=None,
):
    """
    Load current NFL spreads and totals from The Odds API.

    Optional commence-time filters allow LineupLab to request
    only games from the DraftKings slate date.
    """

    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "spreads,totals",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }

    if commence_time_from:
        params["commenceTimeFrom"] = commence_time_from

    if commence_time_to:
        params["commenceTimeTo"] = commence_time_to

    response = requests.get(
        NFL_ODDS_URL,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    rows = []

    for game in data:
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        commence_time = game.get("commence_time")

        bookmakers = game.get("bookmakers", [])

        if not bookmakers:
            continue

        # v0.1: use first available bookmaker
        bookmaker = bookmakers[0]

        spread_market = None
        total_market = None

        for market in bookmaker.get("markets", []):
            if market.get("key") == "spreads":
                spread_market = market

            elif market.get("key") == "totals":
                total_market = market

        game_total = None
        home_spread = None
        away_spread = None

        if total_market:
            for outcome in total_market.get("outcomes", []):
                if outcome.get("name") == "Over":
                    game_total = outcome.get("point")
                    break

        if spread_market:
            for outcome in spread_market.get("outcomes", []):
                if outcome.get("name") == home_team:
                    home_spread = outcome.get("point")

                elif outcome.get("name") == away_team:
                    away_spread = outcome.get("point")

        rows.append(
            {
                "commence_time": commence_time,
                "home_team_name": home_team,
                "away_team_name": away_team,
                "game_total": game_total,
                "home_spread": home_spread,
                "away_spread": away_spread,
            }
        )

    return pd.DataFrame(rows)

TEAM_NAME_TO_ABBREV = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}


def normalize_odds_teams(odds_df):
    """
    Convert Odds API full team names to DraftKings abbreviations.
    """

    df = odds_df.copy()

    df["home_team"] = df["home_team_name"].map(TEAM_NAME_TO_ABBREV)
    df["away_team"] = df["away_team_name"].map(TEAM_NAME_TO_ABBREV)

    return df