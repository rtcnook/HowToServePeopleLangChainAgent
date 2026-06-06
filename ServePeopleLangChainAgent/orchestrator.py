"""
CEO orchestrator — builds the root agent and exposes the public API.

Two modes:
  - run()        → blocking, returns full answer
  - run_stream() → generator, yields chunks as they arrive
"""
from typing import Iterator

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessageChunk

from .config import get_model
from .agents import ensure_built, CEO_TOOLS
from .prompts import CEO_PROMPT

# ── Lazy CEO singleton ──────────────────────────────────────────────────────
_ceo_agent = None


def _get_ceo() -> "CompiledStateGraph":
    global _ceo_agent
    if _ceo_agent is None:
        ensure_built()
        _ceo_agent = create_react_agent(get_model(), CEO_TOOLS, prompt=CEO_PROMPT)
    return _ceo_agent


# ── Streaming public API ────────────────────────────────────────────────────

_TOOL_LABELS = {
    "delegate_google_search":     "🔍 正在联网搜索 ...",
    "delegate_url_context":       "📄 正在读取网页 ...",
    "delegate_job_search":        "💼 正在检索考公/考编岗位 ...",
    "delegate_match_positions":   "🎯 正在匹配岗位条件 ...",
    "delegate_task":              "📝 正在执行任务 ...",
    "delegate_quality_review":    "✅ 正在审查结果 ...",
}


def run_stream(user_input: str) -> Iterator[str]:
    """Stream the agent's response token by token.

    Yields text chunks. Tool calls are signalled as status lines.
    """
    agent = _get_ceo()

    for chunk, meta in agent.stream(
        {"messages": [HumanMessage(content=user_input)]},
        stream_mode="messages",
    ):
        if isinstance(chunk, AIMessageChunk):
            # -- tool calls (delegation) --
            if chunk.tool_calls:
                for tc in chunk.tool_calls:
                    name = tc.get("name") or tc.get("function", {}).get("name", "")
                    label = _TOOL_LABELS.get(name, f"⚙️ 调用 {name} ..." if name else "⚙️ 正在调用工具 ...")
                    yield f"\n{label}\n"

            # -- text content --
            if chunk.content:
                yield chunk.content


# ── Blocking API (unchanged) ────────────────────────────────────────────────

def run(user_input: str) -> str:
    """Run the full multi-agent pipeline synchronously."""
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
