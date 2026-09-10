"""Presentation-only UI for the local FastAPI prototype."""

import os
from pathlib import Path

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
TEST_CASE_ROOT = Path(__file__).parent / "eval" / "cases"
CASE_CONFIG = {
    "01_ibm_dhl": ("ibm", "dhl"),
    "02_servicenow_dhl": ("servicenow", "dhl"),
    "03_sap_dhl": ("sap", "dhl"),
    "04_ibm_fedex": ("ibm", "fedex"),
    "05_ibm_bosch": ("ibm", "bosch"),
}
TEMPLATE_IDS = (
    "newsletter",
    "brochure",
    "slogan",
    "case_study",
    "event_invitation",
)
TEMPLATE_PROMPTS = {
    "newsletter": (
        "Write a concise B2B newsletter article connecting the sender's documented "
        "capabilities to the receiver's documented business context. Include at "
        "least one explicitly supported fact about each company. Frame the "
        "connection as a potential fit. Do not invent partnerships, deployments, "
        "customers, outcomes, metrics, or other unsupported claims."
    ),
    "brochure": (
        "Write concise brochure copy explaining how the sender's documented "
        "capabilities could address the receiver's documented priorities. Use "
        "only supported facts, avoid unsupported numbers and claims, and frame "
        "the relationship as a potential fit rather than an existing partnership."
    ),
    "slogan": (
        "Write a short, memorable B2B slogan connecting the sender's documented "
        "capability with the receiver's documented context. Use no unsupported "
        "claims, metrics, partnerships, or implied deployments. Keep it to at "
        "most two non-empty lines."
    ),
    "case_study": (
        "Write a hypothetical case-study-style article connecting the sender's "
        "documented capabilities with the receiver's documented context. Clearly "
        "frame the connection as hypothetical. Do not claim that the companies "
        "work together or invent results, customers, deployments, or metrics."
    ),
    "event_invitation": (
        "Write an event invitation connecting the sender's documented capabilities "
        "with the receiver's documented interests. Use only explicitly supported "
        "facts. Do not invent event dates, times, locations, speakers, registration "
        "links, partnerships, outcomes, or percentages; use 'To be announced' when "
        "event details are not provided. Frame the connection as a potential fit."
    ),
}

st.set_page_config(page_title="Marketing Collateral Demo", page_icon="📝")
st.title("Automated Marketing Collateral")
st.caption(f"Demo UI connected to `{BACKEND_URL}`")
st.page_link("pages/tracking.py", label="Open tracking dashboard", icon="📈")

selected_case = st.selectbox(
    "Evaluation case",
    options=tuple(CASE_CONFIG),
    format_func=lambda case_id: f"Case {case_id.split('_', maxsplit=1)[0]}",
    help="Loads the matching sender/receiver IDs and default context PDFs.",
)
SENDER_ID, RECEIVER_ID = CASE_CONFIG[selected_case]
TEST_CASE_DIR = TEST_CASE_ROOT / selected_case
st.info(
    f"Reference — Sender: `{SENDER_ID}` · Receiver: `{RECEIVER_ID}`\n\n"
    "The selected case supplies default context. Custom IDs remain optional."
)


def show_error(error: Exception) -> None:
    if isinstance(error, httpx.HTTPStatusError):
        st.error(
            f"Backend returned {error.response.status_code}: {error.response.text}"
        )
    else:
        st.error(f"Request failed: {error}")


