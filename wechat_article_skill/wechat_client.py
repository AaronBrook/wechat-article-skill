import json
import os
from pathlib import Path
from typing import Any

import requests


DEFAULT_WECHAT_APP_ID = "YOUR_WECHAT_APP_ID"
DEFAULT_WECHAT_APP_SECRET = "YOUR_WECHAT_APP_SECRET"
DEFAULT_WECHAT_AUTHOR = ""
DEFAULT_WECHAT_CONTENT_SOURCE_URL = ""


class WeChatClientError(RuntimeError):
    pass


class WeChatOfficialAccountClient:
    def __init__(self) -> None:
        self.app_id = os.getenv("WECHAT_OFFICIAL_ACCOUNT_APP_ID", DEFAULT_WECHAT_APP_ID)
        self.app_secret = os.getenv("WECHAT_OFFICIAL_ACCOUNT_APP_SECRET", DEFAULT_WECHAT_APP_SECRET)
        self.default_author = os.getenv("WECHAT_OFFICIAL_ACCOUNT_AUTHOR", DEFAULT_WECHAT_AUTHOR)
        self.default_content_source_url = os.getenv("WECHAT_OFFICIAL_ACCOUNT_CONTENT_SOURCE_URL", DEFAULT_WECHAT_CONTENT_SOURCE_URL)
        self.default_need_open_comment = int(os.getenv("WECHAT_OFFICIAL_ACCOUNT_NEED_OPEN_COMMENT", "0") or "0")
        self.default_only_fans_can_comment = int(os.getenv("WECHAT_OFFICIAL_ACCOUNT_ONLY_FANS_CAN_COMMENT", "0") or "0")
        self._validate()

    def _validate(self) -> None:
        missing = []
        if self.app_id == DEFAULT_WECHAT_APP_ID:
            missing.append("WECHAT_OFFICIAL_ACCOUNT_APP_ID")
        if self.app_secret == DEFAULT_WECHAT_APP_SECRET:
            missing.append("WECHAT_OFFICIAL_ACCOUNT_APP_SECRET")
        if missing:
            raise WeChatClientError(f"缺少微信公众号配置: {', '.join(missing)}")

    def get_access_token(self) -> str:
        response = requests.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            },
            timeout=60,
        )
        if response.status_code >= 400:
            raise WeChatClientError(f"获取 access_token 失败 [{response.status_code}]: {response.text}")
        data = response.json()
        if data.get("errcode"):
            raise WeChatClientError(f"获取 access_token 失败: {data}")
        token = data.get("access_token")
        if not token:
            raise WeChatClientError(f"access_token 响应缺少 access_token: {data}")
        return token

    def upload_image_material(self, access_token: str, image_path: str | Path) -> dict[str, Any]:
        source = Path(image_path)
        if not source.exists():
            raise WeChatClientError(f"封面图不存在: {source}")
        with source.open("rb") as file_obj:
            response = requests.post(
                "https://api.weixin.qq.com/cgi-bin/material/add_material",
                params={"access_token": access_token, "type": "image"},
                files={"media": (source.name, file_obj, "image/png")},
                timeout=120,
            )
        if response.status_code >= 400:
            raise WeChatClientError(f"上传封面图失败 [{response.status_code}]: {response.text}")
        data = response.json()
        if data.get("errcode"):
            raise WeChatClientError(f"上传封面图失败: {data}")
        if not data.get("media_id"):
            raise WeChatClientError(f"封面图响应缺少 media_id: {data}")
        return data

    def upload_article_image(self, access_token: str, image_path: str | Path) -> dict[str, Any]:
        source = Path(image_path)
        if not source.exists():
            raise WeChatClientError(f"正文图片不存在: {source}")
        with source.open("rb") as file_obj:
            response = requests.post(
                "https://api.weixin.qq.com/cgi-bin/media/uploadimg",
                params={"access_token": access_token},
                files={"media": (source.name, file_obj, "image/png")},
                timeout=120,
            )
        if response.status_code >= 400:
            raise WeChatClientError(f"上传正文图片失败 [{response.status_code}]: {response.text}")
        data = response.json()
        if data.get("errcode"):
            raise WeChatClientError(f"上传正文图片失败: {data}")
        if not data.get("url"):
            raise WeChatClientError(f"正文图片响应缺少 url: {data}")
        return data

    def add_draft(
        self,
        access_token: str,
        *,
        title: str,
        author: str,
        digest: str,
        content: str,
        thumb_media_id: str,
        content_source_url: str = "",
        need_open_comment: int | None = None,
        only_fans_can_comment: int | None = None,
    ) -> dict[str, Any]:
        payload = {
            "articles": [
                {
                    "title": title,
                    "author": author,
                    "digest": digest,
                    "content": content,
                    "content_source_url": content_source_url,
                    "thumb_media_id": thumb_media_id,
                    "need_open_comment": self.default_need_open_comment if need_open_comment is None else int(need_open_comment),
                    "only_fans_can_comment": self.default_only_fans_can_comment if only_fans_can_comment is None else int(only_fans_can_comment),
                }
            ]
        }
        response = requests.post(
            "https://api.weixin.qq.com/cgi-bin/draft/add",
            params={"access_token": access_token},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=120,
        )
        if response.status_code >= 400:
            raise WeChatClientError(f"创建草稿失败 [{response.status_code}]: {response.text}")
        data = response.json()
        if data.get("errcode"):
            raise WeChatClientError(f"创建草稿失败: {data}")
        return data
