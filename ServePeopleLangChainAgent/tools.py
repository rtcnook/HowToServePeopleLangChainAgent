"""
Base tools for the HowToServePeopleLangChainAgent system.
"""
import os
from pathlib import Path

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
    and content snippets.  Source attribution is included."""
    resp = _tavily_client.search(query, max_results=5, include_raw_content=False)
    results = resp.get("results", [])
    if not results:
        return f"Tavily 搜索无结果。查询: {query}"
    lines = [f"搜索: {query}", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '无标题')}")
        lines.append(f"   URL: {r.get('url', 'N/A')}")
        lines.append(f"   {r.get('content', '')[:400]}")
        lines.append("")
    return "\n".join(lines)


# ── URL Reader ──────────────────────────────────────────────────────────────

@tool
def read_url(url: str) -> str:
    """Read the full text content of a web page given its URL.
    Returns the extracted text, or an error if inaccessible."""
    try:
        loader = WebBaseLoader(url)
        docs = loader.load()
        if not docs:
            return f"无法加载: {url}"
        content = docs[0].page_content
        if len(content) > 12000:
            content = content[:12000] + "\n\n... [已截断]"
        return f"[网页内容] {url}\n\n{content}"
    except Exception as e:
        return f"读取 URL 失败 ({url}): {e}"


# ── Document Parser (PDF / Word / Excel) ────────────────────────────────────

_MAX_CHARS = 20000

_SUPPORTED = {
    ".pdf": "PDF",
    ".docx": "Word (docx)",
    ".doc": "Word (doc)",
    ".xlsx": "Excel (xlsx)",
    ".xls": "Excel (xls)",
    ".et": "WPS 表格",
}


@tool
def parse_document(file_path: str) -> str:
    """Parse a recruitment document — PDF, Word (.docx), or Excel (.xlsx/.xls).

    Use this when the user uploads a 招聘公告 / 职位表 / 报考简章 file.
    Excel files are treated as position tables with column headers.

    Returns the full text, or an error if parsing fails."""
    path = Path(file_path)
    
    # Auto-detect: if file doesn't exist, try ServePeopleLangChainAgent/doc/
    if not path.exists():
        alt_path = Path("ServePeopleLangChainAgent/doc") / file_path
        if alt_path.exists():
            path = alt_path
        else:
            # Try just the filename in doc/
            alt_path2 = Path("ServePeopleLangChainAgent/doc") / Path(file_path).name
            if alt_path2.exists():
                path = alt_path2
            else:
                return f"文件不存在: {file_path}"

    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED:
        return f"不支持的文件格式: {suffix}。支持: {', '.join(_SUPPORTED.values())}"

    try:
        if suffix == ".pdf":
            return _parse_pdf(path)
        elif suffix in (".docx", ".doc"):
            return _parse_docx(path)
        else:
            return _parse_excel(path)
    except Exception as e:
        return f"解析文件失败 ({file_path}): {e}"


@tool
def list_documents(directory: str = "doc") -> str:
    """List all supported document files in the specified directory.
    
    Scans for: .xlsx, .xls, .docx, .doc, .pdf
    Returns: A formatted list of available files with their sizes.
    """
    path = Path(directory)
    
    if not path.exists():
        return f"目录不存在：{directory}"
    
    if not path.is_dir():
        return f"不是目录：{directory}"
    
    supported_extensions = {'.xlsx', '.xls', '.docx', '.doc', '.pdf'}
    files = []
    
    for file_path in path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            size = file_path.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            files.append(f"  - {file_path.name} ({size_str})")
    
    if not files:
        return f"目录 {directory} 中没有找到支持的文档文件（支持：Excel/Word/PDF）"
    
    result = f"在 {directory} 目录下找到 {len(files)} 个文件：\n"
    result += "\n".join(sorted(files))
    # Pick first file for example
    first_file = sorted([fp.name for fp in path.iterdir() if fp.is_file() and fp.suffix.lower() in supported_extensions])
    if first_file:
        result += f"\n\n输入 upload {first_file[0]} 即可解析匹配"
    return result


def _parse_pdf(path: Path) -> str:
    import pymupdf

    doc = pymupdf.open(str(path))
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()

    full = "\n\n".join(pages)
    if len(full) > _MAX_CHARS:
        full = full[:_MAX_CHARS] + "\n\n... [已截断]"
    return f"[PDF] {path.name}\n\n{full}"


def _parse_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    paragraphs = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text)

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))

    full = "\n".join(paragraphs)
    if len(full) > _MAX_CHARS:
        full = full[:_MAX_CHARS] + "\n\n... [已截断]"
    return f"[DOCX] {path.name}\n\n{full}"


def _parse_excel(path: Path) -> str:
    """Parse Excel file with row numbers for source tracking."""
    suffix = path.suffix.lower()

    if suffix in (".xls",):
        import xlrd
        wb = xlrd.open_workbook(str(path))
        sheets = []
        for name in wb.sheet_names():
            ws = wb.sheet_by_name(name)
            rows = []
            for r in range(ws.nrows):
                cells = [str(ws.cell_value(r, c)).strip() for c in range(ws.ncols) if str(ws.cell_value(r, c)).strip()]
                if cells:
                    rows.append(f"行{r+1}: " + " | ".join(cells))
            if rows:
                sheets.append(f"【{name}】\n" + "\n".join(rows))
    else:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        sheets = []
        for name in wb.sheetnames:
            ws = wb[name]
            rows = []
            for r_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if cells:
                    rows.append(f"行{r_idx}: " + " | ".join(cells))
            if rows:
                sheets.append(f"【{name}】\n" + "\n".join(rows))
        wb.close()

    full = "\n\n".join(sheets)
    fmt = _SUPPORTED.get(suffix, suffix)
    if len(full) > _MAX_CHARS:
        full = full[:_MAX_CHARS] + "\n\n... [已截断]"
    return f"[{fmt}] {path.name}\n\n{full}"


# ── Report Generator ─────────────────────────────────────────────────────────

def generate_report(
    user_profile: dict,
    matched_positions: list[dict],
    source_file: str,
    output_path: str = "岗位匹配报告.docx",
) -> str:
    """Generate a .docx report with profile + matched positions + source info.

    Args:
        user_profile: dict with keys like 性别, 学历, 专业, etc.
        matched_positions: list of dicts, each with:
            - 岗位名称: str
            - 单位: str
            - 工作地点: str
            - 匹配详情: dict (条件: 判定)
            - 行号: int (source row number)
        source_file: path to the original file
        output_path: where to save the report

    Returns:
        str: path to the generated report
    """
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from datetime import datetime

    doc = Document()

    # Title
    title = doc.add_heading("岗位匹配报告", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Metadata
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta.add_run(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    run.font.size = Pt(10)
    run.font.color.rgb = None

    # Section 1: User Profile
    doc.add_heading("一、用户基本信息", 1)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "项目"
    hdr[1].text = "内容"

    for key, value in user_profile.items():
        if key == "原始输入":
            continue
        row = table.add_row().cells
        row[0].text = key
        row[1].text = str(value)

    # Section 2: Matched Positions
    doc.add_heading("二、匹配岗位详情", 1)

    if not matched_positions:
        doc.add_paragraph("未找到符合条件的岗位。")
    else:
        for i, pos in enumerate(matched_positions, 1):
            doc.add_heading(f"岗位 {i}: {pos.get('岗位名称', 'N/A')}", 2)

            # Basic info table
            info_table = doc.add_table(rows=1, cols=2)
            info_table.style = "Light Grid Accent 1"
            hdr = info_table.rows[0].cells
            hdr[0].text = "项目"
            hdr[1].text = "内容"

            for field in ["单位", "工作地点", "学历要求", "专业要求", "招聘人数"]:
                if pos.get(field):
                    row = info_table.add_row().cells
                    row[0].text = field
                    row[1].text = str(pos[field])

            # Match details
            doc.add_paragraph("\n匹配判定：")
            match_table = doc.add_table(rows=1, cols=2)
            match_table.style = "Light Grid Accent 1"
            hdr = match_table.rows[0].cells
            hdr[0].text = "条件"
            hdr[1].text = "判定"

            for cond, verdict in pos.get("匹配详情", {}).items():
                row = match_table.add_row().cells
                row[0].text = cond
                row[1].text = verdict

            # Source citation
            doc.add_paragraph("\n")
            source_para = doc.add_paragraph()
            run = source_para.add_run(f"📍 来源：{source_file}，第 {pos.get('行号', '?')} 行")
            run.font.size = Pt(9)
            run.font.italic = True

    # Section 3: Summary
    doc.add_heading("三、总结", 1)
    summary = doc.add_paragraph()
    summary.add_run(f"共扫描职位表，匹配到 {len(matched_positions)} 个岗位。")

    doc.save(output_path)
    return output_path
