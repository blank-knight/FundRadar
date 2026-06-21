/**
 * Vercel Serverless Function — 删除持仓
 *
 * POST /api/delete-position
 * Body: { fund_code: "000001" }
 *
 * 通过 GitHub Contents API 从 portfolio.json 中删除对应持仓。
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
  const { fund_code } = req.body;

  if (!fund_code) {
    return res.status(400).json({ error: "缺少 fund_code" });
  }

  try {
    const getUrl = `https://api.github.com/repos/${repo}/contents/${FILE_PATH}?ref=main`;
    const getResp = await fetch(getUrl, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
      },
    });

    if (!getResp.ok) {
      return res.status(502).json({ error: `读取 portfolio.json 失败: ${getResp.status}` });
    }

    const fileData = await getResp.json();
    const existingSha = fileData.sha;
    const content = Buffer.from(fileData.content, "base64").toString("utf-8");
    const data = JSON.parse(content);

    // 过滤掉要删除的持仓
    const before = (data.holdings || []).length;
    data.holdings = (data.holdings || []).filter((h: any) => {
      const code = h.fund_code || h.code;
      return code !== fund_code;
    });
    const after = data.holdings.length;
    data.generated_at = new Date().toISOString();

    if (before === after) {
      return res.status(404).json({ error: `未找到代码为 ${fund_code} 的持仓` });
    }

    // Commit 更新
    const newContent = Buffer.from(JSON.stringify(data, null, 2)).toString("base64");
    const putResp = await fetch(`https://api.github.com/repos/${repo}/contents/${FILE_PATH}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: `chore: 删除持仓 ${fund_code}`,
        content: newContent,
        sha: existingSha,
        branch: "main",
      }),
    });

    if (!putResp.ok) {
      const errText = await putResp.text();
      console.error("GitHub API error:", putResp.status, errText);
      return res.status(502).json({ error: `GitHub commit 失败: ${putResp.status}` });
    }

    return res.status(200).json({
      success: true,
      deleted: fund_code,
      remaining: after,
      message: `已删除，剩余 ${after} 只持仓`,
    });
  } catch (err: any) {
    console.error("Delete handler error:", err);
    return res.status(500).json({ error: err.message || "删除失败" });
  }
}
