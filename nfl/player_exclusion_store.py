from datetime import datetime, timezone

from nfl.auth import (
    get_authenticated_client,
    get_current_user_id,
)


TABLE_NAME = "nfl_player_exclusions"


def load_nfl_player_exclusions(
    slate_date: str,
    slate_name: str = "Main",
) -> list[str]:
    """
    Load the authenticated user's saved player exclusions
    for one NFL slate.
    """

    user_id = get_current_user_id()
    supabase = get_authenticated_client()

    response = (
        supabase.table(TABLE_NAME)
        .select("excluded_player_ids")
        .eq("user_id", user_id)
        .eq("slate_date", str(slate_date))
        .eq("slate_name", str(slate_name).strip() or "Main")
        .limit(1)
        .execute()
    )

    if not response.data:
        return []

    excluded_ids = response.data[0].get(
        "excluded_player_ids",
        [],
    )

    if not isinstance(excluded_ids, list):
        return []

    return [
        str(player_id)
        for player_id in excluded_ids
        if str(player_id).strip()
    ]


def save_nfl_player_exclusions(
    excluded_player_ids,
    slate_date: str,
    slate_name: str = "Main",
) -> dict:
    """
    Save the authenticated user's player exclusions
    for one NFL slate.
    """

    user_id = get_current_user_id()
    supabase = get_authenticated_client()

    normalized_ids = sorted(
        {
            str(player_id).strip()
            for player_id in excluded_player_ids
            if str(player_id).strip()
        }
    )

    payload = {
        "user_id": user_id,
        "slate_date": str(slate_date),
        "slate_name": str(slate_name).strip() or "Main",
        "excluded_player_ids": normalized_ids,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    response = (
        supabase.table(TABLE_NAME)
        .upsert(
            payload,
            on_conflict="user_id,slate_date,slate_name",
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the saved NFL player exclusions."
        )

    return response.data[0]