import hashlib
import pandas as pd


def lineup_id_from_text(lineup_text: str) -> str:
    cleaned = "|".join(
        sorted(
            p.strip().lower()
            for p in str(lineup_text).replace(";", ",").split(",")
            if p.strip()
        )
    )

    if not cleaned:
        cleaned = str(lineup_text).strip().lower()

    return hashlib.md5(
        cleaned.encode("utf-8")
    ).hexdigest()[:10]


def lineup_id_from_dataframe(lineup: pd.DataFrame) -> str:
    if lineup is None or lineup.empty:
        raise ValueError("Cannot create lineup id from an empty lineup.")

    required = {"Slot", "Player"}

    if not required.issubset(lineup.columns):
        raise ValueError(
            "Lineup must contain Slot and Player columns."
        )

    lineup_text = " ".join(
        f"{row['Slot']} {row['Player']}"
        for _, row in lineup.iterrows()
    )

    return lineup_id_from_text(lineup_text)