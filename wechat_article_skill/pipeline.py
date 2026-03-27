import json
import re
import shutil
from pathlib import Path
from typing import Any

from text_2_image import text_to_image_skill

from .generator import OUTPUT_DIR, _slugify_filename, generate_wechat_article
from .publisher import publish_existing_article_from_json


def _bundle_dir_from_article(markdown_path: str, title: str) -> Path:
    article_path = Path(markdown_path)
    base_name = article_path.stem
    slug = _slugify_filename(title)
    if slug and not base_name.endswith(slug):
        base_name = f"{base_name}_{slug}"
    return article_path.parent / base_name


def _copy_article_files(article_result: dict[str, Any], bundle_dir: Path) -> tuple[Path, Path]:
    source_markdown = Path(article_result["markdown_path"])
    source_json = Path(article_result["json_path"])
    article_md = bundle_dir / "article.md"
    article_json = bundle_dir / "article.json"
    shutil.copy2(source_markdown, article_md)
    shutil.copy2(source_json, article_json)
    return article_md, article_json


def _relative_markdown_path(from_file: Path, target_file: str) -> str:
    return Path(target_file).relative_to(from_file.parent).as_posix()


def _inject_images_into_markdown(markdown_text: str, cover_path: str | None, body_paths: list[str], sections: list[dict[str, Any]] | None = None) -> str:
    text = markdown_text

    if cover_path:
        cover_markdown = f"![封面图]({cover_path})\n"
        if text.startswith("# "):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[: first_newline + 1] + "\n" + cover_markdown + text[first_newline + 1 :]
            else:
                text = text + "\n\n" + cover_markdown
        else:
            text = cover_markdown + "\n" + text

    section_map = {}
    if sections:
        for index, section in enumerate(sections):
            if index < len(body_paths):
                section_map[str(section.get("id", "")).strip()] = body_paths[index]

    if section_map:
        for section_id, image_path in section_map.items():
            marker = f"[IMG:{section_id}]"
            image_markdown = f"![正文配图]({image_path})"
            text = text.replace(marker, image_markdown)
        return text if text.endswith("\n") else text + "\n"

    for image_path in body_paths:
        image_markdown = f"![正文配图]({image_path})"
        if "《图片》" in text:
            text = text.replace("《图片》", image_markdown, 1)
        else:
            match = re.search(r"(?m)^### .+$", text)
            if match:
                insert_at = text.find("\n", match.end())
                if insert_at == -1:
                    text += f"\n\n{image_markdown}\n"
                else:
                    text = text[: insert_at + 1] + image_markdown + "\n" + text[insert_at + 1 :]
            else:
                text += f"\n\n{image_markdown}\n"

    return text if text.endswith("\n") else text + "\n"


def _load_existing_article(article_json_path: str) -> dict[str, Any]:
    json_path = Path(article_json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    title = str(data.get("new_title", "未命名文章")).strip()
    markdown_path = json_path.with_suffix(".md")
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
        "warnings": [],
        "raw": data,
    }


