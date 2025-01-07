from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from dotenv import load_dotenv

load_dotenv()  # Load the .env file explicitly

class Config(BaseSettings):
    """Plugin Config Here"""

    rsshub_base_url: str = Field(...) # 使用占位符
    rsshub_query_param: str = Field(...)
    openai_api_base: str = Field(...)
    openai_api_key: str = Field(...)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")