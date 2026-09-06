import re
from datetime import date

import pandas as pd
import streamlit as st

from nfl.final_lineup_store import (
    find_nfl_final_lineup_by_id,
    nfl_lineup_id_from_names,
)


DEFAULT_ENTRY_NAME = "rentisdue"


def _clean_col_name(col):
    return str(col).strip().replace("\ufeff", "")


def _find_col(df, possible_names):
    lookup = {
        _clean_col_name(col).lower(): col
        for col in df.columns
    }

    for name in possible_names:
        match = lookup.get(name.lower())
        if match is not None:
            return match

    return None


def _safe_num(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def parse_nfl_lineup_players(lineup_text):
    text = str(lineup_text or "").strip()

    if not text:
        return []

    pattern = re.compile(
        r"(?:^|\s)(QB|RB|WR|TE|FLEX|DST)\s+"
        r"(.+?)"
        r"(?=\s+(?:QB|RB|WR|TE|FLEX|DST)\s+|$)",
        flags=re.IGNORECASE,
    )

    return [
        match.group(2).strip()
        for match in pattern.finditer(text)
        if match.group(2).strip()
    ]


def _infer_contest_type(field_size):
    if field_size and field_size < 100:
        return "Double-Up"

    return "GPP"


def _build_saved_lineup_lookup(record):
    lookup = {}

    if not record:
        return lookup

    lineup_data = record.get("lineup_data", [])

    if not isinstance(lineup_data, list):
        return lookup

    for player in lineup_data:
        if not isinstance(player, dict):
            continue

        name = (
            player.get("player")
            or player.get("Player")
            or ""
        )

        key = str(name).strip().lower()

        if key:
            lookup[key] = player

    return lookup


def render_nfl_contest_review():
    st.subheader("🏟 NFL Contest Review")
    st.markdown(
        '<div class="ll-section-rule"></div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Upload a DraftKings NFL contest standings CSV after the slate. "
        "This v0.1 parser is provisional until we validate it against a "
        "real Week 1 export."
    )

    slate_date = st.date_input(
        "Contest Slate Date",
        value=date.today(),
        key="nfl_contest_review_slate_date",
    )

    uploaded_files = st.file_uploader(
        "Upload DraftKings NFL contest standings CSV",
        type=["csv"],
        accept_multiple_files=True,
        key="nfl_contest_review_uploader",
    )

    if not uploaded_files:
        st.info(
            "No contest file uploaded yet. "
            "This section is ready for your Week 1 DraftKings export."
        )
        return

    for file_index, file in enumerate(uploaded_files):
        with st.expander(
            file.name,
            expanded=(file_index == 0),
        ):
            try:
                df = pd.read_csv(file)
            except Exception as exc:
                st.error(
                    f"Could not read {file.name}: {exc}"
                )
                continue

            df.columns = [
                _clean_col_name(col)
                for col in df.columns
            ]

            entry_col = _find_col(
                df,
                ["EntryName", "Entry Name"],
            )
            rank_col = _find_col(
                df,
                ["Rank", "Place"],
            )
            points_col = _find_col(
                df,
                ["Points", "FPTS", "Fantasy Points"],
            )
            lineup_col = _find_col(
                df,
                ["Lineup"],
            )

            required = {
                "Entry Name": entry_col,
                "Rank": rank_col,
                "Points": points_col,
                "Lineup": lineup_col,
            }

            missing = [
                label
                for label, column in required.items()
                if column is None
            ]

            if missing:
                st.error(
                    "This DraftKings export is missing the "
                    f"expected columns: {', '.join(missing)}"
                )
                st.caption(
                    "Columns found: "
                    + ", ".join(
                        df.columns.astype(str).tolist()
                    )
                )
                continue

            standings = df[
                df[entry_col].notna()
            ].copy()

            if standings.empty:
                st.warning(
                    "No contest standings rows were found."
                )
                continue

            entry_names = (
                standings[entry_col]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            default_index = 0

            for index, name in enumerate(entry_names):
                if name.lower() == DEFAULT_ENTRY_NAME:
                    default_index = index
                    break

            selected_entry = st.selectbox(
                "Select your entry",
                options=entry_names,
                index=default_index,
                key=(
                    f"nfl_contest_entry_"
                    f"{file_index}_{file.name}"
                ),
            )

            my_row = standings[
                standings[entry_col].astype(str)
                == selected_entry
            ].iloc[0]

            rank = int(
                _safe_num(
                    my_row[rank_col],
                    0,
                )
            )

            field_size_value = pd.to_numeric(
                standings[rank_col],
                errors="coerce",
            ).max()

            field_size = int(
                field_size_value
                if pd.notna(field_size_value)
                else 0
            )

            points = _safe_num(
                my_row[points_col],
                0,
            )

            lineup_text = str(
                my_row[lineup_col]
            )

            lineup_players = parse_nfl_lineup_players(
                lineup_text
            )

            lineup_id = (
                nfl_lineup_id_from_names(lineup_players)
                if lineup_players
                else ""
            )

            matched_final = None

            if lineup_id:
                try:
                    matched_final = (
                        find_nfl_final_lineup_by_id(
                            lineup_id=lineup_id,
                            slate_date=slate_date.isoformat(),
                        )
                    )
                except Exception as exc:
                    st.warning(
                        "Could not check NFL Final Lineup "
                        f"matching: {exc}"
                    )

            contest_type = _infer_contest_type(
                field_size
            )

            metric1, metric2, metric3, metric4 = st.columns(4)

            metric1.metric(
                "Entry",
                selected_entry,
            )
            metric2.metric(
                "Contest",
                contest_type,
            )
            metric3.metric(
                "Finish",
                f"{rank} / {field_size}",
            )
            metric4.metric(
                "DK Points",
                f"{points:.2f}",
            )

            st.markdown("#### DraftKings Lineup")
            st.write(lineup_text)

            if len(lineup_players) == 9:
                st.success(
                    "Parsed all 9 NFL roster spots."
                )
            else:
                st.warning(
                    f"Parsed {len(lineup_players)} of 9 expected "
                    "NFL players. We may need to adjust the parser "
                    "for DraftKings' 2026 export format."
                )

            parsed_df = pd.DataFrame(
                {
                    "Parsed Player": lineup_players
                }
            )

            if not parsed_df.empty:
                st.dataframe(
                    parsed_df,
                    use_container_width=True,
                    hide_index=True,
                )

            st.caption(
                f"NFL Lineup ID: {lineup_id or 'Unavailable'}"
            )

            if matched_final:
                st.success(
                    "🏁 Matched NFL Final Lineup: "
                    f"{matched_final.get('lineup_slot', 'Unknown')} "
                    f"— {matched_final.get('strategy', 'Unknown')} "
                    f"— {matched_final.get('slate_name', 'Main')}"
                )

                saved_lookup = _build_saved_lineup_lookup(
                    matched_final
                )

                enriched_rows = []

                for player_name in lineup_players:
                    saved = saved_lookup.get(
                        str(player_name).strip().lower(),
                        {},
                    )

                    enriched_rows.append(
                        {
                            "Player": player_name,
                            "Slot": saved.get("slot", ""),
                            "Position": saved.get(
                                "position",
                                "",
                            ),
                            "Team": saved.get("team", ""),
                            "Opponent": saved.get(
                                "opponent",
                                "",
                            ),
                            "Salary": saved.get(
                                "salary",
                                0,
                            ),
                            "LL Projection": saved.get(
                                "ll_projection",
                                0,
                            ),
                            "Cash Score": saved.get(
                                "cash_score",
                                0,
                            ),
                            "GPP Score": saved.get(
                                "gpp_score",
                                0,
                            ),
                        }
                    )

                st.markdown(
                    "#### Matched Pre-Lock Lineup Metadata"
                )

                st.dataframe(
                    pd.DataFrame(enriched_rows),
                    use_container_width=True,
                    hide_index=True,
                )

            else:
                st.info(
                    "No saved NFL Final Lineup matched this entry."
                )

            st.caption(
                "Contest History saving is intentionally not enabled "
                "in v0.1. First we will validate this parser against "
                "a real Week 1 DraftKings NFL export."
            )