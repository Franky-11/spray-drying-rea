from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def main() -> None:
    st.set_page_config(page_title="Sprühtrockner REA", layout="wide")

    navigation = st.navigation(
        [
            st.Page("pages/overview.py", title="Überblick", default=True),
            st.Page("pages/simulation.py", title="REA-Trocknungskinetik"),
            st.Page("pages/process_simulation.py", title="Prozesssimulation"),
        ],
        position="sidebar",
    )

    navigation.run()


if __name__ == "__main__":
    main()
