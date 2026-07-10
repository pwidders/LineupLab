import pandas as pd
import pulp

def percent_rank(series):
    series = pd.to_numeric(series, errors="coerce").fillna(0)
    return series.rank(pct=True)

def find_col(df, possible_names):
    cols = {c.strip().lower(): c for c in df.columns}
    for name in possible_names:
        if name.lower() in cols:
            return cols[name.lower()]
    raise KeyError(f"Could not find any of these columns: {possible_names}")

def compute_pitcher_ratings(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    projection_col = find_col(df, ["Projection"])
    value_col = find_col(df, ["Projected value", "Value"])
    hr_col = find_col(df, ["Pitcher HR rate", "HR"])
    opp_runs_col = find_col(df, ["Opp Projected Point total", "OppRuns"])
    k_col = find_col(df, ["K %", "K%"])
    opp_k_col = find_col(df, ["OPP K %", "Opp K%"])

    df["Cash"] = (
        0.4 * percent_rank(df[projection_col]) +
        0.3 * percent_rank(df[value_col]) +
        0.2 * (1 - percent_rank(df[hr_col])) +
        0.1 * (1 - percent_rank(df[opp_runs_col]))
    ) * 100

    df["GPP"] = (
        0.35 * percent_rank(df[projection_col]) +
        0.3 * percent_rank(df[k_col]) +
        0.2 * percent_rank(df[opp_k_col]) +
        0.1 * (1 - percent_rank(df[hr_col])) +
        0.05 * percent_rank(df[value_col])
    ) * 100

    df["Overall"] = (df["Cash"] * 0.65 + df["GPP"] * 0.35)

    return df

def compute_hitter_ratings(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    def percent_rank(series):
        series = pd.to_numeric(series, errors="coerce").fillna(0)
        return series.rank(pct=True)

    # Find columns (flexible naming)
    projection = find_col(df, ["Projection"])
    value = find_col(df, ["Projected value"])
    hr_weight = find_col(df, ["HR weight"])
    team_runs = find_col(df, ["Team Implied Runs"])

    df["Cash"] = (
        0.4 * percent_rank(df[projection]) +
        0.25 * percent_rank(df[value]) +
        0.2 * percent_rank(df[team_runs]) +
        0.15 * percent_rank(df[hr_weight])
    ) * 100

    df["GPP"] = (
        0.35 * percent_rank(df[projection]) +
        0.3 * percent_rank(df[hr_weight]) +
        0.2 * percent_rank(df[team_runs]) +
        0.15 * percent_rank(df[value])
    ) * 100

    df["Overall"] = (df["Cash"] * 0.5 + df["GPP"] * 0.5)

    return df

def build_stacks(hitters):
    df = hitters.copy()

    # Ensure numeric
    df["Overall"] = pd.to_numeric(df["Overall"], errors="coerce").fillna(0)

    stacks = []

    for team, group in df.groupby("Team"):
        top_hitters = group.sort_values("Overall", ascending=False).head(5)

        stack_score = top_hitters["Overall"].mean()

        stacks.append({
            "Team": team,
            "Stack Score": round(stack_score, 2),
            "Players": ", ".join(top_hitters["Players"].astype(str))
        })

    stacks_df = pd.DataFrame(stacks).sort_values("Stack Score", ascending=False)

    return stacks_df

from itertools import combinations

DK_SALARY_CAP = 50000

def find_optional_col(df, names):
    cols = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in cols:
            return cols[name.lower()]
    return None

def assign_hitter_slots(hitter_rows, pos_col):
    slots = ["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]
    assigned = []
    used_indexes = set()

    for slot in slots:
        for idx, row in hitter_rows.iterrows():
            if idx in used_indexes:
                continue

            positions = str(row[pos_col]).split("/")
            positions = [p.strip() for p in positions]

            if slot in positions:
                assigned.append((slot, idx))
                used_indexes.add(idx)
                break

    if len(assigned) != 8:
        return None

    return assigned

def build_stack_lineup(hitters, pitchers, stacks_df):
    hitters = hitters.copy()
    pitchers = pitchers.copy()

    player_col = find_col(hitters, ["Players", "Player", "Name"])
    team_col = find_col(hitters, ["Team"])
    pos_col = find_col(hitters, ["Position", "Pos"])
    salary_col = find_col(hitters, ["Salary"])
    score_col = find_col(hitters, ["Overall"])

    p_player = find_col(pitchers, ["Players", "Player", "Name"])
    p_salary = find_col(pitchers, ["Salary"])
    p_score = find_col(pitchers, ["Overall"])

    def money_to_num(s):
        return pd.to_numeric(
            s.astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False),
            errors="coerce"
        ).fillna(0)

    hitters["_salary"] = money_to_num(hitters[salary_col])
    hitters["_score"] = pd.to_numeric(hitters[score_col], errors="coerce").fillna(0)
    pitchers["_salary"] = money_to_num(pitchers[p_salary])
    pitchers["_score"] = pd.to_numeric(pitchers[p_score], errors="coerce").fillna(0)

    slots = ["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]

    def eligible(row, slot):
        positions = [p.strip() for p in str(row[pos_col]).split("/")]
        return slot in positions

    def assign_slots(rows):
        rows = rows.copy()
        assigned = []
        used = set()

        for slot in slots:
            candidates = rows[~rows.index.isin(used)]
            candidates = candidates[candidates.apply(lambda r: eligible(r, slot), axis=1)]
            candidates = candidates.sort_values("_score", ascending=False)

            if candidates.empty:
                return None

            idx = candidates.index[0]
            used.add(idx)
            assigned.append((slot, idx))

        return assigned

    best_lineup = None
    best_score = -1

    top_pitchers = pitchers.sort_values("_score", ascending=False).head(3)
    stack_teams = stacks_df["Team"].head(2).tolist()

    for primary in stack_teams:
        for secondary in stack_teams:
            if primary == secondary:
                continue

            primary_pool = hitters[hitters[team_col] == primary].sort_values("_score", ascending=False).head(5)
            secondary_pool = hitters[hitters[team_col] == secondary].sort_values("_score", ascending=False).head(4)
            oneoff_pool = hitters[~hitters[team_col].isin([primary, secondary])].sort_values("_score", ascending=False).head(6)

            if len(primary_pool) < 4 or len(secondary_pool) < 3:
                continue

            for p_combo in combinations(top_pitchers.index, 2):
                p_rows = pitchers.loc[list(p_combo)]
                p_salary_total = p_rows["_salary"].sum()
                p_score_total = p_rows["_score"].sum()

                for pri_combo in combinations(primary_pool.index, 4):
                    for sec_combo in combinations(secondary_pool.index, 3):
                        for one_idx in oneoff_pool.index:
                            hitter_indexes = list(pri_combo) + list(sec_combo) + [one_idx]

                            if len(set(hitter_indexes)) != 8:
                                continue

                            h_rows = hitters.loc[hitter_indexes]
                            total_salary = p_salary_total + h_rows["_salary"].sum()

                            if total_salary > DK_SALARY_CAP:
                                continue

                            slot_assignment = assign_slots(h_rows)

                            if slot_assignment is None:
                                continue

                            total_score = p_score_total + h_rows["_score"].sum()

                            if total_score > best_score:
                                final_rows = []

                                for _, row in p_rows.iterrows():
                                    final_rows.append({
                                        "Slot": "P",
                                        "Player": row[p_player],
                                        "Team": row.get("Team", ""),
                                        "Salary": row["_salary"],
                                        "Score": row["_score"]
                                    })

                                for slot, idx in slot_assignment:
                                    row = hitters.loc[idx]
                                    final_rows.append({
                                        "Slot": slot,
                                        "Player": row[player_col],
                                        "Team": row[team_col],
                                        "Salary": row["_salary"],
                                        "Score": row["_score"]
                                    })

                                best_score = total_score
                                best_lineup = pd.DataFrame(final_rows)

    if best_lineup is None:
        return pd.DataFrame(), 0, 0

    return best_lineup, best_lineup["Salary"].sum(), best_lineup["Score"].sum()

def build_real_optimizer_lineup(
    hitters,
    pitchers,
    stacks_df,
    locked_players=None,
    excluded_players=None,
    primary_stack=None,
    secondary_stack=None,
    min_salary=0
):
    locked_players = set([str(p) for p in locked_players]) if locked_players else set()
    excluded_players = set([str(p) for p in excluded_players]) if excluded_players else set()

    hitters = hitters.copy()
    pitchers = pitchers.copy()

    player_col = find_col(hitters, ["Players", "Player", "Name"])
    team_col = find_col(hitters, ["Team"])
    opp_col = find_col(hitters, ["Opponent", "Opp"])
    pos_col = find_col(hitters, ["Position", "Pos"])
    salary_col = find_col(hitters, ["Salary"])
    score_col = find_col(hitters, ["DK Projection", "Projection"])

    p_player_col = find_col(pitchers, ["Players", "Player", "Name"])
    p_team_col = find_col(pitchers, ["Team"])
    p_opp_col = find_col(pitchers, ["Opponent", "Opp"])
    p_salary_col = find_col(pitchers, ["Salary"])
    p_score_col = find_col(pitchers, ["DK Projection", "Projection"])

    def clean_money(series):
        return pd.to_numeric(
            series.astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False),
            errors="coerce"
        ).fillna(0)

    hitters["_salary"] = clean_money(hitters[salary_col])
    hitters["_score"] = pd.to_numeric(hitters[score_col], errors="coerce").fillna(0)
    pitchers["_salary"] = clean_money(pitchers[p_salary_col])
    pitchers["_score"] = pd.to_numeric(pitchers[p_score_col], errors="coerce").fillna(0)

    hitters = hitters[hitters["_salary"] > 0].reset_index(drop=True)
    pitchers = pitchers[pitchers["_salary"] > 0].reset_index(drop=True)

    if primary_stack is None or secondary_stack is None:
        top_stacks = stacks_df["Team"].head(2).astype(str).tolist()
        if len(top_stacks) < 2:
            return pd.DataFrame(), 0, 0
        primary_stack, secondary_stack = top_stacks[0], top_stacks[1]

    primary_stack = str(primary_stack)
    secondary_stack = str(secondary_stack)

    if primary_stack == secondary_stack:
        return pd.DataFrame(), 0, 0

    hitter_slots = ["C", "1B", "2B", "3B", "SS", "OF1", "OF2", "OF3"]

    def eligible(pos_string, slot):
        base_slot = "OF" if slot.startswith("OF") else slot
        positions = [p.strip() for p in str(pos_string).split("/")]
        return base_slot in positions

    prob = pulp.LpProblem("DK_MLB_Lineup", pulp.LpMaximize)

    p_vars = {i: pulp.LpVariable(f"p_{i}", cat="Binary") for i in pitchers.index}

    # Hitter-slot variables
    h_vars = {}
    for i in hitters.index:
        for slot in hitter_slots:
            if eligible(hitters.loc[i, pos_col], slot):
                h_vars[(i, slot)] = pulp.LpVariable(f"h_{i}_{slot}", cat="Binary")

    # Objective
    prob += (
        pulp.lpSum(p_vars[i] * pitchers.loc[i, "_score"] for i in pitchers.index) +
        pulp.lpSum(h_vars[(i, slot)] * hitters.loc[i, "_score"] for (i, slot) in h_vars)
    )

    total_salary = (
        pulp.lpSum(p_vars[i] * pitchers.loc[i, "_salary"] for i in pitchers.index) +
        pulp.lpSum(h_vars[(i, slot)] * hitters.loc[i, "_salary"] for (i, slot) in h_vars)
    )

    # Salary constraints
    prob += total_salary <= DK_SALARY_CAP
    prob += total_salary >= min_salary

    # Pitchers
    prob += pulp.lpSum(p_vars[i] for i in pitchers.index) == 2
    # Do not allow two pitchers facing each other
    for i in pitchers.index:
        for j in pitchers.index:
            if i >= j:
                continue

            team_i = str(pitchers.loc[i, p_team_col]).strip()
            opp_i = str(pitchers.loc[i, p_opp_col]).strip()
            team_j = str(pitchers.loc[j, p_team_col]).strip()
            opp_j = str(pitchers.loc[j, p_opp_col]).strip()

            if team_i == opp_j and team_j == opp_i:
                prob += p_vars[i] + p_vars[j] <= 1

    # Exactly one player per hitter slot
    for slot in hitter_slots:
        prob += pulp.lpSum(h_vars[(i, s)] for (i, s) in h_vars if s == slot) == 1

    # Each hitter can only be used once
    for i in hitters.index:
        prob += pulp.lpSum(h_vars[(h_i, slot)] for (h_i, slot) in h_vars if h_i == i) <= 1

    # Stack rules: 4 primary, 3 secondary
    prob += pulp.lpSum(
        h_vars[(i, slot)]
        for (i, slot) in h_vars
        if str(hitters.loc[i, team_col]) == primary_stack
    ) >= 4

    prob += pulp.lpSum(
        h_vars[(i, slot)]
        for (i, slot) in h_vars
        if str(hitters.loc[i, team_col]) == secondary_stack
    ) >= 3

    # Locks / excludes for hitters
    for i in hitters.index:
        player_name = str(hitters.loc[i, player_col])
        hitter_selected = pulp.lpSum(h_vars[(h_i, slot)] for (h_i, slot) in h_vars if h_i == i)

        if player_name in locked_players:
            prob += hitter_selected == 1

        if player_name in excluded_players:
            prob += hitter_selected == 0

    # Locks / excludes for pitchers
    for i in pitchers.index:
        player_name = str(pitchers.loc[i, p_player_col])

        if player_name in locked_players:
            prob += p_vars[i] == 1

        if player_name in excluded_players:
            prob += p_vars[i] == 0

    # No hitters vs selected pitchers
    for p_idx in pitchers.index:
        pitcher_team = str(pitchers.loc[p_idx, p_team_col]).strip()

        for (h_idx, slot) in h_vars:
            hitter_opp = str(hitters.loc[h_idx, opp_col]).strip()
            if hitter_opp == pitcher_team:
                prob += p_vars[p_idx] + h_vars[(h_idx, slot)] <= 1

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    if pulp.LpStatus[prob.status] != "Optimal":
        return pd.DataFrame(), 0, 0

    rows = []

    selected_pitchers = [i for i in pitchers.index if pulp.value(p_vars[i]) == 1]

    for i in selected_pitchers:
        rows.append({
            "Slot": "P",
            "Player": pitchers.loc[i, p_player_col],
            "Team": pitchers.loc[i, p_team_col],
            "Salary": pitchers.loc[i, "_salary"],
            "Score": pitchers.loc[i, "_score"]
        })

    for slot in hitter_slots:
        for (i, s) in h_vars:
            if s == slot and pulp.value(h_vars[(i, s)]) == 1:
                display_slot = "OF" if slot.startswith("OF") else slot
                rows.append({
                    "Slot": display_slot,
                    "Player": hitters.loc[i, player_col],
                    "Team": hitters.loc[i, team_col],
                    "Salary": hitters.loc[i, "_salary"],
                    "Score": hitters.loc[i, "_score"]
                })

    lineup = pd.DataFrame(rows)

    return lineup, lineup["Salary"].sum(), lineup["Score"].sum()

def build_multiple_lineups(
    hitters,
    pitchers,
    stacks_df,
    num_lineups=3,
    locked_players=None,
    excluded_players=None,
    primary_stack=None,
    secondary_stack=None,
    min_salary=0
):
    lineups = []
    global_excludes = set(excluded_players or [])
    previous_lineup_sets = []

    for n in range(num_lineups):
        lineup, salary, score = build_real_optimizer_lineup(
            hitters,
            pitchers,
            stacks_df,
            locked_players=locked_players,
            excluded_players=list(global_excludes),
            primary_stack=primary_stack,
            secondary_stack=secondary_stack,
            min_salary=min_salary
        )

        if lineup.empty:
            break

        lineup_players = set(lineup["Player"].astype(str))

        # Avoid exact duplicate lineups
        if lineup_players in previous_lineup_sets:
            break

        lineup = lineup.copy()
        lineup["Lineup #"] = n + 1
        lineups.append(lineup)
        previous_lineup_sets.append(lineup_players)

        # Smarter variation:
        # Exclude a strong, non-locked hitter from the current lineup,
        # not the weakest punt.
        hitters_only = lineup[lineup["Slot"] != "P"].copy()
        hitters_only = hitters_only[~hitters_only["Player"].astype(str).isin(set(locked_players or []))]

        if hitters_only.empty:
            break

        # Avoid excluding pitchers. Pick from upper-middle hitters to force meaningful variation.
        hitters_only = hitters_only.sort_values("Score", ascending=False)

        if len(hitters_only) >= 4:
            player_to_exclude = hitters_only.iloc[2]["Player"]
        else:
            player_to_exclude = hitters_only.iloc[0]["Player"]

        global_excludes.add(str(player_to_exclude))

    if not lineups:
        return pd.DataFrame()

    return pd.concat(lineups, ignore_index=True)

def late_swap_optimizer(
    hitters,
    pitchers,
    stacks,
    current_players,
    unavailable_players,
    min_salary=49000,
    manual_locked_players=None,
):
    """
    Late swap optimizer that tries to preserve as much of the current lineup as possible.
    First locks all available current players.
    If no valid lineup is found, gradually unlocks the weakest saved players.
    """

    unavailable = {
        str(p).strip()
        for p in unavailable_players
        if str(p).strip()
    }

    available_current_players = [
        str(p).strip()
        for p in current_players
        if str(p).strip() and str(p).strip() not in unavailable
    ]

    manual_locked_players = {
    str(p).strip()
    for p in (manual_locked_players or [])
    if str(p).strip()
    }

    hard_locked_players = [
        p for p in available_current_players
        if p in manual_locked_players
    ]

    # Combine hitters + pitchers so we can rank current players by Score
    player_pool = pd.concat([hitters, pitchers], ignore_index=True).copy()

    if "Player" not in player_pool.columns and "Players" in player_pool.columns:
        player_pool["Player"] = player_pool["Players"]

    if "Score" not in player_pool.columns:
        if "Overall" in player_pool.columns:
            player_pool["Score"] = player_pool["Overall"]
        elif "Projection" in player_pool.columns:
            player_pool["Score"] = player_pool["Projection"]
        else:
            player_pool["Score"] = 0

    current_pool = player_pool[
        player_pool["Player"].astype(str).str.strip().isin(available_current_players)
    ].copy()

    current_pool = current_pool.sort_values("Score", ascending=True)

    # Try keeping 9, then 8, then 7, etc.
    for unlock_count in range(0, len(available_current_players) + 1):
        players_to_unlock = (
            current_pool.head(unlock_count)["Player"].astype(str).tolist()
            if unlock_count > 0
            else []
        )

        locked_players = sorted(set(
            hard_locked_players +
            [
                p for p in available_current_players
                if p not in players_to_unlock
            ]
        ))

        lineup, salary, score = build_real_optimizer_lineup(
            hitters,
            pitchers,
            stacks,
            locked_players=locked_players,
            excluded_players=list(unavailable),
            min_salary=min_salary,
        )

        if not lineup.empty:
            return lineup, salary, score

    return pd.DataFrame(), 0, 0