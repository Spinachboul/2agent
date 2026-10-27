
import os
import requests
import streamlit as st

API_URL = os.getenv(
    "BRD_API_URL",
    "http://localhost:8000/api/v1",
).rstrip("/")

st.set_page_config(page_title="BRD Copilot", layout="wide")
st.title("BRD Copilot")

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "last_error" not in st.session_state:
    st.session_state.last_error = None


def api_request(method, path, **kwargs):
    """Make an API request and preserve useful backend errors."""
    response = requests.request(
        method,
        f"{API_URL}{path}",
        timeout=kwargs.pop("timeout", 120),
        **kwargs,
    )

    if not response.ok:
        raise RuntimeError(
            f"API {method} {path} returned "
            f"{response.status_code}: {response.text[:2000]}"
        )

    return response.json()


uploaded = st.file_uploader(
    "Upload a BRD",
    type=["pdf", "docx", "xlsx", "pptx", "png", "jpg", "jpeg"],
)

if st.button("Generate Knowledge Base", disabled=uploaded is None):
    with st.spinner("Extracting and analyzing document..."):
        try:
            result = api_request(
                "POST",
                "/documents",
                files={
                    "file": (
                        uploaded.name,
                        uploaded.getvalue(),
                        uploaded.type or "application/octet-stream",
                    )
                },
                timeout=600,
            )

            session_id = result.get("session_id")
            if not session_id:
                st.error(f"API did not return a session_id: {result}")
            else:
                st.session_state.session_id = session_id
                st.session_state.chat_messages = []
                st.session_state.last_error = None
                st.success(f"Session created: {session_id}")
                st.rerun()

        except Exception as exc:
            st.error(f"Document processing failed: {exc}")


session_id = st.session_state.session_id

if session_id:
    st.caption(f"Session: {session_id}")

    try:
        state = api_request(
            "GET",
            f"/sessions/{session_id}",
            timeout=30,
        )

        report = state.get("validation_report") or {}
        usage = state.get("token_usage") or {}

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Validation score",
            f"{report.get('validation_score', 0):.1f}/100",
        )
        col2.metric("Total tokens", usage.get("total_tokens", 0))
        col3.metric(
            "Estimated cost",
            f"${usage.get('total_cost', 0):.4f}",
        )

        with st.expander("Validation report"):
            st.json(report)

        # Display artifacts under whichever keys the API returns.
        # Confirm exact field names using the raw session JSON below.
        architecture = state.get("architecture")
        workflow = state.get("workflow_plan")
        agents = state.get("identified_agents", [])

        st.subheader("Generated architecture")
        if architecture:
            st.json(architecture)
        else:
            st.info(
                "No architecture field was found in the session response."
            )

        st.subheader("Workflow")
        if workflow:
            st.json(workflow)
        else:
            st.info(
                "No workflow_plan field was found in the session response."
            )

        with st.expander("Identified agents"):
            st.json(agents)

        with st.expander("Token usage by agent"):
            st.json(usage.get("per_agent", {}))

        with st.expander("Debug: complete session response"):
            st.write("Available fields:", list(state.keys()))
            st.json(state)

        st.divider()
        st.subheader("Chat with your BRD")

        # Render persisted-in-UI conversation history.
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        question = st.chat_input(
            "Ask about requirements, architecture, or workflow..."
        )

        if question:
            st.session_state.chat_messages.append(
                {"role": "user", "content": question}
            )

            with st.spinner("Reasoning over your BRD..."):
                try:
                    result = api_request(
                        "POST",
                        "/chat",
                        json={
                            "session_id": session_id,
                            "question": question,
                        },
                        timeout=120,
                    )

                    # Adjust this mapping to your actual chat response schema.
                    answer = (
                        result.get("answer")
                        or result.get("response")
                        or result.get("message")
                    )

                    if isinstance(answer, dict):
                        answer = answer.get("content")

                    if not answer:
                        raise RuntimeError(
                            "Chat API returned no recognized answer field. "
                            f"Response: {str(result)[:1500]}"
                        )

                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": str(answer)}
                    )
                    st.rerun()

                except Exception as exc:
                    st.session_state.last_error = str(exc)

        if st.session_state.last_error:
            st.error(st.session_state.last_error)

    except Exception as exc:
        st.error(f"Unable to load session: {exc}")
else:
    st.info("Upload a BRD and generate the knowledge base to get started.")
