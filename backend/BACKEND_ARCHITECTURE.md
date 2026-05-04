# Backend Architecture

## Summary

This backend is a FastAPI service with one LangGraph shopping agent, one Magento catalog layer, and optional RAG document retrieval.

Runtime flow:

```text
frontend widget
  -> POST /api/chat
  -> app.server.http_chat
  -> app.agent.graph.get_agent().ainvoke
  -> runtime prompt
     = base system prompt
     + live storefront filter catalog
     + per-thread search context
  -> tool call
     -> app.products.service for Magento work
     -> or app.rag.retriever for document search
  -> assistant text + optional UI component payload
```

## Runtime Modules

- `run.py`
  Starts Uvicorn with `app.server:app`.

- `app/server.py`
  Owns FastAPI routes, startup hooks, in-memory thread state, and response shaping.

- `app/config.py`
  Loads all environment-driven runtime settings.

- `app/agent/prompts.py`
  Defines the single system prompt and response rules.

- `app/agent/state.py`
  Defines LangGraph state:
  - `messages`
  - `components`
  - `thread_id`
  - `last_search_context`
  - `pending_search_confirmation`

- `app/agent/graph.py`
  Builds the LangGraph graph, injects runtime prompt context, and persists search/component state derived from tool outputs.

- `app/agent/tools.py`
  Exposes the active tools:
  - `search_products`
  - `prepare_search_confirmation`
  - `get_product_details`
  - `get_similar_products`
  - `search_documents`

- `app/products/service.py`
  Handles Magento GraphQL access, cached filter metadata, deterministic filter resolution, list/detail formatting, pagination, and runtime filter prompt generation.

- `app/rag/ingest.py`
  Ingests local documents into Chroma.

- `app/rag/retriever.py`
  Retrieves relevant document chunks for FAQ, policy, and company questions.

## HTTP API

- `GET /`
  Welcome response.

- `GET /health`
  Health response with active provider.

- `POST /api/chat`
  Main assistant endpoint.

- `POST /api/ingest`
  Manual document ingestion.

- `POST /api/filters/refresh`
  Manual Magento filter cache refresh.

## Thread State

Each thread is process-local and stored in memory inside `app.server`.

- `messages`
  Full LangChain/LangGraph message history.

- `last_search_context`
  Most recent successful normalized product-search context, including query, price, and applied attributes like category or size.

- `pending_search_confirmation`
  Temporary state used when the LLM asks whether a short follow-up filter should apply to the same category/search or a different one.

## Product Search Design

- Magento `products.aggregations` is the source of truth for live filter options.
- The only local alias is:
  - `category` -> `category_uid`
- The agent passes human-readable labels in `attributes`.
- The backend maps labels to Magento GraphQL values deterministically.
- Unsupported filters return a validation response with one short clarification question.
- Pagination replays the exact applied filters through internal `PAGINATE_PRODUCTS ...` commands.

## Configuration

Environment variables used by `app/config.py`:

- `LLM_PROVIDER`
  Supported values: `huggingface`, `groq`, `openai`

- `HUGGINGFACEHUB_API_TOKEN`
- `HF_MODEL_ID`

- `GROQ_API_KEY`
- `GROQ_MODEL_ID`

- `OPENAI_API_KEY`
- `OPENAI_MODEL_ID`

- `EMBEDDING_MODEL`
  Embedding model for document ingestion/retrieval.

- `CHROMA_PERSIST_DIR`
  Chroma persistence directory.

- `MAGENTO_STOREFRONT_URL`
  Storefront base URL for product links.

- `MAGENTO_GRAPHQL_URL`
  Magento GraphQL endpoint for filters and products.

- `MAGENTO_PAGE_SIZE`
  Default result page size.

- `HOST`
- `PORT`
- `RELOAD`
- `AUTO_INGEST_ON_STARTUP`

Example values are defined in [backend/.env.example](/Users/dhruvinvaghani/Documents/medusa/ecom-chat/backend/.env.example).

## Current Architecture Decisions

- HTTP-only chat transport.
- Process-local in-memory thread storage.
- Magento is the live catalog source of truth.
- RAG is optional and document-backed through Chroma.
- The LLM handles conversational clarification.
- Backend filter execution and pagination remain deterministic.
- UI cards are returned as structured tool payloads.
