import streamlit as st
from supabase import create_client

BUCKET = "projections"
LATEST_FILE = "latest_projection_sheet.xlsx"


def get_supabase_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def save_projection_file(uploaded_file):
    supabase = get_supabase_client()
    file_bytes = uploaded_file.getvalue()

    try:
        supabase.storage.from_(BUCKET).remove([LATEST_FILE])
    except Exception:
        pass

    supabase.storage.from_(BUCKET).upload(
        path=LATEST_FILE,
        file=file_bytes,
        file_options={
            "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "upsert": "true",
        },
    )

    return LATEST_FILE


def load_projection_file():
    supabase = get_supabase_client()
    return supabase.storage.from_(BUCKET).download(LATEST_FILE)