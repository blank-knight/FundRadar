"""持仓截图识别 — 接收图片，用 Claude Vision 识别基金信息，akshare 补全基金代码。

流程：
1. 接收 base64 图片
2. 调 Claude Vision API 识别基金名称、金额、盈亏等
3. 用 akshare fund_name_em 查询基金代码
4. 返回结构化列表，前端预览确认后批量添加

API: POST /portfolio/import-screenshot
"""
import base64
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Claude Vision 配置（用 rightcode 中转，智谱 vision 需单独充值）
VISION_API_KEY = os.getenv("RIGHTCODE_API_KEY", "")
VISION_BASE_URL = "https://right.codes/claude/v1"
VISION_MODEL = "claude-sonnet-4-6"

# 基金代码缓存（避免每次调 akshare）
_fund_cache: dict[str, str] = {}  # name → code
_cache_loaded = False


async def recognize_portfolio_screenshot(image_b64: str, media_type: str = "image/jpeg") -> list[dict]:
    """识别持仓截图，返回基金列表。

    Args:
        image_b64: base64 编码的图片
        media_type: 图片 MIME 类型

    Returns:
        基金信息列表，每项含 fund_name, fund_code, amount, profit, profit_pct 等
    """
    if not VISION_API_KEY:
        raise ValueError("RIGHTCODE_API_KEY 未配置，无法使用截图识别功能")

    headers = {
        "x-api-key": VISION_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    prompt = """这是基金持仓截图。请识别图中每一只基金的信息。
返回JSON数组格式，每个元素包含以下字段（如果图中没有某个字段就设为null）：
- fund_name: 基金名称（完整名称，含后缀A/C）
- fund_code: 基金代码（6位数字，如果图中可见）
- shares: 持有份额（纯数字）
- cost_nav: 买入成本净值（纯数字）
- current_nav: 当前净值（纯数字）
- amount: 当前金额/市值（纯数字）
- profit: 盈亏金额（纯数字，正为盈负为亏）
- profit_pct: 收益率百分比（纯数字，如 12.98 表示 12.98%）

只返回JSON数组，不要markdown代码块，不要其他文字。"""

    body = {
        "model": VISION_MODEL,
        "max_tokens": 4000,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.post(f"{VISION_BASE_URL}/messages", headers=headers, json=body)

    if resp.status_code != 200:
        logger.error(f"Vision API error: {resp.status_code} {resp.text[:200]}")
        raise RuntimeError(f"截图识别失败: API返回 {resp.status_code}")

    data = resp.json()
    content = data["content"][0]["text"].strip()

    # 清理 markdown 代码块标记
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    content = content.strip()

    funds = json.loads(content)
    logger.info(f"Vision 识别到 {len(funds)} 只基金")

    # 补全基金代码
    funds = await enrich_fund_codes(funds)

    return funds


async def enrich_fund_codes(funds: list[dict]) -> list[dict]:
    """用 akshare 补全缺失的基金代码。"""
    global _cache_loaded

    # 检查哪些需要查代码
    need_lookup = [f for f in funds if not f.get("fund_code")]
    if not need_lookup:
        return funds

    # 懒加载基金列表
    if not _cache_loaded:
        try:
            import akshare as ak
            import asyncio

            df = await asyncio.to_thread(ak.fund_name_em)
            for _, row in df.iterrows():
                name = str(row.get("基金简称", "")).strip()
                code = str(row.get("基金代码", "")).strip()
                if name and code:
                    _fund_cache[name] = code
            _cache_loaded = True
            logger.info(f"基金代码缓存加载: {len(_fund_cache)} 只")
        except Exception as e:
            logger.error(f"akshare 基金列表加载失败: {e}")
            return funds

    # 为每只基金查找代码
    for fund in need_lookup:
        name = fund.get("fund_name", "")
        code = _lookup_fund_code(name)
        if code:
            fund["fund_code"] = code
            logger.info(f"基金代码匹配: {name} → {code}")

    return funds


def _lookup_fund_code(name: str) -> str | None:
    """从缓存中查找基金代码，支持精确+模糊+关键词匹配。"""
    if not name:
        return None

    # 1. 精确匹配
    if name in _fund_cache:
        return _fund_cache[name]

    # 2. 去掉空格匹配
    name_clean = name.replace(" ", "").replace("（", "(").replace("）", ")")
    if name_clean in _fund_cache:
        return _fund_cache[name_clean]

    # 3. 前缀模糊匹配（核心6-8字符）
    core = name_clean.rstrip("ACac")
    if len(core) < 4:
        core = name_clean[:6]

    candidates: list[tuple[int, str]] = []
    for cached_name, code in _fund_cache.items():
        cn = cached_name.replace(" ", "")
        # 核心名称包含关系
        if core in cn or cn.startswith(core[:6]):
            suffix = name_clean[-1].upper() if name_clean[-1].upper() in ("A", "C") else ""
            if suffix and cn.endswith(suffix):
                candidates.append((0, code))
            elif not suffix or suffix == "A":
                candidates.append((1, code))
            else:
                candidates.append((2, code))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    # 4. 关键词组合匹配（针对名称中间部分有特征的基金）
    # 提取可能的关键词：去掉公司名前缀后的特征词
    keywords = []
    for kw in ["科创50联接", "高股息低波动", "半导体材料", "电网设备", "稀有金属",
                "人工智能", "纳斯达克", "恒生科技", "港股通", "创业板", "沪深300"]:
        if kw in name_clean:
            keywords.append(kw)
    # 加上 A/C 后缀
    suffix = name_clean[-1].upper() if name_clean and name_clean[-1].upper() in ("A", "C") else ""

    for kw in keywords:
        matches = []
        for cn, code in _fund_cache.items():
            cn_clean = cn.replace(" ", "")
            if kw in cn_clean:
                if suffix and cn_clean.endswith(suffix):
                    matches.append((0, code, cn))
                elif not suffix:
                    matches.append((1, code, cn))
        if matches:
            matches.sort(key=lambda x: x[0])
            return matches[0][1]

    return None
