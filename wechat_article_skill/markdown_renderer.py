import html
import re
from typing import Any


_IMAGE_PATTERN = re.compile(r"!\[(.*?)\]\((.*?)\)")


def extract_markdown_images(markdown_text: str) -> list[dict[str, Any]]:
    images = []
    for match in _IMAGE_PATTERN.finditer(markdown_text):
        images.append(
            {
                "alt": match.group(1).strip(),
                "path": match.group(2).strip(),
                "start": match.start(),
                "end": match.end(),
            }
        )
    return images


def replace_markdown_image_paths(markdown_text: str, path_mapping: dict[str, str]) -> str:
    text = markdown_text
    for original, replacement in path_mapping.items():
        text = text.replace(f"]({original})", f"]({replacement})")
    return text


def strip_top_level_title(markdown_text: str) -> str:
    if not markdown_text.startswith("# "):
        return markdown_text.strip()
    first_newline = markdown_text.find("\n")
    if first_newline == -1:
        return ""
    return markdown_text[first_newline + 1 :].strip()


def strip_leading_cover_image(markdown_text: str) -> str:
    text = markdown_text.lstrip()
    image_match = _IMAGE_PATTERN.match(text)
    if not image_match:
        return markdown_text.strip()
    remainder = text[image_match.end():].lstrip("\r\n")
    return remainder.strip()


def strip_prompt_sections(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    kept_lines: list[str] = []
    skip_mode: str | None = None

    for line in lines:
        stripped = line.strip()
        if stripped == "## 封面图提示词":
            skip_mode = "cover"
            continue
        if stripped == "## 配图提示词":
            skip_mode = "body"
            continue
        if stripped == "## 正文":
            skip_mode = None
            continue

        if skip_mode is not None:
            continue
        kept_lines.append(line)

    return "\n".join(kept_lines).strip()


def markdown_to_wechat_html(markdown_text: str) -> str:
    lines = markdown_text.strip().splitlines()
    blocks: list[str] = []
    list_items: list[str] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            content = "<br/>".join(html.escape(line.strip()) for line in paragraph_lines if line.strip())
            if content:
                blocks.append(f"<p>{content}</p>")
            paragraph_lines = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(list_items) + "</ul>")
            list_items = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        image_match = _IMAGE_PATTERN.fullmatch(stripped)
        if image_match:
            flush_paragraph()
            flush_list()
            alt = html.escape(image_match.group(1).strip())
            src = html.escape(image_match.group(2).strip(), quote=True)
            blocks.append(f'<p><img src="{src}" alt="{alt}" /></p>')
            continue

        if stripped.startswith("### "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h3>{html.escape(stripped[4:].strip())}</h3>")
            continue

        if stripped.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h2>{html.escape(stripped[3:].strip())}</h2>")
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            list_items.append(f"<li>{html.escape(stripped[2:].strip())}</li>")
            continue

        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_list()
    return "\n".join(blocks)
