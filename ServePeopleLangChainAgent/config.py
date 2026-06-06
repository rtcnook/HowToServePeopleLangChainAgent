"""
Configuration: reads .env and builds only what's configured.

No hardcoded defaults — everything is driven by the .env file.
If a service has no key in .env, it simply won't be available.
"""
import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

load_dotenv()

# ── LangSmith tracing (only if key present) ──────────────────────────────────
_ls_key = os.getenv("LANGSMITH_API_KEY", "")
if _ls_key and len(_ls_key) > 10:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", os.getenv("LANGSMITH_PROJECT", "HowToServePeopleLangChainAgent"))

# ── Provider registry — one entry per supported service ─────────────────────

PROVIDERS = {
    "dashscope": {
        "keys": ["DASHSCOPE_KEY", "DASHSCOPE_API_KEY"],
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen3.7-plus",
        "label": "阿里云百炼",
    },
    "siliconflow": {
        "keys": ["SILICONFLOW_API_KEY"],
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen3.6-35B-A3B",
        "label": "硅基流动",
    },
    "gemini": {
        "keys": ["GOOGLE_API_KEY"],
        "base_url": None,
        "default_model": "gemini-2.5-flash",
        "label": "Google Gemini",
    },
}


def _resolve_key(provider_cfg: dict) -> str:
    """Find the first available API key from the provider's key list."""
    for key_name in provider_cfg["keys"]:
        val = os.getenv(key_name, "").strip()
        if val and len(val) > 10:
            return val
    return ""


def detect_provider() -> str | None:
    """Return the first provider that has a valid key in .env."""
    for name in PROVIDERS:
        if _resolve_key(PROVIDERS[name]):
            return name
    return None


def active_provider() -> str:
    """LLM_PROVIDER from .env, or auto-detect from keys."""
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit and explicit in PROVIDERS:
        return explicit
    detected = detect_provider()
    if detected:
        return detected
    return ""


def is_configured(provider: str) -> bool:
    """Check if a specific provider has its key configured in .env."""
    return bool(_resolve_key(PROVIDERS.get(provider, {})))


# ── Model ───────────────────────────────────────────────────────────────────

def _get_model_name(provider: str) -> str:
    custom = os.getenv("LLM_MODEL", "").strip()
    if custom:
        return custom
    return PROVIDERS.get(provider, {}).get("default_model", "")


# ── Lazy model singleton ────────────────────────────────────────────────────
_model: BaseChatModel | None = None
_active: str = ""


def get_model() -> BaseChatModel:
    """Return the singleton chat model, building it on first call."""
    global _model, _active
    if _model is None:
        _active = active_provider()
        if not _active:
            raise RuntimeError(
                "未找到任何有效的 API Key。请在 .env 中配置 DASHSCOPE_KEY / "
                "SILICONFLOW_API_KEY / GOOGLE_API_KEY 其中之一。"
            )
        _model = _build_model(_active)
    return _model


def _build_model(provider: str) -> BaseChatModel:
    cfg = PROVIDERS[provider]
    model = _get_model_name(provider)
    api_key = _resolve_key(cfg)

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, temperature=0.2)
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            base_url=cfg["base_url"],
            api_key=api_key,
            temperature=0.2,
        )


# ── Status helpers (for CLI display) ────────────────────────────────────────

def provider_label() -> str:
    """Human-readable name of the active provider."""
    name = _active or active_provider()
    cfg = PROVIDERS.get(name, {})
    return cfg.get("label", name or "未配置")


def active_model_name() -> str:
    return _get_model_name(_active or active_provider())


def tavily_available() -> bool:
    return bool(os.getenv("TAVILY_API_KEY", "").strip().startswith("tvly-"))


def langsmith_available() -> bool:
    return bool(_ls_key and len(_ls_key) > 10)
