"""
StudySync AI - Page 2: Smart Notes
Enables uploading PDF and TXT files, validating formats and size limits,
extracting document text via PyMuPDF, previewing content, inspecting metadata,
detecting scanned documents requiring OCR, and managing persistent study notes (save, edit, delete, open).
"""

import streamlit as st
from typing import Dict, Any, List

st.set_page_config(page_title="Smart Notes | StudySync AI", page_icon="📝", layout="wide")

from utils.database import (
    init_db,
    create_note,
    get_all_notes,
    update_note,
    delete_note,
    get_note_by_id,
    get_distinct_subjects
)
from utils.pdf_processor import (
    extract_text_from_pdf,
    extract_text_from_txt,
    validate_uploaded_file,
    format_file_size
)
from utils.text_processor import calculate_readability, extract_keywords
from utils.helpers import (
    apply_theme,
    render_sidebar_header,
    render_page_header,
    render_empty_state,
    render_metric_card
)

init_db()
apply_theme()
render_sidebar_header()

render_page_header(
    title="Smart Notes",
    subtitle="Upload academic textbooks, PDF lecture slides, or TXT notes with instant text extraction, document metadata, readability scoring, and note management.",
    badge_text="PyMuPDF + NLP",
    badge_type="primary"
)

# Standard subject list with ability to specify custom subjects
DEFAULT_SUBJECTS = [
    "Computer Science",
    "Biology",
    "Psychology",
    "Mathematics",
    "Physics",
    "Chemistry",
    "Economics",
    "Literature",
    "General Studies"
]

tab_upload, tab_manual, tab_browse = st.tabs([
    "📄 Upload Document",
    "✍️ Manual Note Editor",
    "📚 Saved Notes Library"
])

