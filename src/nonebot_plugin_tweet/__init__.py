from __future__ import annotations

import asyncio
import re
from typing import Optional

import httpx
from nonebot import get_plugin_config, on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    GroupMessageEvent,
    Message,
    MessageSegment,
)
from nonebot.log import logger
from nonebot.params import EventPlainText
from nonebot.plugin import PluginMetadata

from .config import Config
from .utils import (
    build_booth_message,
    build_message,
    build_message_content_only,
    build_message_original,
    fetch_booth_data,
    fetch_tweet_data,
    resolve_twitter_link,
    translate_text,
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
    extra={"version": "0.3.0"},
)

config = get_plugin_config(Config)

twitter_link_pattern = re.compile(
    r"https?://(?:x\.com|twitter\.com)/(\w+)/status/(\d+)",
    re.IGNORECASE,
)

booth_link_pattern = re.compile(
    r"https://(?:[a-zA-Z0-9-]+\.)?booth\.pm/(?:[a-z\-]+/)?items/(\d+)",
    re.IGNORECASE,
)

tweet_forwarder = on_message(priority=5, block=False)


@tweet_forwarder.handle()
async def handle_message(bot: Bot, event: Event, message: str = EventPlainText()) -> None:
    text = message.strip()
    if not text:
        return

    if await handle_tweet_link(text, event):
        return
    if await handle_booth_link(bot, event, text):
        return


async def handle_tweet_link(text: str, event: Event) -> bool:
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
        return False

    if not config.rsshub_base_url:
        logger.warning("RSSHub base URL is not configured; skip tweet handling.")
        await tweet_forwarder.finish("插件尚未配置 RSSHub 地址，请联系管理员。")

    user_name = match.group(1)
    tweet_id = match.group(2)
    original_link = match.group(0)

    if user_name.lower() == "i":
        resolved = await resolve_twitter_link(tweet_id)
        if not resolved:
            await tweet_forwarder.finish("未能解析推文链接 ")
        user_name, original_link = resolved

    base_url = str(config.rsshub_base_url).rstrip('/')
    query = config.rsshub_query_param or ''
    if query and not query.startswith('?'):
        query = f'?{query}'
    rss_url = f"{base_url}/{user_name}/status/{tweet_id}{query}"

    tweet_data = await fetch_tweet_data(rss_url, original_link)
    if not tweet_data:
        await tweet_forwarder.finish("未能获取该推文 ")

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

    if not command and (text_content := tweet_data.get("text")):
        translated_text = await translate_text(
            text_content,
            config.translate_target_language,
            api_base=config.openai_api_base,
            api_key=config.openai_api_key,
            model=config.openai_model,
        )
        if translated_text:
            await tweet_forwarder.send(MessageSegment.text(translated_text))

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

    return True


async def handle_booth_link(bot: Bot, event: Event, text: str) -> bool:
    match = booth_link_pattern.search(text)
    if not match:
        return False

    item_id = match.group(1)
    booth_data = await fetch_booth_data(item_id)
    if not booth_data:
        await tweet_forwarder.finish("未能获取该 BOOTH 商品信息 ")

    message_to_send = await build_booth_message(booth_data)
    if not message_to_send:
        logger.info("BOOTH item %s did not contain sendable text or images", item_id)
        return True

    images = booth_data.get("images", [])
    if len(images) < 5:
        await tweet_forwarder.send(message_to_send)
    else:
        if name := booth_data.get("name"):
            first_message = Message()
            first_message.append(MessageSegment.text(f"{name}\n"))
            if images and (image_url := images[0].get("original")):
                first_message.append(MessageSegment.image(image_url))
            await tweet_forwarder.send(first_message)

        if not isinstance(event, GroupMessageEvent):
            await tweet_forwarder.send(message_to_send)
            return True

        nodes = [
            {
                "type": "node",
                "data": {
                    "name": "BOOTH",
                    "uin": bot.self_id,
                    "content": message_to_send,
                },
            }
        ]
        await bot.send_group_forward_msg(group_id=event.group_id, messages=nodes)

    return True
