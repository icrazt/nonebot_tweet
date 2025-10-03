from __future__ import annotations

import asyncio
import re
from typing import Optional

import httpx
from nonebot import get_plugin_config, on_message
from nonebot.adapters.onebot.v11 import Event, MessageSegment
from nonebot.log import logger
from nonebot.params import EventPlainText
from nonebot.plugin import PluginMetadata

from .config import Config
from .utils import (
    build_message,
    build_message_content_only,
    build_message_original,
    fetch_tweet_data,
)

__all__ = ("tweet_forwarder",)

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-tweet",
    description="Forward tweets via RSSHub with optional translation support.",
    usage="发送推文链接，或使用前缀 'c ' 仅发送媒体，'o ' 发送原文。",
    type="application",
    homepage="https://github.com/icrazt/nonebot_tweet",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

config = get_plugin_config(Config)

twitter_link_pattern = re.compile(
    r"https?://(?:x\.com|twitter\.com)/(\w+)/status/(\d+)",
    re.IGNORECASE,
)

tweet_forwarder = on_message(priority=5, block=False)


@tweet_forwarder.handle()
async def handle_tweet_link(_event: Event, message: str = EventPlainText()) -> None:
    text = message.strip()
    if not text:
        return

    command: Optional[str] = None
    lowered = text.lower()
    if lowered.startswith("c ") or lowered.startswith("content "):
        command = "content"
        text = text.split(" ", 1)[1] if " " in text else ""
    elif lowered.startswith("o ") or lowered.startswith("origin "):
        command = "origin"
        text = text.split(" ", 1)[1] if " " in text else ""

    match = twitter_link_pattern.search(text)
    if not match:
        return

    if not config.rsshub_base_url:
        logger.warning("RSSHub base URL is not configured; skip tweet handling.")
        await tweet_forwarder.finish("插件尚未配置 RSSHub 地址，请联系管理员。")

    user_name = match.group(1)
    tweet_id = match.group(2)
    original_link = match.group(0)

    base_url = str(config.rsshub_base_url).rstrip('/')
    query = config.rsshub_query_param or ''
    if query and not query.startswith('?'):
        query = f'?{query}'
    rss_url = f"{base_url}/{user_name}/status/{tweet_id}{query}"

    tweet_data = await fetch_tweet_data(rss_url, original_link)
    if not tweet_data:
        await tweet_forwarder.finish("未能获取该推文，请稍后再试。")

    if command == "content":
        message_to_send = await build_message_content_only(tweet_data, user_name)
    elif command == "origin":
        message_to_send = await build_message_original(tweet_data, user_name)
    else:
        message_to_send = await build_message(tweet_data, user_name)

    if message_to_send:
        await tweet_forwarder.send(message_to_send)
    else:
        logger.info("Tweet %s did not contain sendable text or images", original_link)

    for video_url in tweet_data.get("videos", []):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True) as client:
                video_response = await client.get(video_url)
                video_response.raise_for_status()
            await tweet_forwarder.send(MessageSegment.video(video_response.content))
            await asyncio.sleep(1)
        except httpx.HTTPError as exc:
            logger.warning("Error fetching or sending video %s: %s", video_url, exc)
            await tweet_forwarder.send(f"发送视频失败：{video_url}")
        except Exception as exc:
            logger.exception("Unexpected error sending video %s", video_url)
            await tweet_forwarder.send(f"发送视频失败：{video_url}")
