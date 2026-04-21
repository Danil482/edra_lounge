from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_mode: Literal["local", "remote"] = "local"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b-instruct"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-7"

    n_min: int = 5
    theta_induce: float = 0.6
    theta_revise: float = 0.5
    recluster_every: int = 3
    cs_window: int = 5

    rng_seed: int = 42
    tick_seconds: int = 20

    db_path: str = "edra_lounge.db"
    embedding_model: str = "all-MiniLM-L6-v2"

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{PROJECT_ROOT / self.db_path}"


settings = Settings()
