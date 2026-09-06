import math
from typing import Tuple

import pandas as pd
import streamlit as st

from nfl.auth import (
    get_authenticated_client,
    get_current_user_id,
)


TABLE_NAME = "nfl_contest_history"


def _get_client():
    """Return the signed-in user client so RLS is enforced."""
    return get_authenticated_client()


def _clean_value(value):
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _row_to_record(row: pd.Series) -> dict:
    """
    Convert one NFL Contest Review summary row into the Supabase schema.
    """
    mapping = {
        "Slate Date": "slate_date",
        "Logged At": "logged_at",
        "Source File": "source_file",
        "Entry ID": "entry_id",
        "Entry Name": "entry_name",
        "Contest Type": "contest_type",
        "Rank": "rank",
        "Field Size": "field_size",
        "Points": "points",
        "Rank Percentile": "rank_percentile",
        "Lineup ID": "lineup_id",
        "Lineup": "lineup",
        "Lineup Slot": "lineup_slot",
        "Strategy": "strategy",
        "Salary": "salary",
        "Projected Score": "projected_score",
        "Optimizer Score": "optimizer_score",
        "Entry Fee": "entry_fee",
        "Winnings": "winnings",
        "Profit": "profit",
        "Player Results": "player_results",
    }

    record = {
        target_col: _clean_value(row.get(source_col))
        for source_col, target_col in mapping.items()
    }

    record["user_id"] = get_current_user_id()
    return record


def save_nfl_contest_history(
    history_df: pd.DataFrame,
) -> Tuple[int, int]:
    """
    Insert new NFL contest records and update matching existing records.

    NOTE:
    This function is intentionally not called by Contest Review v0.1 yet.
    It is ready for use after the Week 1 DraftKings export is validated.
    """
    if history_df is None or history_df.empty:
        return 0, 0

    client = _get_client()
    user_id = get_current_user_id()
    inserted = 0
    updated = 0

    for _, row in history_df.iterrows():
        record = _row_to_record(row)

        entry_id = record.get("entry_id")

        if entry_id:
            duplicate_query = (
                client.table(TABLE_NAME)
                .select("id")
                .eq("user_id", user_id)
                .eq("entry_id", entry_id)
                .limit(1)
                .execute()
            )
        else:
            duplicate_query = (
                client.table(TABLE_NAME)
                .select("id")
                .eq("user_id", user_id)
                .eq("slate_date", record["slate_date"])
                .eq("source_file", record["source_file"])
                .eq("entry_name", record["entry_name"])
                .eq("lineup_id", record["lineup_id"])
                .limit(1)
                .execute()
            )

        if duplicate_query.data:
            existing_id = duplicate_query.data[0]["id"]

            (
                client.table(TABLE_NAME)
                .update(record)
                .eq("id", existing_id)
                .execute()
            )

            updated += 1
            continue

        (
            client.table(TABLE_NAME)
            .insert(record)
            .execute()
        )

        inserted += 1

    return inserted, updated


def load_nfl_contest_history() -> pd.DataFrame:
    """
    Load all saved NFL contest-history records.
    """
    client = _get_client()
    user_id = get_current_user_id()

    response = (
        client.table(TABLE_NAME)
        .select("*")
        .eq("user_id", user_id)
        .order("slate_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    df = pd.DataFrame(response.data)

    numeric_cols = [
        "rank",
        "field_size",
        "points",
        "rank_percentile",
        "salary",
        "projected_score",
        "optimizer_score",
        "entry_fee",
        "winnings",
        "profit",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            ).fillna(0)

    if "slate_date" in df.columns:
        df["slate_date"] = pd.to_datetime(
            df["slate_date"],
            errors="coerce",
        )

    return df