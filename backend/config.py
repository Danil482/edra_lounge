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

    # LLM provider:
    #   local    → Ollama on localhost (offline-capable booth default)
    #   remote   → Anthropic Messages API
    #   openai   → OpenAI Chat Completions API
    llm_mode: Literal["local", "remote", "openai"] = "local"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b-instruct"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-7"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    n_min: int = 3
    theta_induce: float = 0.6
    theta_revise: float = 0.5
    recluster_every: int = 3
    cs_window: int = 5

    rng_seed: int = 42
    tick_seconds: int = 20

    db_path: str = "edra_lounge.db"
    embedding_model: str = "all-MiniLM-L6-v2"

    # Phase 3 — live mode (default: live with the `mock` RapidAPI sentinel so
    # the booth boots into the right mode with zero env-vars. Override via .env:
    # LIVE_MODE=false → synthetic auto-play (dev/test). RAPIDAPI_KEY=<real-key>
    # → real LinkedIn fetches against fresh-linkedin-profile-data.p.rapidapi.com.)
    live_mode: bool = True
    rapidapi_key: str = "mock"

    resend_api_key: str = ""
    outreach_from_email: str = "onboarding@resend.dev"
    outreach_from_name: str = "Daniil Onishchenko"

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{PROJECT_ROOT / self.db_path}"


settings = Settings()
