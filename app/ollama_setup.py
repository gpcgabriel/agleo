import streamlit as st

from app.helper_functions.ollama_helper import (
    DEFAULT_MODEL,
    is_ollama_running,
    list_local_models,
    pull_model,
    start_ollama,
)


def ollama_setup() -> bool:
    """Render the Ollama health-check / auto-start / model-download UI.

    Returns:
        bool: True if Ollama is running and reachable.
    """
    ollama_ok = is_ollama_running()

    if not ollama_ok:
        st.warning("Ollama is not running. The agent requires Ollama to function.")
        if st.button("Start Ollama", key="start_ollama_button"):
            with st.spinner("Starting Ollama daemon..."):
                if start_ollama():
                    st.success("Ollama daemon started successfully!")
                    st.rerun()
                else:
                    st.error("Failed to start Ollama daemon. Please run 'ollama serve' in your terminal.")
        return ollama_ok

    # Verify if the default model is available
    local_models = list_local_models()
    default_downloaded = any(
        m == DEFAULT_MODEL or m.startswith(DEFAULT_MODEL + ":") or DEFAULT_MODEL.startswith(m + ":")
        for m in local_models
    )
    if not default_downloaded:
        st.info(f"Default model '{DEFAULT_MODEL}' is not available locally. Would you like to download it?")
        if st.button(f"Download {DEFAULT_MODEL}", key="download_default_model_button"):
            progress_placeholder = st.empty()

            def progress_cb(line):
                progress_placeholder.text(f"Ollama: {line}")

            with st.spinner("Downloading model... This may take a few minutes."):
                if pull_model(DEFAULT_MODEL, progress_callback=progress_cb):
                    st.success(f"Model '{DEFAULT_MODEL}' downloaded successfully!")
                    st.rerun()
                else:
                    st.error(
                        f"Failed to download model '{DEFAULT_MODEL}'. Please run 'ollama pull {DEFAULT_MODEL}' in terminal."
                    )

    return ollama_ok
