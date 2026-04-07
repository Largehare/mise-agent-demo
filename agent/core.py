"""LangChain agent assembly for the Mise booking assistant."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from config import ANTHROPIC_API_KEY, MODEL_NAME, MAX_TOKENS
from agent.prompts import SYSTEM_PROMPT
from agent.tools import all_tools


class _AgentWrapper:
    """Wraps a LangGraph react agent to expose the same .invoke() interface
    that app.py and main.py expect:
      input:  {"input": str}
      output: {"output": str, "intermediate_steps": [(action, observation), ...]}
    Conversation history is managed internally by LangGraph via MemorySaver.
    """

    def __init__(self, graph):
        self._graph = graph

    def invoke(self, inputs: dict, config: dict | None = None) -> dict:
        session_id = (
            (config or {}).get("configurable", {}).get("session_id", "default")
        )
        thread_config = {"configurable": {"thread_id": session_id}}

        result = self._graph.invoke(
            {"messages": [HumanMessage(content=inputs["input"])]},
            config=thread_config,
        )

        messages = result["messages"]
        raw_content = messages[-1].content if messages else ""
        # Claude sometimes returns a list of content blocks instead of a plain string
        if isinstance(raw_content, list):
            output = "".join(
                block["text"]
                for block in raw_content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            output = raw_content

        # Build intermediate_steps from tool-call/tool-result pairs
        intermediate_steps = []
        for i, msg in enumerate(messages):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    observation = ""
                    for later in messages[i + 1:]:
                        if (
                            isinstance(later, ToolMessage)
                            and later.tool_call_id == tc["id"]
                        ):
                            observation = later.content
                            break

                    class _Action:
                        def __init__(self, tool, tool_input):
                            self.tool = tool
                            self.tool_input = tool_input

                    intermediate_steps.append(
                        (_Action(tc["name"], tc["args"]), observation)
                    )

        return {"output": output, "intermediate_steps": intermediate_steps}


def _build_graph() -> _AgentWrapper:
    llm = ChatAnthropic(
        model=MODEL_NAME,
        anthropic_api_key=ANTHROPIC_API_KEY,
        temperature=0,
        max_tokens=MAX_TOKENS,
        timeout=60,
    )
    graph = create_react_agent(
        llm,
        all_tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
    )
    return _AgentWrapper(graph)


def create_agent() -> _AgentWrapper:
    """Create and return the configured agent (used by app.py)."""
    return _build_graph()


def create_session_agent():
    """Create an agent with conversation memory (used by main.py).
    Returns (agent, store) for API compatibility; store is unused because
    LangGraph manages history internally via MemorySaver.
    """
    return _build_graph(), {}
