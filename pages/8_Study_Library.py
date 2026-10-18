"""
StudySync AI - Page 8: Central Study Library
Unified, searchable, filterable, and paginated repository for all academic assets:
notes, extractive summaries, flashcard decks, and practice quizzes.
Supports sorting by creation/update dates, opening full item details, deletion, and export.
"""

import streamlit as st
import json
import math
import time
from typing import Dict, Any, List

st.set_page_config(page_title="Study Library | StudySync AI", page_icon="📚", layout="wide")

from utils.database import (
    init_db,
    get_all_notes,
    delete_note,
    get_all_summaries,
    delete_summary,
    get_all_decks,
    get_flashcards_by_deck,
    delete_deck,
    get_all_quizzes,
    delete_quiz,
    get_distinct_subjects,
    get_unified_library_items
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
    title="Central Study Library",
    subtitle="Unified repository to search, filter, open, export, and manage your saved notes, extractive summaries, flashcard decks, and practice quizzes.",
    badge_text="Repository",
    badge_type="primary"
)

# =========================================================================
# FILTERS & CONTROLS BAR
# =========================================================================
st.markdown("### 🔍 Search & Filter Library")

c_search, c_type, c_subj, c_sort = st.columns([3, 2, 2, 2])

with c_search:
    search_term = st.text_input(
        "Search Keyword",
        placeholder="Search titles, text, tags, questions...",
        key="lib_search_term"
    )

with c_type:
    type_options = ["All Materials", "Saved Notes", "Extractive Summaries", "Flashcard Decks", "Practice Quizzes"]
    material_choice = st.selectbox("Material Type", options=type_options, key="lib_type_select")

with c_subj:
    db_subjects = get_distinct_subjects()
    subject_choices = ["All Subjects"] + db_subjects
    subject_choice = st.selectbox("Subject Area", options=subject_choices, key="lib_subj_select")

with c_sort:
    sort_options = ["Recently Updated", "Recently Created", "Title (A-Z)", "Title (Z-A)"]
    sort_choice = st.selectbox("Sort Order", options=sort_options, key="lib_sort_select")

sort_map = {
    "Recently Updated": "recent_updated",
    "Recently Created": "recent_created",
    "Title (A-Z)": "title_asc",
    "Title (Z-A)": "title_desc"
}

# Fetch aggregated items matching criteria
subj_filter_val = "All" if subject_choice == "All Subjects" else subject_choice
items = get_unified_library_items(
    search_query=search_term,
    material_type=material_choice,
    subject_filter=subj_filter_val,
    sort_by=sort_map[sort_choice]
)

# Counts for overview cards
total_notes_cnt = len(get_all_notes())
total_summs_cnt = len(get_all_summaries())
total_decks_cnt = len(get_all_decks())
total_quiz_cnt = len(get_all_quizzes())

m1, m2, m3, m4 = st.columns(4)
with m1:
    render_metric_card("Notes in Library", total_notes_cnt, "PDF & TXT uploads")
with m2:
    render_metric_card("AI Summaries", total_summs_cnt, "Extractive summaries")
with m3:
    render_metric_card("Flashcard Decks", total_decks_cnt, "Active recall decks")
with m4:
    render_metric_card("Practice Quizzes", total_quiz_cnt, "Formulated quizzes")

st.markdown("<br>", unsafe_allow_html=True)

# =========================================================================
# PAGINATION CONTROLS
# =========================================================================
ITEMS_PER_PAGE_OPTIONS = [5, 10, 20, 50]

if "library_page_num" not in st.session_state:
    st.session_state["library_page_num"] = 1

col_count, col_per_page = st.columns([3, 1])
with col_per_page:
    per_page = st.selectbox("Items per page", options=ITEMS_PER_PAGE_OPTIONS, index=1, key="lib_per_page")

total_items = len(items)
total_pages = max(1, math.ceil(total_items / per_page))

# Ensure current page is within valid range
if st.session_state["library_page_num"] > total_pages:
    st.session_state["library_page_num"] = total_pages
elif st.session_state["library_page_num"] < 1:
    st.session_state["library_page_num"] = 1

