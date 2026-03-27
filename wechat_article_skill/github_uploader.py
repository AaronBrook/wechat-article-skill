import base64
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


DEFAULT_GITHUB_TOKEN = "YOUR_GITHUB_TOKEN"
DEFAULT_GITHUB_REPO_OWNER = "YOUR_GITHUB_REPO_OWNER"
DEFAULT_GITHUB_REPO_NAME = "YOUR_GITHUB_REPO_NAME"
DEFAULT_GITHUB_REPO_BRANCH = "main"
DEFAULT_GITHUB_IMAGE_BASE_PATH = "wechat-assets"
DEFAULT_GITHUB_PAGES_BASE_URL = ""


class GitHubUploadError(RuntimeError):
    pass


class GitHubImageUploader:
    def __init__(self) -> None:
        self.token = os.getenv("GITHUB_TOKEN", DEFAULT_GITHUB_TOKEN)
        self.owner = os.getenv("GITHUB_REPO_OWNER", DEFAULT_GITHUB_REPO_OWNER)
        self.repo = os.getenv("GITHUB_REPO_NAME", DEFAULT_GITHUB_REPO_NAME)
        self.branch = os.getenv("GITHUB_REPO_BRANCH", DEFAULT_GITHUB_REPO_BRANCH)
        self.base_path = os.getenv("GITHUB_IMAGE_BASE_PATH", DEFAULT_GITHUB_IMAGE_BASE_PATH).strip("/")
        self.pages_base_url = os.getenv("GITHUB_PAGES_BASE_URL", DEFAULT_GITHUB_PAGES_BASE_URL).strip().rstrip("/")
        if not self.pages_base_url:
            self.pages_base_url = f"https://{self.owner}.github.io/{self.repo}"
        self.committer_name = os.getenv("GITHUB_COMMITTER_NAME", "Claude Code")
        self.committer_email = os.getenv("GITHUB_COMMITTER_EMAIL", "noreply@example.com")
        self._validate()
        self.base_api = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _validate(self) -> None:
        missing = []
        if self.token == DEFAULT_GITHUB_TOKEN:
            missing.append("GITHUB_TOKEN")
        if self.owner == DEFAULT_GITHUB_REPO_OWNER:
            missing.append("GITHUB_REPO_OWNER")
        if self.repo == DEFAULT_GITHUB_REPO_NAME:
            missing.append("GITHUB_REPO_NAME")
        if missing:
            raise GitHubUploadError(f"缺少 GitHub 配置: {', '.join(missing)}")

    def build_target_path(self, bundle_name: str, local_relative_path: str) -> str:
        relative = local_relative_path.strip("/")
        return f"{self.base_path}/{bundle_name}/{relative}" if self.base_path else f"{bundle_name}/{relative}"

    def build_raw_url(self, repo_path: str) -> str:
        return f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/{repo_path}"

    def build_public_url(self, repo_path: str) -> str:
        if self.pages_base_url:
            return f"{self.pages_base_url}/{quote(repo_path)}"
        return self.build_raw_url(repo_path)

    def plan_uploads(self, bundle_name: str, local_relative_paths: list[str]) -> dict[str, str]:
        return {
            relative_path: self.build_public_url(self.build_target_path(bundle_name, relative_path))
            for relative_path in local_relative_paths
        }

    def _content_url(self, repo_path: str) -> str:
        return f"{self.base_api}/{quote(repo_path)}"

    def _get_existing_sha(self, repo_path: str) -> str | None:
        response = requests.get(
            self._content_url(repo_path),
            headers=self.headers,
            params={"ref": self.branch},
            timeout=60,
        )
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise GitHubUploadError(f"查询 GitHub 文件失败 [{response.status_code}]: {response.text}")
        data = response.json()
        return data.get("sha")

    def upload_file(self, file_path: str | Path, bundle_name: str, local_relative_path: str) -> dict[str, Any]:
        source = Path(file_path)
        if not source.exists():
            raise GitHubUploadError(f"待上传文件不存在: {source}")

        repo_path = self.build_target_path(bundle_name, local_relative_path)
        sha = self._get_existing_sha(repo_path)
        payload: dict[str, Any] = {
            "message": f"Upload WeChat article asset: {bundle_name}",
            "content": base64.b64encode(source.read_bytes()).decode("ascii"),
            "branch": self.branch,
            "committer": {
                "name": self.committer_name,
                "email": self.committer_email,
            },
        }
        if sha:
            payload["sha"] = sha

        response = requests.put(
            self._content_url(repo_path),
            headers=self.headers,
            json=payload,
            timeout=120,
        )
        if response.status_code >= 400:
            raise GitHubUploadError(f"上传 GitHub 文件失败 [{response.status_code}]: {response.text}")

        return {
            "local_path": str(source),
            "relative_path": local_relative_path,
            "repo_path": repo_path,
            "raw_url": self.build_raw_url(repo_path),
            "public_url": self.build_public_url(repo_path),
            "response": response.json(),
        }
