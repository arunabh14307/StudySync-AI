"""
StudySync AI - Page 3: AI Summarizer
Extractive NLP summarization engine. Generates high-yield summaries,
key bullet points, and compression metrics with adjustable length.
"""

import streamlit as st
from typing import Optional

st.set_page_config(page_title="AI Summarizer | StudySync AI", page_icon="⚡", layout="wide")

from utils.database import (
    init_db,
    save_summary,
    get_all_notes,
    get_all_summaries,
    delete_summary
)
from utils.summarizer import generate_summary
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
    title="AI Document Summarizer",
    subtitle="Condense complex textbook chapters and lecture notes into concise executive summaries and bullet points using extractive NLP algorithms.",
    badge_text="Extractive NLP",
    badge_type="info"
)

st.info(
    "💡 **Extractive NLP Engine:** This module uses explainable extractive text summarization "
    "(TF-ISF word frequency scoring, lead thesis position weighting, and MMR diversity filtering). "
    "It ranks and extracts the most significant sentences directly from your document, preserving the exact original wording "
    "without hallucinating facts.",
    icon="ℹ️"
)

# Check if text was passed from another page (e.g. Smart Notes)
preset_text = st.session_state.pop("active_text_for_summary", "")
preset_note_id = st.session_state.pop("active_note_id", None)
preset_title = st.session_state.pop("active_note_title", "")

tab_generate, tab_saved = st.tabs(["Generate Summary", "Saved Summaries"])

with tab_generate:
    # Option to quickly load a note from database
    saved_notes = get_all_notes()
    if saved_notes:
        with st.expander("📥 Or select an existing note from your StudySync Library"):
            note_titles = {f"{n['title']} ({n['subject']})": n for n in saved_notes}
            selected_note_name = st.selectbox("Choose a note to load", options=["-- Select Note --"] + list(note_titles.keys()))
            if selected_note_name != "-- Select Note --":
                chosen = note_titles[selected_note_name]
                preset_text = chosen['content']
                preset_title = chosen['title']
                preset_note_id = chosen['id']

    st.markdown("### Source Material")
    summary_title_input = st.text_input(
        "Summary Title",
        value=f"Summary: {preset_title}" if preset_title else "",
        placeholder="e.g. Summary: Cellular Respiration"
    )

    source_text = st.text_area(
        "Study Text / Notes",
        value=preset_text,
        placeholder="Paste your lecture notes, textbook paragraph, or study material here (minimum 25 words)...",
        height=240
    )

    col_ctrl1, col_ctrl2 = st.columns([2, 1])
    with col_ctrl1:
        ratio_slider = st.slider(
            "Target Summary Length (% of original)",
            min_value=15,
            max_value=65,
            value=35,
            step=5,
            help="Higher values retain more supporting details; lower values produce ultra-dense executive takeaways."
        )
    with col_ctrl2:
        method_choice = st.selectbox(
            "Algorithm Strategy",
            options=["Extractive Hybrid (TF-ISF + Lead Bias)", "Lead & Thesis Dominant", "Keyword Density Only"]
        )

    if st.button("✨ Generate AI Summary", type="primary", use_container_width=True):
        if not source_text.strip():
            st.error("Please enter or paste study text to summarize.")
        elif len(source_text.strip().split()) < 25:
            st.warning("The provided text is too short (less than 25 words). Please input at least a full paragraph.")
        else:
            with st.spinner("Analyzing linguistic structures and selecting key sentences..."):
                ratio_val = ratio_slider / 100.0
                result = generate_summary(source_text, ratio=ratio_val, method=method_choice)

            if not result["success"]:
                st.error(result["error"])
            else:
                st.session_state["last_summary_result"] = result
                st.session_state["last_summary_source"] = source_text
                st.session_state["last_summary_title"] = summary_title_input or "Academic Summary"
                st.session_state["last_summary_note_id"] = preset_note_id

    # Display results if available in session state
    if "last_summary_result" in st.session_state:
        res = st.session_state["last_summary_result"]
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 📋 Generated Summary")

        # Metrics bar
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_metric_card("Original Words", res["original_word_count"], "Source text")
        with m2:
            render_metric_card("Summary Words", res["summary_word_count"], res.get("sentence_reduction", ""))
        with m3:
            render_metric_card("Compression", f"{res['compression_ratio']}%", "Text reduced")
        with m4:
            render_metric_card("Time Saved", f"{res['time_saved_min']} min", "Estimated reading time")

        st.markdown("<br>", unsafe_allow_html=True)

        # Summary Paragraph Box
        st.markdown(
            f"""
            <div class="sync-card">
                <div class="sync-card-title">📖 Executive Summary</div>
                <p style="font-size: 15px; line-height: 1.6; color: var(--text-primary); margin-top: 10px;">
                    {res['summary_text']}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Key Takeaway Bullets
        if res.get("key_points"):
            st.markdown("#### 💡 Key Takeaway Highlights")
            for idx, pt in enumerate(res["key_points"], 1):
                st.markdown(f"- **Point {idx}:** {pt}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Action Buttons: Save & Export
        col_s1, col_s2 = st.columns([1, 1])
        with col_s1:
            if st.button("💾 Save Summary to StudySync Library", type="secondary", use_container_width=True):
                save_title = st.session_state.get("last_summary_title", "Academic Summary")
                src_txt = st.session_state.get("last_summary_source", "")
                note_id_fk = st.session_state.get("last_summary_note_id")
                
                new_sum_id = save_summary(
                    title=save_title,
                    original_text=src_txt,
                    summary_text=res["summary_text"],
                    key_points=res.get("key_points", []),
                    compression_ratio=res["compression_ratio"],
                    method=res.get("method", "Extractive NLP"),
                    note_id=note_id_fk
                )
                st.success(f"Summary '{save_title}' saved to database! (ID: {new_sum_id})")

        with col_s2:
            export_content = f"# {st.session_state.get('last_summary_title', 'Summary')}\n\n## Executive Summary\n{res['summary_text']}\n\n## Key Points\n" + "\n".join([f"- {p}" for p in res.get('key_points', [])])
            st.download_button(
                label="📥 Download Markdown Summary",
                data=export_content,
                file_name="StudySync_Summary.md",
                mime="text/markdown",
                use_container_width=True
            )

with tab_saved:
    st.markdown("### Saved Summaries Collection")
    summaries = get_all_summaries()

    if summaries:
        st.caption(f"You have **{len(summaries)}** saved summaries.")
        for s in summaries:
            with st.expander(f"📑 {s['title']} — {s['compression_ratio']}% Compressed ({s['created_at'][:10]})"):
                st.markdown("#### Summary Text")
                st.write(s['summary_text'])
                
                if s.get('key_points'):
                    st.markdown("#### Key Takeaways")
                    for pt in s['key_points']:
                        st.markdown(f"• {pt}")
                
                st.markdown("---")
                col_d1, _ = st.columns([1, 4])
                with col_d1:
                    if st.button("🗑️ Delete Summary", key=f"del_sum_{s['id']}"):
                        delete_summary(s['id'])
                        st.success("Summary deleted.")
                        st.rerun()
    else:
        render_empty_state("No Saved Summaries", "Generate and save summaries above to store them in your permanent library.", "⚡")
