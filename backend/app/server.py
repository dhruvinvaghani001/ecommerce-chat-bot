import asyncio
import json
import logging
import traceback
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.graph import get_agent
from app.config import settings
from app.products.service import refresh_filter_options_cache
from app.rag.ingest import ingest_documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Ecom Chat AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

threads: dict[str, dict] = {}


@app.on_event("startup")
async def startup():
    try:
        refresh_filter_options_cache()
    except Exception:
        logging.exception("initial filter options refresh failed")

    if not settings.AUTO_INGEST_ON_STARTUP:
        print("Automatic document ingestion disabled.")
        return

    async def _ingest_in_background():
        print("Ingesting documents into vector store...")
        try:
            count = await asyncio.to_thread(ingest_documents)
            print(f"Document ingestion complete: {count} chunks.")
        except Exception as e:
            print(f"Document ingestion skipped: {e}")

    asyncio.create_task(_ingest_in_background())


@app.get("/")
async def root():
    return {"message": "Welcome to Ecom Chat AI Agent"}


@app.get("/health")
async def health():
    return {"status": "ok", "provider": settings.LLM_PROVIDER}


def _parse_component(content: str) -> dict | None:
    """Try to extract a UI component from tool output JSON."""
    try:
        data = json.loads(content)
        comp_type = data.get("component_type")
        if comp_type:
            return {"type": comp_type, "data": data["data"]}
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return None


@app.post("/api/chat")
async def http_chat(request: dict):
    user_message = request.get("content", "")
    thread_id = request.get("thread_id") or str(uuid.uuid4())

    if thread_id not in threads:
        threads[thread_id] = {
            "messages": [],
            "last_search_context": None,
            "pending_search_confirmation": None,
        }

    thread_state = threads[thread_id]
    thread_state["messages"].append(HumanMessage(content=user_message))

    agent = get_agent()

    try:
        prev_msg_count = len(thread_state["messages"]) - 1

        result = await agent.ainvoke(
            {
                "messages": thread_state["messages"],
                "components": [],
                "thread_id": thread_id,
                "last_search_context": thread_state.get("last_search_context"),
                "pending_search_confirmation": thread_state.get(
                    "pending_search_confirmation"
                ),
            }
        )

        thread_state["messages"] = result["messages"]
        thread_state["last_search_context"] = result.get("last_search_context")
        thread_state["pending_search_confirmation"] = result.get(
            "pending_search_confirmation"
        )

        new_messages = result["messages"][prev_msg_count:]

        components = []
        seen = set()
        for msg in new_messages:
            if not isinstance(msg, ToolMessage):
                continue
            comp = _parse_component(msg.content)
            if not comp:
                continue
            if comp["type"] == "card-list":
                items = comp.get("data", {}).get("items", [])
                if not items:
                    continue
            key = (comp["type"], json.dumps(comp["data"], sort_keys=True))
            if key in seen:
                continue
            seen.add(key)
            components.append(comp)

        if len(components) > 1:
            components = [components[-1]]

        ai_content = ""
        for msg in reversed(new_messages):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                ai_content = msg.content
                break

        return {
            "type": "assistant_message",
            "content": ai_content,
            "components": components,
            "thread_id": thread_id,
        }

    except Exception as e:
        traceback.print_exc()
        logging.exception("chat request failed")
        return {
            "type": "error",
            "content": "Failed to fetch products currently.",
            "thread_id": thread_id,
        }


@app.post("/api/ingest")
async def trigger_ingest():
    """Manually trigger document ingestion."""
    count = ingest_documents()
    return {"status": "ok", "chunks_ingested": count}


@app.post("/api/filters/refresh")
async def trigger_filter_refresh():
    """Manually refresh cached Magento filter metadata."""
    data = refresh_filter_options_cache()
    return {"status": "ok", **data}
