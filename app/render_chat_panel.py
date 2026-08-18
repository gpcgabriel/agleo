import streamlit as st

from app.dashboard_agent.run_agent import run_agent
from app.gui.icons import icon_bot, wrap_icon
from app.helper_functions.ollama_helper import DEFAULT_MODEL, list_local_models
from app.helper_functions.simulation_helper import execute_pending_action, get_simulation_state_summary
from app.helper_functions.slash_commands import SLASH_COMMANDS, get_help_message


def render_chat_panel(curr_idx: int, history: list, snapshot: dict, agent_mode, ollama_ok: bool) -> None:
    """Render the Agent Orchestrator column: the pending-action confirmation
    gate, the chat history, and the chat input that drives the agent.

    Args:
        curr_idx: index of the currently viewed step in `history`.
        history: full simulation_history list.
        snapshot: the snapshot currently being viewed (history[curr_idx]).
        agent_mode: "Tools", "Skills", or None if agent actions are disabled.
        ollama_ok: whether Ollama is currently reachable.
    """
    st.markdown(f"<h3>{wrap_icon(icon_bot(20))} Agent Orchestrator</h3>", unsafe_allow_html=True)

    # Render Confirmation Gate
    pending = st.session_state["pending_action"]
    if pending:
        st.markdown(
            f"""<div class="proposed-box">
            <h4>{wrap_icon(icon_bot(20))} Agent Proposed Action</h4>
            <p style='margin: 5px 0;'><b>Change:</b> {pending['description']}</p>
            </div>""",
            unsafe_allow_html=True,
        )
        col_yes, col_no = st.columns(2)

        st.markdown('<div class="btn-confirm-marker"></div>', unsafe_allow_html=True)
        if col_yes.button("Confirm Execution", use_container_width=True, key="btn_confirm"):
            execute_pending_action()
            st.rerun()

        st.markdown('<div class="btn-cancel-marker"></div>', unsafe_allow_html=True)
        if col_no.button("Cancel Proposal", use_container_width=True, key="btn_cancel"):
            st.session_state["chat_messages"].append(
                {"role": "system", "content": f"Action rejected by user: {pending['description']}"}
            )
            st.session_state["toast_message"] = f"Action cancelled: {pending['description']}"
            st.session_state["pending_action"] = None
            st.rerun()

    # Render Chat History
    chat_container = st.container(height=450)
    with chat_container:
        for msg in st.session_state["chat_messages"]:
            if msg["role"] == "system":
                st.markdown(
                    f'<div class="system-msg">{wrap_icon(icon_bot(16))} {msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

    # --- DYNAMIC CHAT INPUT STATUS & PLACEHOLDER ---
    steps_active = st.session_state.get("steps_remaining", 0) > 0
    local_models = list_local_models() if ollama_ok else []
    selected_model = st.session_state.get("selected_model", DEFAULT_MODEL)

    # Check if the currently selected model is downloaded
    model_downloaded = (
        any(
            m == selected_model or m.startswith(selected_model + ":") or selected_model.startswith(m + ":")
            for m in local_models
        )
        if ollama_ok
        else False
    )

    # Set dynamic parameters for single chat_input widget
    if steps_active:
        placeholder = "⏳ Simulation in progress..."
        chat_disabled = True
    elif not ollama_ok:
        placeholder = "⚠️ Agent unavailable — Ollama not running"
        chat_disabled = True
    elif not model_downloaded:
        placeholder = f"⚠️ Agent unavailable — Model '{selected_model}' not downloaded"
        chat_disabled = True
    else:
        placeholder = "Type a command for the agent (e.g., 'Advance simulation by 3 steps')"
        chat_disabled = False

    if prompt := st.chat_input(placeholder, disabled=chat_disabled, key="agent_chat_input"):

        # Save and display the user's message immediately in the chat container
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})

        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

            # Open assistant message space inside the chat container
            with st.chat_message("assistant"):
                response_content = ""  # Variable to storage the final reponse

                if prompt.lower().strip() in ("/", "/help"):
                    response_content = get_help_message()
                    st.markdown(response_content)

                elif prompt.strip().startswith("/") and not any(
                    prompt.strip().startswith(c["cmd"].strip()) for c in SLASH_COMMANDS
                ):
                    help_message = get_help_message()
                    response_content = f"**Unknown command:** `{prompt.strip()}`\n\n{help_message}"
                    st.markdown(response_content)

                elif curr_idx != len(history) - 1:
                    response_content = "⚠️ You are viewing a historical step. To send commands, drag the slider to the most recent step."
                    st.error(response_content)

                elif st.session_state["pending_action"] is not None:
                    response_content = (
                        "⚠️ Resolve the pending proposed action in the upper panel before continuing the conversation."
                    )
                    st.warning(response_content)

                else:
                    # Instantiate the agent and run inference
                    with st.spinner("🤖 Agent calculating response (Inference)..."):

                        # Contextual state injection (Detailed state summary or minimal optimized summary)
                        if prompt.startswith("/") and not prompt.lower().startswith("/review"):
                            context_state = (
                                "Quick Command Mode (Slash Command). "
                                "Execute the corresponding action immediately by calling the appropriate tool."
                            )
                        else:
                            detailed_summary = get_simulation_state_summary(snapshot)
                            context_state = (
                                "You have access to the current detailed simulation state below:\n\n"
                                f"{detailed_summary}\n\n"
                                "Use this data to answer informational questions. "
                                "If the operator explicitly requests a change or advancement to the simulation in natural language, you MUST use the appropriate tool to propose the action."
                            )

                        selected_model = st.session_state.get("selected_model", DEFAULT_MODEL)

                        response = run_agent(prompt, selected_model, agent_mode, context_state)
                        response_content = response.content
                        st.markdown(response_content)

        # Save the generated response in the general history and reload the page
        st.session_state["chat_messages"].append({"role": "assistant", "content": response_content})
        st.rerun()
