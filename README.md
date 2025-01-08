# nonebot_tweet

A NoneBot2 plugin to forward tweets.

> **Note**: You need to build your own [RSSHub](https://github.com/DIYgod/RSSHub) instance to retrieve tweet content.  
> This plugin also uses an [OpenAI-compatible API](https://platform.openai.com/docs/introduction) to translate the tweet text.

## Usage

Just send a tweet link to the bot, and it will automatically fetch and forward the tweet content.

You can also use the following commands:

- `c` or `content`: Send only the images and videos, without any text or translation.  
- `o` or `origin`: Send the original tweet text without translation.

## Install
Install by nb-cli (current not available)
```bash
 nb plugin nonebot_plugin_tweet
```
Or install by pip
```bash
pip install nonebot_plugin_tweet
```
then add plugin name to your `pyproject.toml` file
```toml
plugins = ["nonebot_plugin_tweet"]
```

## Configuration

You need to configure the following options in the `.env` file:

- `rsshub_base_url`: The base URL of your RSSHub instance.  
- `rsshub_query_param`: The query parameters for the RSSHub URL (for private).  
- `openai_api_base`: The base URL of your OpenAI-compatible API.  
- `openai_api_key`: Your OpenAI API key.  

Create a file named `.env` in the root directory of your project and add the following lines:

```bash
RSSHUB_BASE_URL=your_rsshub_url
RSSHUB_QUERY_PARAM=your_query_params
OPENAI_API_BASE=your_openai_api_base
OPENAI_API_KEY=your_openai_api_key
```

NoneBot will automatically load the `.env` file when it starts.

## Directly RUN
This project can also be run directly in a Python environment using the following command:
```bash
pip install -r requirements.txt && python bot.py
```