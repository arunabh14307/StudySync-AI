"""
StudySync AI - Page 7: Study Analytics
Visualizes genuine academic progress metrics and analytics using Plotly charts:
task completion rates, quiz mastery curves, subject-wise performance breakdowns,
and study session history.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import datetime
from typing import Optional, Tuple

st.set_page_config(page_title="Study Analytics | StudySync AI", page_icon="📈", layout="wide")

from utils.database import (
    init_db,
    get_all_notes,
    get_notes_stats,
    get_all_tasks,
    get_task_stats,
    get_all_quiz_attempts,
    get_quiz_stats,
    get_subject_quiz_performance,
    get_study_sessions,
    get_study_session_stats,
    log_study_session,
    delete_study_session,
    get_distinct_subjects
)
from utils.helpers import (
    apply_theme,
    render_sidebar_header,
    render_page_header,
    render_metric_card,
    render_empty_state
)

init_db()
current_theme = apply_theme()
render_sidebar_header()

render_page_header(
    title="Study Analytics & Progress Insights",
    subtitle="Data-driven performance metrics, quiz mastery curves, and time investment computed from real study records.",
    badge_text="Plotly Analytics",
    badge_type="primary"
)

# Plotly theme styling
is_dark = current_theme == "dark"
plot_bg = "#182234" if is_dark else "#ffffff"
paper_bg = "#0a0d14" if is_dark else "#f8fafc"
font_color = "#f8fafc" if is_dark else "#0f172a"
grid_color = "rgba(255, 255, 255, 0.08)" if is_dark else "rgba(0, 0, 0, 0.08)"

# -----------------------------------------------------------------------------
# Date-Range Filtering Controls
# -----------------------------------------------------------------------------
today = datetime.date.today()

col_filt_title, col_filt_opt = st.columns([1, 2])
with col_filt_title:
    st.markdown("### 🗓️ Analytics Scope")
with col_filt_opt:
    time_preset = st.radio(
        "Date Range Selection",
        options=["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom Range"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )

start_date_str: Optional[str] = None
end_date_str: Optional[str] = None

if time_preset == "Last 7 Days":
    start_date_str = (today - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    end_date_str = today.strftime("%Y-%m-%d")
elif time_preset == "Last 30 Days":
    start_date_str = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end_date_str = today.strftime("%Y-%m-%d")
elif time_preset == "Last 90 Days":
    start_date_str = (today - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    end_date_str = today.strftime("%Y-%m-%d")
elif time_preset == "Custom Range":
    c_d1, c_d2 = st.columns(2)
    with c_d1:
        custom_start = st.date_input("Start Date", value=today - datetime.timedelta(days=14), max_value=today)
    with c_d2:
        custom_end = st.date_input("End Date", value=today, min_value=custom_start)
    start_date_str = custom_start.strftime("%Y-%m-%d")
    end_date_str = custom_end.strftime("%Y-%m-%d")

if start_date_str and end_date_str:
    st.caption(f"Showing analytics data from **{start_date_str}** to **{end_date_str}**")
else:
    st.caption("Showing cumulative analytics across **All Time**")

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Fetch Genuine Database Records
# -----------------------------------------------------------------------------
notes_stats = get_notes_stats(start_date=start_date_str, end_date=end_date_str)
task_stats = get_task_stats(start_date=start_date_str, end_date=end_date_str)
quiz_stats = get_quiz_stats(start_date=start_date_str, end_date=end_date_str)
subject_perf = get_subject_quiz_performance(start_date=start_date_str, end_date=end_date_str)
session_stats = get_study_session_stats(start_date=start_date_str, end_date=end_date_str)
attempts = get_all_quiz_attempts(start_date=start_date_str, end_date=end_date_str)
sessions = get_study_sessions(start_date=start_date_str, end_date=end_date_str)
all_tasks = get_all_tasks()

# -----------------------------------------------------------------------------
# Metric Tiles: Row 1 - Content & Task Metrics
# -----------------------------------------------------------------------------
st.markdown("#### 📊 Academic Volume & Completion")
m1, m2, m3, m4 = st.columns(4)
with m1:
    render_metric_card(
        "Total Notes Created",
        notes_stats["total_notes"],
        f"{notes_stats['total_words']} total words"
    )
with m2:
    render_metric_card(
        "Total Tasks",
        task_stats["total"],
        f"{task_stats['completion_rate']}% Completion Rate"
    )
with m3:
    render_metric_card(
        "Completed Tasks",
        task_stats["completed"],
        f"{task_stats['pending']} Pending • {task_stats['in_progress']} Active"
    )
with m4:
    overdue_text = f"⚠️ {task_stats['overdue']} Overdue" if task_stats['overdue'] > 0 else "0 Overdue Tasks"
    render_metric_card(
        "Overdue Tasks",
        task_stats["overdue"],
        overdue_text
    )

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Metric Tiles: Row 2 - Quiz Performance & Study Time
# -----------------------------------------------------------------------------
st.markdown("#### 🎯 Quiz Readiness & Study Investment")
m5, m6, m7, m8 = st.columns(4)
with m5:
    render_metric_card(
        "Quiz Attempts",
        quiz_stats["attempts_count"],
        f"{quiz_stats['total_questions_answered']} questions solved"
    )
with m6:
    render_metric_card(
        "Average Quiz Score",
        f"{quiz_stats['avg_score']}%",
        "Calculated from attempts"
    )
with m7:
    render_metric_card(
        "Best Quiz Score",
        f"{quiz_stats['highest_score']}%",
        f"Lowest: {quiz_stats['lowest_score']}%"
    )
with m8:
    render_metric_card(
        "Study Time Logged",
        f"{session_stats['total_hours']} hrs",
        f"{session_stats['total_sessions']} study sessions"
    )

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Row 3: Quiz Visualizations
# -----------------------------------------------------------------------------
col_q1, col_q2 = st.columns(2)

with col_q1:
    st.markdown("#### 📈 Quiz Accuracy Trajectory")
    if attempts:
        df_attempts = pd.DataFrame(attempts)
        df_attempts['completed_at'] = pd.to_datetime(df_attempts['completed_at'])
        df_attempts = df_attempts.sort_values('completed_at')

        fig_trend = px.line(
            df_attempts,
            x='completed_at',
            y='percentage',
            markers=True,
            hover_data=['quiz_title', 'subject', 'score', 'total_questions'],
            labels={'completed_at': 'Date & Time', 'percentage': 'Score %'},
            color_discrete_sequence=['#6366f1']
        )
        fig_trend.add_hline(y=80, line_dash="dash", line_color="#10b981", annotation_text="Target Mastery (80%)")
        fig_trend.update_layout(
            paper_bgcolor=plot_bg,
            plot_bgcolor=plot_bg,
            font=dict(color=font_color, family="Plus Jakarta Sans"),
            margin=dict(t=30, b=20, l=20, r=20),
            height=320,
            xaxis=dict(gridcolor=grid_color),
            yaxis=dict(gridcolor=grid_color, range=[0, 105], title="Score (%)")
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        render_empty_state("No Quiz Attempts", "Complete practice quizzes in the Quizzes module to visualize your learning trajectory.", "🎯")

with col_q2:
    st.markdown("#### 📚 Subject-Wise Quiz Performance")
    if subject_perf:
        df_subj = pd.DataFrame(subject_perf)
        fig_subj = go.Figure()
        fig_subj.add_trace(go.Bar(
            name='Average Score (%)',
            x=df_subj['subject'],
            y=df_subj['avg_score'],
            marker_color='#6366f1',
            text=df_subj['avg_score'].apply(lambda x: f"{x}%"),
            textposition='auto'
        ))
        fig_subj.add_trace(go.Bar(
            name='Best Score (%)',
            x=df_subj['subject'],
            y=df_subj['best_score'],
            marker_color='#10b981',
            text=df_subj['best_score'].apply(lambda x: f"{x}%"),
            textposition='auto'
        ))
        fig_subj.update_layout(
            barmode='group',
            paper_bgcolor=plot_bg,
            plot_bgcolor=plot_bg,
            font=dict(color=font_color, family="Plus Jakarta Sans"),
            margin=dict(t=30, b=20, l=20, r=20),
            height=320,
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor=grid_color, range=[0, 105], title="Score (%)"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_subj, use_container_width=True)
    else:
        render_empty_state("No Subject Quiz Data", "Take quizzes with assigned courses to view subject-specific performance comparisons.", "📊")

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Row 4: Task Status & Study Hours Distribution
# -----------------------------------------------------------------------------
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.markdown("#### ✅ Task Completion Breakdown")
    if task_stats["total"] > 0:
        task_data = []
        if task_stats["completed"] > 0:
            task_data.append({"Status": "Completed", "Count": task_stats["completed"], "Color": "#10b981"})
        if task_stats["in_progress"] > 0:
            task_data.append({"Status": "In Progress", "Count": task_stats["in_progress"], "Color": "#3b82f6"})
        if task_stats["pending"] > 0:
            task_data.append({"Status": "Pending", "Count": task_stats["pending"], "Color": "#f59e0b"})
        if task_stats["overdue"] > 0:
            task_data.append({"Status": "Overdue", "Count": task_stats["overdue"], "Color": "#ef4444"})

        df_task_pie = pd.DataFrame(task_data)
        fig_task = px.pie(
            df_task_pie,
            names="Status",
            values="Count",
            hole=0.55,
            color="Status",
            color_discrete_map={d["Status"]: d["Color"] for d in task_data}
        )
        fig_task.update_layout(
            paper_bgcolor=plot_bg,
            plot_bgcolor=plot_bg,
            font=dict(color=font_color, family="Plus Jakarta Sans"),
            margin=dict(t=20, b=20, l=20, r=20),
            height=300,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_task, use_container_width=True)
    else:
        render_empty_state("No Tasks Found", "Create assignments in the Task Manager to track completion rates and status distribution.", "✅")

with col_t2:
    st.markdown("#### ⏳ Study Hours by Activity Type")
    if sessions:
        df_sess = pd.DataFrame(sessions)
        type_dur = df_sess.groupby('session_type')['duration_minutes'].sum().reset_index()
        type_dur['hours'] = (type_dur['duration_minutes'] / 60).round(1)

        fig_types = px.pie(
            type_dur,
            names='session_type',
            values='hours',
            hole=0.55,
            color_discrete_sequence=['#6366f1', '#10b981', '#3b82f6', '#f59e0b', '#ec4899', '#8b5cf6']
        )
        fig_types.update_layout(
            paper_bgcolor=plot_bg,
            plot_bgcolor=plot_bg,
            font=dict(color=font_color, family="Plus Jakarta Sans"),
            margin=dict(t=20, b=20, l=20, r=20),
            height=300,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_types, use_container_width=True)
    else:
        render_empty_state("No Study Sessions Logged", "Record focused study sessions below to inspect your time distribution across study activities.", "⏱️")

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Row 5: Study Hours by Course / Subject (if sessions exist)
# -----------------------------------------------------------------------------
if sessions:
    st.markdown("#### 📖 Study Time Investment by Subject")
    df_sess = pd.DataFrame(sessions)
    subj_dur = df_sess.groupby('subject')['duration_minutes'].sum().reset_index()
    subj_dur['hours'] = (subj_dur['duration_minutes'] / 60).round(1)
    subj_dur = subj_dur.sort_values('hours', ascending=False)

    fig_subj_hours = px.bar(
        subj_dur,
        x='subject',
        y='hours',
        text='hours',
        color='subject',
        labels={'subject': 'Subject', 'hours': 'Total Hours'},
        color_discrete_sequence=px.colors.qualitative.Plotly
    )
    fig_subj_hours.update_layout(
        paper_bgcolor=plot_bg,
        plot_bgcolor=plot_bg,
        font=dict(color=font_color, family="Plus Jakarta Sans"),
        margin=dict(t=20, b=20, l=20, r=20),
        height=280,
        showlegend=False,
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=grid_color, title="Hours Logged")
    )
    st.plotly_chart(fig_subj_hours, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Study Session Tracking & History Log
# -----------------------------------------------------------------------------
st.markdown("### ⏱️ Study Session Tracking & History")

with st.expander("➕ Log a Completed Study Session"):
    all_subjs = get_distinct_subjects()
    sess_subjs = sorted(list(set(["Computer Science", "Biology", "Psychology", "Mathematics", "Physics", "Chemistry", "Economics", "Literature", "General Study"] + all_subjs)))
    sess_subjs_opts = sess_subjs + ["+ Custom Subject"]

    with st.form("log_study_session_form"):
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            sess_topic = st.text_input("Topic / Focus Area", placeholder="e.g. Chapter 4 Cellular Respiration review")
        with col_s2:
            sess_chosen_subj = st.selectbox("Subject", options=sess_subjs_opts, index=0)

        custom_sess_subj = ""
        if sess_chosen_subj == "+ Custom Subject":
            custom_sess_subj = st.text_input("Enter Subject Name", placeholder="e.g. Organic Chemistry")

        col_s3, col_s4 = st.columns(2)
        with col_s3:
            sess_type = st.selectbox(
                "Activity Type",
                options=["Reading", "Quiz Review", "Flashcards", "Problem Solving", "Lecture Review", "Writing", "Project Work"],
                index=0
            )
        with col_s4:
            sess_mins = st.number_input("Duration (minutes)", min_value=5, max_value=360, value=30, step=5)

        sess_notes = st.text_area("Key Takeaways / Reflection (Optional)", placeholder="Summarize what you accomplished during this session.", height=80)

        if st.form_submit_button("Record Study Session", type="primary"):
            final_sub = custom_sess_subj.strip() if (sess_chosen_subj == "+ Custom Subject" and custom_sess_subj.strip()) else sess_chosen_subj
            if final_sub == "+ Custom Subject":
                final_sub = "General Study"

            log_study_session(
                subject=final_sub,
                topic=sess_topic.strip(),
                duration_minutes=int(sess_mins),
                session_type=sess_type,
                notes=sess_notes.strip()
            )
            st.success("Study session logged successfully!")
            st.rerun()

# Display Session History
if sessions:
    st.markdown(f"##### Recent Session History ({len(sessions)} records)")
    for s in sessions[:15]:
        s_hours = round(s['duration_minutes'] / 60, 2)
        with st.container():
            st.markdown(
                f"""
                <div class="sync-card" style="padding: 12px 18px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>{s.get('topic') or s.get('subject')}</strong> &nbsp;
                            <span style="font-size: 13px; color: var(--accent-primary); font-weight: 600;">{s.get('subject')}</span>
                            <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                                {s.get('created_at')} • <strong>{s.get('duration_minutes')} mins</strong> ({s_hours} hrs)
                                {f' • <em>{s.get("notes")}</em>' if s.get("notes") else ''}
                            </div>
                        </div>
                        <div>
                            <span class="badge badge-info">{s.get('session_type', 'Study')}</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
else:
    render_empty_state("No Study Sessions in Range", "Log your study sessions using the form above to track focused study hours and habits.", "⏱️")
