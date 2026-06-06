"""
HowToServePeopleLangChainAgent
═══════════════════════════════

Usage: uv run main.py
"""
import os
import sys
import threading
import time

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

from ServePeopleLangChainAgent import run as _run


# ── Spinner ──────────────────────────────────────────────────────────────────

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _spinner(stop: threading.Event, label: str):
    i = 0
    start = time.time()
    while not stop.is_set():
        elapsed = int(time.time() - start)
        sys.stdout.write(f"\r  {_SPINNER[i % len(_SPINNER)]} {label} ({elapsed}s) ")
        sys.stdout.flush()
        time.sleep(0.12)
        i += 1
    sys.stdout.write("\r" + " " * 50 + "\r")
    sys.stdout.flush()


def run_with_spinner(user_input: str, label: str = "思考中") -> str:
    stop = threading.Event()
    t = threading.Thread(target=_spinner, args=(stop, label), daemon=True)
    t.start()
    try:
        result = _run(user_input)
    finally:
        stop.set()
        t.join(timeout=0.5)
    return result


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
        if user_input.lower() == "help":
            print("""
  ┌─ 帮助 ──────────────────────────────────────────┐
  │  考公岗位搜索  直接输入个人画像，例如：            │
  │    男，2019年毕业，计算机科学与技术，山西太原      │
  │                                                   │
  │  普通搜索      直接输入问题                       │
  │  读取链接      粘贴 URL                           │
  │  写文档/分析   描述需求                           │
  │                                                   │
  │  exit / q      退出                               │
  └───────────────────────────────────────────────────┘
            """)
            continue

        try:
            answer = run_with_spinner(user_input, label="CEO 调度子 Agent 中")
            print(f"  {'─' * 56}")
            for line in answer.split("\n"):
                print(f"  {line}")
            print(f"  {'─' * 56}")
            print()
        except Exception as e:
            print(f"  ❌ {e}")
            print()


if __name__ == "__main__":
    main()
