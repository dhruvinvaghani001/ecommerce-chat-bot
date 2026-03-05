import json
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.config import settings
from .state import AgentState
from .tools import ALL_TOOLS
from .prompts import SYSTEM_PROMPT


def _get_llm():
    """Create the LLM based on configuration."""
    if settings.LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.GROQ_MODEL_ID,
            api_key=settings.GROQ_API_KEY,
            temperature=0.3,
            max_tokens=2048,
        )
    else:
        from langchain_huggingface import (
            ChatHuggingFace,
            HuggingFaceEndpoint,
        )

        endpoint = HuggingFaceEndpoint(
            repo_id=settings.HF_MODEL_ID,
            huggingfacehub_api_token=settings.HUGGINGFACEHUB_API_TOKEN,
            temperature=0.3,
            max_new_tokens=2048,
        )
        return ChatHuggingFace(llm=endpoint)


def _build_graph() -> StateGraph:
    llm = _get_llm()
    model_with_tools = llm.bind_tools(ALL_TOOLS)
    tool_node = ToolNode(ALL_TOOLS)

    def agent_node(state: AgentState) -> dict:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    def extract_components(state: AgentState) -> dict:
        """After tool execution, parse tool results for UI components."""
        components = list(state.get("components", []))
        messages = state["messages"]

        for msg in messages:
            if not isinstance(msg, ToolMessage):
                continue
            try:
                data = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                continue

            comp_type = data.get("component_type")
            if comp_type:
                components.append({"type": comp_type, "data": data["data"]})

        return {"components": components}

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return "end"

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("extract_components", extract_components)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "extract_components")
    graph.add_edge("extract_components", "agent")

    return graph.compile()


_compiled_graph = None


def get_agent():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph
