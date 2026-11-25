"""All configuration comes from environment variables."""
import os


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.api_keys = [k.strip() for k in os.getenv("LLM_API_KEYS", "").split(",") if k.strip()]
        self.model = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:////data/app.db")
        self.allowed_origins = [
            o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
        ]
        self.enable_failure_simulation = _bool("ENABLE_FAILURE_SIMULATION")
        self.default_system_prompt = os.getenv(
            "DEFAULT_SYSTEM_PROMPT", "You are a helpful, concise assistant."
        )
        self.request_timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        # Dev/test only: answer with a deterministic mock instead of calling a provider.
        self.mock_llm = _bool("MOCK_LLM")

    @property
    def db_path(self) -> str:
        url = self.database_url
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]  # sqlite:////data/app.db -> /data/app.db
        return url
