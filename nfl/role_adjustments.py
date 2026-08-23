import numpy as np
import pandas as pd


# Week 1 / early-season workload priors.
# These are intentionally conservative and salary-aware. They are not
# "projections" by themselves; they supply opportunity when last-season
# history is missing or clearly stale.
ROLE_PRIORS = {
    "QB": {
        "high": {"attempts": 34.0, "rushing_yards": 18.0},
        "mid":  {"attempts": 31.0, "rushing_yards": 12.0},
        "low":  {"attempts": 27.0, "rushing_yards": 8.0},
    },
    "RB": {
        "high": {"carries": 16.0, "targets": 4.5},
        "mid":  {"carries": 11.0, "targets": 3.0},
        "low":  {"carries": 6.0, "targets": 2.0},
    },
    "WR": {
        "high": {"targets": 8.0},
        "mid":  {"targets": 5.5},
        "low":  {"targets": 3.5},
    },
    "TE": {
        "high": {"targets": 6.5},
        "mid":  {"targets": 4.5},
        "low":  {"targets": 2.8},
    },
}


def _salary_tier(position, salary):
    """Position-specific DK salary tier used only as an early-season role prior."""
    if pd.isna(salary):
        return "low"

    salary = float(salary)

    thresholds = {
        "QB": (6500, 5600),
        "RB": (6500, 5000),
        "WR": (6500, 4800),
        "TE": (5000, 3500),
    }
    high, mid = thresholds.get(position, (999999, 999998))

    if salary >= high:
        return "high"
    if salary >= mid:
        return "mid"
    return "low"


def _num(row, key):
    value = row.get(key, np.nan)
    return pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]


def _blend(old, prior, prior_weight):
    if pd.isna(old):
        return prior
    return old * (1.0 - prior_weight) + prior * prior_weight


def _has_history(row, position):
    if position == "QB":
        return not pd.isna(_num(row, "recent_attempts")) and _num(row, "recent_attempts") > 0
    if position == "RB":
        return not pd.isna(_num(row, "recent_carries"))
    if position in ("WR", "TE"):
        return not pd.isna(_num(row, "recent_targets"))
    return True


def apply_role_adjustments(players):
    """
    Add LineupLab's early-season role-transition layer.

    Goals:
      1. Prevent rookies/new starters/no-history players from becoming NaN.
      2. Reduce the assumption that a player's late-2025 workload is frozen.
      3. Flag every adjustment so it can be audited later in Performance Center.

    The layer is deliberately conservative:
      - stable-history players keep 90% of their historical opportunity;
      - players who changed teams keep 75% of history;
      - no-history players use salary-tier workload priors.

    It does NOT pretend to know a live depth chart. Manual/live depth-chart
    overrides can be added later without changing the projection model.
    """
    players = players.copy()

    if "historical_team" not in players.columns:
        players["historical_team"] = np.nan

    players["role_tier"] = players.apply(
        lambda r: _salary_tier(r.get("position"), r.get("salary")),
        axis=1,
    )
    players["role_source"] = "2025 recent baseline"
    players["role_adjustment"] = "stable"
    players["role_prior_weight"] = 0.10

    for idx, row in players.iterrows():
        pos = row.get("position")
        if pos not in ROLE_PRIORS:
            continue

        tier = row["role_tier"]
        priors = ROLE_PRIORS[pos][tier]
        has_history = _has_history(row, pos)

        current_team = str(row.get("team", "") or "").upper()
        historical_team = str(row.get("historical_team", "") or "").upper()
        changed_team = (
            historical_team not in ("", "NAN", "NONE")
            and current_team not in ("", "NAN", "NONE")
            and historical_team != current_team
        )

        if not has_history:
            prior_weight = 1.0
            source = "2026 salary-tier fallback (true no-history / unmatched)"
            adjustment = "no 2025 usable history"
        elif changed_team:
            prior_weight = 0.25
            source = "2025 baseline + 2026 team-change prior"
            adjustment = f"team change {historical_team}->{current_team}"
        else:
            prior_weight = 0.10
            source = "2025 baseline + light 2026 role prior"
            adjustment = "early-season role regression"

        players.at[idx, "role_prior_weight"] = prior_weight
        players.at[idx, "role_source"] = source
        players.at[idx, "role_adjustment"] = adjustment

        if pos == "QB":
            players.at[idx, "recent_attempts"] = _blend(
                _num(row, "recent_attempts"), priors["attempts"], prior_weight
            )
            if pd.isna(_num(row, "recent_completions")):
                players.at[idx, "recent_completions"] = players.at[idx, "recent_attempts"] * 0.65
            if pd.isna(_num(row, "recent_passing_yards")):
                players.at[idx, "recent_passing_yards"] = players.at[idx, "recent_attempts"] * 7.2
            if pd.isna(_num(row, "recent_passing_tds")):
                players.at[idx, "recent_passing_tds"] = players.at[idx, "recent_attempts"] * 0.045
            if pd.isna(_num(row, "recent_passing_interceptions")):
                players.at[idx, "recent_passing_interceptions"] = players.at[idx, "recent_attempts"] * 0.022
            players.at[idx, "recent_rushing_yards"] = _blend(
                _num(row, "recent_rushing_yards"), priors["rushing_yards"], prior_weight
            )
            if pd.isna(_num(row, "recent_rushing_tds")):
                players.at[idx, "recent_rushing_tds"] = 0.12

        elif pos == "RB":
            players.at[idx, "recent_carries"] = _blend(
                _num(row, "recent_carries"), priors["carries"], prior_weight
            )
            players.at[idx, "recent_targets"] = _blend(
                _num(row, "recent_targets"), priors["targets"], prior_weight
            )
            targets = players.at[idx, "recent_targets"]
            if pd.isna(_num(row, "recent_receptions")):
                players.at[idx, "recent_receptions"] = targets * 0.75
            carries = players.at[idx, "recent_carries"]
            if pd.isna(_num(row, "recent_rushing_yards")):
                players.at[idx, "recent_rushing_yards"] = carries * 4.3
            if pd.isna(_num(row, "recent_receiving_yards")):
                players.at[idx, "recent_receiving_yards"] = targets * 0.75 * 7.5
            if pd.isna(_num(row, "recent_rushing_tds")):
                players.at[idx, "recent_rushing_tds"] = 0.30
            if pd.isna(_num(row, "recent_receiving_tds")):
                players.at[idx, "recent_receiving_tds"] = 0.06

        elif pos in ("WR", "TE"):
            players.at[idx, "recent_targets"] = _blend(
                _num(row, "recent_targets"), priors["targets"], prior_weight
            )
            targets = players.at[idx, "recent_targets"]
            catch_rate = 0.70 if pos == "TE" else 0.65
            ypr = 10.5 if pos == "TE" else 12.0
            if pd.isna(_num(row, "recent_receptions")):
                players.at[idx, "recent_receptions"] = targets * catch_rate
            receptions = players.at[idx, "recent_receptions"]
            if pd.isna(_num(row, "recent_receiving_yards")):
                players.at[idx, "recent_receiving_yards"] = receptions * ypr
            if pd.isna(_num(row, "recent_receiving_tds")):
                players.at[idx, "recent_receiving_tds"] = 0.20 if pos == "TE" else 0.25
            if pd.isna(_num(row, "recent_rushing_yards")):
                players.at[idx, "recent_rushing_yards"] = 0.0
            if pd.isna(_num(row, "recent_rushing_tds")):
                players.at[idx, "recent_rushing_tds"] = 0.0

    return players