"""Obesity & T2D commercial intelligence: the dashboard (M6).

Run from the repo root with the virtual environment active:
    streamlit run app/streamlit_app.py

Reads only app/data/ (refresh it with: python scripts/build_app_data.py).
"""

import streamlit as st

st.set_page_config(page_title="Obesity & T2D intel", page_icon="💊", layout="wide")

PAGES = [
    st.Page("views/home.py", title="Overview", icon="🏠", default=True),
    st.Page("views/landscape.py", title="Landscape", icon="🧪"),
    st.Page("views/changes.py", title="What changed", icon="📰"),
    st.Page("views/segments.py", title="Who to target", icon="🎯"),
    st.Page("views/call_list.py", title="Call list", icon="📇"),
]
st.navigation(PAGES).run()