current_page = st.session_state["library_page_num"]
start_idx = (current_page - 1) * per_page
end_idx = min(start_idx + per_page, total_items)
paginated_items = items[start_idx:end_idx]

with col_count:
    if total_items > 0:
        st.markdown(f"Showing **{start_idx + 1} – {end_idx}** of **{total_items}** study material{'s' if total_items != 1 else ''}")
    else:
        st.caption("No matching study materials.")

# =========================================================================
# MATERIAL ITEMS FEED
# =========================================================================
if not paginated_items:
    if search_term or (subject_choice != "All Subjects") or (material_choice != "All Materials"):
        render_empty_state(
            "No Matching Study Materials Found",
            f"No items match your search for '{search_term or 'selected filters'}'. Try clearing search terms or subject filters.",
            "🔍"
        )
        if st.button("🔄 Clear All Filters", key="reset_filters_btn"):
            st.session_state["lib_search_term"] = ""
            st.session_state["lib_type_select"] = "All Materials"
            st.session_state["lib_subj_select"] = "All Subjects"
            st.session_state["library_page_num"] = 1
            st.rerun()
    else:
        render_empty_state(
            "Your Study Library is Empty",
            "Upload study documents in Smart Notes, generate summaries, or create flashcard decks to see them here.",
            "📚"
        )
