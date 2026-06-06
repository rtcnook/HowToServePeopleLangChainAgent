"""
HowToServePeopleLangChainAgent
═══════════════════════════════

两步走流程:
  1. profile <基本信息>     → 录入个人画像
  2. upload <文件路径>      → 上传职位表，自动匹配筛选

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
    print("⚠️  未找到有效的 API Key。")
    print()
    print("请在 .env 中配置以下任一服务的 Key：")
    for name, cfg in PROVIDERS.items():
        print(f"  {cfg['label']:12s} →  {cfg['keys'][0]}=***")
    sys.exit(1)

from ServePeopleLangChainAgent import run_stream
from ServePeopleLangChainAgent.tools import parse_document


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_profile(raw: str) -> dict:
    """Parse free-text profile into structured fields."""
    fields = {}
    raw_lower = raw.lower()

    # Sex
    if "男" in raw:
        fields["性别"] = "男"
    elif "女" in raw:
        fields["性别"] = "女"

    # Graduation year
    import re
    m = re.search(r"(20\d{2})\s*年.*?毕业", raw)
    if m:
        fields["毕业年份"] = m.group(1)

    # Education
    for edu in ["博士", "硕士", "本科", "大专", "中专"]:
        if edu in raw:
            fields["学历"] = edu
            break

    # Major - try common patterns
    for pat in [
        r"专业[是为：]?\s*([\u4e00-\u9fffA-Za-z\u00b7、/]+(?:[与和、/]\s*[\u4e00-\u9fffA-Za-z\u00b7]+)*)",
        r"([\u4e00-\u9fff]{2,6}(?:科学与技术|工程与技术|技术|管理与技术))",
    ]:
        m = re.search(pat, raw)
        if m:
            fields["专业"] = m.group(1).strip()
            break
    if "专业" not in fields:
        majors = ["计算机", "软件工程", "电子信息", "机械", "土木", "会计", "法学", "汉语言", "新闻", "医学", "护理", "金融", "经济"]
        for mj in majors:
            if mj in raw:
                fields["专业"] = mj
                break

    # Location
    cities = ["太原", "大同", "阳泉", "长治", "晋城", "朔州", "忻州", "吕梁", "晋中", "临汾", "运城", "汾阳", "北京", "上海", "广州", "深圳", "杭州", "南京", "武汉", "成都", "西安"]
    found = []
    for c in cities:
        if c in raw:
            found.append(c)
    if found:
        fields["目标地区"] = "、".join(found)

    # Age
    m = re.search(r"(\d{1,2})\s*岁", raw)
    if m:
        fields["年龄"] = m.group(1)

    return fields


def _format_profile(profile: dict) -> str:
    """Pretty-print the profile."""
    lines = []
    for k, v in profile.items():
        lines.append(f"    {k}: {v}")
    return "\n".join(lines) if lines else "    (空)"


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # -- status bar --
    llm_lines = []
    for name, cfg in PROVIDERS.items():
        ok = is_configured(name)
        llm_lines.append(f"    {cfg['label']:12s} {'✓' if ok else '✗'}")

    print()
    print(f"  ╭─ 考公/考编岗位智能匹配系统 ─────────────────────╮")
    print(f"  │  LLM")
    for line in llm_lines:
        print(f"  │{line}")
    print(f"  │  搜索       Tavily {'✓' if tavily_available() else '✗'}")
    print(f"  │  文档       PDF · Word · Excel")
    print(f"  │  当前       {provider_label()} / {active_model_name()}")
    print(f"  ╰────────────────────────────────────────────────────╯")
    print()
    print(f"  📋 第 1 步: 输入 profile 设置你的基本信息")
    print(f"  📎 第 2 步: 输入 upload 上传招聘公告/职位表文件")
    print(f"  💬 也可以直接输入问题进行搜索或提问")
    print(f"  📖 help 查看帮助  ·  exit 退出")
    print()

    user_profile = {}

    while True:
        try:
            raw = input("  ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  👋 再见！")
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "q"):
            print("  👋 再见！")
            break

        # ── Commands ──────────────────────────────────────────────────────

        if raw.lower() == "show":
            if user_profile:
                print(f"\n  📋 当前用户画像:\n{_format_profile(user_profile)}\n")
            else:
                print("\n  ⚠️ 尚未设置用户画像。请使用: profile <你的基本信息>\n")
            continue

        if raw.lower() == "clear":
            user_profile = {}
            print("\n  ✅ 用户画像已清除\n")
            continue

        if raw.lower() == "help":
            print("""
  ┌─ 帮助 ──────────────────────────────────────────────┐
  │                                                       │
  │  【两步流程】                                         │
  │  profile <信息>     录入个人画像                       │
  │    ▸ profile 男, 2019年毕业, 计算机本科, 山西太原     │
  │                                                       │
  │  upload <文件>      上传职位表，自动匹配筛选            │
  │    ▸ upload doc/职位表.xlsx                            │
  │    ▸ upload doc/招聘公告.pdf                           │
  │    支持 .pdf  .docx  .xlsx  .xls                      │
  │                                                       │
  │  【其他命令】                                         │
  │  show               查看当前用户画像                   │
  │  clear              清除用户画像                       │
  │  自由输入           搜索或提问                         │
  │  exit / q           退出                               │
  │                                                       │
  └───────────────────────────────────────────────────────┘
            """)
            continue

        # ── profile command ───────────────────────────────────────────────

        if raw.lower().startswith("profile "):
            info = raw[8:].strip()
            if not info:
                print("\n  ⚠️ 请提供你的基本信息。例如:")
                print("    profile 男, 2019年毕业, 计算机科学与技术本科, 山西太原\n")
                continue

            user_profile = _parse_profile(info)
            user_profile["原始输入"] = info
            print(f"\n  ✅ 用户画像已保存:\n{_format_profile(user_profile)}")
            print(f"\n  📎 现在可以上传职位表了: upload <文件路径>\n")
            continue

        # ── upload command ────────────────────────────────────────────────

        if raw.lower().startswith("upload "):
            file_path = raw[7:].strip()

            if not user_profile:
                print("\n  ⚠️ 请先设置你的基本信息。例如:")
                print("    profile 男, 2019年毕业, 计算机本科, 山西太原\n")
                continue

            # Parse document
            print(f"\n  📄 正在解析: {file_path} ...")
            doc_text = parse_document.invoke({"file_path": file_path})

            if doc_text.startswith("文件不存在") or doc_text.startswith("不支持") or doc_text.startswith("解析"):
                print(f"  ❌ {doc_text}\n")
                continue

            # Truncate for context window
            max_len = 4000
            if len(doc_text) > max_len:
                doc_text = doc_text[:max_len] + "\n... [已截断]"

            # Build query with profile + document
            profile_text = ", ".join(f"{k}:{v}" for k, v in user_profile.items() if k != "原始输入") or user_profile.get("原始输入", "")
            query = (
                f"用户画像: {profile_text}\n\n"
                f"招聘职位表:\n{doc_text}\n\n"
                f"请调用 delegate_match_positions，将职位表中的每一个岗位与用户画像逐一对比，"
                f"筛选出用户符合条件的岗位。对每个岗位给出 ✓满足 / ✗不满足 / ⚠不确定 的详细分析。"
            )

            print(f"  🎯 正在匹配岗位 ...")
            print(f"  {'─' * 56}")
            sys.stdout.write("  ")
            sys.stdout.flush()

            try:
                for chunk in run_stream(query):
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                print(f"\n  {'─' * 56}")
                print()
            except Exception as e:
                print(f"\n  ❌ {e}\n")
            continue

        # ── Free-form query ───────────────────────────────────────────────

        # If profile exists, prepend it
        query = raw
        if user_profile:
            profile_text = ", ".join(f"{k}:{v}" for k, v in user_profile.items() if k != "原始输入") or user_profile.get("原始输入", "")
            query = f"[用户画像: {profile_text}]\n\n{raw}"

        print(f"  {'─' * 56}")
        sys.stdout.write("  ")
        sys.stdout.flush()

        try:
            for chunk in run_stream(query):
                sys.stdout.write(chunk)
                sys.stdout.flush()
            print(f"\n  {'─' * 56}")
            print()
        except Exception as e:
            print(f"\n  ❌ {e}\n")


if __name__ == "__main__":
    main()
