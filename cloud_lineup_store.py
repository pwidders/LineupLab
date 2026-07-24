import json
from datetime import datetime, timezone

import pandas as pd

from projection_store import get_supabase_client
from lineup_id import lineup_id_from_dataframe


TABLE_NAME = "saved_lineups"
WORKING_TABLE_NAME = "working_lineups"
FINAL_TABLE_NAME = "final_lineups"


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
        "salary": int(salary),
        "projected_score": round(float(projected_score), 2),
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

def save_cloud_working_lineup(
    lineup: pd.DataFrame,
    salary: float,
    projected_score: float,
    slate_date: str,
    slate_name: str,
    last_action: str = "Working Lineup Update",
) -> dict:
    """
    Create or overwrite the live working lineup for one slate.

    This is separate from the permanent Lineup Vault.
    """

    slate_name = str(slate_name).strip() or "Main"

    payload = {
        "slate_date": str(slate_date),
        "slate_name": slate_name,
        "lineup_data": _lineup_to_json(lineup),
        "salary": float(salary),
        "projected_score": float(projected_score),
        "last_action": (
            str(last_action).strip()
            if str(last_action).strip()
            else "Working Lineup Update"
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    supabase = get_supabase_client()

    response = (
        supabase.table(WORKING_TABLE_NAME)
        .upsert(
            payload,
            on_conflict="slate_date,slate_name",
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the saved working lineup."
        )

    return response.data[0]


def load_cloud_working_lineup(
    slate_date: str,
    slate_name: str,
) -> tuple[pd.DataFrame, float, float, dict] | None:
    """
    Load the live working lineup for one slate.

    Returns None when no working lineup has been saved.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table(WORKING_TABLE_NAME)
        .select("*")
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    record = response.data[0]
    lineup = pd.DataFrame(record["lineup_data"])

    return (
        lineup,
        float(record.get("salary", 0)),
        float(record.get("projected_score", 0)),
        record,
    )


def delete_cloud_working_lineup(
    slate_date: str,
    slate_name: str,
) -> None:
    """
    Delete the live working lineup for one slate.

    This does not affect any permanent Lineup Vault entries.
    """

    supabase = get_supabase_client()

    (
        supabase.table(WORKING_TABLE_NAME)
        .delete()
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .execute()
    )

def save_cloud_final_lineup(
    lineup: pd.DataFrame,
    salary: float,
    projected_score: float,
    slate_date: str,
    slate_name: str,
    lineup_slot: str,
) -> dict:
    """
    Create or overwrite the official Final Lineup for one slate/slot.
    """

    payload = {
        "slate_date": str(slate_date),
        "slate_name": str(slate_name).strip() or "Main",
        "lineup_slot": str(lineup_slot).strip() or "Cash",
        "lineup_data": _lineup_to_json(lineup),
        "salary": int(round(float(salary))),
        "projected_score": round(float(projected_score), 2),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lineup_id": lineup_id_from_dataframe(lineup),
    }

    supabase = get_supabase_client()

    response = (
        supabase.table(FINAL_TABLE_NAME)
        .upsert(
            payload,
            on_conflict="slate_date,slate_name,lineup_slot",
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError("Supabase did not return the saved final lineup.")

    return response.data[0]

def list_cloud_final_lineups(
    slate_date: str,
    slate_name: str,
) -> list[dict]:

    supabase = get_supabase_client()

    response = (
        supabase.table(FINAL_TABLE_NAME)
        .select("*")
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .order("lineup_slot")
        .execute()
    )

    return response.data or []

def find_cloud_final_lineup_by_id(
    lineup_id: str,
    slate_date: str | None = None,
) -> dict | None:
    """
    Find a saved Final Lineup using its lineup fingerprint.

    The slate date is optional, but using it prevents an identical lineup
    from another date from being treated as the current slate's match.
    """

    lineup_id = str(lineup_id).strip()

    if not lineup_id:
        return None

    supabase = get_supabase_client()

    query = (
        supabase.table(FINAL_TABLE_NAME)
        .select(
            "id, slate_date, slate_name, lineup_slot, lineup_id, "
            "salary, projected_score, saved_at, updated_at"
        )
        .eq("lineup_id", lineup_id)
    )

    if slate_date:
        query = query.eq("slate_date", str(slate_date))

    response = (
        query
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]

def delete_cloud_final_lineup(
    slate_date: str,
    slate_name: str,
    lineup_slot: str,
) -> None:

    supabase = get_supabase_client()

    (
        supabase.table(FINAL_TABLE_NAME)
        .delete()
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .eq("lineup_slot", str(lineup_slot).strip())
        .execute()
    )