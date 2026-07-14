import streamlit as st


def render_performance_center():
    st.header("📊 Performance Center")

    st.info("Contest analytics will appear here.")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Profit", "$0")

    with c2:
        st.metric("ROI", "0%")

    with c3:
        st.metric("Cash Rate", "0%")

    st.divider()

    st.subheader("Slate History")

    st.caption("Your logged contests will appear here.")