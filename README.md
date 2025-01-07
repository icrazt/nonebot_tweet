# nonebot_tweet

A NoneBot2 plugin to forward tweets.

## Usage

Just send a tweet link to the bot, and it will automatically fetch and forward the tweet content.

You can also use the following commands:

-   `c` or `content`: Send only the image and video content, without translation.
-   `o` or `origin`: Send the original tweet content without translation.

## Configuration

You need configure the following options in the `.env` file:

-   `rsshub_base_url`: The base URL of your RssHub instance. This bot uses RSSHub to fetch Twitter content.
-   `rsshub_query_param`: The query parameters for the RssHub URL (for private).
-   `openai_api_base`: The base URL of your OpenAI compatible API.
-   `openai_api_key`: Your OpenAI API key.

Create a file named .env in the root directory of your project.

Add the following lines to the  .env file:

```
RSSHUB_BASE_URL=your_rsshub_url
RSSHUB_QUERY_PARAM=your_query_params
OPENAI_API_BASE=your_openai_api_base
OPENAI_API_KEY=your_openai_api_key
```

NoneBot will automatically load the .env file when it starts.