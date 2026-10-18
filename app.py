"""
StudySync AI - Application Launcher
Entrypoint that routes directly to the primary Academic Dashboard.
"""

import streamlit as st
from utils.database import init_db

# Initialize Streamlit configuration
st.set_page_config(
    page_title="StudySync AI - Academic Workspace",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure database is initialized
init_db()

# Route into primary Dashboard
st.switch_page("pages/1_Dashboard.py")
