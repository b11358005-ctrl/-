"""Local configuration manager with Fernet-encrypted API key persistence."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from pydantic import BaseModel, Field


SUPPORTED_PROVIDERS = (
    "openai",
    "anthropic",
    "gemini",
    "deepseek",
    "ollama",
    "openai_compatible",
)

ALL_SECRET_KEYS = (
    "openai",
    "anthropic",
    "gemini",
    "deepseek",
    "ollama",
    "openai_compatible",
    "tavily",
)

DEFAULT_BASE_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama": "http://localhost:11434/v1",
    "openai_compatible": "https://openrouter.ai/api/v1",
}

SUGGESTED_MODELS: Dict[str, list[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o", "o3-mini", "gpt-4.1-mini", "gpt-4.1"],
    "anthropic": [
        "claude-3-7-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-sonnet-4-20250514",
    ],
    "gemini": ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "ollama": ["qwen2.5:14b", "llama3.1:8b", "deepseek-r1:14b", "gemma3:12b"],
    "openai_compatible": ["meta-llama/llama-3.3-70b-instruct", "qwen/qwen-2.5-72b-instruct"],
}

ENV_KEY_MAP: Dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openai_compatible": "CUSTOM_OPENAI_API_KEY",
    "tavily": "TAVILY_API_KEY",
}


def get_app_base_dir() -> Path:
    """Resolve writable app root directory for both dev mode and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        # Handle macOS .app bundle: MyApp.app/Contents/MacOS/MyApp
        if sys.platform == "darwin" and exe_dir.name == "MacOS" and exe_dir.parent.name == "Contents":
            candidate = exe_dir.parent.parent.parent
        else:
            candidate = exe_dir

        if os.access(candidate, os.W_OK):
            return candidate
        fallback = Path.home() / "StockMultiAgentDesktop"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    return Path(__file__).resolve().parents[2]


def get_config_dir() -> Path:
    path = get_app_base_dir() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    path = get_app_base_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


class AgentModelConfig(BaseModel):
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    max_tokens: int = Field(default=8192, ge=256, le=32768)


class AnalysisPreferences(BaseModel):
    history_years: int = Field(default=2, ge=1, le=5)
    news_lookback_days: int = Field(default=10, ge=3, le=30)
    cache_ttl_minutes: int = Field(default=60, ge=0, le=1440)
    report_language: str = "zh-TW"


class AppSettings(BaseModel):
    base_urls: Dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_BASE_URLS))
    agent_models: Dict[str, AgentModelConfig] = Field(
        default_factory=lambda: {
            "orchestrator": AgentModelConfig(provider="gemini", model="gemini-2.5-flash", temperature=0.2, max_tokens=8192),
            "past_agent": AgentModelConfig(provider="gemini", model="gemini-2.5-flash", temperature=0.15, max_tokens=8192),
            "present_agent": AgentModelConfig(provider="gemini", model="gemini-2.5-flash", temperature=0.15, max_tokens=8192),
            "future_agent": AgentModelConfig(provider="gemini", model="gemini-2.5-flash", temperature=0.3, max_tokens=8192),
            "risk_agent": AgentModelConfig(provider="gemini", model="gemini-2.5-flash", temperature=0.2, max_tokens=8192),
        }
    )
    preferences: AnalysisPreferences = Field(default_factory=AnalysisPreferences)
    encrypted_api_keys: Dict[str, str] = Field(default_factory=dict)


@dataclass
class ResolvedRuntimeSettings:
    settings: AppSettings
    api_keys: Dict[str, str]


class ConfigManager:
    """Handles encrypted local persistence of settings.json and API keys."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or get_config_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.config_dir / "settings.json"
        self.key_path = self.config_dir / ".key"

        # Load optional .env from app base dir without overriding OS env
        env_file = get_app_base_dir() / ".env"
        if env_file.exists():
            load_dotenv(dotenv_path=env_file, override=False)

    def _get_or_create_fernet(self) -> Fernet:
        if self.key_path.exists():
            raw_key = self.key_path.read_bytes().strip()
        else:
            raw_key = Fernet.generate_key()
            self.key_path.write_bytes(raw_key)
            if os.name == "posix":
                os.chmod(self.key_path, 0o600)
        return Fernet(raw_key)

    def _encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        fernet = self._get_or_create_fernet()
        return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def _decrypt(self, token: str) -> str:
        if not token:
            return ""
        try:
            fernet = self._get_or_create_fernet()
            return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            return ""

    def load(self) -> ResolvedRuntimeSettings:
        if self.settings_path.exists():
            try:
                raw_data: Dict[str, Any] = json.loads(self.settings_path.read_text(encoding="utf-8"))
                settings = AppSettings.model_validate(raw_data)
            except Exception:
                settings = AppSettings()
        else:
            settings = AppSettings()

        # Ensure all default base URLs and agent roles exist
        for provider, url in DEFAULT_BASE_URLS.items():
            settings.base_urls.setdefault(provider, url)
        default_agents = AppSettings().agent_models
        for role, cfg in default_agents.items():
            settings.agent_models.setdefault(role, cfg)

        # Decrypt saved keys and optionally backfill from .env if missing
        api_keys: Dict[str, str] = {}
        for key_name in ALL_SECRET_KEYS:
            encrypted_val = settings.encrypted_api_keys.get(key_name, "")
            decrypted = self._decrypt(encrypted_val)
            if not decrypted and key_name in ENV_KEY_MAP:
                decrypted = os.getenv(ENV_KEY_MAP[key_name], "").strip()
            api_keys[key_name] = decrypted

        # Allow .env custom base URL override if settings still hold default
        ollama_env = os.getenv("OLLAMA_BASE_URL", "").strip()
        if ollama_env and settings.base_urls.get("ollama") == DEFAULT_BASE_URLS["ollama"]:
            settings.base_urls["ollama"] = ollama_env
        custom_env_url = os.getenv("CUSTOM_OPENAI_BASE_URL", "").strip()
        if custom_env_url and settings.base_urls.get("openai_compatible") == DEFAULT_BASE_URLS["openai_compatible"]:
            settings.base_urls["openai_compatible"] = custom_env_url

        if not self.settings_path.exists():
            self.save(settings, api_keys)

        return ResolvedRuntimeSettings(settings=settings, api_keys=api_keys)

    def save(self, settings: AppSettings, api_keys: Dict[str, str]) -> None:
        encrypted_map: Dict[str, str] = {}
        for key_name in ALL_SECRET_KEYS:
            val = api_keys.get(key_name, "").strip()
            encrypted_map[key_name] = self._encrypt(val) if val else ""

        settings.encrypted_api_keys = encrypted_map
        payload = settings.model_dump(mode="json")
        self.settings_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if os.name == "posix":
            os.chmod(self.settings_path, 0o600)
