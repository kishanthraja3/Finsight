import os
import time
import threading
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "backend" / "vectorstore" / "chroma_db"))
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    NEXT_PUBLIC_API_BASE_URL: str = os.getenv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000")
    ALPHA_VANTAGE_MAX_PER_MINUTE: int = int(os.getenv("ALPHA_VANTAGE_MAX_PER_MINUTE", "5"))
    ALPHA_VANTAGE_MAX_PER_DAY: int = int(os.getenv("ALPHA_VANTAGE_MAX_PER_DAY", "25"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "8"))
    
    DOCUMENTS_DIR: Path = BASE_DIR / "data" / "documents"
    CACHE_DIR: Path = BASE_DIR / "backend" / "cache" / "alpha_vantage_cache"
    
    # Model configuration - Primary: 120b/20b, Fallback: qwen/qwen3.8-27b on rate-limit
    MODEL_PLANNER: str = os.getenv("MODEL_PLANNER", "openai/gpt-oss-120b")
    MODEL_GAP_FILL: str = os.getenv("MODEL_GAP_FILL", "openai/gpt-oss-20b")
    MODEL_RISK: str = os.getenv("MODEL_RISK", "openai/gpt-oss-120b")
    MODEL_SYNTHESIS: str = os.getenv("MODEL_SYNTHESIS", "openai/gpt-oss-120b")
    MODEL_CRITIC: str = os.getenv("MODEL_CRITIC", "openai/gpt-oss-120b")
    MODEL_REPLANNER_FAST: str = os.getenv("MODEL_REPLANNER_FAST", "openai/gpt-oss-20b")
    MODEL_REPLANNER_COMPLEX: str = os.getenv("MODEL_REPLANNER_COMPLEX", "openai/gpt-oss-120b")
    MODEL_FALLBACK: str = os.getenv("MODEL_FALLBACK", "qwen/qwen3.8-27b")

    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "openai/gpt-oss-120b")
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Mock Data Control: mock market/news data allowed ONLY in explicit test-fixture mode
    ALLOW_MOCK_DATA: bool = os.getenv("ALLOW_MOCK_DATA", "false").lower() == "true"

    # Telemetry and Execution Budgets
    MAX_LLM_CALLS_PER_RUN: int = int(os.getenv("MAX_LLM_CALLS_PER_RUN", "15"))
    MAX_RUN_TIME_SECONDS: int = int(os.getenv("MAX_RUN_TIME_SECONDS", "180"))
    LLM_CLIENT_MAX_RETRIES: int = int(os.getenv("LLM_CLIENT_MAX_RETRIES", "1"))

    class Config:
        arbitrary_types_allowed = True

settings = Settings()

# Ensure directories exist
Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)

class SharedRateLimiter:
    """Thread-safe rate limiter shared across Market Data and News agents for Alpha Vantage."""
    def __init__(self, max_per_minute: int, max_per_day: int):
        self.max_per_minute = max_per_minute
        self.max_per_day = max_per_day
        self.minute_timestamps: list[float] = []
        self.day_timestamps: list[float] = []
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.time()
            # Clean old timestamps
            self.minute_timestamps = [t for t in self.minute_timestamps if now - t < 60.0]
            self.day_timestamps = [t for t in self.day_timestamps if now - t < 86400.0]

            if len(self.day_timestamps) >= self.max_per_day:
                raise RuntimeError(f"Alpha Vantage daily rate limit reached ({self.max_per_day}/day). Use cached data.")

            if len(self.minute_timestamps) >= self.max_per_minute:
                # Sleep until the oldest call in the last minute has expired
                sleep_duration = 60.0 - (now - self.minute_timestamps[0]) + 0.1
                if sleep_duration > 0:
                    time.sleep(sleep_duration)
                    now = time.time()
                    self.minute_timestamps = [t for t in self.minute_timestamps if now - t < 60.0]

            self.minute_timestamps.append(now)
            self.day_timestamps.append(now)

rate_limiter = SharedRateLimiter(
    max_per_minute=settings.ALPHA_VANTAGE_MAX_PER_MINUTE,
    max_per_day=settings.ALPHA_VANTAGE_MAX_PER_DAY
)
