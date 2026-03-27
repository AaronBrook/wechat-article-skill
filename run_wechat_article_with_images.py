import sys

from wechat_article_skill.cli import main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        raise SystemExit('请提供文章主题，例如：python3.10 run_wechat_article_with_images.py "你的主题"')
    if sys.argv[1].startswith("--"):
        sys.argv.insert(1, "占位主题")
    if "--mode" not in sys.argv and "--with-images" not in sys.argv:
        sys.argv.extend(["--mode", "all"])
    main()
