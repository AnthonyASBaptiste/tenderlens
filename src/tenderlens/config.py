from pydantic import BaseModel
import os

class Settings(BaseModel):
    app_name: str = "TenderLens T&T"
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/tenderlens.db")
    storage_dir: str = os.getenv("STORAGE_DIR", "data/tenders")
    
    # Gemma / LLM Backend (Supports OpenRouter, Groq, HuggingFace, or local Ollama)
    llm_api_base: str = os.getenv("LLM_API_BASE", "http://localhost:11434/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "gemma2:9b")
    
    # Temporal Config
    temporal_host: str = os.getenv("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace: str = os.getenv("TEMPORAL_NAMESPACE", "default")
    temporal_api_key: str = os.getenv("TEMPORAL_API_KEY", "")
    temporal_task_queue: str = "tenderlens-followthrough-queue"
    
    # WhatsApp Webhook Config
    whatsapp_verify_token: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "tenderlens_dev_token")
    whatsapp_api_token: str = os.getenv("WHATSAPP_API_TOKEN", "")
    whatsapp_phone_number_id: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

settings = Settings()
