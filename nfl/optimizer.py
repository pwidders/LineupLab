import pandas as pd
import pulp


SALARY_CAP = 50000


def optimize_lineup(
    players,
    strategy="Cash",
    min_salary=0,
    require_qb_stack=False,
    qb_stack_size=1,
    require_dst_rb=False,
    previous_lineups=None,
    max_overlap=6,
    excluded_dk_ids=None,
    diversify_repeated_qb_stacks=False,
    min_stack_partner_gpp_score=0,
):
    """
    Optimize a DraftKings NFL classic lineup using PuLP/CBC.

    Roster:
      1 QB
      2-3 RB
      3-4 WR
      1-2 TE
      1 DST
      1 FLEX (RB/WR/TE)

    Strategy:
      Cash -> maximize cash_projection
      GPP  -> maximize gpp_projection
    """

    if qb_stack_size not in (1, 2):
        raise ValueError("qb_stack_size must be 1 or 2.")

    if min_stack_partner_gpp_score < 0:
        raise ValueError("min_stack_partner_gpp_score must be >= 0.")

    df = players.copy().reset_index(drop=True)

    # --------------------------------
    # Clean player pool
    # --------------------------------

    required_cols = [
        "player",
        "position",
        "team",
        "opponent",
        "salary",
        "ll_projection",
        "cash_score",
        "gpp_score",
        "cash_projection",
        "gpp_projection",
        "dk_id",
    ]

    missing = [
        col for col in required_cols
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Optimizer missing columns: {missing}"
        )

    df["salary"] = pd.to_numeric(
        df["salary"],
        errors="coerce",
    )

    df["ll_projection"] = pd.to_numeric(
        df["ll_projection"],
        errors="coerce",
    )

    df["cash_score"] = pd.to_numeric(
        df["cash_score"],
        errors="coerce",
    )

    df["gpp_score"] = pd.to_numeric(
        df["gpp_score"],
        errors="coerce",
    )

    df["cash_projection"] = pd.to_numeric(
        df["cash_projection"],
        errors="coerce",
    )

    df["gpp_projection"] = pd.to_numeric(
        df["gpp_projection"],
        errors="coerce",
    )

    df = df[
        df["salary"].notna()
        & df["ll_projection"].notna()
        & (df["ll_projection"] > 0)
    ].copy()

    objective_col = (
        "cash_projection"
        if strategy == "Cash"
        else "gpp_projection"
    )

    df[objective_col] = df[
        objective_col
    ].fillna(0)

    # --------------------------------
    # Optimization model
    # --------------------------------

    model = pulp.LpProblem(
        "LineupLab_NFL",
        pulp.LpMaximize,
    )

    x = {
        i: pulp.LpVariable(
            f"player_{i}",
            cat="Binary",
        )
        for i in df.index
    }

    # --------------------------------
    # Objective
    # --------------------------------

    model += pulp.lpSum(
        x[i] * float(df.loc[i, objective_col])
        for i in df.index
    )

    # --------------------------------
    # Explicit exclusions
    # --------------------------------

    if excluded_dk_ids:
        excluded_ids = {str(player_id) for player_id in excluded_dk_ids}

        for i in df.index:
            if str(df.loc[i, "dk_id"]) in excluded_ids:
                model += x[i] == 0

    # --------------------------------
    # Exactly 9 players
    # --------------------------------

    model += (
        pulp.lpSum(x[i] for i in df.index)
        == 9
    )

    # --------------------------------
    # Salary
    # --------------------------------

    total_salary = pulp.lpSum(
        x[i] * float(df.loc[i, "salary"])
        for i in df.index
    )

    model += total_salary <= SALARY_CAP
    model += total_salary >= min_salary

    # --------------------------------
    # Position constraints
    # --------------------------------

    def position_sum(position):
        return pulp.lpSum(
            x[i]
            for i in df.index
            if df.loc[i, "position"] == position
        )

    # Exactly one QB and DST
    model += position_sum("QB") == 1
    model += position_sum("DST") == 1

    # DK roster + FLEX
    model += position_sum("RB") >= 2
    model += position_sum("RB") <= 3

    model += position_sum("WR") >= 3
    model += position_sum("WR") <= 4

    model += position_sum("TE") >= 1
    model += position_sum("TE") <= 2

    # --------------------------------
    # GPP: QB + WR/TE stack
    # --------------------------------

    if require_qb_stack:

        qb_indices = df[
            df["position"] == "QB"
        ].index

        for qb_i in qb_indices:

            qb_team = df.loc[qb_i, "team"]

            pass_catchers = [
                i
                for i in df.index
                if (
                    df.loc[i, "team"] == qb_team
                    and df.loc[i, "position"] in ["WR", "TE"]
                    and float(df.loc[i, "gpp_score"])
                    >= float(min_stack_partner_gpp_score)
                )
            ]

            if len(pass_catchers) >= qb_stack_size:
                model += (
                    pulp.lpSum(
                        x[i]
                        for i in pass_catchers
                    )
                    >= qb_stack_size * x[qb_i]
                )

            else:
                model += x[qb_i] == 0

    # --------------------------------
    # Portfolio: diversify repeated QB stacks
    # --------------------------------

    if diversify_repeated_qb_stacks and require_qb_stack and previous_lineups:
        for previous_lineup in previous_lineups:
            if previous_lineup is None or previous_lineup.empty:
                continue

            previous_qbs = previous_lineup[
                previous_lineup["position"] == "QB"
            ]
            if previous_qbs.empty:
                continue

            previous_qb = previous_qbs.iloc[0]
            previous_qb_id = str(previous_qb["dk_id"])
            previous_qb_team = previous_qb["team"]

            qb_matches = [
                i for i in df.index
                if (
                    df.loc[i, "position"] == "QB"
                    and str(df.loc[i, "dk_id"]) == previous_qb_id
                )
            ]
            if not qb_matches:
                continue

            qb_i = qb_matches[0]

            previous_stack_ids = set(
                previous_lineup[
                    (previous_lineup["team"] == previous_qb_team)
                    & (previous_lineup["position"].isin(["WR", "TE"]))
                ]["dk_id"].dropna().astype(str)
            )

            prior_stack_indices = [
                i for i in df.index
                if (
                    str(df.loc[i, "dk_id"]) in previous_stack_ids
                    and df.loc[i, "team"] == previous_qb_team
                    and df.loc[i, "position"] in ["WR", "TE"]
                )
            ]

            # If this QB is reused, at least one of his prior pass catchers
            # must change. This prevents an identical QB stack from repeating.
            if prior_stack_indices:
                model += (
                    pulp.lpSum(x[i] for i in prior_stack_indices)
                    <= len(prior_stack_indices) - x[qb_i]
                )

    # --------------------------------
    # GPP: DST + same-team RB
    # --------------------------------

    if require_dst_rb:

        dst_indices = df[
            df["position"] == "DST"
        ].index

        for dst_i in dst_indices:

            dst_team = df.loc[
                dst_i,
                "team",
            ]

            same_team_rbs = [
                i
                for i in df.index
                if (
                    df.loc[i, "team"] == dst_team
                    and df.loc[i, "position"] == "RB"
                )
            ]

            if same_team_rbs:
                model += (
                    pulp.lpSum(
                        x[i]
                        for i in same_team_rbs
                    )
                    >= x[dst_i]
                )

            else:
                model += x[dst_i] == 0

    # --------------------------------
    # Portfolio: max overlap with prior lineups
    # --------------------------------

    if previous_lineups:
        for lineup_num, previous_lineup in enumerate(previous_lineups, start=1):
            if previous_lineup is None or previous_lineup.empty:
                continue

            previous_ids = set(
                previous_lineup["dk_id"].dropna().astype(str)
            )

            overlapping_indices = [
                i for i in df.index
                if str(df.loc[i, "dk_id"]) in previous_ids
            ]

            if overlapping_indices:
                model += (
                    pulp.lpSum(x[i] for i in overlapping_indices)
                    <= max_overlap
                ), f"max_overlap_lineup_{lineup_num}"

    # --------------------------------
    # Solve
    # --------------------------------

    solver = pulp.PULP_CBC_CMD(
        msg=False,
    )

    model.solve(solver)

    if pulp.LpStatus[model.status] != "Optimal":
        return None

    selected_indices = [
        i
        for i in df.index
        if pulp.value(x[i]) > 0.5
    ]

    selected = df.loc[
        selected_indices
    ].copy()

    # --------------------------------
    # Assign DK roster slots
    # --------------------------------

    lineup_rows = []

    qb = selected[
        selected["position"] == "QB"
    ].iloc[0]

    dst = selected[
        selected["position"] == "DST"
    ].iloc[0]

    rbs = selected[
        selected["position"] == "RB"
    ].copy()

    wrs = selected[
        selected["position"] == "WR"
    ].copy()

    tes = selected[
        selected["position"] == "TE"
    ].copy()

    lineup_rows.append(("QB", qb))

    # Required RBs
    for _, player in rbs.iloc[:2].iterrows():
        lineup_rows.append(("RB", player))

    # Required WRs
    for _, player in wrs.iloc[:3].iterrows():
        lineup_rows.append(("WR", player))

    # Required TE
    lineup_rows.append(
        ("TE", tes.iloc[0])
    )

    # Find FLEX
    used_ids = {
        player["dk_id"]
        for _, player in lineup_rows
    }

    flex_candidates = selected[
        selected["position"].isin(
            ["RB", "WR", "TE"]
        )
        & ~selected["dk_id"].isin(used_ids)
    ]

    if len(flex_candidates) != 1:
        raise ValueError(
            "Could not determine FLEX player."
        )

    lineup_rows.append(
        ("FLEX", flex_candidates.iloc[0])
    )

    lineup_rows.append(("DST", dst))

    # --------------------------------
    # Output
    # --------------------------------

    rows = []

    for slot, player in lineup_rows:

        rows.append(
            {
                "slot": slot,
                "player": player["player"],
                "position": player["position"],
                "team": player["team"],
                "opponent": player["opponent"],
                "salary": player["salary"],
                "ll_projection": player["ll_projection"],
                "cash_score": player["cash_score"],
                "gpp_score": player["gpp_score"],
                "cash_projection": player["cash_projection"],
                "gpp_projection": player["gpp_projection"],
                "dk_id": player["dk_id"],
            }
        )

    lineup_df = pd.DataFrame(rows)

    lineup_df.attrs["total_salary"] = (
        lineup_df["salary"].sum()
    )

    lineup_df.attrs["total_projection"] = (
        lineup_df["ll_projection"].sum()
    )

    lineup_df.attrs["strategy"] = strategy

    lineup_df.attrs["optimizer_score"] = (
        lineup_df[
            "cash_projection"
            if strategy == "Cash"
            else "gpp_projection"
        ].sum()
    )

    return lineup_df


