"""
Configuration: environment loading, LangSmith tracing, model factory.

Supports three backends (set LLM_PROVIDER in .env):
  - dashscope    → 阿里云百炼  (needs DASHSCOPE_API_KEY or DASHSCOPE_KEY_P1+P2)
  - siliconflow  → SiliconFlow  (needs SILICONFLOW_API_KEY)
  - gemini       → Google Gemini (needs GOOGLE_API_KEY)
"""
import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

load_dotenv()

# ── LangSmith tracing ───────────────────────────────────────────────────────
if os.getenv("LANGSMITH_API_KEY"):
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", os.getenv("LANGSMITH_PROJECT", "HowToServePeopleLangChainAgent"))

# ── Provider / model ────────────────────────────────────────────────────────
PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
MODEL_NAME = os.getenv("LLM_MODEL", "").strip()

# ── Lazy model singleton ────────────────────────────────────────────────────
_model: BaseChatModel | None = None


def get_model() -> BaseChatModel:
    """Return the singleton chat model, building it on first call."""
    global _model
    if _model is None:
        _model = _build_model()
    return _model


def _build_model() -> BaseChatModel:
    """Create the chat model based on LLM_PROVIDER env var."""
    if PROVIDER == "dashscope":
        return _build_dashscope()
    elif PROVIDER == "siliconflow":
        return _build_siliconflow()
    else:
        return _build_gemini()


def _build_dashscope() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    model = MODEL_NAME or "qwen3.7-plus"
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    # Key may be split into two parts to avoid platform filtering
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        p1 = os.getenv("DASHSCOPE_KEY_P1", "")
        p2 = os.getenv("DASHSCOPE_KEY_P2", "")
        api_key = p1 + p2
    return ChatOpenAI(model=model, base_url=base_url, api_key=api_key, temperature=0.2)


def _build_siliconflow() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    model = MODEL_NAME or "Qwen/Qwen3.6-35B-A3B"
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        temperature=0.2,
    )


def _build_gemini() -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    model = MODEL_NAME or "gemini-2.5-flash"
    return ChatGoogleGenerativeAI(model=model, temperature=0.2)


def tavily_available() -> bool:
    """Check if Tavily search is configured."""
    return bool(os.getenv("TAVILY_API_KEY", "").strip().startswith("tvly-"))
