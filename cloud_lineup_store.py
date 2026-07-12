import json
from datetime import datetime, timezone

import pandas as pd

from projection_store import get_supabase_client


TABLE_NAME = "saved_lineups"


def _lineup_to_json(lineup: pd.DataFrame) -> list[dict]:
    """
    Convert the lineup DataFrame into JSON-safe Python objects.

    Using DataFrame.to_json avoids issues with NumPy numeric types
    that Supabase cannot serialize directly.
    """
    if lineup is None or lineup.empty:
        raise ValueError("Cannot save an empty lineup.")

    return json.loads(
        lineup.to_json(
            orient="records",
            date_format="iso",
        )
    )


def save_cloud_lineup(
    lineup: pd.DataFrame,
    salary: float,
    projected_score: float,
    slate_date: str,
    slate_name: str,
    lineup_slot: int,
    lineup_name: str | None = None,
) -> dict:
    """
    Create or overwrite one lineup slot for a specific slate.
    """

    slate_name = str(slate_name).strip() or "Main"
    lineup_slot = int(lineup_slot)

    if lineup_slot < 1:
        raise ValueError("Lineup slot must be 1 or greater.")

    payload = {
        "slate_date": str(slate_date),
        "slate_name": slate_name,
        "lineup_slot": lineup_slot,
        "lineup_name": (
            str(lineup_name).strip()
            if lineup_name and str(lineup_name).strip()
            else f"Lineup #{lineup_slot}"
        ),
        "salary": float(salary),
        "projected_score": float(projected_score),
        "lineup_data": _lineup_to_json(lineup),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    supabase = get_supabase_client()

    response = (
        supabase.table(TABLE_NAME)
        .upsert(
            payload,
            on_conflict="slate_date,slate_name,lineup_slot",
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError("Supabase did not return the saved lineup.")

    return response.data[0]


def list_cloud_lineups(
    slate_date: str,
    slate_name: str,
) -> list[dict]:
    """
    Return all saved lineup slots for one slate.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table(TABLE_NAME)
        .select(
            "id, slate_date, slate_name, lineup_slot, lineup_name, "
            "salary, projected_score, created_at, updated_at"
        )
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .order("lineup_slot")
        .execute()
    )

    return response.data or []


def load_cloud_lineup(
    slate_date: str,
    slate_name: str,
    lineup_slot: int,
) -> tuple[pd.DataFrame, float, float, dict]:
    """
    Load one saved lineup slot from Supabase.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table(TABLE_NAME)
        .select("*")
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .eq("lineup_slot", int(lineup_slot))
        .limit(1)
        .execute()
    )

    if not response.data:
        raise FileNotFoundError(
            f"No saved Lineup #{lineup_slot} was found for "
            f"{slate_date} {slate_name}."
        )

    record = response.data[0]
    lineup = pd.DataFrame(record["lineup_data"])

    return (
        lineup,
        float(record.get("salary", 0)),
        float(record.get("projected_score", 0)),
        record,
    )


def delete_cloud_lineup(
    slate_date: str,
    slate_name: str,
    lineup_slot: int,
) -> None:
    """
    Delete one lineup slot without affecting the other saved lineups.
    """

    supabase = get_supabase_client()

    (
        supabase.table(TABLE_NAME)
        .delete()
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .eq("lineup_slot", int(lineup_slot))
        .execute()
    )