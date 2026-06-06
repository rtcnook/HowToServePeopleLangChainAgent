"""
HowToServePeopleLangChainAgent  v0.2.0
═══════════════════════════════

Multi-agent system for Chinese civil-service / public-institution job search.
LangChain + LangGraph  ·  Gemini / SiliconFlow Qwen  ·  Tavily / DuckDuckGo

Usage:
    # 1. 配置 .env
    cp .env.example .env   → 填入 API keys

    # 2. 运行
    uv run main.py

    # 或以编程方式调用
    python -c "from ServePeopleLangChainAgent import run; print(run('...'))"
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ── Validate configuration ───────────────────────────────────────────────────
provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

if provider == "dashscope":
    required = "DASHSCOPE_API_KEY"
    display_name = "阿里云百炼 / qwen3.7-plus"
elif provider == "siliconflow":
    required = "SILICONFLOW_API_KEY"
    display_name = "SiliconFlow / Qwen"
else:
    required = "GOOGLE_API_KEY"
    display_name = "Google Gemini"

if not os.getenv(required):
    print(f"⚠️  {required} 未设置！")
    print(f"当前 LLM_PROVIDER={provider} → 需要 {required}")
    print()
    print("请将 API key 写入 .env 文件：")
    print(f"  {required}=***")
    print()
    print("或切换到 gemini：")
    print("  LLM_PROVIDER=gemini")
    sys.exit(1)

from ServePeopleLangChainAgent import run


def main() -> None:
    s_icon = "✓" if os.getenv("TAVILY_API_KEY", "").startswith("tvly-") else "✗ (DuckDuckGo)"
    langsmith = "✓" if os.getenv("LANGSMITH_API_KEY") else "✗"

    print("=" * 60)
    print(f"  HowToServePeopleLangChainAgent  v0.2.0")
    print(f"  Model:  {display_name}")
    print(f"  Search: Tavily {s_icon}")
    print(f"  Trace:  LangSmith {langsmith}")
    print("=" * 60)
    print()
    print("试试输入：")
    print("  「男，2019年毕业，计算机科学与技术，想找山西太原或汾阳考公考编岗位」")
    print()

    while True:
        try:
            user_input = input("\n👉 ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("👋 再见！")
            break

        print(f"\n⏳ CEO Agent 正在协调子 Agent ...\n")
        try:
            answer = run(user_input)
            print("─" * 60)
            print(answer)
            print("─" * 60)
        except Exception as e:
            print(f"❌ 处理出错: {e}")


if __name__ == "__main__":
    main()
