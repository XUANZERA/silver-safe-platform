import os

import httpx

from app.core.errors import AppError

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"


async def call_deepseek(prompt: str) -> tuple[str, str]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise AppError(503, "AI 服务尚未配置", "AI_NOT_CONFIGURED")

    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 800,
    }
    try:
        async with httpx.AsyncClient(base_url=DEEPSEEK_BASE_URL, timeout=30.0) as client:
            response = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise AppError(503, "AI 服务暂时不可用", "AI_NETWORK_ERROR") from exc

    if response.status_code == 401:
        raise AppError(503, "AI 服务密钥无效", "AI_AUTH_ERROR")
    if response.status_code == 429:
        raise AppError(503, "AI 服务请求过于频繁，请稍后再试", "AI_RATE_LIMITED")
    if response.is_error:
        raise AppError(503, "AI 服务返回异常", "AI_PROVIDER_ERROR")

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AppError(503, "AI 服务未返回有效内容", "AI_EMPTY_RESPONSE") from exc
    if not isinstance(content, str) or not content.strip():
        raise AppError(503, "AI 服务未返回有效内容", "AI_EMPTY_RESPONSE")
    return content.strip(), model
