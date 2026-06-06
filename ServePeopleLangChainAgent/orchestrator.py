"""
CEO orchestrator — builds the root agent and exposes the public API.

The CEO is a LangGraph ReAct agent that delegates to five specialist
sub-agents via tool calling.
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from .config import get_model
from .agents import ensure_built, CEO_TOOLS
from .prompts import CEO_PROMPT

# ── Lazy CEO singleton ──────────────────────────────────────────────────────
_ceo_agent = None


def _get_ceo() -> "CompiledStateGraph":
    """Build (once) and return the CEO agent."""
    global _ceo_agent
    if _ceo_agent is None:
        ensure_built()
        _ceo_agent = create_react_agent(get_model(), CEO_TOOLS, prompt=CEO_PROMPT)
    return _ceo_agent


# ── Public API ──────────────────────────────────────────────────────────────

def run(user_input: str) -> str:
    """Run the full multi-agent pipeline on a single user message.

    The CEO may delegate to multiple sub-agents (search → URL read → task →
    quality review → search …) before returning the final answer.
    """
    result = _get_ceo().invoke({"messages": [HumanMessage(content=user_input)]})
    msgs = result.get("messages", [])
    return msgs[-1].content if msgs else "Agent 未返回任何内容。"


async def run_async(user_input: str) -> str:
    """Async version of run()."""
    result = await _get_ceo().ainvoke({"messages": [HumanMessage(content=user_input)]})
    msgs = result.get("messages", [])
    return msgs[-1].content if msgs else "Agent 未返回任何内容。"


def get_ceo_agent():
    """Return the compiled CEO agent (for inspection / advanced use)."""
    return _get_ceo()
