import os
import json
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "huggingface")

    HUGGINGFACEHUB_API_TOKEN: str = os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
    HF_MODEL_ID: str = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-72B-Instruct")

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL_ID: str = os.getenv("GROQ_MODEL_ID", "llama-3.3-70b-versatile")

    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    CORS_ORIGINS: list[str] = json.loads(
        os.getenv(
            "CORS_ORIGINS",
            '["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5500"]',
        )
    )


settings = Settings()
