"""
Sub-agent builders + delegation tools.

Each sub-agent is a compiled LangGraph ReAct agent.  They are wrapped as
LangChain @tool functions so the CEO can delegate to them naturally.

All agents are lazily built on first use — imports are free.
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from .config import get_model, tavily_available, provider_label
from .tools import web_search, read_url, parse_document, list_documents
from .prompts import (
    GOOGLE_SEARCH_PROMPT,
    URL_CONTEXT_PROMPT,
    JOB_SEARCH_PROMPT,
    TASK_PROMPT,
    QUALITY_PROMPT,
    MATCH_PROMPT,
)

# ── Lazy agent singletons ───────────────────────────────────────────────────
_google_search_agent = None
_url_context_agent = None
_job_search_agent = None
_match_agent = None
_task_agent = None
_quality_agent = None
_built = False


def ensure_built() -> None:
    """Build all five sub-agents (idempotent)."""
    global _built, \
        _google_search_agent, _url_context_agent, \
        _job_search_agent, _match_agent, _task_agent, _quality_agent

    if _built:
        return

    model = get_model()
    print(f"[agents] 初始化 {provider_label()} 模型, 6 个 Agent ...")

    _google_search_agent = create_react_agent(model, [web_search], prompt=GOOGLE_SEARCH_PROMPT)
    _url_context_agent = create_react_agent(model, [read_url], prompt=URL_CONTEXT_PROMPT)
    _job_search_agent = create_react_agent(model, [web_search], prompt=JOB_SEARCH_PROMPT)
    _match_agent = create_react_agent(model, [web_search, parse_document], prompt=MATCH_PROMPT)
    _task_agent = create_react_agent(model, [web_search, read_url], prompt=TASK_PROMPT)
    _quality_agent = create_react_agent(model, [web_search, read_url], prompt=QUALITY_PROMPT)

    _built = True
    print(f"[agents] 就绪。Tavily={'✓' if tavily_available() else '✗ (DuckDuckGo)'}")


# ── Internal helper ─────────────────────────────────────────────────────────

def _invoke(agent, task: str) -> str:
    """Run a sub-agent and return its final text response."""
    result = agent.invoke({"messages": [HumanMessage(content=task)]})
    msgs = result.get("messages", [])
    return msgs[-1].content if msgs else "子 Agent 未返回任何内容。"


# ── Delegation tools (exposed to CEO) ───────────────────────────────────────

@tool
def delegate_google_search(query: str) -> str:
    """Search the web for real-time information. Use this whenever the user asks about
    current events, policies, news, or any topic that requires up-to-date public data.
    The sub-agent will return key findings with source names and dates."""
    return _invoke(_google_search_agent, query)


@tool
def delegate_url_context(url: str) -> str:
    """Read the content of a specific URL and extract relevant facts. Use this when the
    user provides a link and wants its contents analysed or summarised."""
    return _invoke(_url_context_agent, url)


@tool
def delegate_job_search(profile: str) -> str:
    """Search for Chinese civil-service (考公), public-institution (考编), and government
    job postings matching a candidate profile.

    IMPORTANT — pass the FULL user profile verbatim, including: gender, graduation year,
    major, target cities/regions.  The sub-agent will construct focused search queries
    like 「山西 太原 事业单位 招聘 计算机科学与技术」.

    Example profile: 「男，2019年毕业，计算机科学与技术，想找山西太原或汾阳考公考编岗位」"""
    return _invoke(_job_search_agent, profile)


@tool
def delegate_task(task: str) -> str:
    """Execute a concrete task that requires writing, coding, analysis, or producing a
    deliverable.  The sub-agent works independently — give it clear instructions and it
    will return a complete, checkable result.  It can search the web or read URLs if
    needed."""
    return _invoke(_task_agent, task)


@tool
def delegate_quality_review(content: str) -> str:
    """Review an output (draft answer, analysis, search results) for correctness,
    completeness, and logical consistency.  Returns a focused critique: what is wrong,
    what is missing, and how to fix it.  If the content is good, returns a brief
    confirmation with residual risks."""
    return _invoke(_quality_agent, content)


@tool
def delegate_match_positions(profile_and_doc: str) -> str:
    """Match a user profile against recruitment positions from a parsed document.

    Input format (include BOTH parts):
    「用户画像: 男, 2019年毕业, 计算机科学与技术本科, 山西太原
      职位表内容: [parsed document text here]」

    The sub-agent will compare each position's requirements against the user profile
    and return a structured match report with ✓/✗/⚠ per condition."""
    return _invoke(_match_agent, profile_and_doc)


# ── Tool list for the CEO ───────────────────────────────────────────────────

CEO_TOOLS = [
    delegate_google_search,
    delegate_url_context,
    delegate_job_search,
    delegate_match_positions,
    delegate_task,
    delegate_quality_review,
    list_documents,
    parse_document,
]
