# nonebot-plugin-tweet

基于 RSSHub 的 Twitter/X 推文转发插件，支持自动翻译与多种输出模式。

## 功能亮点
- 转发 twitter.com / x.com 链接中的推文文本、图片与视频
- 支持 `c` / `content` 前缀仅发送多媒体内容
- 支持 `o` / `origin` 前缀仅发送未翻译原文
- 可选通过 OpenAI 兼容接口自动翻译推文文本

## 安装
### nb-cli
```bash
nb plugin install nonebot-plugin-tweet
```

### pip
```bash
pip install nonebot-plugin-tweet
```

安装完成后，将插件名加入 NoneBot 配置：

```toml
[tool.nonebot]
plugins = ["nonebot_plugin_tweet"]
```

或在代码中手动加载：

```python
nonebot.load_plugin("nonebot_plugin_tweet")
```

## 配置
通过环境变量或 `.env` 文件配置插件参数：

| 变量名 | 默认值 | 说明 |
| --- | --- | --- |
| `RSSHUB_BASE_URL` | `https://rsshub.app/twitter/user/` | RSSHub 推文路由基础地址，需包含末尾 `/` |
| `RSSHUB_QUERY_PARAM` | 空字符串 | 追加到 RSSHub 请求的查询参数，示例：`?format=raw` |
| `TRANSLATE_TARGET_LANGUAGE` | `zh-Hans` | 翻译目标语言，留空代表禁用翻译 |
| `OPENAI_API_BASE` | 未设置 | OpenAI 兼容接口地址，启用翻译时必填 |
| `OPENAI_API_KEY` | 未设置 | OpenAI 兼容接口密钥，启用翻译时必填 |

> 如果仅需转发原始内容，可将 `TRANSLATE_TARGET_LANGUAGE` 置空或不配置，同时无需填写 OpenAI 相关参数。

## 使用说明
- 直接发送推文链接即可触发转发。
- 使用 `c ` / `content ` 前缀仅发送图片和视频。
- 使用 `o ` / `origin ` 前缀仅发送未翻译的原始文本。
- 视频会按顺序逐条下载并发送，发送间隔约为 1 秒。

## 本地调试
项目内置 `bot.py`，可在本地快速启动：

```bash
pip install -r requirements.txt
python bot.py
```

## 许可证
本项目基于 [MIT](LICENSE) 许可证开源。
