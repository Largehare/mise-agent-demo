"""LangChain agent assembly for the Mise booking assistant."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from config import ANTHROPIC_API_KEY, MODEL_NAME, MAX_TOKENS
from agent.prompts import SYSTEM_PROMPT
from agent.tools import all_tools


def create_agent() -> AgentExecutor:
    """Create and return the configured LangChain agent executor."""
    llm = ChatAnthropic(
        model=MODEL_NAME,
        anthropic_api_key=ANTHROPIC_API_KEY,
        temperature=0,
        max_tokens=MAX_TOKENS,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, all_tools, prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=all_tools,
        verbose=True,
        max_iterations=5,
        return_intermediate_steps=True,
    )

    return executor


def create_session_agent():
    """Create an agent with conversation memory for a chat session."""
    executor = create_agent()

    # In-memory chat history store keyed by session_id
    store = {}

    def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
        if session_id not in store:
            store[session_id] = InMemoryChatMessageHistory()
        return store[session_id]

    agent_with_history = RunnableWithMessageHistory(
        executor,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    return agent_with_history, store
