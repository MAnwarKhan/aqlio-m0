"""Minimal Phase 1 participant-facing foundation screen."""

import streamlit as st

from app.application import build_development_foundation
from app.config import SettingsError


def render_home() -> None:
    st.set_page_config(page_title="Aqlio", page_icon="✨", layout="centered")
    st.title("Welcome to Aqlio")
    try:
        foundation = build_development_foundation()
    except (SettingsError, ValueError):
        st.error("Aqlio could not start safely. Please contact support.")
        st.stop()

    user = foundation.auth.current_user()
    st.subheader(f"Hello, {user.display_name}")
    st.write("Build a useful assistant from your documents—one clear step at a time.")
    st.info("The project-building journey arrives in the next implementation phase.")
    st.button("Create my first project", type="primary", disabled=True)
