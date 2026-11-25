"""Obesity & T2D commercial intelligence: the dashboard (M6).

Run from the repo root with the virtual environment active:
    streamlit run app/streamlit_app.py

Reads only app/data/ (refresh it with: python scripts/build_app_data.py).
"""

import streamlit as st

import common as C

st.set_page_config(page_title="Obesity & T2D Intelligence", page_icon=":material/monitoring:", layout="wide")

PAGES = {
    "": [st.Page("views/home.py", title="Overview", icon=":material/dashboard:", default=True)],
    "Market": [
        st.Page("views/landscape.py", title="Landscape", icon=":material/science:"),
        st.Page("views/changes.py", title="What changed", icon=":material/notifications:"),
    ],
    "Field force": [
        st.Page("views/segments.py", title="Who to target", icon=":material/target:"),
        st.Page("views/call_list.py", title="Call list", icon=":material/contact_page:"),
    ],
    "Reference": [st.Page("views/about.py", title="About the data", icon=":material/info:")],
}
st.logo(str(C.LOGO), size="large")
page = st.navigation(PAGES, position="top")
C.inject_css()
page.run()
C.footer()
