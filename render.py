import streamlit as st

DK_SALARY_CAP = 50000


def render_lineup(lineup, salary, score):
    st.markdown(
        f"### 💰 ${salary:,.0f} | 🔮 {round(score, 1)} pts | 💵 ${DK_SALARY_CAP - salary:,.0f} left"
    )

    for _, row in lineup.iterrows():
        st.write(
            f"**{row['Slot']}** — {row['Player']} ({row['Team']}) | "
            f"${int(row['Salary'])} | {round(row['Score'], 1)} pts"
        )

    lineup_text = "\n".join(
        f"{row['Slot']} - {row['Player']}" for _, row in lineup.iterrows()
    )

    st.code(lineup_text, language="text")