
"""
阿里云百炼平台 - 文生图 Claude Skill
支持模型：
  - 万相文生图 V2 (wanx2.1-t2i-turbo / wanx2.1-t2i-plus)
  - 千问文生图   (qwen-vl-plus 多模态 / wanx-v1)

依赖安装：
  pip install dashscope requests
  
使用前请设置环境变量：
  export DASHSCOPE_API_KEY="your_api_key_here"
"""

import os
import time
import requests
from enum import Enum

try:
    import dashscope
    from dashscope import ImageSynthesis
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False


# ─────────────────────────────────────────────
# 配置区
# ─────────────────────────────────────────────
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "YOUR_API_KEY_HERE")
BASE_URL = "https://dashscope.aliyuncs.com/api/v1"


class ImageModel(str, Enum):
    """支持的文生图模型"""
    WANX_V2_TURBO = "wanx2.1-t2i-turbo"   # 万相 V2 Turbo（速度快、性价比高）
    WANX_V2_PLUS  = "wanx2.1-t2i-plus"    # 万相 V2 Plus（质量更高）
    WANX_V1       = "wanx-v1"             # 万相 V1（经典版）


class ImageSize(str, Enum):
    """支持的图像尺寸"""
    SIZE_512   = "512*512"
    SIZE_720P  = "1280*720"
    SIZE_1080P = "1920*1080"
    PORTRAIT   = "768*1024"
    LANDSCAPE  = "1024*768"
    SQUARE     = "1024*1024"


# ─────────────────────────────────────────────
# 核心：HTTP 直接调用（无需 SDK）
# ─────────────────────────────────────────────

class BailianText2ImageClient:
    """
    阿里云百炼平台文生图客户端
    使用异步任务模式：
      1. 提交任务 → 获取 task_id
      2. 轮询任务状态
      3. 返回图片 URL 列表
    """

    def __init__(self, api_key: str = DASHSCOPE_API_KEY):
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            raise ValueError("请设置有效的 DASHSCOPE_API_KEY")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",  # 启用异步模式
        }

    # ── 1. 提交文生图任务 ──────────────────────────────────────────────
    def submit_task(
        self,
        prompt: str,
        negative_prompt: str = "",
        model: ImageModel = ImageModel.WANX_V2_TURBO,
        size: ImageSize = ImageSize.SQUARE,
        n: int = 1,
        seed: int | None = None,
        style: str = "<auto>",
    ) -> str:
        """
        提交文生图任务，返回 task_id。

        Args:
            prompt:           正向提示词（中英文均可）
            negative_prompt:  负向提示词（不希望出现的内容）
            model:            使用的模型
            size:             图片尺寸，格式 "宽*高"
            n:                生成图片数量（1~4）
            seed:             随机种子，None 表示随机
            style:            风格，如 "<anime>"、"<photography>"、"<auto>"

        Returns:
            task_id (str)
        """
        payload = {
            "model": model.value,
            "input": {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
            },
            "parameters": {
                "size": size.value,
                "n": max(1, min(4, n)),
                "style": style,
            }
        }
        if seed is not None:
            payload["parameters"]["seed"] = seed

        url = f"{BASE_URL}/services/aigc/text2image/image-synthesis"
        resp = requests.post(url, json=payload, headers=self.headers, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        if "output" not in data or "task_id" not in data["output"]:
            raise RuntimeError(f"提交任务失败：{data}")

        task_id = data["output"]["task_id"]
        print(f"✅ 任务已提交，task_id: {task_id}")
        return task_id

    # ── 2. 查询任务状态 ────────────────────────────────────────────────
    def query_task(self, task_id: str) -> dict:
        """查询任务状态，返回完整响应体"""
        url = f"{BASE_URL}/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ── 3. 轮询直到完成 ────────────────────────────────────────────────
    def wait_for_result(
        self,
        task_id: str,
        poll_interval: float = 2.0,
        timeout: float = 120.0,
    ) -> list[str]:
        """
        轮询任务直到完成，返回图片 URL 列表。

        Args:
            task_id:       任务 ID
            poll_interval: 轮询间隔（秒）
            timeout:       最大等待时间（秒）

        Returns:
            图片 URL 列表
        """
        elapsed = 0.0
        while elapsed < timeout:
            result = self.query_task(task_id)
            status = result.get("output", {}).get("task_status", "")

            print(f"⏳ 任务状态：{status}（已等待 {elapsed:.0f}s）")

            if status == "SUCCEEDED":
                results = result["output"].get("results", [])
                image_urls = [r["url"] for r in results if "url" in r]
                print(f"🎉 生成完成！共 {len(image_urls)} 张图片")
                return image_urls

            elif status == "FAILED":
                error_msg = result.get("output", {}).get("message", "未知错误")
                raise RuntimeError(f"任务失败：{error_msg}")

            time.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"任务 {task_id} 超时（>{timeout}s）")

    # ── 4. 一步调用（提交 + 等待）────────────────────────────────────
    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        model: ImageModel = ImageModel.WANX_V2_TURBO,
        size: ImageSize = ImageSize.SQUARE,
        n: int = 1,
        seed: int | None = None,
        style: str = "<auto>",
        save_dir: str | None = None,
    ) -> dict:
        """
        一步完成文生图（提交任务 → 轮询 → 返回 URL 与本地文件路径）。

        Args:
            prompt:           提示词
            negative_prompt:  负向提示词
            model:            模型选择
            size:             图片尺寸
            n:                生成数量
            seed:             随机种子
            style:            风格
            save_dir:         本地保存目录（None 则不保存）

        Returns:
            {
                "urls": list[str],
                "saved_paths": list[str]
            }
        """
        task_id = self.submit_task(
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            size=size,
            n=n,
            seed=seed,
            style=style,
        )
        urls = self.wait_for_result(task_id)
        saved_paths = self._save_images(urls, save_dir) if save_dir else []
        return {
            "urls": urls,
            "saved_paths": saved_paths,
        }

    # ── 5. 下载并保存图片 ─────────────────────────────────────────────
    def _save_images(self, urls: list[str], save_dir: str) -> list[str]:
        """将图片下载到本地目录"""
        os.makedirs(save_dir, exist_ok=True)
        saved_paths = []
        for i, url in enumerate(urls):
            filename = os.path.join(save_dir, f"generated_{int(time.time())}_{i}.png")
            img_data = requests.get(url, timeout=30).content
            with open(filename, "wb") as f:
                f.write(img_data)
            print(f"💾 图片已保存：{filename}")
            saved_paths.append(filename)
        return saved_paths


