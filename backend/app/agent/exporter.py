"""Generate complete DOCX and Cyrillic-safe PDF protocol files."""

from __future__ import annotations

from html import escape
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import ProtocolResult


def export_files(result: ProtocolResult, folder: Path) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    docx_path = folder / "protocol.docx"
    pdf_path = folder / "protocol.pdf"
    _export_docx(result, docx_path)
    _export_pdf(result, pdf_path)
    return docx_path, pdf_path


def _speaker_name(speaker: str) -> str:
    if speaker.startswith("SPEAKER_"):
        try:
            return f"Спикер {int(speaker.rsplit('_', 1)[1]) + 1}"
        except ValueError:
            pass
    return speaker or "Спикер"


def _export_docx(result: ProtocolResult, destination: Path) -> None:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    title = doc.add_heading("Протокол совещания", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.runs[0].font.color.rgb = RGBColor(20, 47, 79)
    doc.add_paragraph(f"Номер записи: {result.meeting_id}")

    doc.add_heading("Краткое саммари", level=1)
    for item in result.summary:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("Поручения", level=1)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Shading Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    labels = ["Суть поручения", "Ответственный", "Срок", "Статус", "Цитата"]
    for cell, label in zip(table.rows[0].cells, labels):
        cell.text = label
    for task in result.tasks:
        cells = table.add_row().cells
        values = [task.description, task.assignee, task.deadline, task.status, task.source_quote]
        for cell, value in zip(cells, values):
            cell.text = value or "—"
    doc.add_heading("Транскрипт", level=1)
    for line in result.transcript:
        paragraph = doc.add_paragraph()
        label = paragraph.add_run(_speaker_name(line.speaker) + "  ")
        label.bold = True
        paragraph.add_run(line.text)
    if result.warnings:
        doc.add_heading("Примечания обработки", level=1)
        for warning in result.warnings:
            doc.add_paragraph(warning, style="List Bullet")
    doc.save(destination)


def _register_font() -> tuple[str, str]:
    candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
    ]
    regular, bold = next(
        ((normal, heavy) for normal, heavy in candidates if normal.is_file()),
        (None, None),
    )
    if regular is None:
        raise RuntimeError("Для PDF нужен установленный локальный шрифт с кириллицей (Arial или DejaVu Sans).")
    if not bold.is_file():
        bold = regular
    pdfmetrics.registerFont(TTFont("MeetingProtocol", str(regular)))
    pdfmetrics.registerFont(TTFont("MeetingProtocolBold", str(bold)))
    pdfmetrics.registerFontFamily("MeetingProtocol", normal="MeetingProtocol", bold="MeetingProtocolBold",
                                 italic="MeetingProtocol", boldItalic="MeetingProtocolBold")
    return "MeetingProtocol", "MeetingProtocolBold"


def _export_pdf(result: ProtocolResult, destination: Path) -> None:
    regular, bold = _register_font()
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "MeetingTitle", parent=base["Title"], fontName=bold, fontSize=20,
        leading=25, alignment=TA_LEFT, textColor=colors.HexColor("#142f4f"),
        spaceAfter=8,
    )
    heading = ParagraphStyle(
        "MeetingHeading", parent=base["Heading2"], fontName=bold, fontSize=12,
        leading=16, textColor=colors.HexColor("#176b66"), spaceBefore=12,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "MeetingBody", parent=base["BodyText"], fontName=regular, fontSize=9.5,
        leading=14, textColor=colors.HexColor("#223047"), spaceAfter=5,
    )
    small = ParagraphStyle("MeetingSmall", parent=body, fontSize=8, leading=11)
    story = [
        Paragraph("Протокол совещания", title),
        Paragraph(f"ID записи: {escape(result.meeting_id)}", small),
        Spacer(1, 7),
        Paragraph("Краткое саммари", heading),
    ]
    for item in result.summary:
        story.append(Paragraph("• " + escape(item), body))

    story.append(Paragraph("Поручения", heading))
    table_data = [[Paragraph(label, small) for label in ["Суть поручения", "Ответственный", "Срок", "Статус", "Источник"]]]
    for task in result.tasks:
        quote = f"<br/><font size='7' color='#657587'>«{escape(task.source_quote)}»</font>" if task.source_quote else ""
        table_data.append([
            Paragraph(escape(task.description) + quote, small),
            Paragraph(escape(task.assignee), small),
            Paragraph(escape(task.deadline), small),
            Paragraph(escape(task.status), small),
            Paragraph("Реплика" if task.source_quote else "—", small),
        ])
    if len(table_data) == 1:
        table_data.append([Paragraph("Поручения не обнаружены", small), "", "", "", ""])
    task_table = Table(table_data, colWidths=[205, 92, 68, 68, 66], repeatRows=1, hAlign="LEFT")
    task_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf1f5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#142f4f")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d4dee7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([task_table, Paragraph("Транскрипт", heading)])
    for line in result.transcript:
        story.append(Paragraph(
            f"<b>{escape(_speaker_name(line.speaker))}</b> — {escape(line.text)}",
            body,
        ))
    if result.warnings:
        story.append(Paragraph("Примечания обработки", heading))
        for warning in result.warnings:
            story.append(Paragraph("• " + escape(warning), small))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(regular, 8)
        canvas.setFillColor(colors.HexColor("#657587"))
        canvas.drawString(40, 24, "Сформировано локально · проверьте автоматические выводы перед рассылкой")
        canvas.drawRightString(A4[0] - 40, 24, str(document.page))
        canvas.restoreState()

    SimpleDocTemplate(
        str(destination), pagesize=A4, leftMargin=40, rightMargin=40,
        topMargin=42, bottomMargin=42, title="Протокол совещания",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
