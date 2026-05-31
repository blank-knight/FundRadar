# FundRadar

AI 驱动的 A 股基金投资信号平台。

从财经博主预测和新闻情绪中提取信号，结合市场数据生成每日基金操作建议。

## 功能

- **博主评分** -- 爬取雪球财经博主的预测，与 T+1 实际走势比对，用指数衰减算法计算准确率排名
- **新闻情绪分析** -- 爬取财经新闻，LLM 分析情绪偏多/偏空
- **信号生成** -- 60% 博主共识 + 40% 新闻情绪，生成每日买入/持有/卖出信号
- **持仓管理** -- 添加关注基金，批量 LLM 分析持仓建议
- **Telegram 推送** -- 信号实时推送到 Telegram，支持绑定/解绑
- **新手教学** -- 基金投资入门内容模块
- **复盘报告** -- 历史信号回顾与准确率统计

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic |
| 数据库 | PostgreSQL 15 / Redis 7 |
| 前端 | React 18 / TypeScript / Tailwind CSS / Recharts |
| 数据源 | 雪球(博主) / 财经新闻 / akshare(行情) |
| AI | LLM API (支持 OpenAI/Anthropic 格式) |
| 部署 | Docker Compose |

## 项目结构

```
fund-radar/
├── backend/
│   ├── app/
│   │   ├── analyzer/      # LLM 分析：信号生成、博主评分、新闻情绪
│   │   ├── api/routes/    # REST API：认证、博主、信号、持仓、订单、Telegram
│   │   ├── core/          # 配置、数据库、安全、订阅计划
│   │   ├── crawler/       # 爬虫：雪球、新闻、基金净值
│   │   ├── models/        # SQLAlchemy 数据模型
│   │   ├── scheduler/     # APScheduler 定时任务
│   │   ├── schemas/       # Pydantic 请求/响应模型
│   │   └── services/      # 业务逻辑：推送、复盘、Telegram bot
│   ├── alembic/           # 数据库迁移
│   ├── main.py            # FastAPI 入口
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/         # 8 个页面：信号、博主、持仓、教学、复盘等
│   │   └── components/    # 布局组件
│   └── package.json
├── docker-compose.yml     # PostgreSQL + Redis
└── .env.example           # 环境变量模板
```

## 快速开始

### 1. 启动数据库

```bash
docker compose up -d
```

PostgreSQL 运行在 5433 端口，Redis 在 6379。

### 2. 配置环境变量

```bash
cp .env.example backend/.env
# 编辑 backend/.env，填入：
# - LLM API Key 和 Base URL
# - Telegram Bot Token（可选）
# - JWT Secret
```

### 3. 启动后端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -e .
alembic upgrade head
uvicorn main:app --reload --port 8000
```

API 文档：http://localhost:8000/api/docs

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## API 概览

| 模块 | 端点 | 说明 |
|---|---|---|
| 认证 | `POST /api/register` / `/api/login` | 注册登录，JWT 认证 |
| 博主 | `GET /api/bloggers` / `/api/bloggers/search` | 博主列表、雪球搜索 |
| 信号 | `GET /api/signals/reviews` | 复盘报告、历史信号 |
| 持仓 | `POST /api/portfolio/analyze/batch` | 批量 LLM 分析持仓 |
| Telegram | `POST /api/telegram/bind-code` | 绑定/解绑推送 |
| 订单 | `GET /api/orders/plans` | 订阅计划 |

## 商业模式

| 方案 | 价格 | 权限 |
|---|---|---|
| 免费 | -- | 延迟数据(T+2)，TOP 3 博主 |
| 月度 | ¥29/月 | 实时信号，完整排名，Telegram 推送 |
| 年度 | ¥299/年 | 月度 8.3 折 |
| 终身 | ¥999 | 一次性买断 |

## License

Private
