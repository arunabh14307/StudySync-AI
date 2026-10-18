"""
UI and Helper utilities for StudySync AI.
Manages theme switching (dark/light) across pages, CSS injection,
sidebar navigation with clean labels, metric displays, and reusable components.
"""

import os
import streamlit as st
from typing import Optional, List, Dict, Any
from utils.database import get_preference, set_preference

CSS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "styles.css")


def load_css() -> str:
    """Reads CSS from the assets stylesheet."""
    if os.path.exists(CSS_PATH):
        try:
            with open(CSS_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""


def apply_theme() -> str:
    """
    Applies the active theme (Dark or Light) via session state and database persistence.
    Injects custom CSS classes and stylesheets into the Streamlit app.
    """
    if "theme" not in st.session_state:
        saved_theme = get_preference("theme", default_value="dark")
        st.session_state["theme"] = saved_theme

    theme = st.session_state["theme"]
    theme_class = f"studysync-theme-{theme}"

    css_content = load_css()

    st.markdown(
        f"""
        <style>
        {css_content}
        </style>
        <div id="studysync-theme-root" class="{theme_class}"></div>
        <script>
            const themeClass = "{theme_class}";
            document.body.className = document.body.className.replace(/studysync-theme-\\w+/g, '') + ' ' + themeClass;
            const appView = document.querySelector('.stApp');
            if (appView) {{
                appView.className = appView.className.replace(/studysync-theme-\\w+/g, '') + ' ' + themeClass;
            }}
        </script>
        """,
        unsafe_allow_html=True
    )
    return theme


def render_sidebar():
    """
    Renders the unified application sidebar:
    1. StudySync AI Branding
    2. Professional page navigation links (clean typography, no emoji clutter)
    3. Working Theme preference toggle
    4. Application information section
    """
    with st.sidebar:
        # Branding
        st.markdown(
            """
            <div class="brand-container">
                <div class="brand-badge">S</div>
                <div>
                    <h2 class="brand-name">StudySync AI</h2>
                    <p class="brand-tagline">Academic Productivity</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Main Navigation
        st.markdown('<div class="sidebar-section-title">Navigation</div>', unsafe_allow_html=True)
        
        st.page_link("pages/1_Dashboard.py", label="Dashboard", icon=":material/dashboard:")
        st.page_link("pages/2_Smart_Notes.py", label="Smart Notes", icon=":material/description:")
        st.page_link("pages/3_AI_Summarizer.py", label="AI Summarizer", icon=":material/auto_stories:")
        st.page_link("pages/4_Quiz_Generator.py", label="Quiz Generator", icon=":material/quiz:")
        st.page_link("pages/5_Flashcards.py", label="Flashcards", icon=":material/style:")
        st.page_link("pages/6_Task_Manager.py", label="Task Manager", icon=":material/task_alt:")
        st.page_link("pages/7_Study_Analytics.py", label="Study Analytics", icon=":material/analytics:")
        st.page_link("pages/8_Study_Library.py", label="Study Library", icon=":material/folder_open:")

        st.markdown('<div class="sidebar-section-title">Preferences</div>', unsafe_allow_html=True)

        # Working Theme preference toggle
        current_theme = st.session_state.get("theme", "dark")
        new_theme = "light" if current_theme == "dark" else "dark"
        btn_label = "Switch to Light Mode" if current_theme == "dark" else "Switch to Dark Mode"
        btn_icon = ":material/light_mode:" if current_theme == "dark" else ":material/dark_mode:"

        if st.button(btn_label, icon=btn_icon, use_container_width=True, key="theme_switcher_btn"):
            st.session_state["theme"] = new_theme
            set_preference("theme", new_theme)
            st.rerun()

        # Application Information Section
        st.markdown(
            """
            <div class="app-info-card">
                <div class="app-info-title">
                    <span>StudySync AI</span>
                    <span class="badge badge-success">v1.2.0</span>
                </div>
                <p class="app-info-desc">
                    Private & Offline Academic Workspace.<br>
                    Data stored in local SQLite.<br>
                    Extractive NLP powered.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_sidebar_header():
    """Backwards-compatible wrapper that renders the complete sidebar."""
    render_sidebar()


def render_page_header(title: str, subtitle: str, badge_text: Optional[str] = None, badge_type: str = "primary"):
    """Renders a standard clean SaaS page header with optional status badge."""
    badge_html = f'<span class="badge badge-{badge_type}">{badge_text}</span>' if badge_text else ""
    st.markdown(
        f"""
        <div class="page-header-container">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 4px;">
                <h1 class="page-title">{title}</h1>
                {badge_html}
            </div>
            <p class="page-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_metric_card(label: str, value: Any, subtext: str = ""):
    """Renders a modern metric KPI box."""
    st.markdown(
        f"""
        <div class="metric-box">
            <div>
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
            </div>
            <div class="metric-sub">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_empty_state(title: str, description: str, icon_symbol: str = "📚", action_hint: str = ""):
    """Renders a consistent, polished empty state placeholder."""
    action_html = f"<div style='margin-top: 8px;'><small style='color: var(--accent); font-weight: 600;'>{action_hint}</small></div>" if action_hint else ""
    st.markdown(
        f"""
        <div class="empty-state">
            <div style="font-size: 32px; line-height: 1; margin-bottom: 8px;">{icon_symbol}</div>
            <div class="empty-state-title">{title}</div>
            <div class="empty-state-desc">{description}</div>
            {action_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_badge(text: str, badge_type: str = "primary") -> str:
    """Returns HTML for a badge component."""
    return f'<span class="badge badge-{badge_type}">{text}</span>'
