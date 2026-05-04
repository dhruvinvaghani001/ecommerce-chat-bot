# Ecom Chat Backend

This backend is an HTTP-first FastAPI service that wraps a LangGraph shopping agent, a Magento product service, and optional RAG document search.

See [BACKEND_ARCHITECTURE.md](/Users/dhruvinvaghani/Documents/medusa/ecom-chat/backend/BACKEND_ARCHITECTURE.md) for the full backend architecture and configuration reference.

## Runtime entrypoints

- `run.py` starts Uvicorn with `app.server:app`.
- `app/server.py` exposes `GET /`, `GET /health`, `POST /api/chat`, and `POST /api/ingest`.

## Active backend modules

- `app/agent/` contains the LangGraph state, prompt, tools, and graph compilation.
- `app/products/` contains Magento catalog search, filtering, and detail formatting.
- `app/rag/` contains document ingestion and Chroma retrieval.
- `app/config.py` loads environment-driven settings for providers and store access.

## Notes

- The backend currently uses HTTP endpoints, not a WebSocket chat endpoint.
- Product data comes from Magento GraphQL, not local mock data files.
- Documents in `backend/documents/` are optional RAG sources.
