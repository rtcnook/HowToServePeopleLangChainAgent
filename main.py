"""
HowToServePeopleLangChainAgent
═══════════════════════════════

两步走流程:
  1. profile <基本信息>     → 录入个人画像
  2. upload <文件路径>      → 上传职位表，自动匹配筛选
  3. report                 → 生成 Word 格式的岗位匹配报告

Usage: uv run main.py
"""
import os
import sys
import re

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
from ServePeopleLangChainAgent.tools import parse_document, list_documents


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_profile(raw: str) -> dict:
    """Parse free-text profile into structured fields."""
    fields = {}

    if "男" in raw:
        fields["性别"] = "男"
    elif "女" in raw:
        fields["性别"] = "女"

    m = re.search(r"(20\d{2})\s*年.*?毕业", raw)
    if m:
        fields["毕业年份"] = m.group(1)

    for edu in ["博士", "硕士", "本科", "大专", "中专"]:
        if edu in raw:
            fields["学历"] = edu
            break

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

    cities = ["太原", "大同", "阳泉", "长治", "晋城", "朔州", "忻州", "吕梁", "晋中", "临汾", "运城", "汾阳", "北京", "上海", "广州", "深圳", "杭州", "南京", "武汉", "成都", "西安"]
    found = [c for c in cities if c in raw]
    if found:
        fields["目标地区"] = "、".join(found)

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


