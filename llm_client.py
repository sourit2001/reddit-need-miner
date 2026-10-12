"""Shared Anthropic client for post analysis and daily reports."""

from anthropic import Anthropic

MODEL = "claude-haiku-5-5"


def generate_text(messages, *, api_key, max_tokens):
    if not api_key:
        raise ValueError("缺少 ANTHROPIC_API_KEY，请配置 Anthropic Console 的 API Key")

    system = "\n\n".join(
        message["content"] for message in messages if message["role"] == "system"
    )
    with Anthropic(api_key=api_key, timeout=60.0, max_retries=0) as client:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[message for message in messages if message["role"] != "system"],
        )

    if response.stop_reason == "max_tokens":
        raise ValueError("Claude 输出达到长度上限，请增加 max_tokens 后重试")
    result = "\n".join(
        block.text for block in response.content if block.type == "text"
    ).strip()
    if not result:
        raise ValueError("Claude 未返回文本内容")
    return result
