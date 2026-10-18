"""
StudySync AI - Page 4: Quiz Generator
Generates practice multiple-choice questions (MCQs) from study material
with distractors, explanations, interactive test modes (Step-by-Step and Multi-Question),
duplicate submission prevention, score calculation, and persistent attempt history in SQLite.
"""

import streamlit as st
import json
import time
from typing import Dict, Any, List

st.set_page_config(page_title="Quiz Generator | StudySync AI", page_icon="🎯", layout="wide")

from utils.database import (
    init_db,
    save_quiz,
    get_all_quizzes,
    get_quiz_by_id,
    delete_quiz,
    save_quiz_attempt,
    get_all_quiz_attempts,
    delete_quiz_attempt,
    get_quiz_stats,
    get_all_notes
)
from utils.quiz_generator import generate_quiz_from_text
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
    title="Practice Quiz Generator",
    subtitle="Formulate realistic multiple-choice practice questions from lecture notes or textbook passages with intelligent distractors and explanations.",
    badge_text="MCQ Generator",
    badge_type="primary"
)

st.info(
    "💡 **Rule-Based MCQ Engine:** Practice questions are formulated using transparent NLP algorithms "
    "(Part-of-Speech tagging, definitional syntactic patterns, and WordNet ontology). "
    "Questions and distractors are verified directly against your source material, with exact sentence citations and zero generative hallucinations.",
    icon="ℹ️"
)

# Handle preset text passed from other pages (e.g. Smart Notes)
preset_text = st.session_state.pop("active_text_for_quiz", "")
preset_title = st.session_state.pop("active_note_title", "")
preset_subj = st.session_state.pop("active_subject", "General Study")
preset_note_id = st.session_state.pop("active_note_id", None)
if preset_note_id:
    st.session_state["quiz_loaded_note_id"] = preset_note_id

tab_gen, tab_saved, tab_history = st.tabs(["🎯 Generate & Take Quiz", "📚 Saved Quizzes", "📈 Attempt History"])

