"""Streamlit web UI for the Mise booking agent demo."""

import datetime
import json
import streamlit as st
from agent.core import create_agent
from db.fake_data import create_booking as db_create_booking


def extract_form_from_steps(intermediate_steps: list) -> dict | None:
    """Build a booking form spec from agent tool call results.

    Scans intermediate_steps (most recent first) for a get_premise_details
    call and an optional check_availability call. Returns a form spec dict
    if sufficient data is found, otherwise None.

    Returns None if create_booking was called (booking already completed).
    """
    # If a booking was just created, don't show the form again
    if any(action.tool == "create_booking" for action, _ in intermediate_steps):
        return None

    premise_details = None
    availability_data = None

    for action, observation in reversed(intermediate_steps):
        if action.tool == "get_premise_details" and premise_details is None:
            try:
                premise_details = json.loads(observation)
            except (json.JSONDecodeError, TypeError):
                continue
        elif action.tool == "check_availability" and availability_data is None:
            try:
                availability_data = json.loads(observation)
            except (json.JSONDecodeError, TypeError):
                continue

    if not premise_details or "error" in premise_details:
        return None

    # Flatten availability slots for the form widget
    slots = []
    if isinstance(availability_data, list):
        for entry in availability_data:
            sid = entry.get("staff_id")
            for slot in entry.get("available_slots", []):
                slots.append({"staff_id": sid, "start": slot["start"], "end": slot["end"]})

    return {
        "premise_id": premise_details["id"],
        "premise_name": premise_details["name"],
        "services": premise_details["services"],
        "staff": premise_details["staff"],
        "slots": slots,
    }


def invoke_agent(prompt: str) -> tuple[str, list, list]:
    """Invoke the agent and return (raw_response, tool_log_entries, intermediate_steps)."""
    agent = get_agent()
    result = agent.invoke(
        {"input": prompt},
        config={"configurable": {"session_id": "streamlit-session"}},
    )
    raw = result.get("output", "I encountered an issue. Please try again.")
    steps = result.get("intermediate_steps", [])
    logs = []
    for action, observation in steps:
        logs.append({
            "tool": action.tool,
            "input": action.tool_input,
            "output_preview": (
                str(observation)[:200] + "..."
                if len(str(observation)) > 200
                else str(observation)
            ),
        })
    return raw, logs, steps


st.set_page_config(
    page_title="Mise AI Booking Assistant",
    page_icon="📅",
    layout="wide",
)


@st.cache_resource
def get_agent():
    return create_agent()


# ── Sidebar ──
with st.sidebar:
    st.title("Mise AI Agent")
    st.markdown("### RAG Pipeline")
    st.markdown("""
    **Architecture:**
    1. User sends natural language query
    2. LLM performs intent recognition
    3. Agent calls tools (parameterized SQL)
    4. Real database results injected as context
    5. LLM generates grounded response

    **Tools Available:**
    - `search_premises` - Find venues by category/keyword
    - `search_services` - Find services with pricing
    - `check_availability` - Real-time schedule queries
    - `get_premise_details` - Full venue information
    - `create_booking` - Create appointments
    """)

    st.markdown("---")
    st.markdown("### Agent Activity Log")
    log_container = st.container()

    if st.button("Clear Conversation"):
        st.session_state.messages = []
        st.session_state.tool_logs = []
        st.session_state.pending_form = None
        st.session_state.pending_booking_input = None
        st.rerun()

# ── Main Chat ──
st.title("Mise AI Booking Assistant")
st.caption("Natural language service search & booking | LLM + RAG + Dynamic SQL")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tool_logs" not in st.session_state:
    st.session_state.tool_logs = []
if "pending_form" not in st.session_state:
    st.session_state.pending_form = None
if "pending_booking_input" not in st.session_state:
    st.session_state.pending_booking_input = None

# ── Chat history ──
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ── Handle pending input (from form submission or quick-start button) ──
# Runs AFTER history loop so history renders existing messages and this
# handler renders only the new ones — prevents duplicate display.
if st.session_state.pending_booking_input:
    booking_input = st.session_state.pending_booking_input
    st.session_state.pending_booking_input = None  # consume immediately

    st.session_state.messages.append({"role": "user", "content": booking_input})
    with st.chat_message("user"):
        st.markdown(booking_input)

    with st.chat_message("assistant"):
        with st.spinner("Searching database and generating response..."):
            try:
                raw, logs, steps = invoke_agent(booking_input)
                st.session_state.tool_logs.extend(logs)
                form_spec = extract_form_from_steps(steps)
                if form_spec:
                    st.session_state.pending_form = form_spec
                st.markdown(raw)
                st.session_state.messages.append({"role": "assistant", "content": raw})
                if form_spec:
                    st.rerun()
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# ── Welcome guide (shown only on a fresh conversation) ──
_QUICK_START_EXAMPLES = [
    "Book a men's haircut at a barber on Friday",
    "Find a 60-minute massage available this weekend",
    "What hair colour services are available at salons?",
]

