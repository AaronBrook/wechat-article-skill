# wechat_article_skill

一套用于生成微信公众号文章、自动配图并写入公众号草稿箱的工作流。

## 它能做什么
- 根据主题生成结构化文章
- 为封面和正文段落生成配图
- 把 Markdown 清洗并转换成微信公众号正文 HTML
- 把正文图片和封面图片上传到微信
- 创建公众号草稿，供你在后台二次编辑后发布

## 文生图说明
本项目的文生图能力使用的是**阿里云百炼 / 通义千问图像生成能力**，通过 [text_2_image.py](text_2_image.py) 调用 DashScope 接口完成。

当前用法依赖：
- `DASHSCOPE_API_KEY`
- 文生图模型参数（默认在代码里配置）

用途分为两类：
- 封面图生成
- 正文分段配图生成

也就是说，这个工程里的“自动配图”不是本地模型生成，也不是 OpenAI 图像接口，而是**阿里千问生图能力**。

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

### 2. 生成文章并配图
```bash
python3.10 run_wechat_article_with_images.py "90年代的年轻人如何努力"
```

### 3. 将现有文章发布到公众号草稿箱
```bash
python3.10 run_wechat_article.py --mode publish --from-json "output/articles/<bundle>/article.json"
```

### 4. 只做发布预演
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
- 如果你想看一篇面向读者的介绍文章，读 [weixin.md](weixin.md)
