# 工作流说明（端到端）

本文档解释从“一个主题”到“公众号草稿箱”的完整链路，以及每个模块的职责。

## 0. 总览（6 步）
1. 读取 `.env`
2. 生成结构化文章（JSON + Markdown）
3. 生成封面/正文图片并插入到 Markdown
4. 清洗 Markdown 并转换成微信公众号兼容 HTML
5. 上传图片到微信（正文图 + 封面图）
6. 创建公众号草稿

## 1. 读取配置
入口：
- [wechat_article_skill/cli.py](../wechat_article_skill/cli.py)

会读取根目录 `.env`（通过 `load_dotenv()` 或 fallback 逻辑）。

## 2. 文章生成（机器 Prompt）
模块：
- [SKILL.md](../SKILL.md)
- [wechat_article_skill/generator.py](../wechat_article_skill/generator.py)

产物：
- `output/articles/<bundle>/article.json`
- `output/articles/<bundle>/article.md`

关键点：
- 运行时会把 `SKILL.md` 作为 system prompt 发送给模型
- 模型输出必须是 JSON，并遵守字段约定

## 3. 图片生成与成稿
模块：
- [wechat_article_skill/pipeline.py](../wechat_article_skill/pipeline.py)
- [text_2_image.py](../text_2_image.py)

产物：
- `output/articles/<bundle>/images/cover/*`
- `output/articles/<bundle>/images/body/*`
- `output/articles/<bundle>/article.with_images.md`

关键点：
- 文章 Markdown 里会使用图片锚点（例如 `[IMG:s1]`）
- pipeline 会把锚点替换成 `![](...)` 形式的图片引用

## 4. Markdown 清洗与微信 HTML 渲染
模块：
- [wechat_article_skill/markdown_renderer.py](../wechat_article_skill/markdown_renderer.py)

做的事：
- 去掉顶层标题，避免和公众号标题重复
- 去掉提示词区块（封面图提示词、配图提示词等）
- 将 Markdown 转为微信公众号可接受的简化 HTML

产物：
- `output/articles/<bundle>/article.wechat.preview.html`

## 5. 微信接口上传与创建草稿
模块：
- [wechat_article_skill/wechat_client.py](../wechat_article_skill/wechat_client.py)
- [wechat_article_skill/publisher.py](../wechat_article_skill/publisher.py)

上传策略：
- 正文图片：`media/uploadimg` → 返回微信托管图片 URL（用于正文 `<img src>`）
- 封面图片：`material/add_material` → 返回 `media_id`（用于 `thumb_media_id`）

最终：
- 调用 `draft/add` 创建草稿
- 返回草稿 `media_id`

## 6. 常用运行方式
- 生成文章：
  - `python3.10 run_wechat_article.py "主题"`
- 生成文章 + 配图：
  - `python3.10 run_wechat_article_with_images.py "主题"`
- 发布到草稿箱：
  - `python3.10 run_wechat_article.py --mode publish --from-json ".../article.json"`
