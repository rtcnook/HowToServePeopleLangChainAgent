"""
Base tools for the HowToServePeopleLangChainAgent system.

Search: Tavily API (requires TAVILY_API_KEY in .env).
"""
import os

from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.tools import tool

load_dotenv()

# ── Web Search (Tavily) ─────────────────────────────────────────────────────

from tavily import TavilyClient

_tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))


@tool
def web_search(query: str) -> str:
    """Search the web for up-to-date information. Returns results with titles, URLs,
    and content snippets. Source attribution is included."""
    resp = _tavily_client.search(query, max_results=5, include_raw_content=False)
    results = resp.get("results", [])
    if not results:
        return f"Tavily 搜索无结果。查询: {query}"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '无标题')}")
        lines.append(f"   URL: {r.get('url', 'N/A')}")
        lines.append(f"   {r.get('content', '')[:400]}")
    return "\n".join(lines)


# ── URL Reader ──────────────────────────────────────────────────────────────

@tool
def read_url(url: str) -> str:
    """Read the full text content of a web page given its URL.
    Use this when the user provides a specific link that needs to be examined.
    Returns the extracted text, or an error message if the page is inaccessible."""
    try:
        loader = WebBaseLoader(url)
        docs = loader.load()
        if not docs:
            return f"Unable to load content from {url}. The page may be empty or blocked."
        content = docs[0].page_content
        if len(content) > 8000:
            content = content[:8000] + "\n\n... [内容已截断，超出 8000 字符]"
        return content
    except Exception as e:
        return f"读取 URL 失败 ({url}): {str(e)}"
