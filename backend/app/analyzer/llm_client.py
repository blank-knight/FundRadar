"""LLM client — 支持 Anthropic 和 OpenAI 两种 API 格式，通过配置切换。

.env 配置示例：

# 当前（0011.ai 中转，Anthropic 格式）
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://aicoding.0011.ai
LLM_MODEL=claude-sonnet-4-20250514
LLM_API_FORMAT=anthropic

# 切换到 DeepSeek
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_API_FORMAT=openai

# 切换到 GLM
LLM_API_KEY=xxx.xxx
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4-flash
LLM_API_FORMAT=openai

# 切换到 Gemini（通过 OpenAI 兼容层）
LLM_API_KEY=AIzaSy-xxx
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-2.0-flash
LLM_API_FORMAT=openai
"""
import asyncio
import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_request(system: str, user: str, max_tokens: int) -> tuple[str, dict, dict]:
    """根据 LLM_API_FORMAT 构建请求 url、headers、body。"""
    fmt = settings.LLM_API_FORMAT.lower()
    model = settings.LLM_MODEL

    if fmt == "anthropic":
        url = f"{settings.LLM_BASE_URL}/v1/messages"
        headers = {
            "x-api-key": settings.LLM_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    else:
        # OpenAI 兼容格式（DeepSeek / GLM / Gemini / 大多数中转）
        url = f"{settings.LLM_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

    return url, headers, body


def _extract_text(data: dict) -> str:
    """从响应中提取文本，兼容两种格式。"""
    # Anthropic 格式
    if "content" in data and isinstance(data["content"], list):
        item = data["content"][0]
        if isinstance(item, dict):
            return item.get("text", "").strip()
        return str(item).strip()
    # OpenAI 格式
    if "choices" in data:
        return data["choices"][0]["message"]["content"].strip()
    raise KeyError(f"Unknown response format: {list(data.keys())}")


def _strip_fences(text: str) -> str:
    """去掉 LLM 返回的 markdown 代码块包裹，并提取第一个 JSON 对象/数组。"""
    # 去掉 ```json ... ``` 或 ``` ... ```
    if "```" in text:
        lines = text.split("\n")
        inner = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_block = not in_block
                continue
            if in_block:
                inner.append(line)
        if inner:
            text = "\n".join(inner).strip()

    # 提取第一个 { ... } 或 [ ... ]（防止 LLM 在 JSON 前后加说明文字）
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]

    return text.strip()


def _fix_json_string_quotes(text: str) -> str:
    """修复 JSON 字符串值里的中文引号（LLM 常见问题）。"""
    text = text.replace('\u201c', '\\"').replace('\u201d', '\\"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    return text


async def llm_json(system: str, user: str, retries: int = 2) -> dict | list | None:
    """调用 LLM，返回解析后的 JSON（dict 或 list）。失败返回 None。"""
    for attempt in range(retries + 1):
        try:
            url, headers, body = _build_request(system, user, max_tokens=1024)
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                text = _extract_text(resp.json())
                cleaned = _strip_fences(text)
                if not cleaned:
                    raise json.JSONDecodeError("empty", "", 0)
                # 先尝试标准解析，失败再用宽松模式
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    # 宽松模式：修复中文引号后再解析
                    fixed = _fix_json_string_quotes(cleaned)
                    return json.loads(fixed)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM JSON parse failed (attempt {attempt+1}): {e}")
            logger.warning(f"LLM raw text was: {text[:400]}")
        except (KeyError, IndexError) as e:
            logger.warning(f"LLM response format error (attempt {attempt+1}): {e}")
        except httpx.HTTPError as e:
            logger.warning(f"LLM HTTP error (attempt {attempt+1}): {e}")
        if attempt < retries:
            await asyncio.sleep(2 ** attempt)
    return None


async def llm_text(system: str, user: str) -> str | None:
    """调用 LLM，返回纯文本。失败返回 None。"""
    try:
        url, headers, body = _build_request(system, user, max_tokens=512)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            return _extract_text(resp.json())
    except Exception as e:
        logger.error(f"LLM text call failed: {e}")
        return None
