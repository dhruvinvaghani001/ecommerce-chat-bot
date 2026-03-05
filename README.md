# Ecom Chat - AI-Powered Shopping Assistant

An embeddable LLM-powered chatbot that helps users navigate product listings, get product details, and query company documents through natural language.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Frontend                        │
│  ┌──────────────┐    ┌───────────────────────┐  │
│  │ Demo Website  │    │  Chat Widget (React)  │  │
│  │  (any site)   │◄──│  Embeddable via <script>│ │
│  └──────────────┘    └──────────┬────────────┘  │
└──────────────────────────────────┼───────────────┘
                                   │ WebSocket
┌──────────────────────────────────┼───────────────┐
│                  Backend (Python)                 │
│  ┌───────────────────────────────┼─────────────┐ │
│  │           FastAPI + WebSocket                │ │
│  └───────────────────┬─────────────────────────┘ │
│  ┌───────────────────┼─────────────────────────┐ │
│  │          LangGraph Agent                     │ │
│  │   ┌──────────┬──────────┬──────────────┐    │ │
│  │   │ Product  │ Product  │  Document    │    │ │
│  │   │ Search   │ Details  │  Search(RAG) │    │ │
│  │   └──────────┴──────────┴──────────────┘    │ │
│  └─────────────────────────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  ChromaDB    │  │  HuggingFace / Groq LLM  │  │
│  │ (Vector DB)  │  │  (Inference API)          │  │
│  └──────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python, FastAPI, WebSocket |
| **Agent Framework** | LangGraph (stateful agent orchestration) |
| **LLM** | HuggingFace Inference API or Groq (free) |
| **Embeddings** | sentence-transformers (local) |
| **Vector Store** | ChromaDB (local, no setup) |
| **Frontend** | React 18 + TypeScript + Vite |
| **Embedding** | Single `<script>` tag |

## Features

- **Real-time chat** via WebSocket
- **Product browsing** - search, filter by type/location/price
- **Product details** - detailed view with images and actions
- **Similar products** - find related listings
- **RAG-based Q&A** - answer questions from uploaded documents/PDFs
- **Action buttons** - Quick Reply (triggers chat message), Navigate (opens URL)
- **Embeddable widget** - drop into any website with one script tag

## Quick Start

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys (see Configuration below)

# Ingest documents (optional - for RAG)
python -m app.rag.ingest

# Start the server
python run.py
```

Backend runs at `http://localhost:8000`

### 2. Frontend Setup

```bash
cd frontend/widget

# Install dependencies
npm install

# Start dev server
npm run dev
```

Widget dev server runs at `http://localhost:5173`

### 3. Demo Site

Open `frontend/demo-site/index.html` in a browser (or serve it):

```bash
# Using Python
cd frontend/demo-site
python3 -m http.server 3000
```

Visit `http://localhost:3000`

## Configuration

### LLM Provider

Edit `backend/.env`:

**Option A: HuggingFace (default)**
```
LLM_PROVIDER=huggingface
HUGGINGFACEHUB_API_TOKEN=hf_your_token_here
HF_MODEL_ID=mistralai/Mistral-7B-Instruct-v0.3
```

Get your free token at https://huggingface.co/settings/tokens

**Option B: Groq (recommended - free, faster, better tool calling)**
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL_ID=llama-3.3-70b-versatile
```

Get your free API key at https://console.groq.com

### Adding Documents for RAG

Place `.pdf`, `.txt`, or `.md` files in `backend/documents/`. The system auto-ingests them on startup. You can also manually trigger ingestion:

```bash
POST http://localhost:8000/api/ingest
```

## Embedding the Widget

Add to any HTML page:

```html
<!-- Production (after building) -->
<script src="path/to/ecom-chat-widget.iife.js"></script>
<script>
  EcomChat.init({
    wsUrl: "ws://your-backend.com/ws/chat",
    title: "AI Assistant",
    subtitle: "Online",
    position: "bottom-right"  // or "bottom-left"
  });
</script>
```

Build the widget for production:
```bash
cd frontend/widget
npm run build:widget
# Output: dist/ecom-chat-widget.iife.js
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ws/chat` | WebSocket | Real-time chat |
| `/api/chat` | POST | HTTP chat fallback |
| `/api/ingest` | POST | Trigger document ingestion |
| `/health` | GET | Health check |

## Project Structure

```
ecom-chat/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app + WebSocket
│   │   ├── config.py         # Settings
│   │   ├── models.py         # Pydantic models
│   │   ├── agent/
│   │   │   ├── graph.py      # LangGraph agent
│   │   │   ├── tools.py      # Agent tools
│   │   │   ├── state.py      # Agent state
│   │   │   └── prompts.py    # System prompts
│   │   ├── rag/
│   │   │   ├── ingest.py     # Document ingestion
│   │   │   └── retriever.py  # RAG search
│   │   └── products/
│   │       ├── data.py       # Mock product data
│   │       └── service.py    # Product operations
│   ├── documents/            # Docs for RAG
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── widget/               # Embeddable React chat
│   │   ├── src/
│   │   │   ├── components/   # UI components
│   │   │   ├── hooks/        # useChat WebSocket hook
│   │   │   ├── types/        # TypeScript types
│   │   │   └── styles/       # CSS
│   │   └── package.json
│   └── demo-site/            # Demo website
│       └── index.html
└── README.md
```
