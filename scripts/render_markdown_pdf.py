import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
)


TITLE = "Sprawozdanie projektu NaturaVision"
INLINE_CODE_PATTERN = re.compile(r"`([^`]+)`")
IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a Markdown file to PDF.")
    parser.add_argument("--input", required=True, help="Path to the input Markdown file.")
    parser.add_argument("--output", required=True, help="Path to the output PDF file.")
    return parser.parse_args()


def register_fonts() -> None:
    candidates = [
        ("DejaVuSans", Path(r"C:\Windows\Fonts\DejaVuSans.ttf")),
        ("DejaVuSansMono", Path(r"C:\Windows\Fonts\DejaVuSansMono.ttf")),
        ("ArialUnicodeMS", Path(r"C:\Windows\Fonts\ARIALUNI.TTF")),
        ("Arial", Path(r"C:\Windows\Fonts\arial.ttf")),
        ("Consolas", Path(r"C:\Windows\Fonts\consola.ttf")),
        ("CourierNew", Path(r"C:\Windows\Fonts\cour.ttf")),
    ]
    for font_name, font_path in candidates:
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            except Exception:
                continue


def choose_font(*names: str, fallback: str) -> str:
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name in names:
        if name in registered:
            return name
    return fallback


def build_styles() -> StyleSheet1:
    register_fonts()
    body_font = choose_font("DejaVuSans", "ArialUnicodeMS", "Arial", fallback="Helvetica")
    mono_font = choose_font("DejaVuSansMono", "Consolas", "CourierNew", fallback="Courier")
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="DocTitle",
            parent=styles["Title"],
            fontName=body_font,
            fontSize=18,
            leading=22,
            spaceAfter=12,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName=body_font,
            fontSize=11,
            leading=15,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading1"],
            fontName=body_font,
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#1F3A5F"),
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subsection",
            parent=styles["Heading2"],
            fontName=body_font,
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#274C77"),
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MinorHeading",
            parent=styles["Heading3"],
            fontName=body_font,
            fontSize=12,
            leading=15,
            spaceBefore=6,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletItem",
            parent=styles["BodyText"],
            fontName=body_font,
            fontSize=11,
            leading=15,
            leftIndent=16,
            firstLineIndent=-10,
            bulletIndent=6,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeBlock",
            fontName=mono_font,
            fontSize=9,
            leading=11,
            leftIndent=8,
            rightIndent=8,
            spaceBefore=6,
            spaceAfter=8,
            borderPadding=6,
            backColor=colors.HexColor("#F4F6F8"),
            borderColor=colors.HexColor("#D5DDE5"),
            borderWidth=0.5,
            borderRadius=2,
        )
    )
    return styles


def normalize_inline(text: str, styles: StyleSheet1) -> str:
    mono_font = styles["CodeBlock"].fontName

    def replace(match: re.Match[str]) -> str:
        code = escape(match.group(1))
        return f'<font name="{mono_font}">{code}</font>'

    escaped = escape(text)
    return INLINE_CODE_PATTERN.sub(replace, escaped)


def flush_paragraph(buffer: list[str], story: list, styles: StyleSheet1) -> None:
    if not buffer:
        return
    text = " ".join(line.strip() for line in buffer if line.strip())
    if text:
        story.append(Paragraph(normalize_inline(text, styles), styles["Body"]))
    buffer.clear()


def flush_code_block(buffer: list[str], story: list, styles: StyleSheet1) -> None:
    if not buffer:
        return
    code = "\n".join(buffer).rstrip()
    if code:
        story.append(Preformatted(code, styles["CodeBlock"]))
    buffer.clear()


def resolve_image(path_text: str, source_dir: Path, max_width: float, max_height: float) -> Image | None:
    image_path = (source_dir / path_text).resolve()
    if not image_path.exists():
        return None

    reader = ImageReader(str(image_path))
    width, height = reader.getSize()
    if width <= 0 or height <= 0:
        return None

    scale = min(max_width / width, max_height / height, 1.0)
    return Image(str(image_path), width=width * scale, height=height * scale)


def parse_markdown(markdown: str, styles: StyleSheet1, source_dir: Path, max_width: float, max_height: float) -> list:
    story: list = [Paragraph(TITLE, styles["DocTitle"]), Spacer(1, 4)]
    paragraph_buffer: list[str] = []
    code_buffer: list[str] = []
    in_code_block = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph(paragraph_buffer, story, styles)
            if in_code_block:
                flush_code_block(code_buffer, story, styles)
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_buffer.append(line)
            continue

        if not stripped:
            flush_paragraph(paragraph_buffer, story, styles)
            story.append(Spacer(1, 3))
            continue

        if stripped == "---":
            flush_paragraph(paragraph_buffer, story, styles)
            story.append(Spacer(1, 8))
            continue

        if stripped.startswith("# "):
            flush_paragraph(paragraph_buffer, story, styles)
            story.append(Paragraph(normalize_inline(stripped[2:].strip(), styles), styles["Section"]))
            continue

        if stripped.startswith("## "):
            flush_paragraph(paragraph_buffer, story, styles)
            story.append(Paragraph(normalize_inline(stripped[3:].strip(), styles), styles["Section"]))
            continue

        if stripped.startswith("### "):
            flush_paragraph(paragraph_buffer, story, styles)
            story.append(Paragraph(normalize_inline(stripped[4:].strip(), styles), styles["Subsection"]))
            continue

        if stripped.startswith("#### "):
            flush_paragraph(paragraph_buffer, story, styles)
            story.append(Paragraph(normalize_inline(stripped[5:].strip(), styles), styles["MinorHeading"]))
            continue

        image_match = IMAGE_PATTERN.fullmatch(stripped)
        if image_match:
            flush_paragraph(paragraph_buffer, story, styles)
            image = resolve_image(image_match.group(1), source_dir, max_width, max_height)
            if image is not None:
                story.append(Spacer(1, 4))
                story.append(image)
                story.append(Spacer(1, 6))
            continue

        if stripped.startswith("- "):
            flush_paragraph(paragraph_buffer, story, styles)
            bullet_text = normalize_inline(stripped[2:].strip(), styles)
            story.append(Paragraph(bullet_text, styles["BulletItem"], bulletText="•"))
            continue

        paragraph_buffer.append(line)

    flush_paragraph(paragraph_buffer, story, styles)
    flush_code_block(code_buffer, story, styles)
    return story


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
    canvas.line(doc.leftMargin, A4[1] - 18 * mm, A4[0] - doc.rightMargin, A4[1] - 18 * mm)
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#486581"))
    canvas.drawString(doc.leftMargin, A4[1] - 15 * mm, TITLE)
    canvas.drawRightString(A4[0] - doc.rightMargin, 12 * mm, f"Strona {canvas.getPageNumber()}")
    canvas.restoreState()


def build_pdf(source: Path, destination: Path) -> None:
    styles = build_styles()
    destination.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=24 * mm,
        bottomMargin=18 * mm,
        title=TITLE,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=draw_page)])

    markdown = source.read_text(encoding="utf-8")
    story = parse_markdown(markdown, styles, source.parent, doc.width, doc.height * 0.42)
    doc.build(story)


def main() -> None:
    args = parse_args()
    source = Path(args.input).resolve()
    destination = Path(args.output).resolve()
    build_pdf(source, destination)


if __name__ == "__main__":
    main()
