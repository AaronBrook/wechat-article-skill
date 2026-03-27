import argparse
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path: str | Path) -> bool:
        path = Path(dotenv_path)
        if not path.exists():
            return False
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        return True

from .generator import generate_wechat_article
from .pipeline import generate_images_for_existing_article, generate_wechat_article_with_images, publish_article_from_existing_json


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate WeChat article markdown from SKILL.md prompt")
    parser.add_argument("topic", nargs="?", help="Article topic")
    parser.add_argument("--extra", default="", help="Extra requirements")
    parser.add_argument("--model", default="qwen-plus", help="DashScope model name")
    parser.add_argument("--with-images", action="store_true", help="Generate article images too")
    parser.add_argument("--mode", choices=["article", "images", "all", "publish"], default=None, help="Generation mode")
    parser.add_argument("--from-json", default="", help="Generate images from an existing article json file")
    parser.add_argument("--article-with-images", default="", help="Existing article.with_images.md path")
    parser.add_argument("--author", default="", help="WeChat draft author")
    parser.add_argument("--digest", default="", help="WeChat draft digest")
    parser.add_argument("--content-source-url", default="", help="WeChat draft content source url")
    parser.add_argument("--dry-run", action="store_true", help="Validate publish payload without remote API calls")
    parser.add_argument("--need-open-comment", type=int, choices=[0, 1], default=None, help="Enable comments for WeChat draft")
    parser.add_argument("--only-fans-can-comment", type=int, choices=[0, 1], default=None, help="Allow only fans to comment")
    parser.add_argument("--image-model", default="wanx2.1-t2i-turbo", help="Image generation model")
    parser.add_argument("--cover-size", default="1280*720", help="Cover image size")
    parser.add_argument("--body-size", default="1024*1024", help="Body image size")
    parser.add_argument("--image-style", default="<auto>", help="Image style")
    args = parser.parse_args()

    mode = args.mode or ("all" if args.with_images else "article")

    if mode == "images":
        if not args.from_json:
            raise SystemExit("--mode images 需要配合 --from-json 使用")
        result = generate_images_for_existing_article(
            article_json_path=args.from_json,
            image_model=args.image_model,
            cover_size=args.cover_size,
            body_size=args.body_size,
            image_style=args.image_style,
        )
    elif mode == "all":
        if not args.topic:
            raise SystemExit("--mode all 需要提供 topic")
        result = generate_wechat_article_with_images(
            topic=args.topic,
            extra_requirements=args.extra,
            model=args.model,
            image_model=args.image_model,
            cover_size=args.cover_size,
            body_size=args.body_size,
            image_style=args.image_style,
        )
    elif mode == "publish":
        if not args.from_json:
            raise SystemExit("--mode publish 需要配合 --from-json 使用")
        result = publish_article_from_existing_json(
            article_json_path=args.from_json,
            article_with_images_path=args.article_with_images,
            author=args.author,
            digest=args.digest,
            content_source_url=args.content_source_url,
            dry_run=args.dry_run,
            need_open_comment=args.need_open_comment,
            only_fans_can_comment=args.only_fans_can_comment,
        )
    else:
        if not args.topic:
            raise SystemExit("--mode article 需要提供 topic")
        result = generate_wechat_article(
            topic=args.topic,
            extra_requirements=args.extra,
            model=args.model,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
