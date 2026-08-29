"""Aqlio M0 Streamlit entry point."""

from app.infrastructure import configure_logging
from app.ui.home import render_home

configure_logging()
render_home()
