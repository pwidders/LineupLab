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

# QB role overrides for early-season / depth-chart uncertainty.
#
# "starter" = eligible for LineupLab's starting-QB workload fallback
# "backup"  = never eligible for the optimizer unless this is changed
#
# Add/update players here as depth charts change.
QB_ROLE_OVERRIDES = {
    "Tyler Shough": "starter",
    "Luke Altmyer": "backup",
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


def _history_strength(row, position):
    """
    Classify how trustworthy the late-2025 workload is for Week 1.

    "none"   = no usable recent NFL workload
    "thin"   = some history exists, but not enough to assume the old role
               should carry forward unchanged
    "stable" = meaningful recent workload exists

    The thresholds are intentionally modest. This is a role-confidence layer,
    not a player-quality model.
    """
    if position == "QB":
        attempts = _num(row, "recent_attempts")

        if pd.isna(attempts) or attempts <= 0:
            return "none"

        if attempts < 15:
            return "thin"

        return "stable"

    if position == "RB":
        carries = _num(row, "recent_carries")
        targets = _num(row, "recent_targets")

        carries = 0 if pd.isna(carries) else carries
        targets = 0 if pd.isna(targets) else targets

        if carries <= 0 and targets <= 0:
            return "none"

        if carries < 6 and targets < 2:
            return "thin"

        return "stable"

    if position in ("WR", "TE"):
        targets = _num(row, "recent_targets")

        if pd.isna(targets) or targets <= 0:
            return "none"

        if targets < 3:
            return "thin"

        return "stable"

    return "stable"


def select_qb_starters(players, overrides=None):
    """Return team -> approved DK ID (or None). Automatic picks are estimates."""
    overrides = overrides or {}
    result = {}
    qbs = players[players["position"].eq("QB")].copy()
    if "status" in qbs:
        qbs = qbs[~qbs["status"].fillna("").astype(str).str.strip().str.upper().isin({"OUT", "O", "IR", "D", "DOUBTFUL"})]
    for team, group in qbs.groupby("team"):
        if team in overrides:
            chosen = overrides[team]
            result[team] = str(chosen) if chosen is not None and str(chosen) in set(group["dk_id"].astype(str)) else None
            continue
        group = group.sort_values("salary", ascending=False)
        top = group.iloc[0]
        # Salary is only a role proxy, never a live depth chart.
        clear_salary = len(group) == 1 or top["salary"] - group.iloc[1]["salary"] >= 500
        if (clear_salary and _num(top, "current_season_games") >= 3
                and _num(top, "recent_attempts") >= 20
                and QB_ROLE_OVERRIDES.get(top["player"]) != "backup"):
            result[team] = str(top["dk_id"])
        else:
            result[team] = None
    return result


def apply_role_adjustments(players, qb_overrides=None):
    """
    Add LineupLab's early-season role-transition layer.

    Goals:
      1. Prevent rookies/new starters/no-history players from becoming NaN.
      2. Reduce the assumption that a player's late-2025 workload is frozen.
      3. Flag every adjustment so it can be audited later in Performance Center.

    The layer is deliberately conservative:
      - stable-history players keep 85% of historical opportunity;
      - players with only thin recent usage lean 50% on the current role prior;
      - players who changed teams keep 65% of historical opportunity;
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
    players["role_prior_weight"] = 0.15
    players["optimizer_eligible"] = True
    players["qb_starter_verified"] = False

    approved_qbs = select_qb_starters(players, qb_overrides)

    for idx, row in players.iterrows():
        pos = row.get("position")
        if pos not in ROLE_PRIORS:
            continue

        tier = row["role_tier"]
        priors = ROLE_PRIORS[pos][tier]
        history_strength = _history_strength(row, pos)

        current_team = str(row.get("team", "") or "").upper()
        historical_team = str(row.get("historical_team", "") or "").upper()
        changed_team = (
            historical_team not in ("", "NAN", "NONE")
            and current_team not in ("", "NAN", "NONE")
            and historical_team != current_team
        )

        games = _num(row, "current_season_games")
        games = 0 if pd.isna(games) else int(games)
        if pos == "QB":
            if approved_qbs.get(row.get("team")) != str(row.get("dk_id")):
                players.at[idx, "optimizer_eligible"] = False
                players.at[idx, "role_source"] = "QB starter protection"
                players.at[idx, "role_adjustment"] = "not approved team starter"
                players.at[idx, "role_prior_weight"] = 0.0
                continue
            players.at[idx, "qb_starter_verified"] = True

        if history_strength == "none":
            # No-history RB/WR/TE players are too uncertain to enter the
            # optimizer automatically. Keep them visible in projections,
            # but require a future role override before they become eligible.
            if pos in ("RB", "WR", "TE"):
                players.at[idx, "optimizer_eligible"] = False
                players.at[idx, "role_source"] = "unverified skill-position role"
                players.at[idx, "role_adjustment"] = "no usable NFL workload / role unverified"
                players.at[idx, "role_prior_weight"] = 0.0
                continue
            
            prior_weight = 1.0
            source = "2026 salary-tier fallback (true no-history / unmatched)"
            adjustment = "no 2025 usable history"

        elif changed_team:
            prior_weight = 0.35
            source = "2025 baseline + stronger 2026 team-change prior"
            adjustment = f"team change {historical_team}->{current_team}"

        elif history_strength == "thin":
            prior_weight = 0.50
            source = "thin 2025 workload + 2026 salary-tier role prior"
            adjustment = "thin recent workload / role uncertainty"

        else:
            prior_weight = 0.15
            source = "2025 baseline + light 2026 role prior"
            adjustment = "early-season role regression"

        # Fade salary priors as actual current-season evidence accumulates.
        if history_strength != "none":
            prior_weight *= max(0.0, 1.0 - games / 5.0)
            if games >= 5:
                source = "current-season workload"
                adjustment = "salary prior retired"
        players.at[idx, "role_prior_weight"] = prior_weight
        players.at[idx, "role_source"] = source
        players.at[idx, "role_adjustment"] = adjustment

        if pos == "QB":
            players.at[idx, "role_source"] = ("manual QB approval" if row.get("team") in (qb_overrides or {}) else "inferred QB starter")
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

def add_workload_confidence(players, approved_ids=()):
    """Conservative sample-size policy; approval permits Cash, not a projection boost."""
    players = players.copy()
    skill = players["position"].isin(["RB", "WR", "TE"])
    current = pd.to_numeric(players.get("current_season_games", pd.Series(0, index=players.index)), errors="coerce").fillna(0).clip(lower=0)
    total = pd.to_numeric(players.get("baseline_games", pd.Series(0, index=players.index)), errors="coerce").fillna(0).clip(lower=0)
    # Prior-season observations count at one quarter of current-season evidence.
    evidence = current + 0.25 * (total - current).clip(lower=0)
    confidence = (evidence / 5).clip(0, 1)
    players["workload_confidence"] = confidence.where(skill, 1.0).round(3)
    players["sample_size_risk"] = np.select(
        [~skill, current.eq(0), evidence.lt(3), evidence.lt(5), current.lt(8)],
        ["not applicable", "unverified", "high", "moderate", "low"], default="established")
    review = skill & (current.eq(0) | evidence.lt(3))
    eligible = players["optimizer_eligible"].eq(True)
    approved = skill & players["dk_id"].astype(str).isin(set(map(str, approved_ids))) & eligible
    players["manual_role_review"] = review & eligible & ~approved
    players["manual_role_approved"] = approved
    players["cash_eligible"] = eligible & (~review | approved)
    return players
