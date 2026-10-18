"""
StudySync AI - Page 5: Flashcards
Interactive active recall flashcard system.
Create flashcards manually, auto-extract concept pairs from study notes using NLP,
study with question-first flip cards, track mastery levels, and organize decks by subject.
"""

import streamlit as st
from typing import List, Dict, Any

st.set_page_config(page_title="Flashcards | StudySync AI", page_icon="🗂️", layout="wide")

from utils.database import (
    init_db,
    create_flashcard_deck,
    get_all_decks,
    get_deck_by_id,
    delete_deck,
    create_flashcard,
    save_flashcards_batch,
    get_flashcards_by_deck,
    update_flashcard_mastery,
    delete_flashcard,
    get_all_notes,
    ValidationError
)
from utils.flashcard_generator import generate_flashcards_from_text
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
    title="Active Recall Flashcards",
    subtitle="Strengthen retention with question-first flashcards. Create cards manually, auto-generate concept pairs from notes, or study your existing decks.",
    badge_text="Active Recall",
    badge_type="primary"
)

# Preset text from other pages (e.g. Smart Notes)
preset_text = st.session_state.pop("active_text_for_cards", "")
preset_title = st.session_state.pop("active_note_title", "")
preset_subj = st.session_state.pop("active_subject", "General Study")
preset_note_id = st.session_state.pop("active_note_id", None)
if preset_note_id:
    st.session_state["fc_source_note_id"] = preset_note_id

tab_study, tab_manual, tab_generate, tab_manage = st.tabs([
    "🗂️ Study Deck Mode",
    "➕ Create Cards Manually",
    "✨ Auto-Generate from Notes",
    "📚 Deck & Card Manager"
])