# ─────────────────────────────────────────────
# SDK 版本（需安装 dashscope）
# ─────────────────────────────────────────────

class BailianText2ImageSDK:
    """使用官方 dashscope SDK 的文生图客户端（更简洁）"""

    def __init__(self, api_key: str = DASHSCOPE_API_KEY):
        if not DASHSCOPE_AVAILABLE:
            raise ImportError("请先安装：pip install dashscope")
        dashscope.api_key = api_key

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        model: str = ImageModel.WANX_V2_TURBO.value,
        size: str = ImageSize.SQUARE.value,
        n: int = 1,
    ) -> list[str]:
        """调用 SDK 生成图片"""
        rsp = ImageSynthesis.call(
            api_key=dashscope.api_key,
            model=model,
            prompt=prompt,
            negative_prompt=negative_prompt,
            n=n,
            size=size,
        )
        if rsp.status_code == 200:
            return [r.url for r in rsp.output.results]
        else:
            raise RuntimeError(f"SDK 调用失败 [{rsp.status_code}]: {rsp.message}")


# ─────────────────────────────────────────────
# Claude Skill 接口定义
# ─────────────────────────────────────────────

def text_to_image_skill(
    prompt: str,
    negative_prompt: str = "低质量, 模糊, 水印, 变形",
    model: str = "wanx2.1-t2i-turbo",
    size: str = "1024*1024",
    n: int = 1,
    style: str = "<auto>",
    save_dir: str | None = "./output",
    use_sdk: bool = False,
) -> dict:
    """
    Claude Skill：文生图

    此函数作为 Claude Skill 注册，当用户请求生成图片时调用。

    Args:
        prompt:           图像描述提示词
        negative_prompt:  不希望出现的内容
        model:            模型名称
        size:             图像尺寸（宽*高）
        n:                生成数量（1-4）
        style:            风格（<auto>/<anime>/<photography>/<watercolor>/<oil-paint>/<sketch>/<flat-illustration>）
        save_dir:         本地保存目录
        use_sdk:          是否使用 dashscope SDK（默认 HTTP 直调）

    Returns:
        {
            "success": bool,
            "urls": list[str],     # 图片链接
            "saved_paths": list[str],  # 本地图片路径
            "prompt": str,
            "model": str,
            "error": str | None
        }
    """
    try:
        if use_sdk and DASHSCOPE_AVAILABLE:
            client = BailianText2ImageSDK()
            urls = client.generate(
                prompt=prompt,
                negative_prompt=negative_prompt,
                model=model,
                size=size,
                n=n,
            )
            saved_paths = []
        else:
            client = BailianText2ImageClient()
            result = client.generate(
                prompt=prompt,
                negative_prompt=negative_prompt,
                model=ImageModel(model),
                size=ImageSize(size),
                n=n,
                style=style,
                save_dir=save_dir,
            )
            urls = result["urls"]
            saved_paths = result["saved_paths"]
        return {
            "success": True,
            "urls": urls,
            "saved_paths": saved_paths,
            "prompt": prompt,
            "model": model,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "urls": [],
            "saved_paths": [],
            "prompt": prompt,
            "model": model,
            "error": str(e),
        }


