"""
StudySync AI - Page 1: Dashboard
Academic productivity dashboard providing live metrics, task progress,
quiz performance trajectories, upcoming deadlines, and recent study activity.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, date

st.set_page_config(
    page_title="Dashboard | StudySync AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

from utils.database import (
    init_db,
    get_dashboard_metrics,
    get_all_tasks,
    get_all_notes,
    get_all_quiz_attempts,
    get_study_sessions,
    update_task_status,
    log_study_session,
    get_task_stats
)
from utils.helpers import (
    apply_theme,
    render_sidebar,
    render_page_header,
    render_metric_card,
    render_empty_state
)

# Initialize database safely
init_db()

# Apply current theme
current_theme = apply_theme()

# Render standard sidebar
render_sidebar()

# Welcome Section & Application Description
now = datetime.now()
greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
today_str = now.strftime("%A, %B %d, %Y")

render_page_header(
    title=f"{greeting}, Scholar",
    subtitle="Welcome to StudySync AI — your personal academic productivity platform. Organize course materials, generate active recall practice, track deadlines, and monitor your exam readiness.",
    badge_text=today_str,
    badge_type="primary"
)

# Fetch genuine stored metrics
metrics = get_dashboard_metrics()
task_stats = get_task_stats()

# 5 Core Required Metric Cards (from actual database)
m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
with m_c1:
    render_metric_card("Saved Notes", metrics["total_notes"], f"{metrics['total_summaries']} Summaries saved")
with m_c2:
    render_metric_card("Completed Tasks", metrics["completed_tasks"], f"{metrics['task_completion_rate']}% of all coursework")
with m_c3:
    render_metric_card("Pending Tasks", metrics["pending_tasks"], f"{metrics['in_progress_tasks']} Currently in progress")
with m_c4:
    render_metric_card("Quizzes Attempted", metrics["quizzes_attempted"], "Practice tests completed")
with m_c5:
    render_metric_card("Avg Quiz Score", f"{metrics['avg_quiz_score']}%", "Overall exam readiness")

st.markdown("<br>", unsafe_allow_html=True)

# Quick-Action Navigation Hub
st.markdown("#### Quick Actions")
qa1, qa2, qa3, qa4, qa5, qa6 = st.columns(6)

with qa1:
    if st.button("New Note", icon=":material/note_add:", use_container_width=True):
        st.switch_page("pages/2_Smart_Notes.py")

with qa2:
    if st.button("AI Summarize", icon=":material/auto_stories:", use_container_width=True):
        st.switch_page("pages/3_AI_Summarizer.py")

with qa3:
    if st.button("Take Quiz", icon=":material/quiz:", use_container_width=True):
        st.switch_page("pages/4_Quiz_Generator.py")

with qa4:
    if st.button("Flashcards", icon=":material/style:", use_container_width=True):
        st.switch_page("pages/5_Flashcards.py")

with qa5:
    if st.button("Task Board", icon=":material/checklist:", use_container_width=True):
        st.switch_page("pages/6_Task_Manager.py")

with qa6:
    if st.button("Full Analytics", icon=":material/insights:", use_container_width=True):
        st.switch_page("pages/7_Study_Analytics.py")

st.markdown("<br>", unsafe_allow_html=True)

# Main Grid Row 1: Task Completion Progress & Quiz Performance Chart
grid_col1, grid_col2 = st.columns([1.1, 1.4])

# Plotly theme styling
is_dark = current_theme == "dark"
plot_bg = "#151f30" if is_dark else "#ffffff"
font_color = "#f8fafc" if is_dark else "#0f172a"
grid_color = "rgba(255, 255, 255, 0.08)" if is_dark else "rgba(0, 0, 0, 0.08)"

with grid_col1:
    st.markdown("#### Coursework Completion Progress")
    
    total_t = task_stats["total"]
    comp_t = task_stats["completed"]
    in_prog_t = task_stats["in_progress"]
    pend_t = task_stats["pending"]
    pct = task_stats["completion_rate"]

    st.markdown(
        f"""
        <div class="sync-card">
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
                <span style="font-size: 13px; font-weight: 600; color: var(--text-secondary);">Overall Task Velocity</span>
                <span style="font-size: 22px; font-weight: 800; color: var(--text-primary);">{pct}%</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.progress(pct / 100.0)

    # 3-stat breakdown
    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 10px; background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 8px;">
                <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Completed</div>
                <div style="font-size: 18px; font-weight: 700; color: #10b981;">{comp_t}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with b2:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 10px; background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 8px;">
                <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">In Progress</div>
                <div style="font-size: 18px; font-weight: 700; color: #6366f1;">{in_prog_t}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with b3:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 10px; background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 8px;">
                <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Pending</div>
                <div style="font-size: 18px; font-weight: 700; color: #f59e0b;">{pend_t}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

