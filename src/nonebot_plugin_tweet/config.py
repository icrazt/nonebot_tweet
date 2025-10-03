from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configuration for nonebot-plugin-tweet."""

    rsshub_base_url: Optional[AnyHttpUrl] = Field(
        default="https://rsshub.app/twitter/user/",
        description=(
            "Base URL of the RSSHub Twitter route, e.g. https://rsshub.app/twitter/user/."
        ),
    )
    rsshub_query_param: Optional[str] = Field(
        default="",
        description=(
            "Optional query string appended to RSSHub requests, including leading '?' if needed."
        ),
    )
    translate_target_language: Optional[str] = Field(
        default="zh-Hans",
        description=(
            "Target language tag for tweet translation. Leave blank to disable translation."
        ),
    )
    openai_api_base: Optional[str] = Field(
        default=None,
        description="OpenAI-compatible API base URL. Required when translation is enabled.",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI-compatible API key. Required when translation is enabled.",
    )

    model_config = SettingsConfigDict(extra="ignore")