def _generate_with_article_result(
    article_result: dict[str, Any],
    topic: str,
    image_model: str,
    cover_size: str,
    body_size: str,
    image_style: str,
) -> dict[str, Any]:
    title = str(article_result["title"])
    bundle_dir = _bundle_dir_from_article(article_result["markdown_path"], title)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    article_md, article_json = _copy_article_files(article_result, bundle_dir)

    image_root = bundle_dir / "images"
    cover_dir = image_root / "cover"
    body_dir = image_root / "body"

    cover_result = {
        "success": False,
        "urls": [],
        "saved_paths": [],
        "prompt": article_result.get("cover_prompt", ""),
        "model": image_model,
        "error": None,
    }
    if article_result.get("cover_prompt"):
        cover_result = text_to_image_skill(
            prompt=article_result["cover_prompt"],
            model=image_model,
            size=cover_size,
            n=1,
            style=image_style,
            save_dir=str(cover_dir),
        )

    prompts = article_result.get("image_prompts", [])
    if article_result.get("sections"):
        prompts = [section.get("image_prompt", "") for section in article_result["sections"] if section.get("image_prompt")]

    body_results = []
    for index, prompt in enumerate(prompts, start=1):
        result = text_to_image_skill(
            prompt=prompt,
            model=image_model,
            size=body_size,
            n=1,
            style=image_style,
            save_dir=str(body_dir),
        )
        body_results.append({"index": index, **result})

    markdown_text = article_md.read_text(encoding="utf-8")
    if article_result.get("content_markdown"):
        markdown_text = markdown_text.replace(str(article_result.get("content", "")).replace("\\n", "\n").strip(), str(article_result.get("content_markdown", "")).replace("\\n", "\n").strip())

    cover_relative = None
    if cover_result.get("saved_paths"):
        cover_relative = _relative_markdown_path(article_md, cover_result["saved_paths"][0])

    body_relative_paths = []
    for result in body_results:
        saved_paths = result.get("saved_paths", [])
        if saved_paths:
            body_relative_paths.append(_relative_markdown_path(article_md, saved_paths[0]))

    markdown_with_images = _inject_images_into_markdown(markdown_text, cover_relative, body_relative_paths, article_result.get("sections", []))
    markdown_with_images_path = bundle_dir / "article.with_images.md"
    markdown_with_images_path.write_text(markdown_with_images, encoding="utf-8")

    body_image_success_count = sum(1 for item in body_results if item.get("success"))
    body_image_failed_count = len(body_results) - body_image_success_count

    result = {
        "success": True,
        "topic": topic,
        "title": title,
        "article": {
            "markdown_path": str(article_md),
            "json_path": str(article_json),
            "markdown_with_images_path": str(markdown_with_images_path),
            "cover_prompt": article_result.get("cover_prompt", ""),
            "image_prompts": article_result.get("image_prompts", []),
            "content": article_result.get("content", ""),
            "wechat_title": article_result.get("wechat_title", ""),
            "angle": article_result.get("angle", ""),
            "summary": article_result.get("summary", ""),
            "sections": article_result.get("sections", []),
            "content_markdown": article_result.get("content_markdown", ""),
            "takeaway": article_result.get("takeaway", ""),
            "warnings": article_result.get("warnings", []),
            "raw": article_result.get("raw", {}),
        },
        "images": {
            "cover": cover_result,
            "body": body_results,
        },
        "summary": {
            "cover_generated": bool(cover_result.get("success") and cover_result.get("saved_paths")),
            "body_image_count": len(body_results),
            "body_image_success_count": body_image_success_count,
            "body_image_failed_count": body_image_failed_count,
        },
        "error": None,
    }

    if not cover_result.get("success") or body_image_failed_count:
        result["success"] = False
        result["error"] = "部分图片生成失败" if prompts else "封面图生成失败"

    return result


def generate_wechat_article_with_images(
    topic: str,
    extra_requirements: str = "",
    model: str = "qwen-plus",
    image_model: str = "wanx2.1-t2i-turbo",
    cover_size: str = "1280*720",
    body_size: str = "1024*1024",
    image_style: str = "<auto>",
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    article_result = generate_wechat_article(
        topic=topic,
        extra_requirements=extra_requirements,
        model=model,
        output_dir=output_dir,
    )
    return _generate_with_article_result(
        article_result=article_result,
        topic=topic,
        image_model=image_model,
        cover_size=cover_size,
        body_size=body_size,
        image_style=image_style,
    )


def generate_images_for_existing_article(
    article_json_path: str,
    image_model: str = "wanx2.1-t2i-turbo",
    cover_size: str = "1280*720",
    body_size: str = "1024*1024",
    image_style: str = "<auto>",
) -> dict[str, Any]:
    article_result = _load_existing_article(article_json_path)
    return _generate_with_article_result(
        article_result=article_result,
        topic=article_result["title"],
        image_model=image_model,
        cover_size=cover_size,
        body_size=body_size,
        image_style=image_style,
    )


def publish_article_from_existing_json(
    article_json_path: str,
    article_with_images_path: str = "",
    author: str = "",
    digest: str = "",
    content_source_url: str = "",
    dry_run: bool = False,
    need_open_comment: int | None = None,
    only_fans_can_comment: int | None = None,
) -> dict[str, Any]:
    return publish_existing_article_from_json(
        article_json_path=article_json_path,
        article_with_images_path=article_with_images_path,
        author=author,
        digest=digest,
        content_source_url=content_source_url,
        dry_run=dry_run,
        need_open_comment=need_open_comment,
        only_fans_can_comment=only_fans_can_comment,
    )
