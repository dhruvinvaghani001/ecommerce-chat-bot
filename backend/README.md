# Ecom Chat Backend

Backend for the Ecom Chat AI Agent — a real estate chatbot powered by LangGraph, LangChain, and FastAPI.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Architecture Diagram](#architecture-diagram)
- [Request Flow](#request-flow)
- [LangGraph Structure](#langgraph-structure)
- [Directory Structure](#directory-structure)
- [Guide: Changing Actions, Trigger Messages & Values](#guide-changing-actions-trigger-messages--values)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ECOM CHAT BACKEND                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────────┐   │
│  │   FastAPI   │     │  LangGraph       │     │  Data / External            │   │
│  │   Server    │────▶│  Agent           │────▶│  - Products (data.py)       │   │
│  │  (server.py)│     │  (graph.py)      │     │  - Vector Store (ChromaDB)  │   │
│  └─────────────┘     └────────┬─────────┘     └─────────────────────────────┘   │
│         │                     │                                                   │
│         │                     │                                                   │
│         ▼                     ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Components                                                               │    │
│  │  • agent/     → LLM, Tools, Prompts, State                                │    │
│  │  • rag/       → Document ingestion, Vector search                         │    │
│  │  • products/  → Product service, Actions, Data                             │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Diagram

### High-Level Flow

```
┌──────────────┐     POST /api/chat      ┌──────────────────────────────────────────────────────────┐
│   Frontend   │ ──────────────────────▶ │  FastAPI Server                                           │
│   Widget     │     { content, thread_id }│  - Validates request                                      │
└──────────────┘                         │  - Loads thread messages                                   │
        │                                │  - Invokes LangGraph agent                                 │
        │                                └─────────────────────────┬──────────────────────────────────┘
        │                                                          │
        │                                                          ▼
        │                                ┌──────────────────────────────────────────────────────────┐
        │                                │  LangGraph Agent (Compiled Graph)                         │
        │                                │                                                           │
        │                                │   ┌─────────┐    tool_calls?    ┌─────────┐               │
        │                                │   │  Agent  │ ──────yes────────▶│  Tools  │               │
        │                                │   │  Node   │                   │  Node   │               │
        │                                │   └────┬────┘                   └────┬────┘               │
        │                                │        │ no                          │                    │
        │                                │        │                             ▼                    │
        │                                │        │                    ┌─────────────────┐          │
        │                                │        │                    │ extract_        │          │
        │                                │        │                    │ components     │          │
        │                                │        │                    └────────┬────────┘          │
        │                                │        │                             │                   │
        │                                │        │                             │ loop back         │
        │                                │        │                             └──────────▶ Agent  │
        │                                │        │                                 (if more tools) │
        │                                │        ▼                                                    │
        │                                │   ┌─────────┐                                               │
        │                                │   │   END   │                                               │
        │                                │   └─────────┘                                               │
        │                                └─────────────────────────┬──────────────────────────────────┘
        │                                                          │
        │                                ┌──────────────────────────┴─────────────────────────────────┐
        │                                │  Server post-processing                                    │
        │                                │  - Extract components from ToolMessages                     │
        │                                │  - Deduplicate, filter empty card-lists                     │
        │                                │  - Return { content, components, thread_id }                │
        │                                └─────────────────────────┬──────────────────────────────────┘
        │                                                          │
        ◀──────────────────────────────────────────────────────────┘
                    { type, content, components, thread_id }
```

---

## Request Flow

1. **Client** sends `POST /api/chat` with `{ content: "user message", thread_id?: "uuid" }`.
2. **Server** appends `HumanMessage` to thread and invokes `agent.ainvoke(...)`.
3. **LangGraph** runs the graph:
   - **agent** node: LLM receives messages + system prompt, decides whether to call a tool.
   - **tools** node: Runs the selected tool (e.g. `search_products`, `get_product_details`).
   - **extract_components** node: Parses tool JSON output for `component_type` and `data`.
   - Loop: If the LLM made tool calls, control returns to **agent**; otherwise **END**.
4. **Server** extracts the final AI text and components from the new messages, deduplicates, and returns JSON.
5. **Client** renders the text and UI components (card-list, card-detail).

---

## LangGraph Structure

### What is LangGraph?

LangGraph extends LangChain with **stateful, cyclic graphs**. The agent is a directed graph where:

- **Nodes** are Python functions that receive and return state updates.
- **Edges** define transitions; **conditional edges** choose the next node based on state.
- **State** is a shared TypedDict (here: `messages`, `components`, `thread_id`).

### Our Graph Definition

Defined in `app/agent/graph.py`:

```
                    ┌─────────────────────────────────────────────────────┐
                    │                 LangGraph StateGraph                  │
                    │                                                       │
                    │  State: AgentState                                    │
                    │  - messages: list (append-only via add_messages)      │
                    │  - components: list[dict]                             │
                    │  - thread_id: str                                     │
                    └─────────────────────────────────────────────────────┘

    Entry ──▶ agent ──┬── should_continue? ── "tools" ──▶ tools ──▶ extract_components ──▶ agent
                      │
                      └── "end" ──▶ END
```

### Nodes

| Node | Function | Purpose |
|------|----------|---------|
| **agent** | `agent_node()` | Injects system prompt, calls LLM with tools. Returns `AIMessage` (with or without `tool_calls`). |
| **tools** | `ToolNode(ALL_TOOLS)` | Executes tool calls from the last `AIMessage`, returns `ToolMessage` per call. |
| **extract_components** | `extract_components()` | Scans `ToolMessage` contents for `component_type` + `data`, appends to `components`. |

### Conditional Edge

```python
def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"   # LLM wants to call tools
    return "end"         # LLM is done, final answer
```

### State Reducer: `add_messages`

`messages` uses `add_messages` as a reducer. When a node returns `{"messages": [new_msg]}`, the new message is **appended** to the list instead of replacing it. This keeps full conversation history.

---

## Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py              # Env vars, LLM/embedding settings
│   ├── server.py              # FastAPI app, /api/chat, /api/ingest
│   │
│   ├── agent/
│   │   ├── graph.py           # LangGraph definition, get_agent()
│   │   ├── state.py           # AgentState TypedDict
│   │   ├── prompts.py         # SYSTEM_PROMPT
│   │   └── tools.py           # LangChain @tool functions, ALL_TOOLS
│   │
│   ├── products/
│   │   ├── data.py            # PRODUCTS list (raw product data)
│   │   └── service.py         # search_products, get_product_by_slug, get_similar_products
│   │                          # + _build_actions() for card actions
│   │
│   └── rag/
│       ├── ingest.py          # Document loading, chunking, ChromaDB ingestion
│       └── retriever.py       # Vector similarity search
│
├── documents/                 # PDFs, TXT, MD for RAG
├── chroma_db/                 # ChromaDB persist directory (created at runtime)
├── run.py                     # Uvicorn entry point
├── requirements.txt
└── README.md
```

---

## Guide: Changing Actions, Trigger Messages & Values

When you want to customize what buttons appear on product cards, what messages are sent when a user clicks them, or what values the agent receives — you change the **actions** and their **instructions**.

---

### 1. Where Actions Are Defined

**File:** `app/products/service.py`

Actions are built in two places:

1. **Product listing cards** (search results, similar products) — `_build_actions()` in `service.py`
2. **Product detail cards** — inline in `get_product_by_slug()` in `service.py`

---

### 2. Action Structure

Each action has:

- `text` — Button label shown in the UI (e.g. "Get Details", "Show Similar")
- `icon` — Icon identifier for the frontend (`"quickreply"`, `"similar"`, `"redirect"`)
- `instructions` — Array of instruction objects that define behavior

**Instruction types:**

| Type | Purpose | Options |
|------|---------|---------|
| `quick_reply` | Sends a message to the chat (triggers agent) | `message`, `value` |
| `navigate` | Opens a URL in a new tab | `value` (URL) |

---

### 3. Changing Actions for Product Listing Cards

**File:** `app/products/service.py` → `_build_actions(product)`

Example:

```python
def _build_actions(product: dict) -> list[dict]:
    return [
        {
            "text": "Get Details",           # ← Button label
            "icon": "quickreply",
            "instructions": [
                {
                    "type": "quick_reply",
                    "options": {
                        "message": f"Get Details of {product['title']}",   # Display text
                        "value": f"Get Details of {product['slug']}",      # Sent to agent
                    },
                }
            ],
        },
        {
            "text": "Show Similar",
            "icon": "similar",
            "instructions": [
                {
                    "type": "quick_reply",
                    "options": {
                        "message": f"Get similar products to {product['title']}",
                        "value": f"Get similar products to type:{product['type']}",  # Agent parses this
                    },
                }
            ],
        },
        {
            "text": "View",
            "icon": "redirect",
            "instructions": [
                {
                    "type": "navigate",
                    "options": {
                        "value": f"https://{DOMAIN}/product/{product['slug']}",  # URL to open
                    },
                }
            ],
        },
    ]
```

**To change:**

- **Button label:** Edit `"text"`.
- **Message shown in chat when clicked:** Edit `options["message"]`.
- **Value sent to the agent:** Edit `options["value"]`. The agent uses this (e.g. `"Get Details of serge33-luxury-villa"`) to call `get_product_details(slug)`.
- **Add/remove actions:** Add or remove dicts in the returned list.
- **Change icon:** Use `"quickreply"`, `"similar"`, or `"redirect"` (must match frontend `getActionIcon`).

---

### 4. Changing Actions for Product Detail Cards

**File:** `app/products/service.py` → `get_product_by_slug()` → `"actions"` list

Example:

```python
"actions": [
    {
        "text": "Contact Agent",
        "icon": "redirect",
        "instructions": [
            {
                "type": "navigate",
                "options": {
                    "value": f"https://{DOMAIN}/contact?product={p['slug']}",
                },
            }
        ],
    },
    {
        "text": "Show Similar",
        "icon": "similar",
        "instructions": [
            {
                "type": "quick_reply",
                "options": {
                    "message": f"Get similar products to {p['title']}",
                    "value": f"Get similar products to type:{p['type']}",
                },
            }
        ],
    },
    {
        "text": "View",
        "icon": "redirect",
        "instructions": [
            {
                "type": "navigate",
                "options": {
                    "value": f"https://{DOMAIN}/product/{p['slug']}",
                },
            }
        ],
    },
]
```

Same structure as listing cards: change `text`, `message`, `value`, or add/remove actions.

---

### 5. Matching Agent Behavior to New Triggers

The agent decides which tool to call based on the user message (the `value` sent from the quick reply).

**File:** `app/agent/prompts.py` — Update the system prompt if you add new triggers.

**File:** `app/agent/tools.py` — The tools parse the message content. For example, `get_similar_products` strips `"type:"` from the argument:

```python
ptype = product_type.replace("type:", "").strip()
```

If you change the trigger format (e.g. `"similar: villa"`), update this parsing and the prompt instructions.

---

### 6. Frontend Mapping

The frontend reads `action.instructions` and:

- For `quick_reply`: calls `onQuickReply(message, value)` → sends `value` to `/api/chat`.
- For `navigate`: opens `options["value"]` in a new tab.

Icons are resolved in `frontend/widget/src/components/Icons.tsx` → `getActionIcon(icon)`.

---

### 7. Quick Reference

| What to change | File | Location |
|----------------|------|----------|
| Listing card actions (labels, messages, values) | `app/products/service.py` | `_build_actions()` |
| Detail card actions | `app/products/service.py` | `get_product_by_slug()` → `"actions"` |
| Base URL for product/contact links | `app/products/service.py` | `DOMAIN = "example-realestate.com"` |
| How the agent interprets user messages | `app/agent/prompts.py` | `SYSTEM_PROMPT` |
| Tool logic / parsing of trigger values | `app/agent/tools.py` | Individual tool functions |
| New action icons | `frontend/widget/src/components/Icons.tsx` | `getActionIcon()` |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `huggingface` | `huggingface` or `groq` |
| `HUGGINGFACEHUB_API_TOKEN` | - | HuggingFace API key |
| `HF_MODEL_ID` | `Qwen/Qwen2.5-72B-Instruct` | HuggingFace model |
| `GROQ_API_KEY` | - | Groq API key |
| `GROQ_MODEL_ID` | `llama-3.3-70b-versatile` | Groq model |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | RAG embeddings |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage path |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check, returns `{ status, provider }` |
| POST | `/api/chat` | Chat with agent; body: `{ content, thread_id? }` |
| POST | `/api/ingest` | Trigger document ingestion for RAG |
