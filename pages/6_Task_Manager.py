"""
StudySync AI - Page 6: Task Manager
Academic task organizer for college students.
Manage deadlines, course priorities, completion status, overdue tracking, and study commitments.
"""

import streamlit as st
import datetime
from typing import Optional

st.set_page_config(page_title="Task Manager | StudySync AI", page_icon="✅", layout="wide")

from utils.database import (
    init_db,
    create_task,
    get_all_tasks,
    update_task_status,
    complete_task,
    update_task,
    delete_task,
    get_task_stats,
    get_upcoming_tasks,
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
apply_theme()
render_sidebar_header()

render_page_header(
    title="Academic Task Manager",
    subtitle="Keep track of coursework, project milestones, exam preparation, and homework deadlines.",
    badge_text="Productivity",
    badge_type="primary"
)

today = datetime.date.today()
today_str = today.strftime("%Y-%m-%d")


def parse_date_safe(date_str: Optional[str]) -> datetime.date:
    """Safely parses a YYYY-MM-DD date string to a datetime.date object."""
    if not date_str:
        return today
    try:
        return datetime.datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except Exception:
        return today


# Statistics Row
stats = get_task_stats()
t1, t2, t3, t4, t5 = st.columns(5)
with t1:
    render_metric_card("Total Tasks", stats["total"], "All assignments")
with t2:
    render_metric_card("Completed", stats["completed"], f"{stats['completion_rate']}% Completed")
with t3:
    render_metric_card("In Progress", stats["in_progress"], "Currently active")
with t4:
    overdue_label = f"⚠️ {stats['overdue']} Overdue" if stats["overdue"] > 0 else "0 Overdue"
    render_metric_card("Overdue", stats["overdue"], overdue_label)
with t5:
    render_metric_card("Due Soon", stats["due_soon"], "Next 7 days")

st.markdown("<br>", unsafe_allow_html=True)

# Overdue Alert Banner if tasks are overdue
if stats["overdue"] > 0:
    st.markdown(
        f"""
        <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-left: 5px solid #ef4444; border-radius: 8px; padding: 12px 18px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 22px;">⚠️</span>
                <div>
                    <strong style="color: #ef4444; font-size: 14px;">Attention: You have {stats['overdue']} overdue task(s)!</strong>
                    <div style="font-size: 13px; color: var(--text-secondary); margin-top: 2px;">
                        Filter by <strong>Overdue</strong> below to reschedule or mark them complete.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Section: Upcoming Deadlines (Next 7 Days)
upcoming_tasks = get_upcoming_tasks(days=7)
with st.expander(f"📅 Upcoming Deadlines (Next 7 Days) — {len(upcoming_tasks)} tasks approaching", expanded=bool(upcoming_tasks)):
    if upcoming_tasks:
        for ut in upcoming_tasks:
            ut_date = parse_date_safe(ut.get('deadline'))
            days_diff = (ut_date - today).days
            if days_diff == 0:
                due_desc = "🚨 Due Today"
                due_badge = "badge-danger"
            elif days_diff == 1:
                due_desc = "⏳ Due Tomorrow"
                due_badge = "badge-warning"
            else:
                due_desc = f"📅 Due in {days_diff} days ({ut['deadline']})"
                due_badge = "badge-info"

            prio_badge = "badge-danger" if ut['priority'] == 'High' else "badge-warning" if ut['priority'] == 'Medium' else "badge-info"

            col_u1, col_u2 = st.columns([4, 1])
            with col_u1:
                st.markdown(
                    f"""
                    <div style="padding: 8px 12px; margin-bottom: 6px; background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>{ut['title']}</strong> &nbsp;
                            <span style="font-size: 12px; color: var(--accent-primary); font-weight: 600;">{ut['subject']}</span>
                            <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">Est: {ut['estimated_hours']} hrs • Status: {ut['status']}</div>
                        </div>
                        <div style="display: flex; gap: 6px; align-items: center;">
                            <span class="badge {due_badge}">{due_desc}</span>
                            <span class="badge {prio_badge}">{ut['priority']}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with col_u2:
                if st.button("✅ Complete", key=f"quick_comp_{ut['id']}", use_container_width=True):
                    complete_task(ut['id'])
                    st.success(f"Completed '{ut['title']}'!")
                    st.rerun()
    else:
        st.info("🎉 No pending tasks due within the next 7 days. You're well ahead of schedule!")

st.markdown("<br>", unsafe_allow_html=True)

# Add Task Section
with st.expander("➕ Add New Academic Task / Assignment", expanded=False):
    all_subjects = get_distinct_subjects()
    default_subjects = ["Computer Science", "Biology", "Psychology", "Mathematics", "Physics", "Chemistry", "Economics", "Literature", "General Study"]
    combined_subjects = sorted(list(set(default_subjects + all_subjects)))
    subject_options = combined_subjects + ["+ Custom Subject"]

    with st.form("create_task_form"):
        col_t1, col_t2 = st.columns([2, 1])
        with col_t1:
            task_title = st.text_input("Task Title *", placeholder="e.g. Prepare Chapter 4 summary for Biology")
        with col_t2:
            chosen_subj = st.selectbox("Course / Subject", options=subject_options, index=0)

        custom_subj = ""
        if chosen_subj == "+ Custom Subject":
            custom_subj = st.text_input("Enter Custom Subject Name", placeholder="e.g. Organic Chemistry II")

        task_desc = st.text_area("Description / Instructions", placeholder="e.g. Read sections 4.1 to 4.4 and solve practice problem set 2.", height=90)

        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1:
            task_prio = st.selectbox("Priority Level", options=["High", "Medium", "Low"], index=1)
        with col_p2:
            task_status = st.selectbox("Initial Status", options=["Pending", "In Progress", "Completed"], index=0)
        with col_p3:
            task_deadline = st.date_input("Due Date", value=today + datetime.timedelta(days=3))
        with col_p4:
            task_hours = st.number_input("Estimated Hours", min_value=0.5, max_value=60.0, value=2.0, step=0.5)

        col_submit, _ = st.columns([1, 3])
        with col_submit:
            add_clicked = st.form_submit_button("Create Task", type="primary", use_container_width=True)

        if add_clicked:
            if not task_title.strip():
                st.error("Please enter a task title.")
            else:
                final_subj = custom_subj.strip() if (chosen_subj == "+ Custom Subject" and custom_subj.strip()) else chosen_subj
                if final_subj == "+ Custom Subject":
                    final_subj = "General Study"

                create_task(
                    title=task_title.strip(),
                    subject=final_subj,
                    description=task_desc.strip(),
                    priority=task_prio,
                    deadline=task_deadline.strftime("%Y-%m-%d"),
                    estimated_hours=float(task_hours),
                    status=task_status
                )
                st.success(f"Task '{task_title}' created successfully!")
                st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# Filter & Sort Controls
st.markdown("### 📋 Task Inventory")
f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([1.2, 1, 1, 1.2, 1.2])

with f_col1:
    status_filter = st.selectbox(
        "Status",
        options=["All", "Pending", "In Progress", "Completed", "Overdue"],
        index=0,
        help="Filter tasks by progress state, including Overdue tasks."
    )

with f_col2:
    prio_filter = st.selectbox(
        "Priority",
        options=["All", "High", "Medium", "Low"],
        index=0
    )

with f_col3:
    all_current_tasks = get_all_tasks()
    task_subjects = ["All"] + sorted(list(set(t["subject"] for t in all_current_tasks if t.get("subject"))))
    subj_filter = st.selectbox("Subject", options=task_subjects, index=0)

with f_col4:
    sort_option = st.selectbox(
        "Sort By",
        options=[
            "Deadline: Earliest First",
            "Deadline: Latest First",
            "Priority: High to Low",
            "Priority: Low to High",
            "Title (A-Z)",
            "Recently Created"
        ],
        index=0
    )

with f_col5:
    search_query = st.text_input("🔍 Search", placeholder="Keywords...", value="")

# Map sort choice to database query parameter
sort_map = {
    "Deadline: Earliest First": "deadline_asc",
    "Deadline: Latest First": "deadline_desc",
    "Priority: High to Low": "priority_high_first",
    "Priority: Low to High": "priority_low_first",
    "Title (A-Z)": "title_asc",
    "Recently Created": "recently_created"
}
sort_key = sort_map.get(sort_option, "deadline_asc")

filtered_tasks = get_all_tasks(
    status_filter=status_filter,
    priority_filter=prio_filter,
    subject_filter=subj_filter,
    sort_by=sort_key,
    search_query=search_query
)

if filtered_tasks:
    st.caption(f"Showing **{len(filtered_tasks)}** task(s) matching criteria")
    for t in filtered_tasks:
        # Check overdue condition
        is_overdue = (
            t['status'] != 'Completed' and
            bool(t.get('deadline')) and
            t['deadline'] < today_str
        )
        
        # Determine badges
        prio_color = "danger" if t['priority'] == 'High' else "warning" if t['priority'] == 'Medium' else "info"
        status_color = "success" if t['status'] == 'Completed' else "primary" if t['status'] == 'In Progress' else "warning"

        # Overdue badge text
        overdue_badge_html = ""
        card_border_style = "border-left: 4px solid var(--accent-primary);"
        if is_overdue:
            overdue_days = (today - parse_date_safe(t['deadline'])).days
            overdue_badge_html = f'<span class="badge badge-danger">⚠️ OVERDUE ({overdue_days}d)</span>'
            card_border_style = "border-left: 4px solid #ef4444; background: rgba(239, 68, 68, 0.04);"
        elif t['status'] == 'Completed':
            card_border_style = "border-left: 4px solid #10b981; opacity: 0.85;"

        with st.container():
            st.markdown(
                f"""
                <div class="sync-card" style="padding: 16px 20px; margin-bottom: 12px; {card_border_style}">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
                        <div style="flex: 1;">
                            <div style="font-size: 16px; font-weight: 700; color: var(--text-primary);">
                                {'<s>' + t['title'] + '</s>' if t['status'] == 'Completed' else t['title']}
                            </div>
                            <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">
                                <strong style="color: var(--accent-primary);">{t['subject']}</strong> • 
                                Due: <strong>{t['deadline'] or 'No deadline'}</strong> • 
                                Est: <strong>{t['estimated_hours']} hrs</strong>
                                {f' • <span style="color: #10b981;">Completed: {t["completed_at"]}</span>' if t.get("completed_at") else ''}
                            </div>
                            {f'<div style="font-size: 13px; color: var(--text-secondary); margin-top: 6px;">{t["description"]}</div>' if t.get("description") else ''}
                        </div>
                        <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap; justify-content: flex-end;">
                            {overdue_badge_html}
                            <span class="badge badge-{prio_color}">{t['priority']}</span>
                            <span class="badge badge-{status_color}">{t['status']}</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Quick status update and management actions
            c_act1, c_act2, c_act3, c_act4 = st.columns([1.1, 1.1, 1.1, 1.1])

            with c_act1:
                if t['status'] != 'Completed':
                    if st.button("✅ Mark Complete", key=f"comp_{t['id']}", use_container_width=True):
                        complete_task(t['id'])
                        st.success(f"Task '{t['title']}' completed!")
                        st.rerun()
                else:
                    if st.button("🔄 Reopen Task", key=f"reopen_{t['id']}", use_container_width=True):
                        update_task_status(t['id'], 'Pending')
                        st.info(f"Task '{t['title']}' reopened as Pending.")
                        st.rerun()

            with c_act2:
                if t['status'] == 'Pending':
                    if st.button("▶️ Start Task", key=f"start_{t['id']}", use_container_width=True):
                        update_task_status(t['id'], 'In Progress')
                        st.rerun()
                elif t['status'] == 'In Progress':
                    if st.button("⏸️ Set Pending", key=f"pause_{t['id']}", use_container_width=True):
                        update_task_status(t['id'], 'Pending')
                        st.rerun()
                else:
                    st.button("Done", key=f"done_disabled_{t['id']}", disabled=True, use_container_width=True)

            with c_act3:
                with st.popover("✏️ Edit Task", use_container_width=True):
                    with st.form(f"edit_task_form_{t['id']}"):
                        e_title = st.text_input("Title", value=t['title'])
                        e_subj = st.text_input("Subject", value=t['subject'])
                        e_desc = st.text_area("Description", value=t.get('description') or "", height=80)
                        
                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            e_prio = st.selectbox(
                                "Priority",
                                options=["High", "Medium", "Low"],
                                index=["High", "Medium", "Low"].index(t['priority']) if t['priority'] in ["High", "Medium", "Low"] else 1
                            )
                        with col_e2:
                            e_status = st.selectbox(
                                "Status",
                                options=["Pending", "In Progress", "Completed"],
                                index=["Pending", "In Progress", "Completed"].index(t['status']) if t['status'] in ["Pending", "In Progress", "Completed"] else 0
                            )

                        col_e3, col_e4 = st.columns(2)
                        with col_e3:
                            current_dl = parse_date_safe(t.get('deadline'))
                            e_deadline = st.date_input("Due Date", value=current_dl)
                        with col_e4:
                            e_hours = st.number_input("Est. Hours", min_value=0.5, max_value=60.0, value=float(t.get('estimated_hours') or 1.0), step=0.5)

                        if st.form_submit_button("Save Changes", type="primary", use_container_width=True):
                            if not e_title.strip():
                                st.error("Title cannot be empty.")
                            else:
                                update_task(
                                    task_id=t['id'],
                                    title=e_title.strip(),
                                    subject=e_subj.strip(),
                                    description=e_desc.strip(),
                                    priority=e_prio,
                                    deadline=e_deadline.strftime("%Y-%m-%d"),
                                    status=e_status,
                                    estimated_hours=float(e_hours)
                                )
                                st.success("Task updated successfully.")
                                st.rerun()

            with c_act4:
                with st.popover("🗑️ Delete", use_container_width=True):
                    st.markdown(f"**Delete task?**")
                    st.markdown(f"*{t['title']}*")
                    st.caption("⚠️ This deletion is permanent and cannot be undone.")
                    if st.button("Confirm Delete", key=f"confirm_del_{t['id']}", type="primary", use_container_width=True):
                        delete_task(t['id'])
                        st.success("Task deleted.")
                        st.rerun()

            st.markdown("<hr style='border: 0; border-top: 1px dashed var(--border-color); margin: 6px 0 16px 0;'>", unsafe_allow_html=True)
else:
    if status_filter == 'Overdue':
        render_empty_state("No Overdue Tasks", "You have zero overdue assignments! Keep up the great pace.", "🎉")
    else:
        render_empty_state("No Tasks Found", "No academic tasks match your current filter criteria. Create a new task above or reset filters.", "✅")