else:
    for item in paginated_items:
        m_type = item["material_type"]
        item_id = item["id"]
        icon = item["icon"]
        type_lbl = item["type_label"]
        raw = item["raw_data"]

        # Date formatting
        c_date = item["created_at"][:16] if item["created_at"] else "N/A"
        u_date = item["updated_at"][:16] if item["updated_at"] else c_date

        expander_title = f"{icon} [{type_lbl}] {item['title']} — {item['subject']}"

        with st.expander(expander_title, expanded=False):
            # Header info bar
            src_note_info = ""
            if item.get("source_note_title"):
                src_note_info = f"&nbsp;|&nbsp; 📌 **Source Note:** *{item['source_note_title']}*"

            st.markdown(
                f"**Type:** `{type_lbl}` &nbsp;|&nbsp; "
                f"**Subject:** `{item['subject']}` &nbsp;|&nbsp; "
                f"**Created:** `{c_date}` &nbsp;|&nbsp; "
                f"**Modified:** `{u_date}`"
                f"{src_note_info}"
            )
            st.markdown("---")

            # -------------------------------------------------------------
            # ITEM TYPE SPECIFIC DETAIL RENDERING
            # -------------------------------------------------------------
            if m_type == "note":
                # Notes Details
                file_info = f"({raw['file_name']})" if raw.get('file_name') else ''
                st.markdown(f"**Source:** `{raw.get('source_type')}` {file_info} &nbsp;|&nbsp; **Word Count:** {raw.get('word_count', 0)} words &nbsp;|&nbsp; **Est. Reading Time:** ~{raw.get('reading_time_min', 0.0)} mins")
                if raw.get("tags"):
                    st.markdown(f"**Tags:** `{raw.get('tags')}`")
                st.markdown("#### Note Content")
                st.write(raw.get("content", ""))

                st.markdown("---")
                c1, c2, c3, c4, c_del = st.columns([1, 1, 1, 1, 1])
                with c1:
                    st.download_button(
                        label="📥 Export TXT",
                        data=raw.get("content", ""),
                        file_name=f"{item['title'].replace(' ', '_')}.txt",
                        mime="text/plain",
                        key=f"lib_dl_note_{item_id}",
                        use_container_width=True
                    )
                with c2:
                    if st.button("⚡ Summarize", key=f"lib_sum_note_{item_id}", use_container_width=True):
                        st.session_state["active_text_for_summary"] = raw.get("content", "")
                        st.session_state["active_note_id"] = item_id
                        st.session_state["active_note_title"] = item["title"]
                        st.switch_page("pages/3_AI_Summarizer.py")
                with c3:
                    if st.button("🎯 Make Quiz", key=f"lib_quiz_note_{item_id}", use_container_width=True):
                        st.session_state["active_text_for_quiz"] = raw.get("content", "")
                        st.session_state["active_note_id"] = item_id
                        st.session_state["active_note_title"] = item["title"]
                        st.session_state["active_subject"] = item["subject"]
                        st.switch_page("pages/4_Quiz_Generator.py")
                with c4:
                    if st.button("🗂️ Flashcards", key=f"lib_fc_note_{item_id}", use_container_width=True):
                        st.session_state["active_text_for_cards"] = raw.get("content", "")
                        st.session_state["active_note_id"] = item_id
                        st.session_state["active_note_title"] = item["title"]
                        st.session_state["active_subject"] = item["subject"]
                        st.switch_page("pages/5_Flashcards.py")
                with c_del:
                    del_k = f"del_confirm_note_{item_id}"
                    if not st.session_state.get(del_k, False):
                        if st.button("🗑️ Delete", key=f"lib_btn_del_note_{item_id}", use_container_width=True):
                            st.session_state[del_k] = True
                            st.rerun()
                    else:
                        st.warning("Delete note?")
                        cy, cn = st.columns(2)
                        with cy:
                            if st.button("Yes", key=f"lib_yes_note_{item_id}", type="primary"):
                                delete_note(item_id)
                                st.session_state.pop(del_k, None)
                                st.success("Note deleted.")
                                st.rerun()
                        with cn:
                            if st.button("No", key=f"lib_no_note_{item_id}"):
                                st.session_state.pop(del_k, None)
                                st.rerun()

            elif m_type == "summary":
                # Summary Details
                st.markdown(f"**Compression:** {raw.get('compression_ratio')}% reduced &nbsp;|&nbsp; **Algorithm:** `{raw.get('method')}`")
                st.markdown("#### Executive Summary")
                st.write(raw.get("summary_text", ""))

                if raw.get("key_points"):
                    st.markdown("#### Key Takeaways")
                    for pt in raw.get("key_points", []):
                        st.markdown(f"• {pt}")

                st.markdown("---")
                c_s1, c_s2, c_sdel = st.columns([1, 1, 1])
                with c_s1:
                    md_text = f"# {item['title']}\n\n{raw.get('summary_text', '')}\n\n## Key Takeaways\n" + "\n".join([f"- {p}" for p in raw.get('key_points', [])])
                    st.download_button(
                        label="📥 Download Markdown",
                        data=md_text,
                        file_name=f"{item['title'].replace(' ', '_')}.md",
                        mime="text/markdown",
                        key=f"lib_dl_sum_{item_id}",
                        use_container_width=True
                    )
                with c_s2:
                    if st.button("⚡ Re-summarize Original", key=f"lib_resum_{item_id}", use_container_width=True):
                        st.session_state["active_text_for_summary"] = raw.get("original_text", "")
                        st.session_state["active_note_id"] = raw.get("note_id")
                        st.session_state["active_note_title"] = item["title"]
                        st.switch_page("pages/3_AI_Summarizer.py")
                with c_sdel:
                    del_k = f"del_confirm_sum_{item_id}"
                    if not st.session_state.get(del_k, False):
                        if st.button("🗑️ Delete Summary", key=f"lib_del_sum_btn_{item_id}", use_container_width=True):
                            st.session_state[del_k] = True
                            st.rerun()
                    else:
                        st.warning("Delete summary?")
                        cy, cn = st.columns(2)
                        with cy:
                            if st.button("Yes", key=f"lib_yes_sum_{item_id}", type="primary"):
                                delete_summary(item_id)
                                st.session_state.pop(del_k, None)
                                st.success("Summary deleted.")
                                st.rerun()
                        with cn:
                            if st.button("No", key=f"lib_no_sum_{item_id}"):
                                st.session_state.pop(del_k, None)
                                st.rerun()

            elif m_type == "deck":
                # Flashcard Deck Details
                st.markdown(f"**Description:** {raw.get('description') or 'No description provided.'}")
                st.markdown(f"**Cards:** {raw.get('card_count', 0)} total &nbsp;|&nbsp; **Mastered:** {raw.get('mastered_count', 0)} cards")

                cards = get_flashcards_by_deck(item_id)
                if cards:
                    st.markdown("##### Cards Preview:")
                    for idx, c in enumerate(cards[:4], 1):
                        st.markdown(f"**Card {idx}:** {c['front']} ➔ *{c['back'][:90]}...*")
                    if len(cards) > 4:
                        st.caption(f"...and {len(cards) - 4} more cards in this deck.")

                st.markdown("---")
                c_d1, c_ddel = st.columns([1, 1])
                with c_d1:
                    if st.button("▶️ Launch Study Mode", key=f"lib_study_deck_{item_id}", type="primary", use_container_width=True):
                        st.switch_page("pages/5_Flashcards.py")
                with c_ddel:
                    del_k = f"del_confirm_deck_{item_id}"
                    if not st.session_state.get(del_k, False):
                        if st.button("🗑️ Delete Deck", key=f"lib_del_deck_btn_{item_id}", use_container_width=True):
                            st.session_state[del_k] = True
                            st.rerun()
                    else:
                        st.warning("Delete deck and all its cards?")
                        cy, cn = st.columns(2)
                        with cy:
                            if st.button("Yes", key=f"lib_yes_deck_{item_id}", type="primary"):
                                delete_deck(item_id)
                                st.session_state.pop(del_k, None)
                                st.success("Deck deleted.")
                                st.rerun()
                        with cn:
                            if st.button("No", key=f"lib_no_deck_{item_id}"):
                                st.session_state.pop(del_k, None)
                                st.rerun()

            elif m_type == "quiz":
                # Quiz Details
                q_list = raw.get("questions") or []
                st.markdown(f"**Questions Formulation:** {len(q_list)} Multiple-Choice Questions")
                for idx, q in enumerate(q_list[:3], 1):
                    st.markdown(f"**Q{idx}:** {q['question']}")
                    st.caption(f"Correct: Option {q['correct_option']} — *{q.get('explanation', '')[:90]}...*")

                if len(q_list) > 3:
                    st.caption(f"...and {len(q_list) - 3} more questions in this quiz.")

                st.markdown("---")
                c_q1, c_qdel = st.columns([1, 1])
                with c_q1:
                    if st.button("▶️ Take This Quiz", key=f"lib_take_quiz_{item_id}", type="primary", use_container_width=True):
                        st.session_state["active_quiz"] = {
                            "saved_id": item_id,
                            "title": item["title"],
                            "subject": item["subject"],
                            "questions": q_list,
                            "note_id": raw.get("note_id"),
                            "start_time": time.time(),
                            "submitted": False,
                            "user_answers": {},
                            "grade_results": None,
                            "current_q_idx": 0,
                            "display_mode": "All Questions"
                        }
                        st.switch_page("pages/4_Quiz_Generator.py")
                with c_qdel:
                    del_k = f"del_confirm_quiz_{item_id}"
                    if not st.session_state.get(del_k, False):
                        if st.button("🗑️ Delete Quiz", key=f"lib_del_quiz_btn_{item_id}", use_container_width=True):
                            st.session_state[del_k] = True
                            st.rerun()
                    else:
                        st.warning("Delete quiz?")
                        cy, cn = st.columns(2)
                        with cy:
                            if st.button("Yes", key=f"lib_yes_quiz_{item_id}", type="primary"):
                                delete_quiz(item_id)
                                st.session_state.pop(del_k, None)
                                st.success("Quiz deleted.")
                                st.rerun()
                        with cn:
                            if st.button("No", key=f"lib_no_quiz_{item_id}"):
                                st.session_state.pop(del_k, None)
                                st.rerun()

# =========================================================================
# PAGINATION NAVIGATION BUTTONS
# =========================================================================
if total_pages > 1:
    st.markdown("<br>", unsafe_allow_html=True)
    c_p1, c_p2, c_p3 = st.columns([1, 2, 1])

    with c_p1:
        if current_page > 1:
            if st.button("◀ Previous Page", key="prev_page_btn", use_container_width=True):
                st.session_state["library_page_num"] -= 1
                st.rerun()

    with c_p2:
        st.markdown(
            f"<div style='text-align: center; padding-top: 8px; font-weight: 600; color: var(--text-secondary);'>"
            f"Page {current_page} of {total_pages}"
            f"</div>",
            unsafe_allow_html=True
        )

    with c_p3:
        if current_page < total_pages:
            if st.button("Next Page ▶", key="next_page_btn", use_container_width=True):
                st.session_state["library_page_num"] += 1
                st.rerun()
