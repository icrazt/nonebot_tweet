from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from nonebot import get_plugin_config
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.log import logger

from .config import Config

config = get_plugin_config(Config)


async def fetch_tweet_data(rss_url: str, original_link: str) -> Optional[Dict[str, Any]]:
    """Fetch and parse tweet data from RSSHub feed."""
    logger.debug(f"Fetching RSS data from: {rss_url}")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=True) as client:
            response = await client.get(rss_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(f"HTTP error fetching RSS feed: {exc}")
        return None

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        logger.warning(f"Error parsing RSS XML: {exc}")
        return None

    items = root.findall(".//item")
    if not items:
        logger.debug("RSS feed returned no items")
        return None

    match = re.search(r"(?:twitter|x)\.com/(\w+)/status/(\d+)", original_link)
    if not match:
        logger.debug(f"Unable to extract tweet id from original link: {original_link}")
        return None
    original_user, original_tweet_id = match.groups()

    for item in reversed(items):
        guid_el = item.find("guid")
        guid = guid_el.text if guid_el is not None else None
        if not guid:
            continue
        guid_match = re.search(r"(?:twitter|x)\.com/(\w+)/status/(\d+)", guid)
        if not guid_match:
            continue
        guid_user, guid_tweet_id = guid_match.groups()
        if guid_user.lower() != original_user.lower() or guid_tweet_id != original_tweet_id:
            continue

        description_el = item.find("description")
        pub_date_el = item.find("pubDate")
        author_el = item.find("author")

        content = description_el.text if description_el is not None else ""
        text, image_urls = extract_text_and_images(content)
        video_urls = extract_video_urls(content)
        return {
            "text": text,
            "images": image_urls,
            "videos": video_urls,
            "pub_date": pub_date_el.text if pub_date_el is not None else "",
            "author": author_el.text if author_el is not None else "",
        }

    logger.debug("No matching item found in RSS feed")
    return None


async def resolve_twitter_link(tweet_id: str) -> Optional[tuple[str, str]]:
    """Resolve shortened t.co or new mobile x.com/i/ web links using vxtwitter API."""
    api_url = f"https://api.vxtwitter.com/i/status/{tweet_id}"
    logger.debug(f"Resolving tweet link via vxtwitter: {api_url}")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=True) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            data = response.json()

            tweet_url = data.get("tweetURL")
            screen_name = data.get("user_screen_name")

            if tweet_url and screen_name:
                return screen_name, tweet_url
            else:
                logger.warning(f"vxtwitter response missing expected fields: {data}")
                return None

    except httpx.HTTPError as exc:
        logger.warning(f"HTTP error resolving tweet link: {exc}")
        return None
    except Exception as exc:
        logger.warning(f"Error parsing vxtwitter response: {exc}")
        return None


async def translate_text(
    text: Optional[str],
    target_language: Optional[str],
    *,
    api_base: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
) -> Optional[str]:
    """Translate text using an OpenAI-compatible API if configured."""
    if not text or not target_language or not api_base or not api_key or not model:
        logger.debug("Translation skipped: missing text, target language, or API configuration.")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    api_url = f"{api_base.rstrip('/')}/v1/chat/completions"

    # 1. Detect language
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            detect_payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a language detection assistant. Respond with only the language code (e.g., en, zh-Hans, ja).",
                    },
                    {"role": "user", "content": text},
                ],
            }
            response = await client.post(api_url, headers=headers, json=detect_payload)
            response.raise_for_status()
            detected_language = response.json()["choices"][0]["message"]["content"].strip()
            logger.debug(f"Detected language: {detected_language}")

            if detected_language.lower() == target_language.lower():
                logger.info(f"Skipping translation: Text is already in the target language ({target_language}).")
                return None
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        logger.warning(f"Language detection failed, proceeding with translation. Error: {exc}")

    # 2. Translate if necessary
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            translate_payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that translates text."},
                    {
                        "role": "user",
                        "content": f"只需要给出翻译不需要解释, 将以下文本翻译成{target_language}：\n\n{text}",
                    },
                ],
            }
            response = await client.post(api_url, headers=headers, json=translate_payload)
            response.raise_for_status()
            translated_text = response.json()["choices"][0]["message"]["content"].strip()
            return translated_text
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        logger.warning(f"Translation request failed: {exc}")
        return None


