# Ecom Chat

Embeddable ecommerce chat assistant with a React widget frontend and a Python backend that uses FastAPI, LangGraph, Magento GraphQL, and optional RAG document search.

## Current shape

- `frontend/widget/`
  - embeddable React chat widget
- `frontend/demo-site/`
  - local demo host page
- `backend/`
  - FastAPI backend for `/api/chat`, `/api/ingest`, and `/health`

## Backend architecture

The backend currently runs over HTTP, not WebSocket chat. Product search and product details come from Magento GraphQL, and policy/company answers come from the local RAG document store.

See [backend/CURRENT_ARCHITECTURE.md](/Users/dhruvinvaghani/Documents/medusa/ecom-chat/backend/CURRENT_ARCHITECTURE.md) for the detailed architecture map and [backend/REMOVED_ITEMS.md](/Users/dhruvinvaghani/Documents/medusa/ecom-chat/backend/REMOVED_ITEMS.md) for the cleanup record.

## Backend quick start

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```
