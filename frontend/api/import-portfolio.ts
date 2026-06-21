/**
 * Vercel Serverless Function — 导入持仓到 GitHub
 *
 * POST /api/import-portfolio
 * Body: { funds: [...], mode: "replace" | "merge" }
 *
 * 通过 GitHub Contents API commit portfolio.json → 触发 Vercel 重建
 *
 * 环境变量:
 * - GITHUB_TOKEN: GitHub PAT (有 repo 写权限)
 * - GITHUB_REPO: 格式 "owner/repo"，默认 blank-knight/FundRadar
 */

const DEFAULT_REPO = "blank-knight/FundRadar";
const FILE_PATH = "frontend/public/data/portfolio.json";

export default async function handler(req: any, res: any) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return res.status(500).json({ error: "GITHUB_TOKEN 未配置" });
  }

  const repo = process.env.GITHUB_REPO || DEFAULT_REPO;
  const { funds, mode = "merge" } = req.body;

  if (!funds || !Array.isArray(funds)) {
    return res.status(400).json({ error: "缺少持仓数据" });
  }

  try {
    // 1. 获取当前 portfolio.json 的 SHA（用于更新）
    const getUrl = `https://api.github.com/repos/${repo}/contents/${FILE_PATH}`;
    let existingSha: string | null = null;
    let existingData: any = { generated_at: new Date().toISOString(), holdings: [] };

    const getResp = await fetch(`${getUrl}?ref=main`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
      },
    });

    if (getResp.ok) {
      const fileData = await getResp.json();
      existingSha = fileData.sha;
      // 解码现有内容
      const content = Buffer.from(fileData.content, "base64").toString("utf-8");
      existingData = JSON.parse(content);
    }

    // 2. 合并或替换持仓
    let holdings: any[];
    if (mode === "replace") {
      holdings = funds.map(formatFund);
    } else {
      // merge: 跳过已存在的 fund_code
      const existingCodes = new Set((existingData.holdings || []).map((h: any) => h.fund_code));
      holdings = [
        ...(existingData.holdings || []),
        ...funds.filter((f: any) => f.fund_code && !existingCodes.has(f.fund_code)).map(formatFund),
      ];
    }

    const newData = {
      generated_at: new Date().toISOString(),
      holdings,
    };

    // 3. 通过 GitHub Contents API commit
    const content = Buffer.from(JSON.stringify(newData, null, 2)).toString("base64");
    const putResp = await fetch(getUrl, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: `feat: 持仓截图导入 (${new Date().toISOString().split("T")[0]})`,
        content,
        sha: existingSha || undefined,
        branch: "main",
      }),
    });

    if (!putResp.ok) {
      const errText = await putResp.text();
      console.error("GitHub API error:", putResp.status, errText);
      return res.status(502).json({ error: `GitHub commit 失败: ${putResp.status}` });
    }

    const result = await putResp.json();

    return res.status(200).json({
      success: true,
      imported: funds.length,
      total: holdings.length,
      commit_sha: result.commit.sha.substring(0, 7),
      message: "持仓已导入，网页正在重建中（约30秒）",
    });
  } catch (err: any) {
    console.error("Import handler error:", err);
    return res.status(500).json({ error: err.message || "导入失败" });
  }
}

function formatFund(f: any) {
  return {
    fund_code: f.fund_code,
    fund_name: f.fund_name,
    amount: f.amount || null,
    profit: f.profit || null,
    profit_pct: f.profit_pct || null,
    cost_total: f.amount && f.profit ? Math.round((f.amount - f.profit) * 100) / 100 : null,
    imported_at: new Date().toISOString(),
  };
}
