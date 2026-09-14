"""Confirmation panel for a proposed action."""

import streamlit as st

from app.ui.gui.icons import icon_bot, wrap_icon
from app.ui.state import clear_pending, confirm_pending, get_pending, push_chat, queue_toast


def render_confirmation_gate():
    """Draws the pending proposal with its confirm and cancel buttons."""
    pending = get_pending()
    if not pending:
        return

    st.markdown(
        f"""<div class="proposed-box">
        <h4>{wrap_icon(icon_bot(20))} Agent Proposed Action</h4>
        <p style='margin: 5px 0;'><b>Change:</b> {pending.description}</p>
        </div>""",
        unsafe_allow_html=True,
    )

    col_yes, col_no = st.columns(2)

    st.markdown('<div class="btn-confirm-marker"></div>', unsafe_allow_html=True)
    if col_yes.button("Confirm Execution", use_container_width=True, key="btn_confirm"):
        confirm_pending()
        st.rerun()

    st.markdown('<div class="btn-cancel-marker"></div>', unsafe_allow_html=True)
    if col_no.button("Cancel Proposal", use_container_width=True, key="btn_cancel"):
        push_chat("system", f"Action rejected by user: {pending.description}")
        queue_toast(f"Action cancelled: {pending.description}")
        clear_pending()
        st.rerun()
