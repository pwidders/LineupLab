import math
from typing import Tuple

import pandas as pd
import streamlit as st
from supabase import create_client


TABLE_NAME = "contest_history"


def _get_client():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_KEY"],
    )


def _clean_value(value):
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _row_to_record(row: pd.Series) -> dict:
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
        "Average Ownership": "average_ownership",
        "Player FPTS Total": "player_fpts_total",
        "Best Player": "best_player",
        "Worst Player": "worst_player",
        "Lineup ID": "lineup_id",
        "Lineup": "lineup",
        "Entry Fee": "entry_fee",
        "Winnings": "winnings",
        "Profit": "profit",
        "Player Results": "player_results",
    }

    return {
        target_col: _clean_value(row.get(source_col))
        for source_col, target_col in mapping.items()
    }


def save_contest_history(
    history_df: pd.DataFrame,
) -> Tuple[int, int]:
    """
    Insert new contest records and update matching existing records.

    Returns:
        inserted: Number of new rows created.
        updated: Number of existing rows updated.
    """
    if history_df is None or history_df.empty:
        return 0, 0

    client = _get_client()
    inserted = 0
    updated = 0

    for _, row in history_df.iterrows():
        record = _row_to_record(row)

        entry_id = record.get("entry_id")

        if entry_id:
            duplicate_query = (
                client.table(TABLE_NAME)
                .select("id")
                .eq("entry_id", entry_id)
                .limit(1)
                .execute()
            )
        else:
            # Legacy fallback for imports that do not contain EntryId.
            duplicate_query = (
                client.table(TABLE_NAME)
                .select("id")
                .eq("slate_date", record["slate_date"])
                .eq("source_file", record["source_file"])
                .eq("entry_name", record["entry_name"])
                .eq("contest_type", record["contest_type"])
                .eq("lineup_id", record["lineup_id"])
                .limit(1)
                .execute()
            )

        if duplicate_query.data:
            existing_id = duplicate_query.data[0]["id"]

            client.table(TABLE_NAME).update(
                record
            ).eq(
                "id",
                existing_id,
            ).execute()

            updated += 1
            continue

        client.table(TABLE_NAME).insert(
            record
        ).execute()

        inserted += 1

    return inserted, updated

def update_contest_history_record(
    record_id: str,
    slate_date: str,
    entry_name: str,
    contest_type: str,
    rank: int,
    field_size: int,
    points: float,
    entry_fee: float,
    winnings: float,
) -> dict:
    """
    Update one previously saved contest-history record.
    """

    if not record_id:
        raise ValueError("A contest-history record ID is required.")

    rank = int(rank)
    field_size = int(field_size)
    points = float(points)
    entry_fee = float(entry_fee)
    winnings = float(winnings)

    profit = winnings - entry_fee
    rank_percentile = (
        rank / field_size
        if field_size > 0
        else 0
    )

    payload = {
        "slate_date": str(slate_date),
        "entry_name": str(entry_name).strip(),
        "contest_type": str(contest_type).strip(),
        "rank": rank,
        "field_size": field_size,
        "points": points,
        "rank_percentile": rank_percentile,
        "entry_fee": entry_fee,
        "winnings": winnings,
        "profit": profit,
    }

    client = _get_client()

    response = (
        client.table(TABLE_NAME)
        .update(payload)
        .eq("id", str(record_id))
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the updated contest record."
        )

    return response.data[0]

def load_contest_history() -> pd.DataFrame:
    client = _get_client()

    response = (
        client.table(TABLE_NAME)
        .select("*")
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
        "average_ownership",
        "player_fpts_total",
        "entry_fee",
        "winnings",
        "profit",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "slate_date" in df.columns:
        df["slate_date"] = pd.to_datetime(
            df["slate_date"],
            errors="coerce",
        )

    return df