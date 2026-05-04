import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "huggingface")

    HUGGINGFACEHUB_API_TOKEN: str = os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
    HF_MODEL_ID: str = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-72B-Instruct")

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL_ID: str = os.getenv("GROQ_MODEL_ID", "llama-3.3-70b-versatile")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL_ID: str = os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini")

    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    MAGENTO_STOREFRONT_URL: str = os.getenv("MAGENTO_STOREFRONT_URL", "")
    MAGENTO_GRAPHQL_URL: str = os.getenv("MAGENTO_GRAPHQL_URL", "")
    MAGENTO_PAGE_SIZE: int = int(os.getenv("MAGENTO_PAGE_SIZE", "10"))

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    RELOAD: bool = os.getenv("RELOAD", "false").lower() == "true"
    AUTO_INGEST_ON_STARTUP: bool = (
        os.getenv("AUTO_INGEST_ON_STARTUP", "true").lower() == "true"
    )


settings = Settings()
