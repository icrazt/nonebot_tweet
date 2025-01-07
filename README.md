# nonebot_tweet

A NoneBot2 plugin to forward tweets.

## How to start

1. generate project using `nb create` .
2. create your plugin using `nb plugin create` .
3. writing your plugins under `src/plugins` folder.
4. run your bot using `nb run --reload` .

## Documentation

See [Docs](https://nonebot.dev/)

## Usage

Just send a tweet link to the bot, and it will automatically fetch and forward the tweet content.

You can also use the following commands:

-   `c` or `content`: Send only the image and video content, without translation.
-   `o` or `origin`: Send the original tweet content without translation.

## Configuration

You can configure the following options in the `src/plugins/nonebot_plugin_tweet/config.py` file:

-   `rsshub_base_url`: The base URL of your RssHub instance.
-   `rsshub_query_param`: The query parameters for the RssHub URL.
-   `openai_api_base`: The base URL of your OpenAI compatible API.
-   `openai_api_key`: Your OpenAI API key.