import streamlit as st
from supabase import create_client

BUCKET = "projections"
LATEST_FILE = "latest_nfl_dk_salaries.csv"
LATEST_NAME_FILE = "latest_nfl_dk_salaries_name.txt"


def get_supabase_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _upload_bytes(supabase, path, data, content_type):
    try:
        supabase.storage.from_(BUCKET).remove([path])
    except Exception:
        pass

    supabase.storage.from_(BUCKET).upload(
        path=path,
        file=data,
        file_options={
            "content-type": content_type,
            "upsert": "true",
        },
    )


def save_latest_salary_file(file_bytes, filename="DKSalaries.csv"):
    supabase = get_supabase_client()

    _upload_bytes(
        supabase,
        LATEST_FILE,
        file_bytes,
        "text/csv",
    )

    _upload_bytes(
        supabase,
        LATEST_NAME_FILE,
        filename.encode("utf-8"),
        "text/plain",
    )

    return LATEST_FILE


def load_latest_salary_file():
    supabase = get_supabase_client()

    file_bytes = supabase.storage.from_(BUCKET).download(
        LATEST_FILE
    )

    filename = "latest_nfl_dk_salaries.csv"

    try:
        name_bytes = supabase.storage.from_(BUCKET).download(
            LATEST_NAME_FILE
        )
        decoded = name_bytes.decode("utf-8").strip()
        if decoded:
            filename = decoded
    except Exception:
        pass

    return file_bytes, filename