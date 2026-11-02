import re
from collections import namedtuple
from html.parser import HTMLParser
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate

TextRun = namedtuple("TextRun", "text bold italic underline")
Block = namedtuple("Block", "runs alignment")

LINE_BREAK = "\n"
MD_PAGE_BREAK = '<div style="page-break-after: always;"></div>'
BLOCK_TAGS = {"p", "div"}
STYLE_TAGS = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic", "u": "underline"}
PDF_ALIGNMENTS = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT, "justify": TA_JUSTIFY}

MD_SPECIAL_CHARS = re.compile(r"([\\`*_\[\]<>&~#])")
MD_LINE_START = re.compile(r"^(\s*\d*)([+=-]|(?<=\d)[.)])")


class _ChapterParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self._runs = None
        self._alignment = "left"
        self._depths = {"bold": 0, "italic": 0, "underline": 0}

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self._close_block()
            self._runs = []
            self._alignment = _alignment_from_style(dict(attrs).get("style"))
        elif tag == "br":
            if self._runs is not None:
                self._runs.append(TextRun(LINE_BREAK, False, False, False))
        elif tag in STYLE_TAGS:
            self._depths[STYLE_TAGS[tag]] += 1

    def handle_endtag(self, tag):
        if tag in BLOCK_TAGS:
            self._close_block()
        elif tag in STYLE_TAGS:
            style = STYLE_TAGS[tag]
            self._depths[style] = max(0, self._depths[style] - 1)

    def handle_data(self, data):
        text = re.sub(r"\s+", " ", data)
        if self._runs is None:
            if not text.strip():
                return
            self._runs = []
            self._alignment = "left"
        self._runs.append(TextRun(text, self._depths["bold"] > 0, self._depths["italic"] > 0,
                                  self._depths["underline"] > 0))

    def close(self):
        super().close()
        self._close_block()

    def _close_block(self):
        if self._runs:
            runs = _normalize_runs(self._runs)
            if runs:
                self.blocks.append(Block(runs, self._alignment))
        self._runs = None


def _alignment_from_style(style):
    match = re.search(r"text-align\s*:\s*(\w+)", style or "")
    return match.group(1).lower() if match else "left"


def _strip_line_end(runs):
    while runs and runs[-1].text != LINE_BREAK:
        text = runs[-1].text.rstrip()
        if text:
            runs[-1] = runs[-1]._replace(text=text)
            return
        runs.pop()


def _normalize_runs(runs):
    """Merge neighbouring runs and drop the spacing HTML wouldn't have displayed."""
    result = []
    for run in runs:
        if run.text == LINE_BREAK:
            _strip_line_end(result)
            result.append(run)
            continue

        text = run.text
        if not result or result[-1].text == LINE_BREAK or result[-1].text.endswith(" "):
            text = text.lstrip()
        if not text:
            continue

        if result and result[-1].text != LINE_BREAK and result[-1][1:] == run[1:]:
            result[-1] = result[-1]._replace(text=result[-1].text + text)
        else:
            result.append(run._replace(text=text))

    _strip_line_end(result)
    while result and result[-1].text == LINE_BREAK:
        result.pop()
        _strip_line_end(result)
    while result and result[0].text == LINE_BREAK:
        result.pop(0)
    return result


def clean_html(html):
    """Turn chapter HTML into a list of Blocks with the tags removed."""
    parser = _ChapterParser()
    parser.feed(html)
    parser.close()
    return parser.blocks


def count_characters(html):
    """Return how many characters of text a chapter has, including spaces."""
    return sum(len(run.text) for block in clean_html(html) for run in block.runs if run.text != LINE_BREAK)


def count_words(html):
    """Return how many words a chapter has, ignoring standalone symbols like dashes."""
    words = 0
    for block in clean_html(html):
        text = "".join(run.text for run in block.runs)
        words += sum(any(char.isalnum() for char in token) for token in text.split())
    return words


def _escape_markdown(text, at_line_start):
    text = MD_SPECIAL_CHARS.sub(r"\\\1", text)
    if not at_line_start:
        return text
    return MD_LINE_START.sub(lambda m: m.group(1) + "\\" + m.group(2), text)


def _markdown_run(run, at_line_start):
    text = _escape_markdown(run.text, at_line_start)
    marker = "*" * (2 * run.bold + run.italic)
    stripped = text.strip()
    if not marker or not stripped:
        return text
    # Markdown ignores emphasis markers that sit next to a space
    leading = text[:len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()):]
    return f"{leading}{marker}{stripped}{marker}{trailing}"


