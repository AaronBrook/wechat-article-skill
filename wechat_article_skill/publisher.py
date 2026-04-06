import json
from pathlib import Path
from typing import Any

from .generator import _slugify_filename
from .github_uploader import GitHubImageUploader
from .markdown_renderer import extract_markdown_images, markdown_to_wechat_html, replace_markdown_image_paths, strip_leading_cover_image, strip_prompt_sections, strip_top_level_title
from .wechat_client import WeChatOfficialAccountClient


class PublishError(RuntimeError):
    pass


def _truncate_utf8_bytes(text: str, max_bytes: int) -> str:
    value = text.strip()
    while value and len(value.encode("utf-8")) > max_bytes:
        value = value[:-1]
    return value.rstrip("，。！？、；：,.!?:; ")


def _load_article_data(article_json_path: str) -> dict[str, Any]:
    json_path = Path(article_json_path)
    if not json_path.exists():
        raise PublishError(f"article.json 不存在: {json_path}")
    return json.loads(json_path.read_text(encoding="utf-8"))


def _resolve_bundle_paths(article_json_path: str, article_with_images_path: str = "") -> tuple[Path, Path, Path]:
    json_path = Path(article_json_path)
    if json_path.name == "article.json" and (json_path.parent / "article.with_images.md").exists():
        bundle_dir = json_path.parent
    else:
        data = _load_article_data(article_json_path)
        title = str(data.get("new_title", "未命名文章")).strip()
        base_name = json_path.stem
        slug = _slugify_filename(title)
        if slug and not base_name.endswith(slug):
            base_name = f"{base_name}_{slug}"
        bundle_dir = json_path.parent / base_name

    markdown_with_images = Path(article_with_images_path) if article_with_images_path else bundle_dir / "article.with_images.md"
    if not markdown_with_images.exists():
        raise PublishError(f"带图文章不存在: {markdown_with_images}，请先执行 --mode all 或 --mode images")
    return bundle_dir, json_path, markdown_with_images


def _resolve_markdown_images(markdown_path: Path) -> list[dict[str, Any]]:
    markdown_text = markdown_path.read_text(encoding="utf-8")
    images = extract_markdown_images(markdown_text)
    resolved = []
    for item in images:
        relative_path = item["path"]
        if relative_path.startswith("http://") or relative_path.startswith("https://"):
            continue
        absolute_path = (markdown_path.parent / relative_path).resolve()
        if not absolute_path.exists():
            raise PublishError(f"正文引用图片不存在: {relative_path}")
        resolved.append({**item, "absolute_path": absolute_path})
    return resolved


def _select_cover_image(resolved_images: list[dict[str, Any]]) -> Path:
    for item in resolved_images:
        if item["path"].startswith("images/cover/"):
            return Path(item["absolute_path"])
    raise PublishError("未找到封面图引用，无法创建微信公众号草稿")


def _build_publish_metadata(data: dict[str, Any], author: str, digest: str, content_source_url: str) -> dict[str, str]:
    wechat_title = str(data.get("new_wechat_title", "")).strip()
    title = wechat_title or str(data.get("new_title", "未命名文章")).strip()
    title = _truncate_utf8_bytes(title, 64)

    summary = digest.strip() or str(data.get("new_summary", "")).strip()
    summary = _truncate_utf8_bytes(summary, 54)
    return {
        "title": title,
        "author": author.strip(),
        "digest": summary,
        "content_source_url": content_source_url.strip(),
    }


