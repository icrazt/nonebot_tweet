import httpx
from xml.etree import ElementTree as ET
from nonebot.adapters.onebot.v11 import Message, MessageSegment
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from nonebot import get_plugin_config
from .config import Config

# Load config at the top level of the module
config = get_plugin_config(Config)
OPENAI_API_BASE = config.openai_api_base
OPENAI_API_KEY = config.openai_api_key

async def fetch_tweet_data(rss_url, original_link):
    """
    Fetches and parses tweet data from the given RSS URL.
    Now it finds the matching item by comparing a portion of guid from the end.

    Args:
        rss_url: The RSS feed URL.
        original_link: The original Twitter link to match against.

    Returns:
        A dictionary containing the tweet content, or None if no matching item found.
    """
    try:
        print(f"Fetching RSS data from: {rss_url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(rss_url)
            response.raise_for_status()

        root = ET.fromstring(response.text)
        items = root.findall(".//item")
        if not items:
            return None

        # Extract user and tweet ID from the original link for comparison
        match = re.search(r"twitter\.com/(\w+)/status/(\d+)", original_link)
        if not match:
          match = re.search(r"x\.com/(\w+)/status/(\d+)", original_link)
        if not match:
            print(f"Could not extract user/tweet ID from original link: {original_link}")
            return None
        original_user, original_tweet_id = match.groups()

        # Iterate items in reverse order
        for item in reversed(items):
            guid = item.find("guid").text
            # Extract user and tweet ID from the guid for comparison
            guid_match = re.search(r"twitter\.com/(\w+)/status/(\d+)", guid)
            if not guid_match:
                continue
            guid_user, guid_tweet_id = guid_match.groups()

            # Compare user and tweet ID
            if guid_user == original_user and guid_tweet_id == original_tweet_id:
                content = item.find("description").text
                pub_date = item.find("pubDate").text
                author = item.find("author").text
                text, image_urls = extract_text_and_images(content)
                video_urls = extract_video_urls(content)
                return {
                    "text": text,
                    "images": image_urls,
                    "videos": video_urls,
                    "pub_date": pub_date,
                    "author": author,
                }

        return None  # No matching item found

    except httpx.HTTPError as e:
        print(f"HTTP error fetching RSS: {e}")
        return None
    except ET.ParseError as e:
        print(f"Error parsing RSS XML: {e}")
        return None

async def translate_text(text, target_language="zh-Hans"):
    """
    Translates the given text to the target language using a compatible OpenAI API.

    Args:
        text: The text to translate.
        target_language: The target language code (e.g., "zh-Hans" for Simplified Chinese).

    Returns:
        The translated text, or None if an error occurred.
    """
    if not text:
        return None
    
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY is not set. Translation will not work.")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    json_data = {
        "model": "gemini-2.0-flash-exp",  # Or whichever model you prefer
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that translates text."},
            {"role": "user", "content": f"只需要给出翻译不需要解释, 将以下文本翻译成{target_language}：\n\n{text}"}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPENAI_API_BASE}/v1/chat/completions",
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            response.raise_for_status()
            translated_text = response.json()["choices"][0]["message"]["content"].strip()
            return translated_text
    except Exception as e:
        print(f"Error translating text: {e}")
        return None

def extract_text_and_images(content):
    """
    Extracts text and image URLs from the raw RSS content.
    This assumes the content is HTML.

    Args:
        content: The raw HTML content from the RSS feed.

    Returns:
        A tuple containing the text content and a list of image URLs.
    """
    soup = BeautifulSoup(content, "html.parser")

    # Remove unnecessary elements (e.g., links to images and videos)
    for a_tag in soup.find_all("a", href=True):
        if "https://pbs.twimg.com/media/" in a_tag["href"] or "https://video.twimg.com/" in a_tag["href"]:
            a_tag.extract()
    
    for video_tag in soup.find_all("video", src=True):
        video_tag.extract()

    # Extract text
    text = soup.get_text(separator="\n", strip=True)

    # Extract image URLs
    image_urls = [
        img["src"] for img in soup.find_all("img", src=re.compile(r"^https://pbs\.twimg\.com/media/"))
    ]

    return text, image_urls