if not st.session_state.messages and not st.session_state.pending_booking_input:
    with st.chat_message("assistant"):
        st.markdown(
            "👋 **Welcome to Mise AI Booking Assistant!**\n\n"
            "I can help you discover and book services across salons, barbers, spas, and more. "
            "Here's how it works:\n\n"
            "1. **Tell me what you're looking for** — service type, location preference, date\n"
            "2. **I'll search** available venues and services in real time\n"
            "3. **A booking form will appear** — pick your service, staff, and time slot\n"
            "4. **Done** — I'll confirm your appointment instantly\n\n"
            "Try one of these to get started:"
        )
        cols = st.columns(len(_QUICK_START_EXAMPLES))
        for col, example in zip(cols, _QUICK_START_EXAMPLES):
            with col:
                if st.button(example, key=f"qs_{example[:25]}", use_container_width=True):
                    st.session_state.pending_booking_input = example
                    st.rerun()

# ── Inline booking form ──
if st.session_state.pending_form:
    spec = st.session_state.pending_form
    services = spec.get("services", [])
    staff_list = spec.get("staff", [])
    slots = spec.get("slots", [])
    premise_name = spec.get("premise_name", "the venue")
    prefill_date = spec.get("date")

    with st.container(border=True):
        st.markdown(f"#### Book at {premise_name}")

        col1, col2 = st.columns(2)

        with col1:
            service_labels = [f"{s['name']} — {s['price']}" for s in services]
            selected_service_idx = st.selectbox(
                "Service",
                range(len(service_labels)),
                format_func=lambda i: service_labels[i],
                key="form_service",
            )
            selected_service = services[selected_service_idx] if services else None

            try:
                default_date = (
                    datetime.date.fromisoformat(prefill_date)
                    if prefill_date
                    else datetime.date.today()
                )
            except ValueError:
                default_date = datetime.date.today()
            if default_date < datetime.date.today():
                default_date = datetime.date.today()

            selected_date = st.date_input(
                "Date",
                value=default_date,
                min_value=datetime.date.today(),
                key="form_date",
            )

        with col2:
            staff_labels = [f"{s['name']} (★ {s['rating']})" for s in staff_list]
            selected_staff_idx = st.selectbox(
                "Staff",
                range(len(staff_labels)),
                format_func=lambda i: staff_labels[i],
                key="form_staff",
            )
            selected_staff = staff_list[selected_staff_idx] if staff_list else None

            # Build time options: real slots from availability check, or standard hours
            if slots and selected_staff:
                staff_slots = [sl for sl in slots if sl["staff_id"] == selected_staff["id"]]
            else:
                staff_slots = []

            if staff_slots:
                slot_labels = [f"{sl['start']} – {sl['end']}" for sl in staff_slots]
                selected_slot_idx = st.selectbox(
                    "Time",
                    range(len(slot_labels)),
                    format_func=lambda i: slot_labels[i],
                    key="form_slot",
                )
                selected_slot = {"start": staff_slots[selected_slot_idx]["start"]}
            else:
                # No availability data — show standard half-hour slots 8:00–18:00
                standard_times = [
                    f"{h:02d}:{m:02d}"
                    for h in range(8, 19)
                    for m in (0, 30)
                    if not (h == 18 and m == 30)
                ]
                selected_time = st.selectbox("Time", standard_times, index=4, key="form_slot")
                selected_slot = {"start": selected_time}

        submit_col, cancel_col, _ = st.columns([1, 1, 4])
        with submit_col:
            submit = st.button("Confirm Booking", type="primary", key="form_submit")
        with cancel_col:
            cancel = st.button("Cancel", key="form_cancel")

        if cancel:
            st.session_state.pending_form = None
            st.rerun()

        if submit:
            if not selected_service or not selected_staff or not selected_slot:
                st.warning("Please fill in all fields before confirming.")
            else:
                result = db_create_booking(
                    staff_id=selected_staff['id'],
                    service_id=selected_service['id'],
                    premise_id=spec['premise_id'],
                    date=selected_date.isoformat(),
                    time=selected_slot['start'],
                )
                st.session_state.pending_form = None
                if "error" in result:
                    msg = f"Booking failed: {result['error']}"
                else:
                    msg = (
                        f"**Booking Confirmed!**\n\n"
                        f"**Booking ID:** {result['booking_id']}\n"
                        f"**Service:** {result['service_name']}\n"
                        f"**Staff:** {result['staff_name']}\n"
                        f"**Date:** {result['date']}\n"
                        f"**Time:** {result['time']}\n"
                        f"**Price:** {result['price']}\n"
                        f"**Status:** {result['status']}\n\n"
                        f"{result['message']}"
                    )
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.rerun()

# ── Chat input (disabled while booking form is active) ──
form_active = st.session_state.pending_form is not None

if prompt := st.chat_input(
    "Ask about services, availability, or make a booking...",
    disabled=form_active,
):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching database and generating response..."):
            try:
                raw, logs, steps = invoke_agent(prompt)
                st.session_state.tool_logs.extend(logs)
                form_spec = extract_form_from_steps(steps)
                if form_spec:
                    st.session_state.pending_form = form_spec
                st.markdown(raw)
                st.session_state.messages.append({"role": "assistant", "content": raw})
                if form_spec:
                    st.rerun()
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# ── Update sidebar with tool logs ──
with log_container:
    if st.session_state.tool_logs:
        for i, log in enumerate(reversed(st.session_state.tool_logs[-10:])):
            with st.expander(f"Tool: {log['tool']}", expanded=(i == 0)):
                st.json(log["input"])
                st.text(log["output_preview"])
    else:
        st.info("No tool calls yet. Start a conversation!")
