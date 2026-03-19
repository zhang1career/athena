import os
from typing import Optional

from openai import OpenAI

from common.components.singleton import Singleton


def _env_base_url() -> str:
    return (
        os.environ.get("AIGC_API_URL")
        or os.environ.get("OPENAI_API_BASE")
        or "https://api.openai.com/v1"
    )


def _env_api_key() -> str:
    return os.environ.get("AIGC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


class OpenAIDriver(Singleton):
    """Singleton driver for OpenAI-compatible client (AIGC / OpenAI env)."""

    def __init__(self) -> None:
        self._base_url = _env_base_url()
        self._api_key = _env_api_key()
        self._client: Optional[OpenAI] = OpenAI(base_url=self._base_url, api_key=self._api_key) if self._api_key else None

    @property
    def is_available(self) -> bool:
        return bool(self._api_key and self._client)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def client(self) -> Optional[OpenAI]:
        return self._client
