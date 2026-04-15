import os
import re
import logging
from typing import Optional, List
from fpdf import FPDF
from datetime import datetime

log = logging.getLogger(__name__)

# 中文字体查找顺序：系统字体 → 项目字体
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",          # macOS
    "/Library/Fonts/Arial Unicode.ttf",                               # macOS alt
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",         # Debian/Ubuntu (fonts-noto-cjk)
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",         # fallback
    os.path.join(os.path.dirname(__file__), "..", "..", "fonts", "NotoSansSC-Regular.otf"),
    os.path.join(os.path.dirname(__file__), "..", "..", "fonts", "NotoSansSC-Regular.ttf"),
]

# 字体文件的 magic bytes — 只校验真正的字体，防止 HTML 错误页 / LFS pointer 被当作字体加载
_FONT_MAGIC = (
    b"\x00\x01\x00\x00",  # TrueType
    b"OTTO",              # OpenType (CFF)
    b"ttcf",              # TrueType Collection
    b"true",              # macOS TrueType
    b"typ1",              # PostScript Type 1
)


def _is_real_font(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(4)
        return head in _FONT_MAGIC
    except OSError:
        return False


def _find_cjk_font() -> Optional[str]:
    for path in FONT_CANDIDATES:
        if os.path.exists(path) and _is_real_font(path):
            return path
    return None


CJK_FONT_PATH = _find_cjk_font()

if CJK_FONT_PATH:
    log.info("[pdf_report] CJK font loaded: %s", CJK_FONT_PATH)
else:
    log.warning(
        "[pdf_report] No valid CJK font found. PDF reports with Chinese text will fail. "
        "Checked: %s",
        FONT_CANDIDATES,
    )


class DigestPDF(FPDF):
    def __init__(self, company_name: str, date_range: str):
        super().__init__()
        self.company_name = company_name
        self.date_range = date_range
        # Determine label from date_range span
        try:
            parts = date_range.replace("–", "-").split("-")
            if len(parts) == 2:
                s = parts[0].strip().split("/")
                e = parts[1].strip().split("/")
                sd = int(s[1]) if len(s) == 2 else int(s[0])
                ed = int(e[1]) if len(e) == 2 else int(e[0])
                self._report_label = "邮件日报" if abs(ed - sd) <= 1 else "邮件周报"
            else:
                self._report_label = "邮件日报"
        except Exception:
            self._report_label = "邮件周报"

        # 加载中文字体 — 缺失时 fail loud，避免运行到中文字符才崩
        if not CJK_FONT_PATH:
            raise RuntimeError(
                "CJK font unavailable; install fonts-noto-cjk or ship a real "
                "NotoSansSC-Regular.{otf,ttf} in engine/fonts/."
            )
        self.add_font("CJK", "", CJK_FONT_PATH, uni=True)
        self.add_font("CJK", "B", CJK_FONT_PATH, uni=True)
        self._font_family = "CJK"

    def header(self):
        self.set_font(self._font_family, "B", 16)
        self.set_text_color(33, 37, 41)
        label = self._report_label
        self.cell(0, 12, f"{self.company_name} {label}", ln=True, align="C")
        self.set_font(self._font_family, "", 10)
        self.set_text_color(108, 117, 125)
        self.cell(0, 8, self.date_range, ln=True, align="C")
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font(self._font_family, "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} · Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C")

    def add_section(self, title: str, content: str, color: tuple = (33, 37, 41)):
        """添加带标题的段落"""
        self.set_font(self._font_family, "B", 12)
        self.set_text_color(*color)
        self.cell(0, 10, title, ln=True)
        self.set_font(self._font_family, "", 10)
        self.set_text_color(33, 37, 41)
        self.multi_cell(0, 6, content)
        self.ln(4)


def _parse_digest_sections(digest_text: str) -> list[tuple[str, str, tuple]]:
    """
    从 Telegram Markdown 格式的摘要文本中解析出各段落。
    返回 [(title, content, color), ...]
    """
    # 清理 Markdown 标记
    text = digest_text.replace("*", "").replace("`", "").replace("_", "")

    sections = []
    # 按 emoji 标题行分割
    markers = [
        ("🔴 需立即处理", (220, 53, 69)),
        ("🟡 需要关注", (255, 193, 7)),
        ("📋 跟进状态", (23, 162, 184)),
        ("⚠️ 删除/垃圾箱审查", (108, 117, 125)),
        ("📝 总结", (40, 167, 69)),
        ("🔴 你需要处理", (220, 53, 69)),
        ("🟡 你需要了解", (255, 193, 7)),
        ("⚠️ 你负责的未跟进项", (108, 117, 125)),
        ("📝 小结", (40, 167, 69)),
    ]

    lines = text.split("\n")
    current_title = ""
    current_color = (33, 37, 41)
    current_lines = []

    for line in lines:
        matched = False
        for marker, color in markers:
            if marker in line:
                if current_title and current_lines:
                    sections.append((current_title, "\n".join(current_lines).strip(), current_color))
                current_title = marker
                current_color = color
                current_lines = []
                matched = True
                break
        if not matched and current_title:
            current_lines.append(line)

    if current_title and current_lines:
        sections.append((current_title, "\n".join(current_lines).strip(), current_color))

    return sections


def generate_report_pdf(
    company_name: str,
    digest_text: str,
    date_range: str,
    action_items: Optional[List[dict]] = None,
) -> bytes:
    """
    生成 PDF 报告，返回 bytes。
    """
    pdf = DigestPDF(company_name, date_range)
    pdf.alias_nb_pages()
    pdf.add_page()

    sections = _parse_digest_sections(digest_text)

    if sections:
        for title, content, color in sections:
            pdf.add_section(title, content, color)
    else:
        # fallback: 直接输出全文
        clean = digest_text.replace("*", "").replace("`", "").replace("_", "")
        pdf.set_font(pdf._font_family, "", 10)
        pdf.multi_cell(0, 6, clean)

    # Action items 附录
    if action_items:
        pdf.add_page()
        pdf.set_font(pdf._font_family, "B", 14)
        pdf.set_text_color(33, 37, 41)
        pdf.cell(0, 12, "待处理事项明细", ln=True)
        pdf.ln(4)

        for i, item in enumerate(action_items, 1):
            raw = item.get("item")
            subject = raw.subject if raw else item.get("subject", "")
            sender = raw.sender if raw else item.get("sender", "")
            reason = item.get("reason", "")
            assignee = item.get("suggested_assignee_email", "未指定")

            pdf.set_font(pdf._font_family, "B", 10)
            pdf.cell(0, 7, f"{i}. {subject}", ln=True)
            pdf.set_font(pdf._font_family, "", 9)
            pdf.set_text_color(108, 117, 125)
            pdf.cell(0, 5, f"   发件人: {sender} | 负责人: {assignee}", ln=True)
            pdf.cell(0, 5, f"   {reason}", ln=True)
            pdf.set_text_color(33, 37, 41)
            pdf.ln(3)

    return pdf.output()