with grid_col2:
    st.markdown("#### Quiz Performance Trajectory")
    attempts = get_all_quiz_attempts()
    if attempts:
        df_att = pd.DataFrame(attempts)
        df_att['completed_at'] = pd.to_datetime(df_att['completed_at'])
        df_att = df_att.sort_values('completed_at')

        fig = px.line(
            df_att,
            x='completed_at',
            y='percentage',
            markers=True,
            hover_data=['quiz_title', 'subject', 'score', 'total_questions'],
            labels={'completed_at': 'Date', 'percentage': 'Score %'},
            color_discrete_sequence=['#6366f1']
        )
        # Add 80% Mastery benchmark line
        fig.add_hline(
            y=80,
            line_dash="dash",
            line_color="#10b981",
            annotation_text="Mastery (80%)",
            annotation_position="bottom right"
        )
        fig.update_layout(
            paper_bgcolor=plot_bg,
            plot_bgcolor=plot_bg,
            font=dict(color=font_color, family="Plus Jakarta Sans"),
            margin=dict(t=20, b=20, l=20, r=20),
            height=215,
            xaxis=dict(gridcolor=grid_color, showgrid=False),
            yaxis=dict(gridcolor=grid_color, range=[0, 105], title="Score %")
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        render_empty_state("No Quiz Attempts", "Take practice quizzes to view your accuracy trajectory.", "🎯")

st.markdown("<br>", unsafe_allow_html=True)

# Main Grid Row 2: Upcoming Deadlines & Recent Study Activity
row2_col1, row2_col2 = st.columns([1.2, 1.2])

with row2_col1:
    st.markdown("#### Upcoming Academic Deadlines")
    pending_tasks = get_all_tasks(status_filter='Pending') + get_all_tasks(status_filter='In Progress')
    
    # Sort by deadline
    pending_tasks_with_deadline = [t for t in pending_tasks if t.get('deadline')]
    pending_tasks_with_deadline.sort(key=lambda t: t['deadline'])

    if pending_tasks_with_deadline:
        for t in pending_tasks_with_deadline[:4]:
            prio = t['priority']
            badge_class = "danger" if prio == 'High' else "warning" if prio == 'Medium' else "info"
            
            c_info, c_action = st.columns([4, 1])
            with c_info:
                st.markdown(
                    f"""
                    <div class="activity-item">
                        <div>
                            <div class="activity-title">{t['title']}</div>
                            <div class="activity-meta">
                                <span style="color: var(--accent); font-weight: 600;">{t['subject']}</span> • Due: <strong>{t['deadline']}</strong> • Est: {t['estimated_hours']}h
                            </div>
                        </div>
                        <div>
                            <span class="badge badge-{badge_class}">{prio}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with c_action:
                if st.button("Complete", key=f"dash_done_{t['id']}", help="Mark completed"):
                    update_task_status(t['id'], 'Completed')
                    st.toast("Task completed! 🎉", icon="✅")
                    st.rerun()

        if st.button("Open Task Manager →", key="dash_view_all_tasks"):
            st.switch_page("pages/6_Task_Manager.py")
    else:
        render_empty_state("All Caught Up!", "No urgent deadlines currently pending.", "🎉")

with row2_col2:
    st.markdown("#### Recent Study Activity")
    sessions = get_study_sessions()
    
    if sessions or attempts:
        # Merge recent sessions and attempts into a timeline
        recent_items = []
        for s in (sessions or [])[:4]:
            recent_items.append({
                "type": "Study Session",
                "title": f"{s['session_type']}: {s.get('topic') or s['subject']}",
                "meta": f"{s['subject']} • {s['duration_minutes']} minutes",
                "time": s['created_at'][:10]
            })
        for a in (attempts or [])[:3]:
            recent_items.append({
                "type": "Practice Quiz",
                "title": a['quiz_title'],
                "meta": f"{a['subject']} • Score: {a['score']}/{a['total_questions']} ({a['percentage']}%)",
                "time": a['completed_at'][:10]
            })

        for item in recent_items[:4]:
            badge_type = "primary" if item["type"] == "Study Session" else "success"
            st.markdown(
                f"""
                <div class="activity-item">
                    <div>
                        <div class="activity-title">{item['title']}</div>
                        <div class="activity-meta">{item['meta']}</div>
                    </div>
                    <div style="text-align: right;">
                        <span class="badge badge-{badge_type}">{item['type']}</span>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 3px;">{item['time']}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with st.popover("⏱️ Quick-Log Study Minutes", use_container_width=True):
            with st.form("dash_quick_log_form"):
                subj_list = metrics["subjects"] if metrics["subjects"] else ["General Study", "Computer Science", "Biology", "Psychology"]
                log_subj = st.selectbox("Subject", options=subj_list)
                log_topic = st.text_input("Topic", placeholder="e.g. Chapter 5 Reading")
                log_mins = st.number_input("Minutes", min_value=5, max_value=360, value=30, step=5)
                log_type = st.selectbox("Activity", options=["Reading", "Quiz Practice", "Flashcards", "Summary Review", "Problem Set"])
                
                if st.form_submit_button("Record Session"):
                    if not log_topic.strip():
                        st.error("Please enter a topic.")
                    else:
                        log_study_session(log_subj, int(log_mins), log_topic, log_type)
                        st.success("Study session logged!")
                        st.rerun()
    else:
        render_empty_state("No Activity Yet", "Log study sessions or complete quizzes to see your timeline.", "⏳")
