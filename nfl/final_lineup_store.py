import hashlib
import json
import re
from datetime import datetime, timezone

import pandas as pd

from nfl.salary_store import get_supabase_client


TABLE_NAME = "nfl_final_lineups"


def _normalize_player_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def nfl_lineup_id_from_names(player_names) -> str:
    names = [
        _normalize_player_name(name)
        for name in player_names
        if _normalize_player_name(name)
    ]

    if not names:
        raise ValueError("Cannot create an NFL lineup ID without player names.")

    fingerprint_text = "|".join(sorted(names))

    return hashlib.sha256(
        fingerprint_text.encode("utf-8")
    ).hexdigest()[:24]


def nfl_lineup_id_from_dataframe(lineup: pd.DataFrame) -> str:
    if lineup is None or lineup.empty:
        raise ValueError("Cannot create a lineup ID from an empty lineup.")

    if "player" not in lineup.columns:
        raise ValueError(
            "NFL lineup needs a player column to create a lineup ID."
        )

    return nfl_lineup_id_from_names(
        lineup["player"].dropna().astype(str).tolist()
    )


def _lineup_to_json(lineup: pd.DataFrame) -> list[dict]:
    if lineup is None or lineup.empty:
        raise ValueError("Cannot save an empty NFL lineup.")

    return json.loads(
        lineup.to_json(
            orient="records",
            date_format="iso",
        )
    )


def save_nfl_final_lineup(
    lineup: pd.DataFrame,
    slate_date: str,
    slate_name: str,
    lineup_slot: str,
    strategy: str,
) -> dict:
    slate_name = str(slate_name).strip() or "Main"
    lineup_slot = str(lineup_slot).strip() or "Lineup 1"
    strategy = str(strategy).strip() or "Unknown"

    salary = float(
        lineup.attrs.get(
            "total_salary",
            pd.to_numeric(
                lineup.get("salary", pd.Series(dtype=float)),
                errors="coerce",
            ).fillna(0).sum(),
        )
    )

    projected_score = float(
        lineup.attrs.get(
            "total_projection",
            pd.to_numeric(
                lineup.get("ll_projection", pd.Series(dtype=float)),
                errors="coerce",
            ).fillna(0).sum(),
        )
    )

    optimizer_score = float(
        lineup.attrs.get("optimizer_score", 0)
    )

    payload = {
        "slate_date": str(slate_date),
        "slate_name": slate_name,
        "lineup_slot": lineup_slot,
        "strategy": strategy,
        "lineup_id": nfl_lineup_id_from_dataframe(lineup),
        "salary": int(round(salary)),
        "projected_score": round(projected_score, 2),
        "optimizer_score": round(optimizer_score, 2),
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
        raise RuntimeError(
            "Supabase did not return the saved NFL Final Lineup."
        )

    return response.data[0]


def list_nfl_final_lineups(
    slate_date: str,
    slate_name: str,
) -> list[dict]:
    supabase = get_supabase_client()

    response = (
        supabase.table(TABLE_NAME)
        .select(
            "id, slate_date, slate_name, lineup_slot, strategy, "
            "lineup_id, salary, projected_score, optimizer_score, "
            "created_at, updated_at"
        )
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .order("lineup_slot")
        .execute()
    )

    return response.data or []


def load_nfl_final_lineup(
    slate_date: str,
    slate_name: str,
    lineup_slot: str,
) -> tuple[pd.DataFrame, dict]:
    supabase = get_supabase_client()

    response = (
        supabase.table(TABLE_NAME)
        .select("*")
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .eq("lineup_slot", str(lineup_slot).strip())
        .limit(1)
        .execute()
    )

    if not response.data:
        raise FileNotFoundError(
            f"No NFL Final Lineup found for "
            f"{slate_date} {slate_name} {lineup_slot}."
        )

    record = response.data[0]
    return pd.DataFrame(record.get("lineup_data", [])), record


def find_nfl_final_lineup_by_id(
    lineup_id: str,
    slate_date: str | None = None,
) -> dict | None:
    lineup_id = str(lineup_id).strip()

    if not lineup_id:
        return None

    supabase = get_supabase_client()

    query = (
        supabase.table(TABLE_NAME)
        .select("*")
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