# =========================================================================
# TAB 1: UPLOAD DOCUMENT (PDF / TXT)
# =========================================================================
with tab_upload:
    st.markdown("### Upload Study Document")
    st.caption("Supported formats: **PDF (.pdf)** up to 25 MB and **Plain Text (.txt)** up to 10 MB.")

    uploaded_file = st.file_uploader(
        "Choose a PDF or TXT file",
        type=["pdf", "txt"],
        key="note_file_uploader",
        help="Upload lecture notes, journal articles, textbook chapters, or study outlines."
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        file_name = uploaded_file.name
        file_size = len(file_bytes)

        # 1. Enforce strict validation
        val_result = validate_uploaded_file(file_name, file_size, file_bytes)

        if not val_result["valid"]:
            st.error(f"❌ **Upload Validation Error:** {val_result['error']}")
        else:
            with st.spinner("Extracting and analyzing document content..."):
                if file_name.lower().endswith(".pdf"):
                    extraction = extract_text_from_pdf(file_bytes)
                else:
                    extraction = extract_text_from_txt(file_bytes, file_name=file_name)

            # 2. Check extraction errors and scanned document OCR requirement
            if not extraction["success"]:
                if extraction.get("is_scanned"):
                    st.warning(
                        "### 🔍 Scanned Document Detected — OCR Required\n\n"
                        "This PDF appears to be composed of **scanned page images or photographs** without a selectable digital text layer. "
                        "StudySync AI extracts text directly from digital text streams, but **image-only scans require Optical Character Recognition (OCR)** "
                        "to convert the picture of text into selectable characters.\n\n"
                        "**How to proceed:**\n"
                        "1. **Apply OCR:** Use an OCR utility such as **Adobe Acrobat Pro**, **Google Drive Document Converter**, or an open-source OCR tool like **Tesseract** to generate a searchable PDF.\n"
                        "2. **Upload Searchable PDF:** Once converted, upload the OCR-processed PDF here.\n"
                        "3. **Manual Entry:** Alternatively, copy and paste text directly into the **Manual Note Editor** tab."
                    )
                else:
                    st.error(f"❌ **Document Extraction Failed:** {extraction['error']}")
            else:
                extracted_text = extraction["text"]
                metadata = extraction.get("metadata", {})
                page_count = extraction.get("page_count", 1)

                st.success(f"✅ Successfully extracted **{file_name}** ({page_count} page{'s' if page_count != 1 else ''}, {val_result['file_size_formatted']})")

                # 3. Document Metadata Panel
                with st.expander("ℹ️ Document Metadata & File Specifications", expanded=True):
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        st.markdown(f"**Document Title:** {metadata.get('title') or 'Untitled'}")
                        st.markdown(f"**Author:** {metadata.get('author') or 'Unknown'}")
                        st.markdown(f"**Subject Area:** {metadata.get('subject') or 'General Study'}")
                    with col_m2:
                        st.markdown(f"**Total Pages:** {page_count}")
                        st.markdown(f"**File Size:** {metadata.get('file_size_formatted') or val_result['file_size_formatted']}")
                        if metadata.get('total_images') is not None:
                            st.markdown(f"**Embedded Images:** {metadata.get('total_images')}")
                    with col_m3:
                        if metadata.get("creation_date"):
                            st.markdown(f"**Created Date:** `{metadata.get('creation_date')}`")
                        if metadata.get("modification_date"):
                            st.markdown(f"**Modified Date:** `{metadata.get('modification_date')}`")
                        if metadata.get("creator") or metadata.get("producer"):
                            st.markdown(f"**Application:** `{metadata.get('creator') or metadata.get('producer')}`")

                # 4. Readability & Linguistic Intelligence
                readability = calculate_readability(extracted_text)
                keywords = extract_keywords(extracted_text, top_n=6)

                st.markdown("#### Document Intelligence & Readability")
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    render_metric_card("Word Count", readability["word_count"], f"{readability['sentence_count']} Sentences")
                with m2:
                    render_metric_card("Reading Ease", f"{readability['flesch_score']}/100", readability["reading_ease"])
                with m3:
                    render_metric_card("Est. Read Time", f"{readability['estimated_reading_time_min']} min", "Standard Pace (200 wpm)")
                with m4:
                    top_kw_str = ", ".join([kw[0] for kw in keywords[:3]]) if keywords else "None"
                    render_metric_card("Top Concepts", top_kw_str, "Key Topics")

                st.markdown("<br>", unsafe_allow_html=True)

                # 5. Save Extracted Note Form
                with st.form("save_extracted_note_form"):
                    st.markdown("#### Save Extracted Note to StudySync")
                    default_title = metadata.get("title")
                    if not default_title or default_title in ("Untitled Document", "Text File", "Plain Text Notes"):
                        default_title = file_name.rsplit(".", 1)[0].replace("_", " ").title()

                    col_t, col_s = st.columns([2, 1])
                    with col_t:
                        note_title = st.text_input("Note Title", value=default_title, help="Customize title for this study note.")
                    with col_s:
                        all_subs = list(dict.fromkeys(DEFAULT_SUBJECTS + get_distinct_subjects()))
                        note_subject = st.selectbox(
                            "Subject Area",
                            options=all_subs,
                            index=0
                        )

                    note_tags = st.text_input(
                        "Tags (comma-separated)",
                        value=", ".join([k[0] for k in keywords[:5]]),
                        help="Enter tags to categorize and easily search this note."
                    )

                    note_content = st.text_area(
                        "Extracted Content Preview (editable)",
                        value=extracted_text,
                        height=280,
                        help="You can review and edit the extracted content before saving."
                    )

                    col_btn1, _ = st.columns([1, 4])
                    with col_btn1:
                        save_clicked = st.form_submit_button("💾 Save to Library", type="primary", use_container_width=True)

                    if save_clicked:
                        if not note_title.strip():
                            st.error("Please provide a note title.")
                        elif not note_content.strip():
                            st.error("Cannot save empty note content.")
                        else:
                            new_id = create_note(
                                title=note_title.strip(),
                                subject=note_subject.strip(),
                                content=note_content.strip(),
                                source_type="pdf" if file_name.lower().endswith(".pdf") else "txt",
                                file_name=file_name,
                                tags=note_tags.strip()
                            )
                            st.success(f"🎉 Note '{note_title}' saved successfully! (Note ID: {new_id})")
                            st.rerun()

# =========================================================================
# TAB 2: MANUAL NOTE EDITOR
# =========================================================================
with tab_manual:
    st.markdown("### Create Notes Manually")
    st.caption("Draft your lecture notes, formula sheets, or study outlines directly.")

    with st.form("manual_note_editor_form"):
        col_m_t, col_m_s = st.columns([2, 1])
        with col_m_t:
            manual_title = st.text_input("Title", placeholder="e.g. Cognitive Psychology: Working Memory")
        with col_m_s:
            all_subs = list(dict.fromkeys(DEFAULT_SUBJECTS + get_distinct_subjects()))
            manual_subject = st.selectbox(
                "Subject Area",
                options=all_subs,
                key="manual_subject_select"
            )

        manual_tags = st.text_input("Tags", placeholder="e.g. Memory, Cognition, Baddeley")
        manual_content = st.text_area(
            "Note Content",
            placeholder="Type or paste your lecture notes or study material here...\n\nExample:\nWorking memory is a cognitive system with a limited capacity that can hold information temporarily...",
            height=280
        )

        col_sub, _ = st.columns([1, 4])
        with col_sub:
            manual_submit = st.form_submit_button("💾 Save Note", type="primary", use_container_width=True)

        if manual_submit:
            if not manual_title.strip():
                st.error("Please enter a title for the note.")
            elif not manual_content.strip():
                st.error("Note content cannot be empty.")
            else:
                new_id = create_note(
                    title=manual_title.strip(),
                    subject=manual_subject.strip(),
                    content=manual_content.strip(),
                    source_type="manual",
                    tags=manual_tags.strip()
                )
                st.success(f"🎉 Note '{manual_title}' saved successfully! (ID: {new_id})")
                st.rerun()

# =========================================================================
# TAB 3: SAVED NOTES DIRECTORY & EDITOR
# =========================================================================
with tab_browse:
    st.markdown("### Saved Notes Directory")
    st.caption("Review, edit, search, and manage your saved notes. Seamlessly launch summaries, quizzes, and flashcards.")

    col_search, col_filter, col_sort = st.columns([2, 1, 1])
    with col_search:
        search_query = st.text_input("🔍 Search notes by keyword, title, tags, or content", placeholder="Search...")
    with col_filter:
        db_subjects = get_distinct_subjects()
        distinct_subjects = ["All"] + db_subjects
        subj_filter = st.selectbox("Filter by Subject", options=distinct_subjects, key="browse_subj_filter")
    with col_sort:
        sort_choice = st.selectbox(
            "Sort by",
            options=["Recently Updated", "Recently Created", "Title (A-Z)", "Title (Z-A)"],
            key="browse_sort_choice"
        )

    sort_map = {
        "Recently Updated": "recent_updated",
        "Recently Created": "recent_created",
        "Title (A-Z)": "title_asc",
        "Title (Z-A)": "title_desc"
    }

    filtered_notes = get_all_notes(
        search_query=search_query,
        subject_filter=subj_filter,
        sort_by=sort_map[sort_choice]
    )

    if filtered_notes:
        st.caption(f"Showing **{len(filtered_notes)}** saved note{'s' if len(filtered_notes) != 1 else ''}")

        for note in filtered_notes:
            note_id = note['id']
            edit_key = f"is_editing_note_{note_id}"

            # Check if this note is currently in edit mode
            is_editing = st.session_state.get(edit_key, False)

            with st.expander(f"📌 {note['title']} — {note['subject']} ({note['word_count']} words)", expanded=is_editing):
                # Metadata row
                created_ts = note.get('created_at', '')[:16] if note.get('created_at') else 'N/A'
                updated_ts = note.get('updated_at', '')[:16] if note.get('updated_at') else created_ts
                file_info = f"({note['file_name']})" if note.get('file_name') else ''
                st.markdown(
                    f"**Tags:** `{note['tags'] or 'None'}` &nbsp;|&nbsp; "
                    f"**Source:** `{note['source_type']}` {file_info} &nbsp;|&nbsp; "
                    f"**Reading Time:** ~{note['reading_time_min']} mins &nbsp;|&nbsp; "
                    f"**Created:** `{created_ts}` &nbsp;|&nbsp; "
                    f"**Updated:** `{updated_ts}`"
                )
                st.markdown("---")

                # ==========================================
                # EDIT MODE FORM
                # ==========================================
                if is_editing:
                    st.markdown("#### ✏️ Edit Note Details")
                    with st.form(f"edit_note_form_{note_id}"):
                        edit_col_t, edit_col_s = st.columns([2, 1])
                        with edit_col_t:
                            edited_title = st.text_input("Title", value=note['title'])
                        with edit_col_s:
                            all_subs = list(dict.fromkeys(DEFAULT_SUBJECTS + get_distinct_subjects()))
                            sub_idx = all_subs.index(note['subject']) if note['subject'] in all_subs else 0
                            edited_subject = st.selectbox("Subject Area", options=all_subs, index=sub_idx)

                        edited_tags = st.text_input("Tags", value=note['tags'] or "")
                        edited_content = st.text_area("Note Content", value=note['content'], height=240)

                        col_save_e, col_cancel_e = st.columns([1, 1])
                        with col_save_e:
                            submit_edit = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
                        with col_cancel_e:
                            cancel_edit = st.form_submit_button("❌ Cancel", use_container_width=True)

                        if submit_edit:
                            if not edited_title.strip():
                                st.error("Note title cannot be empty.")
                            elif not edited_content.strip():
                                st.error("Note content cannot be empty.")
                            else:
                                update_note(
                                    note_id=note_id,
                                    title=edited_title.strip(),
                                    subject=edited_subject.strip(),
                                    content=edited_content.strip(),
                                    tags=edited_tags.strip()
                                )
                                st.session_state[edit_key] = False
                                st.success("Note updated successfully!")
                                st.rerun()

                        if cancel_edit:
                            st.session_state[edit_key] = False
                            st.rerun()

                # ==========================================
                # VIEW MODE
                # ==========================================
                else:
                    st.write(note['content'])
                    st.markdown("---")

                    col_a1, col_a2, col_a3, col_edit, col_del = st.columns([1, 1, 1, 1, 1])
                    with col_a1:
                        if st.button("⚡ Summarize", key=f"sum_btn_{note_id}", help="Open in AI Summarizer"):
                            st.session_state["active_text_for_summary"] = note['content']
                            st.session_state["active_note_id"] = note_id
                            st.session_state["active_note_title"] = note['title']
                            st.switch_page("pages/3_AI_Summarizer.py")

                    with col_a2:
                        if st.button("🎯 Make Quiz", key=f"quiz_btn_{note_id}", help="Generate practice quiz from note"):
                            st.session_state["active_text_for_quiz"] = note['content']
                            st.session_state["active_note_id"] = note_id
                            st.session_state["active_note_title"] = note['title']
                            st.session_state["active_subject"] = note['subject']
                            st.switch_page("pages/4_Quiz_Generator.py")

                    with col_a3:
                        if st.button("🗂️ Flashcards", key=f"fc_btn_{note_id}", help="Create flashcard deck from note"):
                            st.session_state["active_text_for_cards"] = note['content']
                            st.session_state["active_note_id"] = note_id
                            st.session_state["active_note_title"] = note['title']
                            st.session_state["active_subject"] = note['subject']
                            st.switch_page("pages/5_Flashcards.py")

                    with col_edit:
                        if st.button("✏️ Edit", key=f"edit_btn_{note_id}", help="Edit note title, subject, and content"):
                            st.session_state[edit_key] = True
                            st.rerun()

                    with col_del:
                        del_confirm_key = f"confirm_del_note_{note_id}"
                        if not st.session_state.get(del_confirm_key, False):
                            if st.button("🗑️ Delete", key=f"del_btn_{note_id}", help="Delete note from database"):
                                st.session_state[del_confirm_key] = True
                                st.rerun()
                        else:
                            st.warning("Confirm delete?")
                            c_y, c_n = st.columns(2)
                            with c_y:
                                if st.button("Yes", key=f"yes_del_{note_id}", type="primary"):
                                    delete_note(note_id)
                                    st.session_state.pop(del_confirm_key, None)
                                    st.success("Note deleted.")
                                    st.rerun()
                            with c_n:
                                if st.button("No", key=f"no_del_{note_id}"):
                                    st.session_state.pop(del_confirm_key, None)
                                    st.rerun()
    else:
        if search_query or (subj_filter and subj_filter != "All"):
            render_empty_state("No Matching Notes Found", "Try adjusting your search query or subject filter.", "🔍")
        else:
            render_empty_state("No Saved Notes", "Upload a PDF/TXT document or write your first study note in the tabs above.", "📝")
