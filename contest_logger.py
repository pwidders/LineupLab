import hashlib
import re
from datetime import datetime, date

import pandas as pd
import streamlit as st

from contest_history_store import (
    load_contest_history,
    save_contest_history,
    update_contest_history_record,
)


DEFAULT_ENTRY_NAME = "rentisdue"
DOUBLE_UP_FIELD_SIZE_CUTOFF = 100


def parse_percent(x):
    try:
        return float(str(x).replace("%", "").strip())
    except Exception:
        return 0.0


def safe_num(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def clean_col_name(col):
    return str(col).strip().replace("\ufeff", "")


def find_col(df, possible_names):
    lookup = {clean_col_name(c).lower(): c for c in df.columns}
    for name in possible_names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def make_lineup_id(lineup_text):
    cleaned = "|".join(
        sorted(
            p.strip().lower()
            for p in str(lineup_text).replace(";", ",").split(",")
            if p.strip()
        )
    )
    if not cleaned:
        cleaned = str(lineup_text).strip().lower()
    return hashlib.md5(cleaned.encode("utf-8")).hexdigest()[:10]




def parse_lineup_players(lineup_text):
    text = str(lineup_text).strip()
    if not text:
        return []

    pattern = re.compile(
        r"(?:^|\s)(P|C|1B|2B|3B|SS|OF)\s+"
        r"(.+?)"
        r"(?=\s+(?:P|C|1B|2B|3B|SS|OF)\s+|$)"
    )

    return [
        match.group(2).strip()
        for match in pattern.finditer(text)
        if match.group(2).strip()
    ]

def infer_contest_type(field_size):
    if field_size and field_size < DOUBLE_UP_FIELD_SIZE_CUTOFF:
        return "Double-Up"
    return "Single-Entry GPP"


def render_single_contest(file, file_index, slate_date):
    try:
        df = pd.read_csv(file)
    except Exception as e:
        st.error(f"Could not read {file.name}: {e}")
        return None

    df.columns = [clean_col_name(c) for c in df.columns]

    entry_col = find_col(df, ["EntryName", "Entry Name"])
    entry_id_col = find_col(df, ["EntryId", "Entry ID"])
    rank_col = find_col(df, ["Rank", "Place"])
    points_col = find_col(df, ["Points", "FPTS", "Fantasy Points"])
    lineup_col = find_col(df, ["Lineup"])
    player_col = find_col(df, ["Player", "PlayerName", "Name"])
    roster_col = find_col(df, ["Roster Position", "RosterPosition", "Position", "Pos"])
    drafted_col = find_col(df, ["%Drafted", "% Drafted", "Ownership", "Own%"])
    fpts_col = find_col(df, ["FPTS", "Fantasy Points", "Points"])

    required = {
        "EntryId": entry_id_col,
        "EntryName": entry_col,
        "Rank": rank_col,
        "Points": points_col,
        "Lineup": lineup_col,
        "Player": player_col,
        "Roster Position": roster_col,
        "%Drafted": drafted_col,
        "FPTS": fpts_col,
    }
    missing = [name for name, col in required.items() if col is None]
    if missing:
        st.error(f"{file.name} is missing required columns: {', '.join(missing)}")
        st.caption(f"Columns found: {', '.join(df.columns.astype(str))}")
        return None

    standings = df[df[entry_col].notna()].copy()
    all_player_rows = df[df[player_col].notna()].copy()

    if standings.empty:
        st.warning(f"No standings rows found in {file.name}.")
        return None

    entry_names = standings[entry_col].dropna().astype(str).unique().tolist()
    default_index = 0
    for i, name in enumerate(entry_names):
        if name.lower() == DEFAULT_ENTRY_NAME:
            default_index = i
            break

    selected_entry = st.selectbox(
        "Select your entry",
        entry_names,
        index=default_index,
        key=f"contest_entry_select_{file_index}_{file.name}",
    )

    my_row = standings[standings[entry_col].astype(str) == selected_entry].iloc[0]
    entry_id = int(safe_num(my_row[entry_id_col], 0))

    rank = int(safe_num(my_row[rank_col], 0))
    field_size = int(pd.to_numeric(standings[rank_col], errors="coerce").max())
    points = safe_num(my_row[points_col], 0.0)
    lineup_text = str(my_row[lineup_col])
    rank_pct = rank / field_size if field_size else 0
    lineup_id = make_lineup_id(lineup_text)
    suggested_type = infer_contest_type(field_size)

    contest_type = st.selectbox(
        "Contest type",
        ["Double-Up", "Single-Entry GPP", "Other"],
        index=["Double-Up", "Single-Entry GPP", "Other"].index(suggested_type),
        key=f"contest_type_{file_index}_{file.name}",
        help="Auto-suggested from field size. Less than 100 entries defaults to Double-Up.",
    )

    money_col1, money_col2, money_col3 = st.columns(3)

    with money_col1:
        entry_fee = st.number_input(
            "Entry fee",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.2f",
            key=f"entry_fee_{file_index}_{file.name}",
        )

    with money_col2:
        winnings = st.number_input(
            "Winnings",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.2f",
            key=f"winnings_{file_index}_{file.name}",
        )

    profit = float(winnings) - float(entry_fee)

    with money_col3:
        st.metric("Profit", f"${profit:,.2f}")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Entry", selected_entry)
    col2.metric("Contest Type", contest_type)
    col3.metric("Rank", f"{rank} / {field_size}")
    col4.metric("Points", round(points, 2))
    col5.metric("Rank Percentile", f"{rank_pct:.1%}")

    st.markdown("### Lineup")
    st.write(lineup_text)
    st.caption(f"Lineup ID: {lineup_id}")

    lineup_players = parse_lineup_players(lineup_text)
    lineup_player_set = {name.strip().lower() for name in lineup_players}

    player_rows = all_player_rows[
        all_player_rows[player_col]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(lineup_player_set)
    ].copy()

    if player_rows.empty:
        st.warning(
            "Could not match the lineup players to the player-results rows. "
            "Showing the full contest player pool for review."
        )
        player_rows = all_player_rows.copy()
    elif len(player_rows) != 10:
        st.warning(
            f"Matched {len(player_rows)} of 10 lineup players. "
            "Review the lineup table before saving."
        )

    player_rows["Ownership %"] = player_rows[drafted_col].apply(parse_percent)
    player_rows["FPTS"] = pd.to_numeric(player_rows[fpts_col], errors="coerce").fillna(0)

    st.markdown("### Your Lineup — Ownership / Results")
    visible = player_rows[[player_col, roster_col, "Ownership %", "FPTS"]].copy()
    visible.columns = ["Player", "Roster Position", "Ownership %", "FPTS"]
    st.dataframe(visible.sort_values("Ownership %", ascending=False), use_container_width=True)

    player_results = (
        visible.rename(
            columns={
                "Player": "player",
                "Roster Position": "roster_position",
                "Ownership %": "ownership",
                "FPTS": "fpts",
            }
        )
        .to_dict(orient="records")
    )

    avg_ownership = player_rows["Ownership %"].mean()
    total_player_fpts = player_rows["FPTS"].sum()

    best_player = ""
    worst_player = ""
    if not player_rows.empty:
        best_player_row = player_rows.sort_values("FPTS", ascending=False).iloc[0]
        worst_player_row = player_rows.sort_values("FPTS", ascending=True).iloc[0]
        best_player = f"{best_player_row[player_col]} ({best_player_row['FPTS']})"
        worst_player = f"{worst_player_row[player_col]} ({worst_player_row['FPTS']})"

    summary = pd.DataFrame(
        [
            {
                "Slate Date": slate_date.strftime("%Y-%m-%d"),
                "Logged At": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Source File": file.name,
                "Entry ID": entry_id,
                "Entry Name": selected_entry,
                "Contest Type": contest_type,
                "Rank": rank,
                "Field Size": field_size,
                "Points": points,
                "Rank Percentile": rank_pct,
                "Average Ownership": avg_ownership,
                "Player FPTS Total": total_player_fpts,
                "Best Player": best_player,
                "Worst Player": worst_player,
                "Lineup ID": lineup_id,
                "Lineup": lineup_text,
                "Entry Fee": float(entry_fee),
                "Winnings": float(winnings),
                "Profit": profit,
                "Player Results": player_results,
            }
        ]
    )

    st.markdown("### Log Row")
    st.dataframe(summary, use_container_width=True)

    st.download_button(
        "Download This Contest Log Row",
        data=summary.to_csv(index=False).encode("utf-8"),
        file_name=f"lineuplab_contest_log_{file_index + 1}.csv",
        mime="text/csv",
        key=f"contest_log_download_{file_index}_{file.name}",
    )

    return summary

def render_saved_contest_editor():
    st.markdown("### ✏️ Edit Saved Contest Result")

    try:
        history = load_contest_history()
    except Exception as exc:
        st.error(f"Could not load saved contest history: {exc}")
        return

    if history.empty:
        st.caption("No saved contest results are available to edit.")
        return

    history = history.copy()

    history["edit_label"] = history.apply(
        lambda row: (
            f"{pd.to_datetime(row.get('slate_date')).strftime('%b %d, %Y')} — "
            f"{row.get('contest_type', 'Unknown')} — "
            f"{row.get('entry_name', 'Unknown')} — "
            f"Rank {int(row.get('rank', 0))}/{int(row.get('field_size', 0))} — "
            f"{float(row.get('points', 0)):.2f} pts"
        ),
        axis=1,
    )

    selected_label = st.selectbox(
        "Select a saved contest result",
        options=history["edit_label"].tolist(),
        key="saved_contest_edit_selector",
    )

    selected_row = history[
        history["edit_label"] == selected_label
    ].iloc[0]

    selected_id = str(selected_row["id"])

    selected_date = pd.to_datetime(
        selected_row.get("slate_date"),
        errors="coerce",
    )

    if pd.isna(selected_date):
        selected_date = pd.Timestamp(date.today())

    contest_type_options = [
        "Double-Up",
        "Single-Entry GPP",
        "Other",
    ]

    current_contest_type = str(
        selected_row.get("contest_type", "Other")
    )

    if current_contest_type not in contest_type_options:
        contest_type_options.append(current_contest_type)

    with st.form("edit_saved_contest_form"):
        edit_slate_date = st.date_input(
            "Slate date",
            value=selected_date.date(),
        )

        edit_entry_name = st.text_input(
            "Entry name",
            value=str(selected_row.get("entry_name", "")),
        )

        edit_contest_type = st.selectbox(
            "Contest type",
            options=contest_type_options,
            index=contest_type_options.index(
                current_contest_type
            ),
        )

        edit_col1, edit_col2, edit_col3 = st.columns(3)

        with edit_col1:
            edit_rank = st.number_input(
                "Rank",
                min_value=0,
                value=int(selected_row.get("rank", 0)),
                step=1,
            )

        with edit_col2:
            edit_field_size = st.number_input(
                "Field size",
                min_value=0,
                value=int(selected_row.get("field_size", 0)),
                step=1,
            )

        with edit_col3:
            edit_points = st.number_input(
                "Points",
                min_value=0.0,
                value=float(selected_row.get("points", 0)),
                step=0.01,
                format="%.2f",
            )

        money_col1, money_col2 = st.columns(2)

        with money_col1:
            edit_entry_fee = st.number_input(
                "Entry fee",
                min_value=0.0,
                value=float(selected_row.get("entry_fee", 0)),
                step=0.50,
                format="%.2f",
            )

        with money_col2:
            edit_winnings = st.number_input(
                "Winnings",
                min_value=0.0,
                value=float(selected_row.get("winnings", 0)),
                step=0.50,
                format="%.2f",
            )

        preview_profit = (
            float(edit_winnings) - float(edit_entry_fee)
        )

        st.metric(
            "Updated Profit",
            f"${preview_profit:,.2f}",
        )

        save_edit = st.form_submit_button(
            "💾 Save Contest Changes",
            type="primary",
        )

    if save_edit:
        try:
            update_contest_history_record(
                record_id=selected_id,
                slate_date=edit_slate_date.isoformat(),
                entry_name=edit_entry_name,
                contest_type=edit_contest_type,
                rank=int(edit_rank),
                field_size=int(edit_field_size),
                points=float(edit_points),
                entry_fee=float(edit_entry_fee),
                winnings=float(edit_winnings),
            )

            st.session_state[
                "contest_history_edit_notice"
            ] = "Contest result updated successfully ✅"

            st.rerun()

        except Exception as exc:
            st.error(f"Could not update contest result: {exc}")

def render_contest_logger():
    st.subheader("Contest Stat Collector")

    edit_notice = st.session_state.pop(
        "contest_history_edit_notice",
        None,
    )

    if edit_notice:
        st.success(edit_notice)

    with st.expander("✏️ Edit Saved Contest Result"):
        render_saved_contest_editor()

    save_notice = st.session_state.pop(
        "contest_history_save_notice",
        None,
    )

    if save_notice:
        st.success(save_notice)

    slate_date = st.date_input(
        "Slate date",
        value=date.today(),
        help="DraftKings exports do not include a slate date, so choose the date this contest belongs to.",
    )

    uploaded_files = st.file_uploader(
        "Upload DraftKings contest standings CSV",
        type=["csv"],
        key="contest_standings_csv_uploader",
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload one or more DraftKings contest exports to review and log results.")
        return

    all_summaries = []

    for i, file in enumerate(uploaded_files):
        with st.expander(f"{file.name}", expanded=(i == 0)):
            summary = render_single_contest(file, i, slate_date)
            if summary is not None:
                all_summaries.append(summary)

    if all_summaries:
        combined = pd.concat(all_summaries, ignore_index=True)

        st.divider()
        st.markdown("### Combined Contest Log")
        st.dataframe(combined, use_container_width=True)

        duplicate_lineups = combined[combined.duplicated("Lineup ID", keep=False)]
        if not duplicate_lineups.empty:
            st.info(
                "Duplicate lineup detected across contest files. This is expected when you enter the same lineup in both a double-up and a GPP. They are still logged as separate contest results."
            )

        total_fee = float(combined["Entry Fee"].sum())
        total_winnings = float(combined["Winnings"].sum())
        total_profit = float(combined["Profit"].sum())

        summary_col1, summary_col2, summary_col3 = st.columns(3)
        summary_col1.metric("Total Entry Fees", f"${total_fee:,.2f}")
        summary_col2.metric("Total Winnings", f"${total_winnings:,.2f}")
        summary_col3.metric("Total Profit", f"${total_profit:,.2f}")

        if st.button(
            "💾 Save Contest History",
            key="save_contest_history",
            type="primary",
        ):
            try:
                inserted, updated = save_contest_history(combined)

                message_parts = []

                if inserted:
                    message_parts.append(
                        f"Saved {inserted} new contest result(s) ✅"
                    )

                if updated:
                    message_parts.append(
                        f"Updated {updated} existing contest result(s) 🔄"
                    )

                if not message_parts:
                    message_parts.append(
                        "No contest results were changed."
                    )

                message = " ".join(message_parts)

                st.session_state[
                    "contest_history_save_notice"
                ] = message

                st.rerun()

            except Exception as exc:
                st.error(f"Could not save contest history: {exc}")

        st.download_button(
            "Download Combined Contest Log",
            data=combined.to_csv(index=False).encode("utf-8"),
            file_name="lineuplab_combined_contest_log.csv",
            mime="text/csv",
            key="combined_contest_log_download",
        )