def _markdown_block(block):
    parts = []
    at_line_start = True
    for run in block.runs:
        if run.text == LINE_BREAK:
            parts.append("  \n")
            at_line_start = True
        else:
            parts.append(_markdown_run(run, at_line_start))
            at_line_start = False
    return "".join(parts)


def _pdf_markup(block):
    parts = []
    for run in block.runs:
        if run.text == LINE_BREAK:
            parts.append("<br/>")
            continue
        text = escape(run.text)
        if run.underline:
            text = f"<u>{text}</u>"
        if run.italic:
            text = f"<i>{text}</i>"
        if run.bold:
            text = f"<b>{text}</b>"
        parts.append(text)
    return "".join(parts)


def _markdown_chapter(title, html, heading):
    sections = [f"{heading} {_escape_markdown(title.strip(), False)}"]
    sections += [_markdown_block(block) for block in clean_html(html)]
    return "\n\n".join(sections)


def _pdf_chapter(title, html, styles):
    content = [Paragraph(escape(title.strip()), styles["Title"])]
    for block in clean_html(html):
        style = ParagraphStyle(
            "Chapter",
            parent=styles["BodyText"],
            fontSize=11,
            leading=15,
            spaceAfter=8,
            alignment=PDF_ALIGNMENTS.get(block.alignment, TA_LEFT),
        )
        content.append(Paragraph(_pdf_markup(block), style))
    return content


def chapter_to_markdown(title, html, output_path):
    """Write a chapter to a .md file, with title as the top-level heading."""
    Path(output_path).write_text(_markdown_chapter(title, html, "#") + "\n", encoding="utf-8")


def chapter_to_pdf(title, html, output_path):
    """Write a chapter to a .pdf file, with title as a heading and the PDF's title."""
    content = _pdf_chapter(title, html, getSampleStyleSheet())
    SimpleDocTemplate(str(output_path), pagesize=A4, title=title.strip()).build(content)


def _markdown_first_page(story_title, metadata):
    lines = [f"# {_escape_markdown(story_title.strip(), False)}"]
    for label, value in metadata.items():
        shown = f"<{value}>" if value.startswith("https://") else _escape_markdown(value, False)
        lines.append(f"**{label}:** {shown}")
    return "\n\n".join(lines)


def _pdf_first_page(story_title, metadata, styles):
    title_style = ParagraphStyle("StoryTitle", parent=styles["Title"], fontSize=24, leading=30, spaceAfter=24)
    detail_style = ParagraphStyle(
        "StoryDetail", parent=styles["BodyText"], fontSize=11, leading=15, spaceAfter=8, alignment=TA_CENTER
    )
    content = [Paragraph(escape(story_title.strip()), title_style)]
    for label, value in metadata.items():
        shown = escape(value)
        if value.startswith("https://"):
            shown = f'<a href={quoteattr(value)} color="blue">{shown}</a>'
        content.append(Paragraph(f"<b>{escape(label)}:</b> {shown}", detail_style))
    return content


class _Bookmark(Flowable):
    """An invisible marker that adds the current page to the PDF's bookmarks."""

    def __init__(self, title, key):
        super().__init__()
        self.title = title
        self.key = key

    def wrap(self, available_width, available_height):
        return 0, 0

    def draw(self):
        # XYZ with a zoom of 0 goes to the top of the page and keeps the reader's zoom
        self.canv.bookmarkPage(self.key, fit="XYZ", left=0, top=A4[1], zoom=0)
        self.canv.addOutlineEntry(self.title, self.key, level=0)


def story_to_markdown(story_title, metadata, chapters, output_path):
    """Write a first page of story details, then (title, html) chapters, to one .md file."""
    sections = [_markdown_first_page(story_title, metadata)]
    sections += [_markdown_chapter(title, html, "##") for title, html in chapters]
    body = f"\n\n{MD_PAGE_BREAK}\n\n".join(sections)
    Path(output_path).write_text(f"{body}\n", encoding="utf-8")


def story_to_pdf(story_title, metadata, chapters, output_path):
    """Write a first page of story details, then bookmarked (title, html) chapters, to one .pdf file."""
    styles = getSampleStyleSheet()
    content = _pdf_first_page(story_title, metadata, styles)
    for number, (title, html) in enumerate(chapters, start=1):
        content.append(PageBreak())
        content.append(_Bookmark(title.strip(), f"chapter-{number}"))
        content += _pdf_chapter(title, html, styles)
    SimpleDocTemplate(str(output_path), pagesize=A4, title=story_title.strip()).build(content)
