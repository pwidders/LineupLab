import json
import pandas as pd

from nfl.salary_store import get_supabase_client, _upload_bytes


BUCKET = "projections"
LATEST_ODDS_FILE = "latest_nfl_odds.json"


def save_latest_odds(odds_df):
    """
    Persist the most recently successful NFL odds pull to Supabase.
    """

    if odds_df is None or odds_df.empty:
        return

    supabase = get_supabase_client()

    records = odds_df.to_dict(orient="records")
    file_bytes = json.dumps(records).encode("utf-8")

    _upload_bytes(
        supabase,
        LATEST_ODDS_FILE,
        file_bytes,
        "application/json",
    )


def load_latest_odds():
    """
    Load the most recently saved NFL odds from Supabase.
    """

    supabase = get_supabase_client()

    file_bytes = (
        supabase.storage
        .from_(BUCKET)
        .download(LATEST_ODDS_FILE)
    )

    records = json.loads(file_bytes.decode("utf-8"))

    return pd.DataFrame(records)