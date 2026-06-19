# Streamlit entry point — AI Usage Dashboard
# TODO: Implement full UI in Phase 1.
# Refer to architecture.md for the two-level tab structure.
# Reference: GeminiLogDashboard_v1/app.py for patterns to adapt.

import streamlit as st
from src.database.schema import init_db
from src.ingestion.loader import ingest_all

st.set_page_config(
    page_title="AI Usage Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

try:
    ingest_all()
except Exception as e:
    st.sidebar.error(f"Auto-ingest failed: {e}")

st.title("📊 AI Usage Dashboard")
st.markdown("Multi-provider AI tool log analysis. Configure providers in the sidebar.")
st.info("UI implementation coming in Phase 1. Database and provider pipeline are ready.")
