import re
import asyncio
from nonebot import on_message, get_plugin_config
from nonebot.adapters.onebot.v11 import Event, Message, MessageSegment
from nonebot.params import EventPlainText
from nonebot.plugin import PluginMetadata
from .utils import fetch_tweet_data, build_message, build_message_original, build_message_content_only
from .config import Config
import httpx

__plugin_meta__ = PluginMetadata(
    name="nonebot_plugin_tweet",
    description="A NoneBot2 plugin to forward tweets",
    usage="Just send a tweet link and the bot will do the rest.",

    type="application",

    homepage="https://github.com/icrazt/nonebot_tweet",

    config=Config,

    supported_adapters={"~onebot.v11"},
)

config = get_plugin_config(Config)

# 匹配推特链接的正则表达式
twitter_link_pattern = re.compile(r"https?://(?:x\.com|twitter\.com)/(\w+)/status/(\d+)(?!.*https?://(?:x\.com|twitter\.com)/(\w+)/status/(\d+))")

# on_message 响应所有消息， on_command 只响应指令
tweet_forwarder = on_message(priority=5)  # 优先级设置为 5，确保在其他插件之前处理

@tweet_forwarder.handle()
async def handle_tweet_link(event: Event, message: str = EventPlainText()):
    """
    Handles messages containing Twitter links.

    Args:
        event: The event object.
        message: The plain text content of the message.
    """
    command = None
    if message.startswith("c ") or message.startswith("content "):
        command = "content"
        message = message[2:] if message.startswith("c ") else message[8:]
    elif message.startswith("o ") or message.startswith("origin "):
        command = "origin"
        message = message[2:] if message.startswith("o ") else message[7:]
    
    match = twitter_link_pattern.search(message)
    if match:
        user_name = match.group(1)
        tweet_id = match.group(2)
        original_link = match.group(0) # 获取完整的原始链接

        rss_url = f"{config.rsshub_base_url}{user_name}/status/{tweet_id}{config.rsshub_query_param}"
        # Pass the original link to fetch_tweet_data for guid comparison
        tweet_data = await fetch_tweet_data(rss_url, original_link)

        if tweet_data:
            if command == "content":
                message_to_send = await build_message_content_only(tweet_data, user_name)
            elif command == "origin":
                message_to_send = await build_message_original(tweet_data, user_name)
            else:
                message_to_send = await build_message(tweet_data, user_name) # Pass user_name here
                
            if message_to_send:
              await tweet_forwarder.send(message_to_send)

            # Send videos separately
            if tweet_data["videos"]:
                for video_url in tweet_data["videos"]:
                    try:
                        print(f"Downloading video: {video_url}")
                        async with httpx.AsyncClient(timeout=30.0) as client:  # 设置超时时间
                            video_response = await client.get(video_url)
                            video_response.raise_for_status()
                        print(f"Video downloaded: {video_url}")

                        print(f"Sending video: {video_url}")
                        # Upload the video as a file
                        await tweet_forwarder.send(MessageSegment.video(video_response.content))
                        print(f"Video sent: {video_url}")
                        await asyncio.sleep(1)  # 添加短暂延迟
                    except httpx.HTTPError as e:
                        print(f"HTTP error fetching or sending video: {e}")
                        await tweet_forwarder.send(f"Error sending video: {video_url}")
                    except Exception as e:
                        print(f"An error occurred: {e}")
                        await tweet_forwarder.send(f"Error sending video: {video_url}")