def optimize_portfolio(
    players,
    num_lineups=3,
    strategy="GPP",
    min_salary=49000,
    require_qb_stack=True,
    qb_stack_size=1,
    require_dst_rb=True,
    max_overlap=6,
    max_qb_exposure=2,
    player_exposure_limits=None,
    use_auto_exposure_tiers=True,
    max_auto_core_players=2,
    diversify_qb_stacks=True,
    min_stack_partner_gpp_score=0,
):
    """
    Build multiple optimized NFL lineups with pairwise overlap limits
    and a portfolio-level quarterback exposure cap.
    """

    if num_lineups < 1:
        raise ValueError("num_lineups must be at least 1.")

    if qb_stack_size not in (1, 2):
        raise ValueError("qb_stack_size must be 1 or 2.")

    if min_stack_partner_gpp_score < 0:
        raise ValueError("min_stack_partner_gpp_score must be >= 0.")

    if not 0 <= max_overlap <= 8:
        raise ValueError("max_overlap must be between 0 and 8.")

    if not 1 <= max_qb_exposure <= num_lineups:
        raise ValueError(
            "max_qb_exposure must be between 1 and num_lineups."
        )

    if not 0 <= max_auto_core_players <= num_lineups:
        raise ValueError(
            "max_auto_core_players must be between 0 and num_lineups."
        )

    lineups = []
    qb_exposure_counts = {}
    player_exposure_counts = {}
    # Manual overrides map dk_id -> max lineup count.
    # For a 3-lineup portfolio:
    # 3 = 100%, 2 = 67%, 1 = 33%, 0 = excluded.
    manual_exposure_limits = {
        str(k): int(v) for k, v in (player_exposure_limits or {}).items()
    }

    # Automatic exposure tiers are based on GPP score.
    # Manual limits always override the automatic tier.
    #
    # Auto Core: top non-QB 95+ plays -> max 3 lineups
    # All other players -> max 2 lineups
    # Manual overrides always take priority
    auto_exposure_limits = {}

    if use_auto_exposure_tiers:
        scored_players = players.copy()
        scored_players["gpp_score"] = pd.to_numeric(
            scored_players["gpp_score"],
            errors="coerce",
        )

        # Select only the highest-rated 95+ NON-QB players as automatic core plays.
        # QB exposure is governed separately by max_qb_exposure.
        core_candidates = (
            scored_players[
                scored_players["gpp_score"].notna()
                & (scored_players["gpp_score"] >= 95)
                & (scored_players["position"] != "QB")
            ]
            .sort_values(
                ["gpp_score", "gpp_projection"],
                ascending=[False, False],
            )
            .head(max_auto_core_players)
        )

        auto_core_ids = set(
            core_candidates["dk_id"].astype(str)
        )

        for _, row in scored_players.iterrows():
            player_id = str(row["dk_id"])
            gpp_score = row["gpp_score"]

            if pd.isna(gpp_score):
                continue

            if player_id in auto_core_ids:
                cap = 3
            else:
                cap = 2

            auto_exposure_limits[player_id] = cap

    effective_exposure_limits = dict(auto_exposure_limits)
    effective_exposure_limits.update(manual_exposure_limits)

    for _ in range(num_lineups):
        blocked_qb_ids = {
            qb_id for qb_id, count in qb_exposure_counts.items()
            if count >= max_qb_exposure
        }
        blocked_player_ids = {
            player_id
            for player_id, cap in effective_exposure_limits.items()
            if player_exposure_counts.get(player_id, 0) >= cap
        }

        lineup = optimize_lineup(
            players=players,
            strategy=strategy,
            min_salary=min_salary,
            require_qb_stack=require_qb_stack,
            qb_stack_size=qb_stack_size,
            require_dst_rb=require_dst_rb,
            previous_lineups=lineups,
            max_overlap=max_overlap,
            excluded_dk_ids=blocked_qb_ids | blocked_player_ids,
            diversify_repeated_qb_stacks=diversify_qb_stacks,
            min_stack_partner_gpp_score=min_stack_partner_gpp_score,
        )

        if lineup is None:
            break

        lineup.attrs["effective_exposure_limits"] = effective_exposure_limits
        lineup.attrs["manual_exposure_limits"] = manual_exposure_limits
        lineup.attrs["auto_exposure_limits"] = auto_exposure_limits
        lineup.attrs["auto_core_ids"] = auto_core_ids if use_auto_exposure_tiers else set()

        lineups.append(lineup)

        for player_id in lineup["dk_id"].astype(str):
            player_exposure_counts[player_id] = player_exposure_counts.get(player_id, 0) + 1

        qb_rows = lineup[lineup["position"] == "QB"]

        if not qb_rows.empty:
            qb_id = str(qb_rows.iloc[0]["dk_id"])
            qb_exposure_counts[qb_id] = (
                qb_exposure_counts.get(qb_id, 0) + 1
            )

    return lineups