def _extract_positions_from_response(response: str, source_file: str) -> list[dict]:
    """Extract matched positions from the LLM match response.

    Parses headings like:
      ### 🎯 唯一可报岗位（行19）
      ### 岗位: [名称] — [单位] — [地点]
    And extracts structured data from tables.
    """
    positions = []

    # Pattern 1: Heading with row number like "### 🎯 唯一可报岗位（行19）"
    heading_pattern = r"#{2,3}\s+(?:🎯\s*)?唯一可报岗位.*?（行(\d+)）"
    heading_matches = list(re.finditer(heading_pattern, response, re.MULTILINE))

    # Pattern 2: "#### 行19 — 网络安全与信息化 | 山西荣光能源有限公司 | 阳泉市郊区"
    row_heading_pattern = r"#{2,4}\s+行(\d+)\s*[—–-]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$)"
    row_heading_matches = list(re.finditer(row_heading_pattern, response, re.MULTILINE))

    # Pattern 3: Generic position headings
    generic_patterns = [
        r"#{2,3}\s+(?:岗位\s*\d*|最推荐)[：:]\s*(.+?)(?:\s*—\s*(.+?))?(?:\s*—\s*(.+?))?$",
        r"#{2,3}\s+[✅⚠️❌]?\s*岗位\s*\d*[：:]\s*(.+?)(?:\s*—\s*(.+?))?(?:\s*—\s*(.+?))?$",
    ]

    for heading_match in heading_matches:
        row_num = int(heading_match.group(1))
        # Get context after this heading
        context_start = heading_match.end()
        context_end = min(len(response), context_start + 2000)
        context = response[context_start:context_end]

        # Extract from tables like "| **岗位名称** | 网络安全与信息化 |"
        pos = {"行号": row_num}

        for table_match in re.finditer(r"\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|", context):
            key = table_match.group(1).strip()
            value = table_match.group(2).strip()

            if "岗位名称" in key:
                pos["岗位名称"] = value
            elif "所属公司" in key or "单位" in key:
                pos["单位"] = value
            elif "工作地点" in key:
                pos["工作地点"] = value
            elif "需求人数" in key or "招聘人数" in key:
                pos["招聘人数"] = value
            elif "学历" in key:
                pos["学历要求"] = value
            elif "专业" in key:
                pos["专业要求"] = value

        # Extract match details
        details = {}
        for detail_match in re.finditer(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*([✅⚠️❌✓✗].+?)\s*\|", context):
            condition = detail_match.group(1).strip()
            verdict = detail_match.group(4).strip()
            if condition and condition not in ("条件", "项目"):
                details[condition] = verdict

        pos["匹配详情"] = details
        positions.append(pos)

    # Process row heading matches (Pattern 2)
    for match in row_heading_matches:
        row_num = int(match.group(1))
        pos_name = match.group(2).strip()
        unit = match.group(3).strip()
        location = match.group(4).strip()

        pos = {
            "行号": row_num,
            "岗位名称": pos_name,
            "单位": unit,
            "工作地点": location,
        }

        # Get context after this heading for match details
        context_start = match.end()
        context_end = min(len(response), context_start + 1500)
        context = response[context_start:context_end]

        # Extract match details
        details = {}
        for detail_match in re.finditer(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*([✅⚠️❌✓✗].+?)\s*\|", context):
            condition = detail_match.group(1).strip()
            verdict = detail_match.group(4).strip()
            if condition and condition not in ("条件", "项目", "判定条件"):
                details[condition] = verdict

        pos["匹配详情"] = details
        positions.append(pos)

    # Also try generic patterns
    for pat in generic_patterns:
        matches = re.finditer(pat, response, re.MULTILINE)
        for match in matches:
            groups = [g.strip() if g else "" for g in match.groups()]
            pos = {"岗位名称": groups[0] if groups else "未知"}
            if len(groups) > 1 and groups[1]:
                pos["单位"] = groups[1]
            if len(groups) > 2 and groups[2]:
                pos["工作地点"] = groups[2]

            # Find source row
            context_start = max(0, match.start() - 500)
            context_end = min(len(response), match.end() + 1500)
            context = response[context_start:context_end]

            row_match = re.search(r"行\s*(\d+)", context)
            if row_match:
                pos["行号"] = int(row_match.group(1))

            # Extract details
            details = {}
            for detail_match in re.finditer(r"([✓✗⚠✅❌])\s*(.+?)[:：]\s*(.+?)(?:\n|$)", context):
                symbol = detail_match.group(1)
                cond = detail_match.group(2).strip()
                desc = detail_match.group(3).strip()
                verdict = f"{symbol} {desc}"
                if cond not in ("", "条件"):
                    details[cond] = verdict

            pos["匹配详情"] = details
            positions.append(pos)

    # Deduplicate by position name
    seen = set()
    unique = []
    for pos in positions:
        name = pos.get("岗位名称", "")
        if name and name not in seen:
            seen.add(name)
            unique.append(pos)

    return unique


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
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
    print(f"  📂 请将招聘文件（PDF/Word/Excel）放到 doc/ 目录下")
    print(f"  📋 第 1 步: profile 设置你的基本信息")
    print(f"  📎 第 2 步: upload 上传文件，自动匹配筛选")
    print(f"  📝 第 3 步: report 生成 Word 格式的匹配报告")
    print(f"  📂 ls 查看 doc/ 目录下的文件")
    print(f"  📖 help 查看帮助  ·  exit 退出")
    print()

    user_profile = {}
    last_doc_text = None
    last_file_path = None
    last_match_response = None

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

        if raw.lower() == "ls":
            print("\n📂 doc/ 目录下的文件：")
            print(list_documents.invoke({"directory": "ServePeopleLangChainAgent/doc"}))
            print()
            continue
        
        # If user types something that looks like profile info but hasn't set profile yet
        if not user_profile and not raw.lower().startswith(("profile", "upload", "report", "help", "exit", "quit", "q", "show", "clear")):
            # Check if it looks like profile information
            profile_keywords = ["男", "女", "岁", "毕业", "本科", "硕士", "博士", "专业", "计算机", "太原", "山西"]
            if any(kw in raw for kw in profile_keywords):
                print("\n  💡 看起来你在输入个人信息。请使用 profile 命令：")
                print(f"     profile {raw}\n")
                continue
        
        if raw.lower() == "show":
            if user_profile:
                print(f"\n  📋 当前用户画像:\n{_format_profile(user_profile)}\n")
            else:
                print("\n  ⚠️ 尚未设置用户画像。请使用: profile <你的基本信息>\n")
            continue

        if raw.lower() == "clear":
            user_profile = {}
            last_doc_text = None
            last_file_path = None
            last_match_response = None
            print("\n  ✅ 已清除所有数据\n")
            continue

        if raw.lower() == "help":
            print("""
  ┌─ 帮助 ──────────────────────────────────────────────┐
  │                                                       │
  │  【三步流程】                                         │
  │  1. profile <信息>     录入个人画像                   │
  │     ▸ profile 男, 2019年毕业, 计算机本科, 山西太原   │
  │                                                       │
  │  2. upload <文件>      上传职位表，自动匹配筛选       │
  │     ▸ upload doc/职位表.xlsx                          │
  │     ▸ upload doc/招聘公告.pdf                         │
  │     支持 .pdf  .docx  .xlsx  .xls                    │
  │                                                       │
  │  3. report             生成 Word 格式的匹配报告       │
  │     报告包含: 个人信息 + 匹配岗位 + 来源(文件+行号)  │
  │                                                       │
  │  【其他命令】                                         │
  │  show               查看当前用户画像                  │
  │  clear              清除所有数据                      │
  │  自由输入           搜索或提问                        │
  │  exit / q           退出                              │
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
            
            # If user just says "doc" or "doc目录", list files
            if file_path.lower() in ("doc", "doc目录", "文档目录", "目录"):
                print("\n📂 doc/ 目录下的文件：")
                print(list_documents("doc"))
                print()
                continue

            if not user_profile:
                print("\n  ⚠️ 请先设置你的基本信息。例如:")
                print("    profile 男, 2019年毕业, 计算机本科, 山西太原\n")
                continue
            
            # Auto-detect files in doc/ directory
            if not os.path.exists(file_path):
                # Try to find file in doc/ directory
                doc_path = os.path.join("doc", file_path)
                if os.path.exists(doc_path):
                    file_path = doc_path
                    print(f"  💡 自动定位到: {file_path}")
            
            # Parse document
            print(f"\n  📄 正在解析: {file_path} ...")
            doc_text = parse_document.invoke({"file_path": file_path})
            
            if doc_text.startswith("文件不存在") or doc_text.startswith("不支持") or doc_text.startswith("解析"):
                print(f"  ❌ {doc_text}\n")
                continue
            
            # Store for report
            last_doc_text = doc_text
            last_file_path = file_path
            
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
                f"对于每个推荐的岗位，请注明其在原始文件中的行号（如「行17」）。"
            )
            
            print(f"  🎯 正在匹配岗位 ...")
            print(f"  {'─' * 56}")
            sys.stdout.write("  ")
            sys.stdout.flush()
            
            try:
                last_match_response = ""
                for chunk in run_stream(query):
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    last_match_response += chunk
                print(f"\n  {'─' * 56}")
                print(f"\n  ✅ 匹配完成！输入 report 生成 Word 报告\n")
            except Exception as e:
                print(f"\n  ❌ {e}\n")
                last_match_response = None
            continue

        # ── report command ────────────────────────────────────────────────

        if raw.lower() == "report":
            if not user_profile:
                print("\n  ⚠️ 请先设置用户画像: profile <你的基本信息>\n")
                continue
            if not last_file_path or not last_doc_text:
                print("\n  ⚠️ 请先上传职位表: upload <文件路径>\n")
                continue
            if not last_match_response:
                print("\n  ⚠️ 没有匹配结果，请先完成 upload 流程\n")
                continue

            try:
                from ServePeopleLangChainAgent.tools import generate_report

                print(f"\n  📝 正在生成报告 ...")

                # Extract structured positions from the match response
                matched_positions = _extract_positions_from_response(
                    last_match_response, last_file_path
                )

                if not matched_positions:
                    print(f"  ⚠️ 未能从匹配结果中提取到岗位信息。")
                    print(f"  💡 可能是返回格式不标准，报告将包含原始匹配结果。\n")
                    # Fallback: put the full response as a single entry
                    matched_positions = [{
                        "岗位名称": "（完整匹配分析）",
                        "单位": "详见下方分析",
                        "匹配详情": {},
                        "行号": "?",
                    }]

                # Generate output filename
                import datetime
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                output_name = f"岗位匹配报告_{ts}.docx"

                output_path = generate_report(
                    user_profile=user_profile,
                    matched_positions=matched_positions,
                    source_file=last_file_path,
                    output_path=output_name,
                )

                print(f"  ✅ 报告已生成: {output_path}")
                print(f"  📊 共提取 {len(matched_positions)} 个匹配岗位")
                print()
            except Exception as e:
                print(f"\n  ❌ 报告生成失败: {e}\n")
            continue

        # ── Free-form query ───────────────────────────────────────────────

        query = raw
        
        # Smart detection: if user mentions doc/ directory or files, auto-scan
        doc_keywords = ["doc目录", "文档目录", "职位表", "doc/", "doc下面", "doc里面", "文件"]
        if any(kw in raw.lower() for kw in doc_keywords):
            print(f"\n  📂 正在扫描 doc/ 目录 ...")
            doc_list_result = list_documents.invoke({"directory": "ServePeopleLangChainAgent/doc"})
            print(f"  {doc_list_result}\n")
            
            if user_profile:
                profile_text = ", ".join(f"{k}:{v}" for k, v in user_profile.items() if k != "原始输入") or user_profile.get("原始输入", "")
                query = f"[用户画像: {profile_text}]\n\n用户提到了文档目录。以下是 doc/ 目录中的文件列表：\n{doc_list_result}\n\n用户的原始问题：{raw}\n\n请帮用户选择合适的文件并进行匹配分析。"
            else:
                query = f"用户提到了文档目录。以下是 doc/ 目录中的文件列表：\n{doc_list_result}\n\n用户的原始问题：{raw}\n\n请帮用户选择合适的文件，并提示用户先设置个人信息（profile）再进行匹配。"
        elif user_profile:
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