def upload_context_form(
    form_key: str,
    role: str,
    sender_id: str,
    receiver_id: str,
    case_dir: Path,
    default_filename: str,
    default_company_id: str,
) -> None:
    default_path = case_dir / default_filename
    with st.form(form_key):
        company_id = st.text_input(
            f"{role.title()} ID",
            value="",
            placeholder="Optional custom company ID",
            key=f"{form_key}_company_id",
        )
        files = st.file_uploader(
            "Context PDFs",
            type=["pdf"],
            accept_multiple_files=True,
            key=f"{form_key}_files",
        )
        st.caption("Selected case PDF is used when no file is uploaded.")
        upload_submitted = st.form_submit_button(f"Upload {role} context")

    if upload_submitted:
        selected_files = files or [
            (default_filename, default_path.read_bytes(), "application/pdf")
        ]
        multipart_files = [
            (
                "files",
                (file.name, file.getvalue(), "application/pdf"),
            )
            if hasattr(file, "getvalue")
            else ("files", file)
            for file in selected_files
        ]
        custom_sender_id = st.session_state.get("sender_upload_form_company_id", "")
        custom_receiver_id = st.session_state.get("receiver_upload_form_company_id", "")
        form_data = {
            "sender_id": custom_sender_id or sender_id,
            "receiver_id": custom_receiver_id or receiver_id,
            "role": role,
        }
        form_data[f"{role}_id"] = company_id.strip() or default_company_id
        try:
            response = httpx.post(
                f"{BACKEND_URL}/upload",
                data=form_data,
                files=multipart_files,
                timeout=60,
            )
            response.raise_for_status()
            st.session_state[f"{role}_upload_response"] = response.json()
        except Exception as error:
            show_error(error)

    saved_upload_response = st.session_state.get(f"{role}_upload_response")
    if saved_upload_response is not None:
        st.success(f"{role.title()} context uploaded")
        st.json(saved_upload_response)


st.header("1. Upload sender context")
st.caption("Use the selected case PDF, or upload your own context.")
upload_context_form(
    "sender_upload_form",
    "sender",
    SENDER_ID,
    RECEIVER_ID,
    TEST_CASE_DIR,
    "sender.pdf",
    SENDER_ID,
)

st.header("2. Upload receiver context")
st.caption("Use the selected case PDF, or upload your own context.")
upload_context_form(
    "receiver_upload_form",
    "receiver",
    SENDER_ID,
    RECEIVER_ID,
    TEST_CASE_DIR,
    "receiver.pdf",
    RECEIVER_ID,
)


st.header("3. Generate article")
st.caption(
    "Generate a structured marketing article using the uploaded company context."
)
template_id = st.selectbox("Template ID", options=TEMPLATE_IDS)
with st.form("generate_form"):
    prompt = st.text_area(
        "Prompt",
        value=TEMPLATE_PROMPTS[template_id],
    )
    event = None
    if template_id == "event_invitation":
        st.caption("Optional event details; missing values are not invented.")
        event_values = {
            "date": st.text_input("Event date", placeholder="To be announced"),
            "time": st.text_input("Event time", placeholder="To be announced"),
            "location": st.text_input("Event location", placeholder="To be announced"),
            "registration_url": st.text_input(
                "Registration URL", placeholder="Optional"
            ),
        }
        event = {key: value for key, value in event_values.items() if value.strip()}
    generate_submitted = st.form_submit_button("Generate article")

if generate_submitted:
    generation_sender_id = st.session_state.get("sender_upload_form_company_id", "")
    generation_receiver_id = st.session_state.get("receiver_upload_form_company_id", "")
    request = {
        "sender_id": generation_sender_id.strip() or SENDER_ID,
        "receiver_id": generation_receiver_id.strip() or RECEIVER_ID,
        "prompt": prompt,
        "template_id": template_id,
        "event": event,
    }
    try:
        response = httpx.post(f"{BACKEND_URL}/generate", json=request, timeout=120)
        response.raise_for_status()
        st.session_state["generation_result"] = response.json()["result"]
    except Exception as error:
        show_error(error)

result = st.session_state.get("generation_result")
if result is not None:
    st.success("Article generated")
    st.subheader("Sections")
    for section in result.get("sections", []):
        count = section["word_count"]
        limit = section["word_limit"]
        marker = "✅" if count <= limit else "⚠️"
        st.markdown(f"**{marker} {section['section_id']} — {count}/{limit} words**")
        st.write(section["text"])

    st.subheader("Images")
    st.json(result.get("images", []))
    st.subheader("Theme")
    theme = result.get("theme", {})
    columns = st.columns(max(len(theme), 1))
    for column, (name, color) in zip(columns, theme.items()):
        column.color_picker(name, value=color, disabled=True)

    st.subheader("Final output JSON")
    st.json(result)