# =========================================================================
# TAB 1: STUDY DECK MODE
# =========================================================================
with tab_study:
    all_decks = get_all_decks()

    if not all_decks:
        render_empty_state(
            "No Flashcard Decks Available",
            "You haven't created any flashcard decks yet. Use '➕ Create Cards Manually' or '✨ Auto-Generate from Notes' to get started.",
            "🗂️"
        )
    else:
        # Group & Filter by Subject (Requirement 8)
        col_filt, col_sel = st.columns([1, 2])
        distinct_subjects = ["All Subjects"] + sorted(list(set(d["subject"] for d in all_decks if d.get("subject"))))
        
        with col_filt:
            subj_filter = st.selectbox("Filter Decks by Subject", options=distinct_subjects, key="study_subj_filter")

        filtered_decks = [d for d in all_decks if subj_filter == "All Subjects" or d["subject"] == subj_filter]

        if not filtered_decks:
            st.info(f"No decks found for subject '{subj_filter}'. Showing all available decks.")
            filtered_decks = all_decks

        deck_options = {f"{d['title']} ({d['subject']} • {d['card_count']} cards)": d for d in filtered_decks}
        
        with col_sel:
            selected_deck_label = st.selectbox("Select Deck to Study", options=list(deck_options.keys()), key="study_deck_selector")
        
        selected_deck = deck_options[selected_deck_label]
        deck_id = selected_deck["id"]

        cards = get_flashcards_by_deck(deck_id)

        # Requirement 10: Handle empty decks gracefully
        if not cards:
            st.warning(f"⚠️ The deck '{selected_deck['title']}' currently contains no flashcards.")
            col_add_empty, _ = st.columns([1, 2])
            with col_add_empty:
                st.info("Tip: Switch to the '➕ Create Cards Manually' tab to add your first question-and-answer pair to this deck.")
        else:
            total_cards = len(cards)

            # Maintain active card index in session state
            session_card_key = f"card_idx_{deck_id}"
            if session_card_key not in st.session_state:
                st.session_state[session_card_key] = 0

            cur_idx = st.session_state[session_card_key]
            # Bounds check
            if cur_idx >= total_cards:
                cur_idx = 0
                st.session_state[session_card_key] = 0
            elif cur_idx < 0:
                cur_idx = 0
                st.session_state[session_card_key] = 0

            cur_card = cards[cur_idx]

            # Deck info banner & metrics
            c_m1, c_m2, c_m3 = st.columns(3)
            with c_m1:
                render_metric_card("Current Deck", selected_deck['title'], selected_deck['subject'])
            with c_m2:
                render_metric_card("Card Position", f"{cur_idx + 1} of {total_cards}", f"{round(((cur_idx + 1) / total_cards) * 100)}% through deck")
            with c_m3:
                mastered_in_deck = sum(1 for c in cards if c.get('mastery_level', 0) >= 3)
                render_metric_card("Deck Mastery", f"{mastered_in_deck} / {total_cards}", "Cards mastered (Level 3)")

            if selected_deck.get("source_note_title"):
                st.caption(f"📌 **Source Note:** *{selected_deck['source_note_title']}*")

            st.markdown("<br>", unsafe_allow_html=True)

            # Progress Bar & Indicator (Requirement 5 & 6)
            progress_val = (cur_idx + 1) / total_cards
            st.progress(progress_val)
            st.caption(f"Card **{cur_idx + 1}** of **{total_cards}** • Deck: *{selected_deck['title']}*")

            # Flip State: Display question first (Requirement 3 & 4)
            flip_key = f"is_flipped_{cur_card['id']}"
            if flip_key not in st.session_state:
                st.session_state[flip_key] = False

            is_flipped = st.session_state[flip_key]

            # Flashcard Visual Display (Question First, Reveal Answer)
            side_label = "BACK — DEFINITION / ANSWER" if is_flipped else "FRONT — CONCEPT / QUESTION"
            card_content = cur_card["back"] if is_flipped else cur_card["front"]
            border_color = "var(--border-accent)" if is_flipped else "var(--border-card)"

            st.markdown(
                f"""
                <div class="flashcard-wrapper">
                    <div class="flashcard" style="border: 2px solid {border_color};">
                        <div class="flashcard-side-tag">{side_label}</div>
                        <div class="flashcard-text">{card_content}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Flip Button (Requirement 4: Add a button to reveal the answer)
            col_flip, col_del_card = st.columns([3, 1])
            with col_flip:
                flip_label = "🔄 Flip to Question" if is_flipped else "🔍 Reveal Answer"
                if st.button(flip_label, key=f"btn_flip_{cur_card['id']}", type="primary", use_container_width=True):
                    st.session_state[flip_key] = not is_flipped
                    st.rerun()

            with col_del_card:
                if st.button("🗑️ Delete Card", key=f"btn_del_cur_card_{cur_card['id']}", type="secondary", use_container_width=True, help="Remove this card from deck"):
                    delete_flashcard(cur_card['id'])
                    # Safe index adjustment
                    if cur_idx > 0:
                        st.session_state[session_card_key] = cur_idx - 1
                    st.success("Card deleted.")
                    st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)

            # Navigation & Mastery Controls (Requirement 5: Previous and Next navigation)
            st.markdown("##### Study Navigation & Confidence Rating")
            c_prev, c_mastery1, c_mastery2, c_mastery3, c_next = st.columns([1, 1, 1, 1, 1])

            with c_prev:
                if st.button("⬅️ Previous", disabled=(cur_idx == 0), use_container_width=True, key=f"study_prev_{deck_id}"):
                    st.session_state[session_card_key] = cur_idx - 1
                    st.session_state[flip_key] = False  # Reset flip state on navigation
                    st.rerun()

            with c_mastery1:
                cur_lvl = cur_card.get('mastery_level', 0)
                btn_txt = "🔴 Needs Work" + (" (Active)" if cur_lvl == 1 else "")
                if st.button(btn_txt, key=f"mast_1_{cur_card['id']}", help="Mark as unlearned (Level 1)", use_container_width=True):
                    update_flashcard_mastery(cur_card['id'], 1)
                    st.toast("Card marked: Needs Work (Level 1)", icon="🔴")
                    if cur_idx < total_cards - 1:
                        st.session_state[session_card_key] = cur_idx + 1
                        st.session_state[flip_key] = False
                    st.rerun()

            with c_mastery2:
                btn_txt = "🟡 Reviewing" + (" (Active)" if cur_lvl == 2 else "")
                if st.button(btn_txt, key=f"mast_2_{cur_card['id']}", help="Mark as familiar (Level 2)", use_container_width=True):
                    update_flashcard_mastery(cur_card['id'], 2)
                    st.toast("Card marked: Reviewing (Level 2)", icon="🟡")
                    if cur_idx < total_cards - 1:
                        st.session_state[session_card_key] = cur_idx + 1
                        st.session_state[flip_key] = False
                    st.rerun()

            with c_mastery3:
                btn_txt = "🟢 Mastered" + (" (Active)" if cur_lvl >= 3 else "")
                if st.button(btn_txt, key=f"mast_3_{cur_card['id']}", help="Mark as mastered (Level 3)", use_container_width=True):
                    update_flashcard_mastery(cur_card['id'], 3)
                    st.toast("Card marked: Mastered! 🎉 (Level 3)", icon="🟢")
                    if cur_idx < total_cards - 1:
                        st.session_state[session_card_key] = cur_idx + 1
                        st.session_state[flip_key] = False
                    st.rerun()

            with c_next:
                if st.button("Next ➡️", disabled=(cur_idx >= total_cards - 1), use_container_width=True, key=f"study_next_{deck_id}"):
                    st.session_state[session_card_key] = cur_idx + 1
                    st.session_state[flip_key] = False  # Reset flip state on navigation
                    st.rerun()

# =========================================================================
# TAB 2: CREATE CARDS MANUALLY (Requirement 1 & 9 & 10)
# =========================================================================
with tab_manual:
    st.markdown("### ➕ Create Flashcards Manually")
    st.caption("Draft custom question-and-answer pairs or formulate a brand new subject deck.")

    creation_mode = st.radio(
        "Choose Creation Workflow",
        options=["Add Card to Existing Deck", "Create a Brand New Deck & Card"],
        horizontal=True,
        key="manual_creation_mode_radio"
    )

    subject_options = [
        "Computer Science", "Biology", "Psychology", "Mathematics",
        "Physics", "Chemistry", "Economics", "Literature", "General Studies"
    ]

    # Workflow A: Add Card to Existing Deck
    if creation_mode == "Add Card to Existing Deck":
        decks = get_all_decks()
        if not decks:
            st.info("No decks exist yet. Please create a new deck first using 'Create a Brand New Deck & Card'.")
        else:
            deck_lookup = {f"{d['title']} ({d['subject']})": d for d in decks}
            chosen_deck_label = st.selectbox("Select Target Deck", options=list(deck_lookup.keys()), key="manual_add_deck_target")
            target_deck = deck_lookup[chosen_deck_label]

            with st.form("manual_add_card_form"):
                st.markdown(f"**Adding to:** `{target_deck['title']}` ({target_deck['subject']})")
                card_front = st.text_area(
                    "Front — Question / Concept / Prompt",
                    placeholder="e.g. What is the primary role of the hippocampus in memory consolidation?",
                    height=100
                )
                card_back = st.text_area(
                    "Back — Answer / Definition / Explanation",
                    placeholder="e.g. It converts short-term memories into long-term memories in the cerebral cortex.",
                    height=120
                )

                card_submitted = st.form_submit_button("➕ Add Flashcard to Deck", type="primary", use_container_width=True)

                if card_submitted:
                    if not card_front.strip():
                        st.error("Flashcard front (question) cannot be empty.")
                    elif not card_back.strip():
                        st.error("Flashcard back (answer) cannot be empty.")
                    else:
                        create_flashcard(
                            front=card_front.strip(),
                            back=card_back.strip(),
                            deck_id=target_deck['id'],
                            subject=target_deck['subject']
                        )
                        st.success(f"Flashcard added to '{target_deck['title']}' successfully!")
                        st.rerun()

    # Workflow B: Create Brand New Deck & Card
    else:
        with st.form("manual_create_deck_and_card_form"):
            st.markdown("#### Step 1: Deck Information")
            c_nd1, c_nd2 = st.columns([2, 1])
            with c_nd1:
                new_deck_title = st.text_input("Deck Title", placeholder="e.g. Organic Chemistry Functional Groups")
            with c_nd2:
                new_deck_subject = st.selectbox("Subject Area", options=subject_options, key="manual_new_deck_subject")

            new_deck_desc = st.text_input("Deck Description (optional)", placeholder="e.g. Core carbonyl and alcohol reactions")

            st.markdown("#### Step 2: First Flashcard")
            new_front = st.text_area(
                "Front — Question / Concept",
                placeholder="e.g. What is an Aldehyde?",
                height=90
            )
            new_back = st.text_area(
                "Back — Answer / Definition",
                placeholder="e.g. An organic compound containing a functional group with the structure −CHO (carbonyl center bonded to hydrogen).",
                height=110
            )

            create_deck_submitted = st.form_submit_button("💾 Save Deck & Add Initial Card", type="primary", use_container_width=True)

            if create_deck_submitted:
                if not new_deck_title.strip():
                    st.error("Deck title cannot be empty.")
                elif not new_front.strip():
                    st.error("Initial flashcard front (question) cannot be empty.")
                elif not new_back.strip():
                    st.error("Initial flashcard back (answer) cannot be empty.")
                else:
                    new_deck_id = create_flashcard_deck(
                        title=new_deck_title.strip(),
                        subject=new_deck_subject,
                        description=new_deck_desc.strip()
                    )
                    create_flashcard(
                        front=new_front.strip(),
                        back=new_back.strip(),
                        deck_id=new_deck_id,
                        subject=new_deck_subject
                    )
                    st.success(f"Deck '{new_deck_title}' created with initial flashcard!")
                    st.rerun()

# =========================================================================
# TAB 3: AUTO-GENERATE DECK FROM NOTES (Requirement 2 & 7)
# =========================================================================
with tab_generate:
    st.markdown("### ✨ Generate Flashcards from Study Material")
    st.caption("Our local NLP engine identifies definitions, mechanisms, and key relationships in your study notes.")

    saved_notes = get_all_notes()
    if saved_notes:
        with st.expander("📥 Or select an existing note from your StudySync Library"):
            note_dict = {f"{n['title']} ({n['subject']})": n for n in saved_notes}
            selected_note_key = st.selectbox("Choose Note", options=["-- Select Note --"] + list(note_dict.keys()), key="fc_note_select")
            if selected_note_key != "-- Select Note --":
                chosen_n = note_dict[selected_note_key]
                preset_text = chosen_n['content']
                preset_title = chosen_n['title']
                preset_subj = chosen_n['subject']
                st.session_state["fc_source_note_id"] = chosen_n['id']

    col_fc1, col_fc2 = st.columns([2, 1])
    with col_fc1:
        auto_deck_title = st.text_input(
            "New Deck Title",
            value=f"{preset_title} Cards" if preset_title else "",
            placeholder="e.g. Cognitive Psychology: Memory Deck",
            key="auto_deck_title_input"
        )
    with col_fc2:
        subj_idx_fc = subject_options.index(preset_subj) if preset_subj in subject_options else 0
        auto_deck_subj = st.selectbox("Subject Area", options=subject_options, index=subj_idx_fc, key="auto_deck_subj_box")

    deck_source_text = st.text_area(
        "Study Text / Lecture Notes for Card Extraction",
        value=preset_text,
        placeholder="Paste your study notes here (minimum 30-40 words required)...",
        height=180,
        key="fc_source_area"
    )

    card_limit = st.slider("Target Number of Flashcards to Extract", min_value=2, max_value=12, value=5, key="auto_fc_limit_slider")

    if st.button("✨ Extract & Formulate Flashcards", type="primary", use_container_width=True, key="extract_fc_btn"):
        if not deck_source_text.strip():
            st.error("Please enter study text before generating flashcards.")
        elif len(deck_source_text.strip().split()) < 30:
            st.warning("Text is too short to extract flashcards. Please provide at least 30-40 words containing key definitions.")
        else:
            with st.spinner("Analyzing linguistic structures and formulating concept cards..."):
                fc_res = generate_flashcards_from_text(deck_source_text, max_cards=card_limit)

            if not fc_res["success"]:
                st.error(fc_res["error"])
            else:
                st.session_state["extracted_cards"] = fc_res["cards"]
                st.session_state["extracted_deck_title"] = auto_deck_title.strip() or "Generated Study Deck"
                st.session_state["extracted_deck_subj"] = auto_deck_subj
                st.success(f"Extracted {fc_res['total_cards']} flashcard pairs!")

    # Review & Save Extracted Cards
    if "extracted_cards" in st.session_state and st.session_state["extracted_cards"]:
        ext_cards = st.session_state["extracted_cards"]
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"#### 🔍 Review Extracted Cards ({len(ext_cards)} cards)")

        for idx, c in enumerate(ext_cards, 1):
            st.markdown(
                f"""
                <div style="background-color: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;">
                    <div style="font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase;">Card {idx} Front (Question)</div>
                    <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 8px;">{c['front']}</div>
                    <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Back (Answer)</div>
                    <div style="font-size: 14px; color: var(--text-secondary);">{c['back']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        col_save_deck, _ = st.columns([1, 2])
        with col_save_deck:
            if st.button("💾 Save as New Flashcard Deck", type="primary", use_container_width=True, key="save_extracted_deck_btn"):
                deck_id = create_flashcard_deck(
                    title=st.session_state.get("extracted_deck_title", "New Deck"),
                    subject=st.session_state.get("extracted_deck_subj", "General Study"),
                    description=f"Auto-generated from study notes ({len(ext_cards)} cards).",
                    note_id=st.session_state.get("fc_source_note_id")
                )
                save_flashcards_batch(deck_id, ext_cards)
                st.session_state.pop("extracted_cards", None)
                st.session_state.pop("fc_source_note_id", None)
                st.success("Flashcard deck saved successfully! Switch to '🗂️ Study Deck Mode' to practice.")
                st.rerun()

# =========================================================================
# TAB 4: DECK & CARD MANAGER (Requirement 7 & 8)
# =========================================================================
with tab_manage:
    st.markdown("### 📚 Flashcard Decks & Content Manager")
    manage_decks = get_all_decks()

    if manage_decks:
        col_m_filter, _ = st.columns([1, 2])
        with col_m_filter:
            m_distinct_subjects = ["All Subjects"] + sorted(list(set(d["subject"] for d in manage_decks if d.get("subject"))))
            m_subj_filter = st.selectbox("Filter Manager by Subject", options=m_distinct_subjects, key="manager_subj_filter")

        filtered_manage_decks = [d for d in manage_decks if m_subj_filter == "All Subjects" or d["subject"] == m_subj_filter]

        st.caption(f"Showing **{len(filtered_manage_decks)}** decks")

        for d in filtered_manage_decks:
            with st.expander(f"📚 {d['title']} — {d['subject']} ({d['card_count']} Cards, {d['mastered_count']} Mastered)"):
                st.markdown(f"**Subject Area:** `{d['subject']}` | **Created:** `{d['created_at'][:10]}`")
                if d.get('description'):
                    st.markdown(f"**Description:** {d['description']}")

                # List cards in this deck
                deck_cards = get_flashcards_by_deck(d['id'])
                if deck_cards:
                    st.markdown("##### Cards in this Deck:")
                    for idx, c in enumerate(deck_cards, 1):
                        col_cf, col_cb, col_cdel = st.columns([3, 4, 1])
                        with col_cf:
                            st.write(f"**Q{idx}:** {c['front']}")
                        with col_cb:
                            st.write(f"**A:** {c['back']}")
                        with col_cdel:
                            if st.button("Delete", key=f"del_card_mgr_{c['id']}", help="Delete this flashcard"):
                                delete_flashcard(c['id'])
                                st.rerun()
                else:
                    st.caption("No flashcards in this deck.")

                st.markdown("---")
                if st.button(f"🗑️ Delete Entire Deck: {d['title']}", key=f"del_deck_mgr_{d['id']}", type="secondary"):
                    delete_deck(d['id'])
                    st.success("Deck and all associated cards deleted.")
                    st.rerun()
    else:
        render_empty_state("No Flashcard Decks", "You haven't created any flashcard decks yet.", "🗂️")
