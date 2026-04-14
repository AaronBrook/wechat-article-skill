# wechat_article_skill

一套用于生成微信公众号文章、自动配图并写入公众号草稿箱的工作流。

## 它能做什么
- 根据主题生成结构化文章
- 为封面和正文段落生成配图
- 把 Markdown 清洗并转换成微信公众号正文 HTML
- 把正文图片和封面图片上传到微信
- 创建公众号草稿，供你在后台二次编辑后发布

## 文生图说明
本项目的文生图能力现在支持两种后端，统一通过 [text_2_image.py](text_2_image.py) 调用：

- **阿里云百炼 / 通义千问图像生成能力（Wanx）**
- **Nano Banana 2**（通过 OpenAI 兼容 relay API 接入）

当前常用配置：
- Wanx：`DASHSCOPE_API_KEY`
- Nano Banana 2：`NANO_BANANA_BASE_URL`、`NANO_BANANA_API_KEY`、`NANO_BANANA_MODEL`、`NANO_BANANA_TIMEOUT_SECONDS`
- 后端选择：`IMAGE_BACKEND=wanx` 或 `IMAGE_BACKEND=nano_banana_2`

用途分为两类：
- 封面图生成
- 正文分段配图生成

说明：
- 真实发布时，最终仍然是把本地图片上传到微信，因此不管前面用 Wanx 还是 Nano Banana 2，后续发布链路都不需要变。
- 默认仍是 Wanx，只有在显式切换 `IMAGE_BACKEND` 或传入 `--image-backend nano_banana_2` 时，才走 Nano Banana 2。
- `gemini-3.1-flash-image-preview` 在部分 relay 上返回较慢，建议为 Nano Banana 2 预留更长超时；可通过 `NANO_BANANA_TIMEOUT_SECONDS` 调整，默认 `240` 秒。
- 发布到公众号草稿箱时，正文会自动移除开头那张封面图，只保留公众号封面位，避免草稿预览里首图重复或显示异常。

## 项目结构
- [SKILL.md](SKILL.md)：机器使用的 Prompt 与输出契约
- [run_wechat_article.py](run_wechat_article.py)：默认生成文章入口
- [run_wechat_article_with_images.py](run_wechat_article_with_images.py)：默认生成带图文章入口
- [wechat_article_skill/](wechat_article_skill/)：核心代码
- [.env.example](.env.example)：环境变量模板
- [docs/WORKFLOW.md](docs/WORKFLOW.md)：工作流说明
- [docs/WECHAT.md](docs/WECHAT.md)：微信侧限制与排障

## 环境准备
复制 `.env.example` 为 `.env`，按实际账号填写：

```env
DASHSCOPE_API_KEY=
IMAGE_BACKEND=wanx
NANO_BANANA_BASE_URL=https://api.laozhang.ai/v1
NANO_BANANA_API_KEY=
NANO_BANANA_MODEL=gemini-3.1-flash-image-preview
NANO_BANANA_TIMEOUT_SECONDS=240

WECHAT_OFFICIAL_ACCOUNT_APP_ID=
WECHAT_OFFICIAL_ACCOUNT_APP_SECRET=
WECHAT_OFFICIAL_ACCOUNT_AUTHOR=
WECHAT_OFFICIAL_ACCOUNT_CONTENT_SOURCE_URL=
WECHAT_OFFICIAL_ACCOUNT_NEED_OPEN_COMMENT=1
WECHAT_OFFICIAL_ACCOUNT_ONLY_FANS_CAN_COMMENT=0

GITHUB_TOKEN=
GITHUB_REPO_OWNER=
GITHUB_REPO_NAME=
GITHUB_REPO_BRANCH=main
GITHUB_IMAGE_BASE_PATH=wechat-assets
GITHUB_COMMITTER_NAME=
GITHUB_COMMITTER_EMAIL=
GITHUB_PAGES_BASE_URL=
```

说明：
- 真实发布现在主要依赖微信图片接口，GitHub / Pages 主要用于 dry-run 预览和调试。
- 不要提交 `.env` 到仓库。

## 常用命令
### 1. 只生成文章
```bash
python3.10 run_wechat_article.py "90年代的年轻人如何努力"
```

### 2. 生成文章并配图（默认 Wanx）
```bash
python3.10 run_wechat_article_with_images.py "90年代的年轻人如何努力"
```

### 3. 使用 Nano Banana 2 生成文章并配图
```bash
python3.10 run_wechat_article_with_images.py "90年代的年轻人如何努力" --image-backend nano_banana_2 --image-model gemini-3.1-flash-image-preview
```

### 4. 将现有文章发布到公众号草稿箱
```bash
python3.10 run_wechat_article.py --mode publish --from-json "output/articles/<bundle>/article.json"
```

### 5. 只做发布预演
```bash
python3.10 run_wechat_article.py --mode publish --from-json "output/articles/<bundle>/article.json" --dry-run
```

## 输出产物
一次完整生成后，通常会得到：
- `article.json`
- `article.md`
- `article.with_images.md`
- `article.wechat.preview.html`
- `images/cover/*`
- `images/body/*`

## 文档说明
- 如果你想看整体调用链路，读 [docs/WORKFLOW.md](docs/WORKFLOW.md)
- 如果你想排查微信标题、摘要、IP 白名单、图片不显示，读 [docs/WECHAT.md](docs/WECHAT.md)