# ─────────────────────────────────────────────
# Claude Tool 定义（用于注册到 Claude API）
# ─────────────────────────────────────────────

CLAUDE_TOOL_DEFINITION = {
    "name": "text_to_image",
    "description": (
        "使用阿里云百炼平台（万相模型）根据文字描述生成图像。"
        "当用户要求绘制、生成、创作图片时调用此工具。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "图像的详细文字描述，越详细效果越好。支持中英文。",
            },
            "negative_prompt": {
                "type": "string",
                "description": "不希望在图像中出现的内容，例如：'模糊,低质量,水印'",
                "default": "低质量, 模糊, 水印, 变形",
            },
            "model": {
                "type": "string",
                "enum": ["wanx2.1-t2i-turbo", "wanx2.1-t2i-plus", "wanx-v1"],
                "description": "使用的模型，turbo 速度快，plus 质量高",
                "default": "wanx2.1-t2i-turbo",
            },
            "size": {
                "type": "string",
                "enum": ["1024*1024", "1280*720", "768*1024", "1024*768", "512*512"],
                "description": "图像尺寸（宽*高），默认正方形 1024*1024",
                "default": "1024*1024",
            },
            "n": {
                "type": "integer",
                "minimum": 1,
                "maximum": 4,
                "description": "生成图片数量",
                "default": 1,
            },
            "style": {
                "type": "string",
                "enum": [
                    "<auto>", "<anime>", "<photography>",
                    "<watercolor>", "<oil-paint>", "<sketch>",
                    "<flat-illustration>",
                ],
                "description": "图像风格",
                "default": "<auto>",
            },
        },
        "required": ["prompt"],
    },
}


# ─────────────────────────────────────────────
# 集成示例：Claude + Tool Use 完整流程
# ─────────────────────────────────────────────

def run_claude_with_t2i_skill(user_message: str, anthropic_api_key: str):
    """
    完整示例：将文生图工具注册到 Claude 并处理 Tool Use 响应。

    需要安装：pip install anthropic
    """
    try:
        import anthropic
    except ImportError:
        print("请安装：pip install anthropic")
        return

    import json

    claude_client = anthropic.Anthropic(api_key=anthropic_api_key)

    print(f"🤖 用户：{user_message}")

    # Step 1: 发送消息给 Claude，携带工具定义
    response = claude_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        tools=[CLAUDE_TOOL_DEFINITION],
        messages=[{"role": "user", "content": user_message}],
    )

    # Step 2: 处理 Tool Use 请求
    if response.stop_reason == "tool_use":
        for block in response.content:
            if block.type == "tool_use" and block.name == "text_to_image":
                tool_input = block.tool_use_input if hasattr(block, "tool_use_input") else block.input
                print(f"🔧 Claude 调用工具，参数：{json.dumps(tool_input, ensure_ascii=False, indent=2)}")

                # Step 3: 执行文生图
                result = text_to_image_skill(**tool_input)

                # Step 4: 将结果返回给 Claude
                follow_up = claude_client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=1024,
                    tools=[CLAUDE_TOOL_DEFINITION],
                    messages=[
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": response.content},
                        {
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, ensure_ascii=False),
                            }],
                        },
                    ],
                )
                print(f"🤖 Claude 回复：{follow_up.content[0].text}")
                return result
    else:
        print(f"🤖 Claude 直接回复（未调用工具）：{response.content[0].text}")


# ─────────────────────────────────────────────
# 快速测试入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # ── 测试 1：直接调用文生图 Skill ──────────────
    print("=" * 50)
    print("测试：直接调用文生图 Skill")
    print("=" * 50)

    result = text_to_image_skill(
        prompt="一只可爱的橙色猫咪坐在樱花树下，日式动漫风格，高清细腻",
        negative_prompt="低质量, 模糊, 水印",
        model="wanx2.1-t2i-turbo",
        size="1024*1024",
        n=1,
        style="<anime>",
        save_dir="./output",
    )

    if result["success"]:
        print(f"\n✅ 成功！图片 URL：")
        for url in result["urls"]:
            print(f"  → {url}")
    else:
        print(f"\n❌ 失败：{result['error']}")

    # ── 测试 2：Claude + Tool Use（需提供 Anthropic Key）──
    # run_claude_with_t2i_skill(
    #     user_message="帮我画一幅水彩风格的山间日出风景画",
    #     anthropic_api_key="your_anthropic_api_key"
    # )
