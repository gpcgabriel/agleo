"""Confirmation panel for a proposed action."""

import streamlit as st

from app.ui.gui.icons import icon_bot, wrap_icon
from app.ui.state import clear_pending, confirm_pending, get_pending, push_chat, queue_toast


def render_confirmation_gate(locked=False):
    """Draws the pending proposal with its confirm and cancel buttons.

    Args:
        locked (bool): Whether the decision is held. Confirming while a batch
            of steps is running would apply the change in the middle of the
            run, which lands a second snapshot on the same tick and reads on
            the timeline as a change the operator never made.
    """
    pending = get_pending()
    if not pending:
        return

    note = getattr(pending, "defaults_note", "")
    note_line = f"<p style='margin: 5px 0; opacity: 0.75;'>{note}</p>" if note else ""

    # Writing the box as one line. Streamlit runs this through a Markdown
    # parser first, and a proposal with no note leaves a whitespace-only line
    # in the middle of the block: Markdown reads it as blank, closes the HTML
    # there, and renders the indented `</div>` that follows as a code block.
    st.markdown(
        '<div class="proposed-box">'
        f"<h4>{wrap_icon(icon_bot(20))} Agent Proposed Action</h4>"
        f"<p style='margin: 5px 0;'><b>Change:</b> {pending.description}</p>"
        f"{note_line}"
        "</div>",
        unsafe_allow_html=True,
    )

    col_yes, col_no = st.columns(2)

    st.markdown('<div class="btn-confirm-marker"></div>', unsafe_allow_html=True)
    if col_yes.button("Confirm Execution", use_container_width=True, key="btn_confirm", disabled=locked):
        confirm_pending()
        st.rerun()

    st.markdown('<div class="btn-cancel-marker"></div>', unsafe_allow_html=True)
    if col_no.button("Cancel Proposal", use_container_width=True, key="btn_cancel", disabled=locked):
        push_chat("system", f"Action rejected by user: {pending.description}")
        queue_toast(f"Action cancelled: {pending.description}")
        clear_pending()
        st.rerun()
