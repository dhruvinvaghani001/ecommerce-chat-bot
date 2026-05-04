import json
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.config import settings
from app.products.service import build_filter_prompt_context
from .state import AgentState
from .tools import ALL_TOOLS
from .prompts import SYSTEM_PROMPT


def _state_search_context_block(state: AgentState) -> str:
    lines = ["## Runtime Conversation Search Context"]

    last_context = state.get("last_search_context")
    if last_context:
        lines.append(
            f"- Active search context: {json.dumps(last_context, ensure_ascii=True, sort_keys=True)}"
        )
    else:
        lines.append("- Active search context: none")

    pending_confirmation = state.get("pending_search_confirmation")
    if pending_confirmation:
        lines.append(
            "- Pending confirmation: "
            f"{json.dumps(pending_confirmation, ensure_ascii=True, sort_keys=True)}"
        )
    else:
        lines.append("- Pending confirmation: none")

    return "\n".join(lines)


def _extract_search_context(search_meta: dict | None) -> dict | None:
    if not isinstance(search_meta, dict):
        return None

    attributes: dict[str, object] = {}
    ignored_keys = {
        "query",
        "name",
        "price",
        "minPrice",
        "maxPrice",
        "page",
        "pageSize",
        "unsupportedAttributes",
    }
    for key, value in search_meta.items():
        if key in ignored_keys or value in (None, ""):
            continue
        attributes[key] = value

    context = {
        "query": search_meta.get("query", ""),
        "name": search_meta.get("name", ""),
        "price": search_meta.get("price", ""),
        "minPrice": search_meta.get("minPrice"),
        "maxPrice": search_meta.get("maxPrice"),
        "page": search_meta.get("page", 1),
        "pageSize": search_meta.get("pageSize"),
        "attributes": attributes,
    }

    category = str(attributes.get("category", "")).strip()
    if category:
        context["summary"] = f"category {category}"
    elif str(context["name"]).strip():
        context["summary"] = f"name {context['name']}"
    elif str(context["query"]).strip():
        context["summary"] = f"search {context['query']}"
    elif attributes:
        key, value = next(iter(attributes.items()))
        context["summary"] = f"{key} {value}"
    else:
        context["summary"] = "current results"

    return context


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
    if settings.LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.OPENAI_MODEL_ID,
            api_key=settings.OPENAI_API_KEY,
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
            runtime_prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"{build_filter_prompt_context()}\n\n"
                f"{_state_search_context_block(state)}"
            )
            messages = [SystemMessage(content=runtime_prompt)] + messages

        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    def extract_components(state: AgentState) -> dict:
        """After tool execution, parse tool results for UI components and thread search state."""
        components = list(state.get("components", []))
        messages = state["messages"]
        last_search_context = state.get("last_search_context")
        pending_search_confirmation = state.get("pending_search_confirmation")

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
                if comp_type == "card-list":
                    next_context = _extract_search_context(data.get("search_context"))
                    if next_context is not None:
                        last_search_context = next_context
                        pending_search_confirmation = None

            internal_state = data.get("internal_state")
            if (
                isinstance(internal_state, dict)
                and internal_state.get("type") == "pending_search_confirmation"
            ):
                pending_search_confirmation = internal_state.get("data")

        return {
            "components": components,
            "last_search_context": last_search_context,
            "pending_search_confirmation": pending_search_confirmation,
        }

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