def publish_existing_article_from_json(
    article_json_path: str,
    *,
    article_with_images_path: str = "",
    author: str = "",
    digest: str = "",
    content_source_url: str = "",
    dry_run: bool = False,
    need_open_comment: int | None = None,
    only_fans_can_comment: int | None = None,
) -> dict[str, Any]:
    bundle_dir, json_path, markdown_with_images_path = _resolve_bundle_paths(article_json_path, article_with_images_path)
    data = _load_article_data(str(json_path))
    markdown_text = markdown_with_images_path.read_text(encoding="utf-8")
    resolved_images = _resolve_markdown_images(markdown_with_images_path)
    if not resolved_images:
        raise PublishError("带图文章中没有可上传的本地图片引用")

    wechat_client = WeChatOfficialAccountClient()
    metadata = _build_publish_metadata(
        data,
        author=author or wechat_client.default_author,
        digest=digest,
        content_source_url=content_source_url or wechat_client.default_content_source_url,
    )
    if not metadata["author"]:
        raise PublishError("缺少作者信息，请配置 WECHAT_OFFICIAL_ACCOUNT_AUTHOR 或通过 --author 传入")
    if not metadata["digest"]:
        raise PublishError("缺少摘要信息，请配置 new_summary 或通过 --digest 传入")

    warnings = []

    if dry_run:
        uploader = GitHubImageUploader()
        bundle_name = _slugify_filename(bundle_dir.name)
        planned_paths = [item["path"] for item in resolved_images]
        warnings = ["dry-run 预览中的图片链接使用 GitHub Pages，仅用于本地预览，不代表最终微信正文图片来源"]
        upload_mapping = uploader.plan_uploads(bundle_name, planned_paths)
        replaced_markdown = replace_markdown_image_paths(markdown_text, upload_mapping)
        cleaned_markdown = strip_leading_cover_image(strip_prompt_sections(strip_top_level_title(replaced_markdown)))
        html_content = markdown_to_wechat_html(cleaned_markdown)
        preview_path = bundle_dir / "article.wechat.preview.html"
        preview_path.write_text(html_content, encoding="utf-8")
        return {
            "success": True,
            "mode": "dry-run",
            "bundle_dir": str(bundle_dir),
            "article_json_path": str(json_path),
            "article_with_images_path": str(markdown_with_images_path),
            "html_preview_path": str(preview_path),
            "github_uploads": upload_mapping,
            "wechat_payload": {
                "title": metadata["title"],
                "author": metadata["author"],
                "digest": metadata["digest"],
                "content_source_url": metadata["content_source_url"],
                "need_open_comment": need_open_comment,
                "only_fans_can_comment": only_fans_can_comment,
            },
            "warnings": warnings,
            "error": None,
        }

    access_token = wechat_client.get_access_token()
    upload_mapping = {}
    cover_image = _select_cover_image(resolved_images)
    body_image_uploads = []
    for item in resolved_images:
        if item["path"].startswith("images/cover/"):
            continue
        article_image = wechat_client.upload_article_image(access_token, item["absolute_path"])
        body_image_uploads.append({
            "path": item["path"],
            "absolute_path": str(item["absolute_path"]),
            "url": article_image["url"],
        })
        upload_mapping[item["path"]] = article_image["url"]

    replaced_markdown = replace_markdown_image_paths(markdown_text, upload_mapping)
    cleaned_markdown = strip_leading_cover_image(strip_prompt_sections(strip_top_level_title(replaced_markdown)))
    html_content = markdown_to_wechat_html(cleaned_markdown)
    preview_path = bundle_dir / "article.wechat.preview.html"
    preview_path.write_text(html_content, encoding="utf-8")

    cover_upload = wechat_client.upload_image_material(access_token, cover_image)
    draft_result = wechat_client.add_draft(
        access_token,
        title=metadata["title"],
        author=metadata["author"],
        digest=metadata["digest"],
        content=html_content,
        thumb_media_id=str(cover_upload["media_id"]),
        content_source_url=metadata["content_source_url"],
        need_open_comment=need_open_comment,
        only_fans_can_comment=only_fans_can_comment,
    )

    return {
        "success": True,
        "mode": "publish",
        "bundle_dir": str(bundle_dir),
        "article_json_path": str(json_path),
        "article_with_images_path": str(markdown_with_images_path),
        "html_preview_path": str(preview_path),
        "github_uploads": {
            "mapping": {},
            "assets": [],
        },
        "wechat_draft": {
            "cover_upload": cover_upload,
            "body_image_uploads": body_image_uploads,
            "draft": draft_result,
        },
        "warnings": warnings,
        "error": None,
    }