def extract_text_and_images(content: str) -> tuple[str, List[str]]:
    """Extract plain text and image URLs from RSS content."""
    soup = BeautifulSoup(content, "html.parser")

    for a_tag in soup.find_all("a", href=True):
        if "https://pbs.twimg.com/media/" in a_tag["href"] or "https://video.twimg.com/" in a_tag["href"]:
            a_tag.extract()

    for video_tag in soup.find_all("video", src=True):
        video_tag.extract()

    text = soup.get_text(separator="\n", strip=True)
    image_urls = [
        img["src"]
        for img in soup.find_all("img", src=re.compile(r"^https://pbs\.twimg\.com/media/"))
    ]

    return text, image_urls


def extract_video_urls(content: str) -> List[str]:
    """Extract video URLs from RSS content."""
    soup = BeautifulSoup(content, "html.parser")
    video_urls: List[str] = []

    for a_tag in soup.find_all("a", href=True):
        if "https://video.twimg.com/" in a_tag["href"]:
            video_urls.append(a_tag["href"])

    for video_tag in soup.find_all("video", src=True):
        if "https://video.twimg.com/" in video_tag["src"]:
            video_urls.append(video_tag["src"])

    return video_urls


def format_pub_date(pub_date_str: str) -> Optional[str]:
    """Convert GMT pubDate string to UTC+8 formatted string."""
    if not pub_date_str:
        return None
    try:
        pub_date_gmt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
    except ValueError as exc:
        logger.debug(f"Error parsing pubDate: {exc}")
        return None

    pub_date_east_asia = pub_date_gmt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
    return pub_date_east_asia.strftime("%y-%m-%d %H:%M")


async def build_message(tweet_data: Dict[str, Any], user_name: str) -> Optional[Message]:
    message = Message()
    formatted_date = format_pub_date(tweet_data.get("pub_date", ""))
    author = tweet_data.get("author")

    if formatted_date and author:
        message.append(MessageSegment.text(f"{author}@{user_name} {formatted_date}\n"))

    text = tweet_data.get("text")
    if text:
        translated_text = await translate_text(
            text,
            config.translate_target_language,
            api_base=config.openai_api_base,
            api_key=config.openai_api_key,
            model=config.openai_model,
        )
        if translated_text:
            message.append(MessageSegment.text(f"{text}\n---\n{translated_text}\n"))
        else:
            message.append(MessageSegment.text(f"{text}\n"))

    for image_url in tweet_data.get("images", []):
        message.append(MessageSegment.image(image_url))

    return message if len(message) > 0 else None


async def build_message_content_only(tweet_data: Dict[str, Any], user_name: str) -> Optional[Message]:
    message = Message()
    for image_url in tweet_data.get("images", []):
        message.append(MessageSegment.image(image_url))
    return message if len(message) > 0 else None


async def build_message_original(tweet_data: Dict[str, Any], user_name: str) -> Optional[Message]:
    message = Message()
    formatted_date = format_pub_date(tweet_data.get("pub_date", ""))
    author = tweet_data.get("author")

    if formatted_date and author:
        message.append(MessageSegment.text(f"{author}@{user_name} {formatted_date}\n"))

    text = tweet_data.get("text")
    if text:
        message.append(MessageSegment.text(f"{text}\n"))

    for image_url in tweet_data.get("images", []):
        message.append(MessageSegment.image(image_url))

    return message if len(message) > 0 else None


async def fetch_booth_data(item_id: str) -> Optional[Dict[str, Any]]:
    """Fetch and parse booth data from booth.pm API."""
    api_url = f"https://booth.pm/zh-cn/items/{item_id}.json"
    logger.debug(f"Fetching BOOTH data from: {api_url}")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=True) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        logger.warning(f"HTTP error fetching BOOTH item: {exc}")
        return None
    except Exception as exc:
        logger.warning(f"Error parsing BOOTH item JSON: {exc}")
        return None


async def build_booth_message(booth_data: Dict[str, Any]) -> Optional[Message]:
    """Build a message from BOOTH data."""
    message = Message()
    name = booth_data.get("name")
    if name:
        message.append(MessageSegment.text(f"{name}\n"))

    images = booth_data.get("images", [])
    for image in images:
        if image_url := image.get("original"):
            message.append(MessageSegment.image(image_url))

    return message if len(message) > 0 else None