def extract_video_urls(content):
    """
    Extracts video URLs from the raw RSS content.
    Now it can handle video URLs in both <a> and <video> tags.

    Args:
        content: The raw HTML content from the RSS feed.

    Returns:
        A list of video URLs.
    """
    soup = BeautifulSoup(content, "html.parser")
    video_urls = []

    # Find video URLs in <a> tags
    for a_tag in soup.find_all("a", href=True):
        if "https://video.twimg.com/" in a_tag["href"]:
            video_urls.append(a_tag["href"])

    # Find video URLs in <video> tags
    for video_tag in soup.find_all("video", src=True):
        if "https://video.twimg.com/" in video_tag["src"]:
            video_urls.append(video_tag["src"])

    return video_urls

def format_pub_date(pub_date_str):
    """
    Converts a GMT formatted pubDate string to a simplified East Asia time string.

    Args:
        pub_date_str: A string representing the publication date in GMT format.

    Returns:
        A string representing the date in a simplified format with East Asia timezone, or None if the input is invalid.
    """
    try:
        # Parse the GMT time string
        pub_date_gmt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
        
        # Convert to East Asia Time (UTC+8)
        pub_date_east_asia = pub_date_gmt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
        
        # Format the date string as desired
        formatted_date_str = pub_date_east_asia.strftime("%y-%m-%d %H:%M")

        return formatted_date_str
    except ValueError as e:
        print(f"Error parsing pubDate: {e}")
        return None

async def build_message(tweet_data, user_name):
    """
    Builds a message from the tweet data, including translated text and Twitter user ID.

    Args:
        tweet_data: A dictionary containing the tweet text, image URLs, and video URLs.
        user_name: The Twitter user ID.

    Returns:
        A Message object ready to be sent, or None if there's no content to send.
    """
    message = Message()
    formatted_date = format_pub_date(tweet_data.get('pub_date',''))
    
    # Add author and time
    if formatted_date and tweet_data.get('author'):
        message.append(MessageSegment.text(f"{tweet_data['author']}@{user_name} 🕒{formatted_date}\n"))
    
    # Add tweet content
    if tweet_data.get('text'):
        message.append(MessageSegment.text(f"{tweet_data['text']}\n"))

    # Translate the text and append both original and translated text
    if tweet_data["text"]:
        translated_text = await translate_text(tweet_data["text"])
        if translated_text:
            message.append(MessageSegment.text(f"--------\n{translated_text}\n"))

    if tweet_data.get("images"):
        for image_url in tweet_data["images"]:
            message.append(MessageSegment.image(image_url))

    # We will handle video sending separately, so we don't add it to the message here.

    # Check if there's any content to send before returning
    if len(message) > 0:
        return message
    else:
        return None
    
async def build_message_content_only(tweet_data, user_name):
    """
    Builds a message containing only image and video content, without translation.

    Args:
        tweet_data: A dictionary containing the tweet text, image URLs, and video URLs.
        user_name: The Twitter user ID.

    Returns:
        A Message object ready to be sent, or None if there's no media content to send.
    """
    message = Message()

    if tweet_data.get("images"):
        for image_url in tweet_data["images"]:
            message.append(MessageSegment.image(image_url))
            
    # Check if there's any content to send before returning
    if len(message) > 0:
        return message
    else:
        return None

async def build_message_original(tweet_data, user_name):
    """
    Builds a message from the tweet data without translation, including Twitter user ID.

    Args:
        tweet_data: A dictionary containing the tweet text, image URLs, and video URLs.
        user_name: The Twitter user ID.

    Returns:
        A Message object ready to be sent, or None if there's no content to send.
    """
    message = Message()
    formatted_date = format_pub_date(tweet_data.get('pub_date',''))

    # Add author and time
    if formatted_date and tweet_data.get('author'):
        message.append(MessageSegment.text(f"{tweet_data['author']}@{user_name} 🕒{formatted_date}\n"))

    # Add tweet content without translation
    if tweet_data.get('text'):
        message.append(MessageSegment.text(f"{tweet_data['text']}\n"))

    if tweet_data.get("images"):
        for image_url in tweet_data["images"]:
            message.append(MessageSegment.image(image_url))
            
    # Check if there's any content to send before returning
    if len(message) > 0:
        return message
    else:
        return None