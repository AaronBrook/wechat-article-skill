import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dashscope import Generation


ROOT_DIR = Path(__file__).resolve().parent.parent
SKILL_FILE = ROOT_DIR / "SKILL.md"
OUTPUT_DIR = ROOT_DIR / "output" / "articles"


class WechatArticleGenerationError(RuntimeError):
    pass


def load_skill_prompt(skill_file: Path = SKILL_FILE) -> str:
    content = skill_file.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) == 3:
            content = parts[2].lstrip("\n")
    return content.strip()


def build_user_prompt(topic: str, extra_requirements: str = "") -> str:
    prompt = (
        "请根据 system prompt 的要求，为下面主题生成一篇公众号文章，并严格只返回 JSON。\n"
        "文章要从普通人的奋斗、打拼、上升焦虑、时代变化与历史进程的关系切入，避免写成廉价鸡汤。\n"
        f"主题：{topic}\n"
    )
    if extra_requirements.strip():
        prompt += f"补充要求：{extra_requirements.strip()}\n"
    return prompt


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise WechatArticleGenerationError("模型返回内容不是有效 JSON")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise WechatArticleGenerationError(f"无法解析模型返回的 JSON: {exc}") from exc


def _slugify_filename(title: str) -> str:
    safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title, flags=re.UNICODE).strip("-")
    return safe[:60] or "wechat-article"


def _validate_article_data(data: dict[str, Any]) -> list[str]:
    warnings = []
    if not str(data.get("new_title", "")).strip():
        raise WechatArticleGenerationError("模型返回缺少 new_title")
    if not str(data.get("new_wechat_title", "")).strip():
        warnings.append("missing_wechat_title")

    has_content = bool(str(data.get("new_content", "")).strip()) or bool(str(data.get("new_content_markdown", "")).strip())
    if not has_content:
        raise WechatArticleGenerationError("模型返回缺少正文内容")

    sections = data.get("new_sections", []) or []
    if sections:
        for idx, section in enumerate(sections, start=1):
            if not str(section.get("id", "")).strip():
                raise WechatArticleGenerationError(f"new_sections[{idx}] 缺少 id")
            if not str(section.get("heading", "")).strip():
                raise WechatArticleGenerationError(f"new_sections[{idx}] 缺少 heading")
            if not str(section.get("body", "")).strip():
                raise WechatArticleGenerationError(f"new_sections[{idx}] 缺少 body")

        content_markdown = str(data.get("new_content_markdown", "")).strip()
        if content_markdown:
            for section in sections:
                marker = f"[IMG:{section['id']}]"
                if marker not in content_markdown:
                    warnings.append(f"missing_marker:{section['id']}")
    return warnings


def _article_markdown(data: dict[str, Any]) -> str:
    title = str(data.get("new_title", "未命名文章")).strip()
    content = str(data.get("new_content_markdown") or data.get("new_content", "")).replace("\\n", "\n").strip()
    cover = str(data.get("new_cover_img_prompt", "")).strip()
    image_prompts = data.get("new_img_prompt", [])

    lines = [f"# {title}", ""]
    if cover:
        lines.extend(["## 封面图提示词", "", cover, ""])
    if image_prompts:
        lines.extend(["## 配图提示词", ""])
        for idx, prompt in enumerate(image_prompts, start=1):
            lines.append(f"{idx}. {prompt}")
        lines.append("")
    lines.extend(["## 正文", "", content, ""])
    return "\n".join(lines).strip() + "\n"


def generate_wechat_article(
    topic: str,
    extra_requirements: str = "",
    model: str = "qwen-plus",
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise WechatArticleGenerationError("未检测到 DASHSCOPE_API_KEY")

    system_prompt = load_skill_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_user_prompt(topic, extra_requirements)},
    ]

    response = Generation.call(
        api_key=api_key,
        model=model,
        messages=messages,
        result_format="message",
    )

    if response.status_code != 200:
        raise WechatArticleGenerationError(
            f"调用失败 [{response.status_code}] {response.code}: {response.message}"
        )

    raw_text = response.output.choices[0].message.content
    data = _extract_json(raw_text)
    warnings = _validate_article_data(data)

    title = str(data.get("new_title", "未命名文章")).strip()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify_filename(title)
    markdown_path = output_dir / f"{timestamp}_{slug}.md"
    json_path = output_dir / f"{timestamp}_{slug}.json"

    markdown_path.write_text(_article_markdown(data), encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "title": title,
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
        "cover_prompt": data.get("new_cover_img_prompt", ""),
        "image_prompts": data.get("new_img_prompt", []),
        "content": data.get("new_content", ""),
        "wechat_title": data.get("new_wechat_title", ""),
        "angle": data.get("new_angle", ""),
        "summary": data.get("new_summary", ""),
        "sections": data.get("new_sections", []),
        "content_markdown": data.get("new_content_markdown", ""),
        "takeaway": data.get("new_takeaway", ""),
        "warnings": warnings,
        "raw": data,
    }
