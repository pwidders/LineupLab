import json
from datetime import datetime, timezone

import pandas as pd

from nfl.salary_store import get_supabase_client, _upload_bytes


BUCKET = "projections"
LATEST_ODDS_FILE = "latest_nfl_odds.json"


def save_latest_odds(odds_df):
    """
    Persist the most recently successful NFL odds pull to Supabase.

    The saved payload includes a UTC refresh timestamp so the app can
    show exactly how old the current odds snapshot is.
    """

    if odds_df is None or odds_df.empty:
        return

    supabase = get_supabase_client()

    payload = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "records": odds_df.to_dict(orient="records"),
    }

    file_bytes = json.dumps(payload).encode("utf-8")

    _upload_bytes(
        supabase,
        LATEST_ODDS_FILE,
        file_bytes,
        "application/json",
    )


def load_latest_odds():
    """
    Load the most recently saved NFL odds from Supabase.

    Backward compatible with the original list-only JSON format.
    """

    odds_df, _ = load_latest_odds_with_meta()
    return odds_df


def load_latest_odds_with_meta():
    """
    Load the saved NFL odds snapshot plus its refresh timestamp.

    Returns:
        (odds_df, refreshed_at)

    refreshed_at is an ISO timestamp string when available, otherwise None.
    """

    supabase = get_supabase_client()

    file_bytes = (
        supabase.storage
        .from_(BUCKET)
        .download(LATEST_ODDS_FILE)
    )

    payload = json.loads(file_bytes.decode("utf-8"))

    # Legacy format: a bare list of odds records.
    if isinstance(payload, list):
        return pd.DataFrame(payload), None

    records = payload.get("records", [])
    refreshed_at = payload.get("refreshed_at")

    return pd.DataFrame(records), refreshed_at
