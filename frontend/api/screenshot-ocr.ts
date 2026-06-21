/**
 * Vercel Serverless Function — 持仓截图识别
 *
 * POST /api/screenshot-ocr
 * Body: { image: "base64编码的图片" }
 * Returns: { funds: [{ fund_name, fund_code, amount, profit, profit_pct }] }
 *
 * 环境变量（在 Vercel Dashboard 配置）:
 * - VISION_API_KEY: Claude Vision API key (rightcode 中转)
 *
 * 流程：接收图片 → Claude Vision 识别 → akshare 查基金代码（需本地后端）
 * 注意：serverless 环境无法跑 akshare，基金代码匹配在前端做（调公开 API）
 */

const VISION_BASE_URL = "https://right.codes/claude/v1";
const VISION_MODEL = "claude-sonnet-4-6";

export default async function handler(req: any, res: any) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const apiKey = process.env.VISION_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: "VISION_API_KEY 未配置" });
  }

  const { image } = req.body;
  if (!image) {
    return res.status(400).json({ error: "缺少图片数据" });
  }

  try {
    const response = await fetch(`${VISION_BASE_URL}/messages`, {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: VISION_MODEL,
        max_tokens: 4000,
        messages: [
          {
            role: "user",
            content: [
              {
                type: "image",
                source: {
                  type: "base64",
                  media_type: "image/jpeg",
                  data: image,
                },
              },
              {
                type: "text",
                text: `这是基金持仓截图。请识别图中每一只基金的信息。
返回JSON数组格式，每个元素包含以下字段（如果图中没有某个字段就设为null）：
- fund_name: 基金名称（完整名称，含后缀A/C）
- fund_code: 基金代码（6位数字，如果图中可见）
- amount: 当前金额/市值（纯数字）
- profit: 盈亏金额（纯数字，正为盈负为亏）
- profit_pct: 收益率百分比（纯数字，如 12.98 表示 12.98%）

只返回JSON数组，不要markdown代码块，不要其他文字。`,
              },
            ],
          },
        ],
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error("Vision API error:", response.status, errText);
      return res.status(502).json({
        error: `截图识别失败: API返回 ${response.status}`,
        detail: errText.substring(0, 200),
      });
    }

    const data = await response.json();
    let content = data.content[0].text.trim();

    // 清理 markdown 代码块
    if (content.startsWith("```")) {
      content = content.split("\n").slice(1).join("\n");
    }
    if (content.endsWith("```")) {
      content = content.slice(0, -3);
    }
    content = content.trim();

    const funds = JSON.parse(content);

    // 基金代码匹配 — 用天天基金 API 查（serverless 环境可用）
    const enriched = await enrichFundCodes(funds);

    return res.status(200).json({ funds: enriched, count: enriched.length });
  } catch (err: any) {
    console.error("OCR handler error:", err);
    return res.status(500).json({ error: err.message || "识别失败" });
  }
}

/**
 * 通过天天基金搜索 API 补全基金代码
 * API: https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashz
 */
async function enrichFundCodes(funds: any[]): Promise<any[]> {
  for (const fund of funds) {
    if (fund.fund_code) continue;

    const name = fund.fund_name;
    if (!name) continue;

    try {
      // 天天基金搜索 API
      const searchUrl = `https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchPageAPI.ashx?m=1&key=${encodeURIComponent(name.substring(0, 10))}&pageindex=0&pagesize=5`;
      const resp = await fetch(searchUrl, {
        headers: { Referer: "https://fund.eastmoney.com/" },
      });
      const text = await resp.text();
      // 返回格式是 jsonp 包裹的
      const jsonStr = text.replace(/^.*?\(/, "").replace(/\)$/, "");
      const data = JSON.parse(jsonStr);

      if (data.Datas && data.Datas.length > 0) {
        // 模糊匹配名称
        const suffix = name.toUpperCase().endsWith("C") ? "C" : name.toUpperCase().endsWith("A") ? "A" : "";
        let best = null;
        for (const item of data.Datas) {
          if (item.NAME === name || item.NAME.replace(/\s/g, "") === name.replace(/\s/g, "")) {
            best = item;
            break;
          }
          // 后缀匹配
          if (suffix && item.NAME.toUpperCase().endsWith(suffix)) {
            const itemCore = item.NAME.substring(0, Math.min(8, item.NAME.length));
            const nameCore = name.substring(0, Math.min(8, name.length));
            if (itemCore.includes(nameCore.substring(0, 4)) || nameCore.includes(itemCore.substring(0, 4))) {
              best = item;
            }
          }
        }
        if (best) {
          fund.fund_code = best.CODE;
        }
      }
    } catch (e) {
      // 搜索失败不影响主流程
      console.log(`Fund code lookup failed for ${name}:`, e);
    }
  }
  return funds;
}
