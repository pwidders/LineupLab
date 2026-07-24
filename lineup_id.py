import hashlib
import re

import pandas as pd


ROSTER_SLOT_PATTERN = re.compile(
    r"(?:^|\s)(?:P|C|1B|2B|3B|SS|OF)\s+"
    r"(.+?)"
    r"(?=\s+(?:P|C|1B|2B|3B|SS|OF)\s+|$)",
    flags=re.IGNORECASE,
)


def _normalize_player_name(name: str) -> str:
    """
    Normalize a player name so lineup order and extra spacing
    do not affect the lineup fingerprint.
    """
    return " ".join(
        str(name).strip().lower().split()
    )


def _hash_player_names(player_names: list[str]) -> str:
    normalized_names = sorted(
        _normalize_player_name(name)
        for name in player_names
        if _normalize_player_name(name)
    )

    if not normalized_names:
        raise ValueError(
            "Cannot create a lineup ID without player names."
        )

    canonical_lineup = "|".join(normalized_names)

    return hashlib.md5(
        canonical_lineup.encode("utf-8")
    ).hexdigest()[:10]


def lineup_id_from_text(lineup_text: str) -> str:
    """
    Create a lineup ID from DraftKings lineup text.

    Position labels and lineup order are ignored.
    """
    text = str(lineup_text).strip()

    player_names = [
        match.group(1).strip()
        for match in ROSTER_SLOT_PATTERN.finditer(text)
        if match.group(1).strip()
    ]

    if not player_names:
        raise ValueError(
            "Could not extract players from the lineup text."
        )

    return _hash_player_names(player_names)


def lineup_id_from_dataframe(
    lineup: pd.DataFrame,
) -> str:
    """
    Create a lineup ID from a LineupLab lineup DataFrame.

    Position labels and lineup order are ignored.
    """
    if lineup is None or lineup.empty:
        raise ValueError(
            "Cannot create a lineup ID from an empty lineup."
        )

    if "Player" not in lineup.columns:
        raise ValueError(
            "Lineup must contain a Player column."
        )

    player_names = (
        lineup["Player"]
        .dropna()
        .astype(str)
        .tolist()
    )

    return _hash_player_names(player_names)