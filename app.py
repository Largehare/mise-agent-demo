"""Streamlit web UI for the Mise booking agent demo."""

import json
import streamlit as st
from agent.core import create_agent


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
        st.rerun()

# ── Main Chat ──
st.title("Mise AI Booking Assistant")
st.caption("Natural language service search & booking | LLM + RAG + Dynamic SQL")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tool_logs" not in st.session_state:
    st.session_state.tool_logs = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about services, availability, or make a booking..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent response
    with st.chat_message("assistant"):
        with st.spinner("Searching database and generating response..."):
            try:
                agent = get_agent()
                result = agent.invoke(
                    {"input": prompt},
                    config={"configurable": {"session_id": "streamlit-session"}},
                )

                response = result.get("output", "I encountered an issue. Please try again.")

                # Log tool calls to sidebar
                if result.get("intermediate_steps"):
                    for action, observation in result["intermediate_steps"]:
                        log_entry = {
                            "tool": action.tool,
                            "input": action.tool_input,
                            "output_preview": str(observation)[:200] + "..." if len(str(observation)) > 200 else str(observation),
                        }
                        st.session_state.tool_logs.append(log_entry)

                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Update sidebar with tool logs
with log_container:
    if st.session_state.tool_logs:
        for i, log in enumerate(reversed(st.session_state.tool_logs[-10:])):
            with st.expander(f"Tool: {log['tool']}", expanded=(i == 0)):
                st.json(log["input"])
                st.text(log["output_preview"])
    else:
        st.info("No tool calls yet. Start a conversation!")
