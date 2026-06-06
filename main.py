"""
HowToServePeopleLangChainAgent
═══════════════════════════════

Usage: uv run main.py
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from ServePeopleLangChainAgent.config import (
    PROVIDERS,
    is_configured,
    active_provider,
    provider_label,
    active_model_name,
    tavily_available,
    langsmith_available,
)

# ── Validate ────────────────────────────────────────────────────────────────

_active = active_provider()
if not _active:
    print("⚠️  未找到任何有效的 API Key。")
    print()
    print("请在 .env 中配置以下任一服务的 Key：")
    for name, cfg in PROVIDERS.items():
        print(f"  {cfg['label']:12s} →  {cfg['keys'][0]}=***")
    sys.exit(1)

from ServePeopleLangChainAgent import run_stream


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # -- scan .env for all configured services --
    llm_lines = []
    for name, cfg in PROVIDERS.items():
        ok = is_configured(name)
        mark = "✓" if ok else "✗"
        llm_lines.append(f"    {cfg['label']:12s} {mark}")

    search_ok = tavily_available()
    ls_ok = langsmith_available()

    print()
    print(f"  ╭─ ServePeopleLangChainAgent ────────────────────────────╮")
    print(f"  │  LLM")
    for line in llm_lines:
        print(f"  │{line}")
    print(f"  │  搜索       Tavily {'✓' if search_ok else '✗'}")
    print(f"  │  追踪       LangSmith {'✓' if ls_ok else '✗'}")
    print(f"  │  当前       {provider_label()} / {active_model_name()}")
    print(f"  ╰────────────────────────────────────────────────────────╯")
    print()
    print("  💡 试试：男，2019年毕业，计算机科学与技术，山西太原考公岗位")
    print("  📎 提供文件：--file 招聘公告.pdf  + 你的基本信息")
    print("  📖 help 查看帮助  ·  exit 退出")
    print()

    while True:
        try:
            user_input = input("  ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  👋 再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("  👋 再见！")
            break

        # --file support: --file path + profile text
        file_path = None
        query = user_input
        if user_input.startswith("--file "):
            parts = user_input[7:].strip().split(" ", 1)
            file_path = parts[0].strip()
            query = parts[1].strip() if len(parts) > 1 else ""
            if not query:
                query = input("  📝 请输入你的基本信息: ").strip()
            # Prepend file content to the query
            from ServePeopleLangChainAgent.tools import parse_document
            doc_text = parse_document.invoke({"file_path": file_path})
            query = f"用户提供了招聘文件 ({file_path})，内容如下：\n\n{doc_text}\n\n---\n用户基本信息: {query}\n---\n请帮我解析职位表中的岗位，并结合用户信息逐个匹配筛选。先调用 parse_document 解析文件，再调用 delegate_match_positions 进行匹配（提供完整的用户画像和职位表内容）。"

        if user_input.lower() == "help":
            print("""
  ┌─ 帮助 ──────────────────────────────────────────┐
  │  考公岗位搜索  直接输入个人画像，例如：            │
  │    男，2019年毕业，计算机科学与技术，山西太原      │
  │                                                   │
  │  提供招聘文件   --file 路径 + 个人信息              │
  │    --file ./职位表.pdf 男, 计算机本科, 太原        │
  │    支持 .pdf  .docx                               │
  │                                                   │
  │  普通搜索      直接输入问题                       │
  │  读取链接      粘贴 URL                           │
  │                                                   │
  │  exit / q      退出                               │
  └───────────────────────────────────────────────────┘
            """)
            continue

        try:
            print(f"  {'─' * 56}")
            sys.stdout.write("  ")
            sys.stdout.flush()

            for chunk in run_stream(query):
                # Tool-call indicators come with leading \n
                sys.stdout.write(chunk)
                sys.stdout.flush()

            print(f"\n  {'─' * 56}")
            print()
        except Exception as e:
            print(f"  ❌ {e}")
            print()
            print()


if __name__ == "__main__":
    main()