# =========================================================================
# TAB 1: GENERATE & TAKE QUIZ
# =========================================================================
with tab_gen:
    # If no active quiz is currently being taken, show generation form
    st.markdown("### 📝 Quiz Setup")
    
    saved_notes = get_all_notes()
    if saved_notes:
        with st.expander("📥 Or select an existing note from your StudySync Library"):
            note_dict = {f"{n['title']} ({n['subject']})": n for n in saved_notes}
            selected_note_key = st.selectbox(
                "Choose Note to Load",
                options=["-- Select Note --"] + list(note_dict.keys()),
                key="quiz_note_selector"
            )
            if selected_note_key != "-- Select Note --":
                chosen_n = note_dict[selected_note_key]
                preset_text = chosen_n['content']
                preset_title = chosen_n['title']
                preset_subj = chosen_n['subject']
                st.session_state["quiz_loaded_note_id"] = chosen_n['id']

    col_q1, col_q2 = st.columns([2, 1])
    with col_q1:
        quiz_title_in = st.text_input(
            "Quiz Title",
            value=f"{preset_title} Practice Quiz" if preset_title else "",
            placeholder="e.g. Deep Learning & Neural Networks Quiz 1",
            key="quiz_title_input"
        )
    with col_q2:
        subject_options = [
            "Computer Science", "Biology", "Psychology", "Mathematics",
            "Physics", "Chemistry", "Economics", "Literature", "General Studies"
        ]
        subj_idx = subject_options.index(preset_subj) if preset_subj in subject_options else 0
        quiz_subj_in = st.selectbox("Subject Area", options=subject_options, index=subj_idx, key="quiz_subject_select")

    study_text = st.text_area(
        "Study Material / Notes for Question Formulation",
        value=preset_text,
        placeholder="Paste your study notes here (minimum 35-40 words required for reliable question formulation)...",
        height=180,
        key="quiz_source_text"
    )

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        num_q_slider = st.slider("Target Number of Questions", min_value=2, max_value=8, value=4, key="quiz_num_q")
    with col_c2:
        diff_select = st.selectbox("Difficulty Level", options=["Easy", "Medium", "Hard"], index=1, key="quiz_diff")

    if st.button("🚀 Formulate Practice Questions", type="primary", use_container_width=True, key="formulate_quiz_btn"):
        if not study_text.strip():
            st.error("Please enter study text before generating a quiz.")
        elif len(study_text.strip().split()) < 35:
            st.warning("The provided study material is too short (less than 35 words). Please input at least a full paragraph with clear definitions.")
        else:
            with st.spinner("Analyzing semantic relationships and generating distractors..."):
                quiz_res = generate_quiz_from_text(study_text, num_questions=num_q_slider, difficulty=diff_select)

            if not quiz_res["success"]:
                st.error(quiz_res["error"])
            else:
                # Initialize active quiz session state
                st.session_state["active_quiz"] = {
                    "title": quiz_title_in.strip() or "StudySync Practice Quiz",
                    "subject": quiz_subj_in,
                    "questions": quiz_res["questions"],
                    "note_id": st.session_state.get("quiz_loaded_note_id"),
                    "source_note_title": preset_title if st.session_state.get("quiz_loaded_note_id") else None,
                    "start_time": time.time(),
                    "submitted": False,
                    "user_answers": {},  # Dict of question id (str) -> selected option letter ('A', 'B', ...)
                    "grade_results": None,
                    "saved_id": None,
                    "current_q_idx": 0,
                    "display_mode": "All Questions"
                }
                st.success(f"Formulated {quiz_res['total_questions']} multiple-choice questions successfully!")
                st.rerun()

    # ---------------------------------------------------------------------
    # ACTIVE QUIZ INTERFACE
    # ---------------------------------------------------------------------
    if "active_quiz" in st.session_state:
        cur_quiz = st.session_state["active_quiz"]
        if "user_answers" not in cur_quiz or not isinstance(cur_quiz["user_answers"], dict):
            cur_quiz["user_answers"] = {}
        if not cur_quiz.get("start_time"):
            cur_quiz["start_time"] = time.time()
        if "display_mode" not in cur_quiz:
            cur_quiz["display_mode"] = "All Questions"
        if "current_q_idx" not in cur_quiz:
            cur_quiz["current_q_idx"] = 0

        questions = cur_quiz["questions"]
        total_q = len(questions)

        st.markdown("<br><hr style='border:0; border-top: 1px solid var(--border-subtle); margin: 24px 0;'>", unsafe_allow_html=True)
        
        # Header row: Title + Actions
        col_hdr1, col_hdr2 = st.columns([3, 1])
        with col_hdr1:
            st.markdown(f"### 📝 {cur_quiz['title']}")
            src_note_str = f" • 📌 *Source Note: {cur_quiz['source_note_title']}*" if cur_quiz.get("source_note_title") else ""
            st.caption(f"Subject: **{cur_quiz['subject']}** • **{total_q}** Multiple Choice Questions{src_note_str}")
        with col_hdr2:
            if st.button("✨ Reset / New Quiz", key="reset_active_quiz_btn", help="Discard active quiz and start over"):
                st.session_state.pop("active_quiz", None)
                st.rerun()

        # If already submitted, display the full Results & Review interface
        if cur_quiz.get("submitted") and cur_quiz.get("grade_results"):
            gr = cur_quiz["grade_results"]
            st.markdown("### 🏆 Quiz Results Summary")

            # Top performance metrics
            c_score1, c_score2, c_score3, c_score4 = st.columns(4)
            with c_score1:
                render_metric_card("Your Score", f"{gr['score']} / {gr['total']}", f"{gr['percentage']}% Accuracy")
            with c_score2:
                render_metric_card("Correct Answers", f"{gr['score']}", "Questions mastered")
            with c_score3:
                incorrect_count = gr['total'] - gr['score']
                render_metric_card("Incorrect Answers", f"{incorrect_count}", "Need review")
            with c_score4:
                render_metric_card("Time Taken", f"{gr['time_taken']}s", "Attempt duration")

            st.markdown("<br>", unsafe_allow_html=True)

            # Performance banner
            if gr['percentage'] >= 80:
                st.success(f"🌟 **Mastered!** Outstanding comprehension of the material ({gr['percentage']}%).", icon="🎉")
            elif gr['percentage'] >= 60:
                st.info(f"👍 **Good Job!** Solid foundation ({gr['percentage']}%), review the missed concepts below.", icon="📖")
            else:
                st.warning(f"✍️ **Needs Practice:** Score {gr['percentage']}%. Review the explanations below to strengthen key definitions.", icon="💡")

            st.markdown("#### 🔍 Detailed Question Review")

            for q in questions:
                q_id = str(q["id"])
                fb = gr["feedback"].get(q_id, {"is_correct": False, "user_choice": "Unanswered", "correct_option": q["correct_option"], "explanation": q["explanation"]})
                is_corr = fb["is_correct"]
                status_icon = "✅ Correct" if is_corr else "❌ Incorrect"
                color_border = "#10b981" if is_corr else "#f43f5e"
                badge_class = "badge-success" if is_corr else "badge-danger"

                st.markdown(
                    f"""
                    <div class="sync-card" style="border-left: 4px solid {color_border}; margin-bottom: 14px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <strong>Question {q['id']}</strong>
                            <span class="badge {badge_class}">{status_icon}</span>
                        </div>
                        <p style="font-size: 15px; font-weight: 500; color: var(--text-primary); margin: 0 0 10px 0;">{q['question']}</p>
                        <div style="margin-bottom: 10px; font-size: 14px;">
                            <strong>Your Answer:</strong> Option {fb['user_choice']} &nbsp;|&nbsp; 
                            <strong>Correct Answer:</strong> Option {fb['correct_option']}
                        </div>
                        <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); padding: 10px 14px; border-radius: 8px; font-size: 13px; color: var(--text-secondary);">
                            💡 {fb['explanation']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # Actions after quiz
            c_act1, c_act2 = st.columns([1, 1])
            with c_act1:
                if st.button("🔄 Retake this Quiz", type="primary", use_container_width=True, key="retake_quiz_btn"):
                    cur_quiz["submitted"] = False
                    cur_quiz["user_answers"] = {}
                    cur_quiz["grade_results"] = None
                    cur_quiz["start_time"] = time.time()
                    cur_quiz["current_q_idx"] = 0
                    st.rerun()

            with c_act2:
                if not cur_quiz.get("saved_id"):
                    if st.button("💾 Save Quiz Template to Library", type="secondary", use_container_width=True, key="save_quiz_template_btn"):
                        saved_q_id = save_quiz(
                            title=cur_quiz["title"],
                            subject=cur_quiz["subject"],
                            questions=cur_quiz["questions"],
                            note_id=cur_quiz.get("note_id")
                        )
                        cur_quiz["saved_id"] = saved_q_id
                        st.success(f"Quiz '{cur_quiz['title']}' saved to your library!")
                else:
                    st.caption("✅ Saved to Quiz Library")

        # Active Quiz Taking Mode (Not yet submitted)
        else:
            # Display Mode Selector (Requirement 4: Display one question at a time or multi-question layout)
            col_mode, col_prog = st.columns([1, 1])
            with col_mode:
                chosen_mode = st.radio(
                    "Layout Mode",
                    options=["📋 All Questions at Once", "⚡ One Question at a Time"],
                    index=0 if cur_quiz.get("display_mode") == "All Questions" else 1,
                    horizontal=True,
                    key="quiz_layout_mode_radio"
                )
                cur_quiz["display_mode"] = "All Questions" if "All" in chosen_mode else "Single Question"

            with col_prog:
                answered_count = len([q for q in questions if str(q["id"]) in cur_quiz["user_answers"]])
                st.caption(f"Progress: **{answered_count}** of **{total_q}** questions answered")
                st.progress(answered_count / total_q if total_q > 0 else 0.0)

            st.markdown("<br>", unsafe_allow_html=True)

            # --- MODE A: ONE QUESTION AT A TIME ---
            if cur_quiz["display_mode"] == "Single Question":
                cur_idx = cur_quiz.get("current_q_idx", 0)
                cur_idx = max(0, min(cur_idx, total_q - 1))
                q = questions[cur_idx]
                q_id = str(q["id"])

                # Question stepper pill indicators
                pill_cols = st.columns(total_q)
                for idx, col in enumerate(pill_cols):
                    p_id = str(questions[idx]["id"])
                    is_ans = p_id in cur_quiz["user_answers"]
                    is_cur = (idx == cur_idx)
                    label = f"Q{idx + 1}{' ✓' if is_ans else ''}"
                    btn_type = "primary" if is_cur else "secondary"
                    with col:
                        if st.button(label, key=f"step_pill_{idx}", type=btn_type, use_container_width=True):
                            cur_quiz["current_q_idx"] = idx
                            st.rerun()

                st.markdown("<br>", unsafe_allow_html=True)

                # Card for current question
                st.markdown(
                    f"""
                    <div class="sync-card" style="margin-bottom: 16px;">
                        <span class="badge badge-primary">Question {cur_idx + 1} of {total_q}</span>
                        <h4 style="margin: 10px 0 16px 0; color: var(--text-primary);">{q['question']}</h4>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Find pre-selected option index
                current_selected = cur_quiz["user_answers"].get(q_id, None)
                selected_opt_idx = None
                if current_selected:
                    for i, opt in enumerate(q["options"]):
                        if opt.startswith(current_selected + ")"):
                            selected_opt_idx = i
                            break

                chosen_option = st.radio(
                    f"Select your answer for Question {cur_idx + 1}:",
                    options=q["options"],
                    index=selected_opt_idx,
                    key=f"single_q_radio_{q_id}",
                    label_visibility="collapsed"
                )

                if chosen_option:
                    letter = chosen_option.split(")")[0].strip()
                    cur_quiz["user_answers"][q_id] = letter

                # Stepper controls
                st.markdown("<br>", unsafe_allow_html=True)
                c_prev, c_submit_btn, c_next = st.columns([1, 2, 1])

                with c_prev:
                    if st.button("⬅️ Previous", disabled=(cur_idx == 0), use_container_width=True, key="step_prev_btn"):
                        cur_quiz["current_q_idx"] = cur_idx - 1
                        st.rerun()

                with c_next:
                    if st.button("Next ➡️", disabled=(cur_idx >= total_q - 1), use_container_width=True, key="step_next_btn"):
                        cur_quiz["current_q_idx"] = cur_idx + 1
                        st.rerun()

                with c_submit_btn:
                    # Submit button
                    if st.button("🏁 Submit Quiz & Grade Answers", type="primary", use_container_width=True, key="submit_single_mode_btn"):
                        # Duplicate submission check (Requirement 7)
                        if not cur_quiz.get("submitted"):
                            correct_count = 0
                            feedback = {}
                            for q_item in questions:
                                q_item_id = str(q_item["id"])
                                user_choice = cur_quiz["user_answers"].get(q_item_id, "Unanswered")
                                is_correct = (user_choice == q_item["correct_option"])
                                if is_correct:
                                    correct_count += 1
                                feedback[q_item_id] = {
                                    "user_choice": user_choice,
                                    "correct_option": q_item["correct_option"],
                                    "correct_text": q_item.get("correct_text", ""),
                                    "is_correct": is_correct,
                                    "explanation": q_item["explanation"]
                                }

                            time_taken = max(1, int(time.time() - cur_quiz.get("start_time", time.time())))
                            pct = round((correct_count / total_q) * 100, 1) if total_q > 0 else 0.0

                            cur_quiz["submitted"] = True
                            cur_quiz["grade_results"] = {
                                "score": correct_count,
                                "total": total_q,
                                "percentage": pct,
                                "time_taken": time_taken,
                                "feedback": feedback
                            }

                            # Save to SQLite database
                            save_quiz_attempt(
                                quiz_id=cur_quiz.get("saved_id", 0),
                                quiz_title=cur_quiz["title"],
                                subject=cur_quiz["subject"],
                                score=correct_count,
                                total_questions=total_q,
                                time_taken_sec=time_taken,
                                user_answers=cur_quiz["user_answers"]
                            )
                            st.rerun()

            # --- MODE B: ALL QUESTIONS AT ONCE ---
            else:
                for q in questions:
                    q_id = str(q["id"])
                    st.markdown(
                        f"""
                        <div class="sync-card" style="margin-bottom: 14px;">
                            <strong>Question {q['id']}:</strong>
                            <p style="font-size: 15px; margin: 6px 0 10px 0; color: var(--text-primary);">{q['question']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    current_selected = cur_quiz["user_answers"].get(q_id, None)
                    selected_opt_idx = None
                    if current_selected:
                        for i, opt in enumerate(q["options"]):
                            if opt.startswith(current_selected + ")"):
                                selected_opt_idx = i
                                break

                    chosen_option = st.radio(
                        f"Answer for Q{q['id']}:",
                        options=q["options"],
                        index=selected_opt_idx,
                        key=f"multi_q_radio_{q_id}",
                        label_visibility="collapsed"
                    )

                    if chosen_option:
                        letter = chosen_option.split(")")[0].strip()
                        cur_quiz["user_answers"][q_id] = letter

                    st.markdown("<hr style='border:0; border-top: 1px dashed var(--border-subtle); margin: 12px 0;'>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                col_sub1, _ = st.columns([1, 1])
                with col_sub1:
                    if st.button("🏁 Submit Quiz & View Score", type="primary", use_container_width=True, key="submit_all_mode_btn"):
                        # Duplicate submission check (Requirement 7)
                        if not cur_quiz.get("submitted"):
                            correct_count = 0
                            feedback = {}
                            for q_item in questions:
                                q_item_id = str(q_item["id"])
                                user_choice = cur_quiz["user_answers"].get(q_item_id, "Unanswered")
                                is_correct = (user_choice == q_item["correct_option"])
                                if is_correct:
                                    correct_count += 1
                                feedback[q_item_id] = {
                                    "user_choice": user_choice,
                                    "correct_option": q_item["correct_option"],
                                    "correct_text": q_item.get("correct_text", ""),
                                    "is_correct": is_correct,
                                    "explanation": q_item["explanation"]
                                }

                            time_taken = max(1, int(time.time() - cur_quiz.get("start_time", time.time())))
                            pct = round((correct_count / total_q) * 100, 1) if total_q > 0 else 0.0

                            cur_quiz["submitted"] = True
                            cur_quiz["grade_results"] = {
                                "score": correct_count,
                                "total": total_q,
                                "percentage": pct,
                                "time_taken": time_taken,
                                "feedback": feedback
                            }

                            save_quiz_attempt(
                                quiz_id=cur_quiz.get("saved_id", 0),
                                quiz_title=cur_quiz["title"],
                                subject=cur_quiz["subject"],
                                score=correct_count,
                                total_questions=total_q,
                                time_taken_sec=time_taken,
                                user_answers=cur_quiz["user_answers"]
                            )
                            st.rerun()

# =========================================================================
# TAB 2: SAVED QUIZZES
# =========================================================================
with tab_saved:
    st.markdown("### 📚 Saved Quiz Templates")
    all_quizzes = get_all_quizzes()

    if all_quizzes:
        st.caption(f"You have **{len(all_quizzes)}** saved quizzes in your library.")
        for qz in all_quizzes:
            with st.expander(f"🎯 {qz['title']} — {qz['subject']} ({qz['total_questions']} Questions)"):
                st.markdown(f"**Subject Area:** `{qz['subject']}` | **Created:** `{qz['created_at'][:10]}`")
                st.markdown(f"**Total Questions:** {qz['total_questions']}")

                col_btn_load, col_btn_del = st.columns([1, 1])
                with col_btn_load:
                    if st.button("▶️ Load and Take this Quiz", key=f"take_saved_quiz_{qz['id']}", use_container_width=True):
                        st.session_state["active_quiz"] = {
                            "saved_id": qz["id"],
                            "title": qz["title"],
                            "subject": qz["subject"],
                            "questions": qz["questions"],
                            "start_time": time.time(),
                            "submitted": False,
                            "user_answers": {},
                            "grade_results": None,
                            "current_q_idx": 0,
                            "display_mode": "All Questions"
                        }
                        st.success(f"Loaded '{qz['title']}'! Switch to the '🎯 Generate & Take Quiz' tab to take it.")
                        st.rerun()

                with col_btn_del:
                    if st.button("🗑️ Delete Quiz", key=f"del_saved_quiz_{qz['id']}", use_container_width=True):
                        delete_quiz(qz["id"])
                        st.success("Quiz deleted from library.")
                        st.rerun()
    else:
        render_empty_state("No Saved Quizzes", "Generate and save a quiz in Tab 1 to build a practice library.", "🎯")

# =========================================================================
# TAB 3: ATTEMPT HISTORY & PERFORMANCE
# =========================================================================
with tab_history:
    st.markdown("### 📈 Quiz Attempt History & Analytics")
    stats = get_quiz_stats()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card("Total Attempts", stats["attempts_count"], "Tests recorded")
    with m2:
        render_metric_card("Average Score", f"{stats['avg_score']}%", "Overall performance")
    with m3:
        render_metric_card("Highest Score", f"{stats['highest_score']}%", "Best attempt")
    with m4:
        render_metric_card("Lowest Score", f"{stats['lowest_score']}%", "Baseline attempt")

    st.markdown("<br>", unsafe_allow_html=True)
    attempts = get_all_quiz_attempts()

    if attempts:
        import pandas as pd
        df_att = pd.DataFrame(attempts)
        df_display = df_att[['id', 'quiz_title', 'subject', 'score', 'total_questions', 'percentage', 'time_taken_sec', 'completed_at']].copy()
        df_display.columns = ['ID', 'Quiz Title', 'Subject', 'Score', 'Total Qs', 'Score %', 'Time (s)', 'Completed At']
        
        st.dataframe(df_display, use_container_width=True)

        with st.expander("🗑️ Manage Attempt History"):
            del_id = st.number_input("Attempt ID to Delete", min_value=1, step=1, key="del_attempt_id_input")
            if st.button("Delete Attempt Record", type="secondary", key="del_attempt_btn"):
                if delete_quiz_attempt(int(del_id)):
                    st.success(f"Attempt #{del_id} deleted successfully.")
                    st.rerun()
                else:
                    st.error(f"Attempt #{del_id} not found.")
    else:
        render_empty_state("No Quiz History", "Complete your first quiz to track your mastery scores over time.", "📈")

