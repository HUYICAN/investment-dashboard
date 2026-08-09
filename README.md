# 投研情报工作台

自动抓取知识星球、财联社电报、东方财富异动数据，通过 AI 评分引擎生成投研工作台 HTML，部署到 GitHub Pages，手机随时查看。

## 架构

```
知识星球 API → 抓取帖子 → AI评分 → 生成HTML → GitHub Pages
财联社电报 API → 快讯
东方财富 API → 异动监控
```

每 10 分钟自动更新，电脑关机也能运行。

## 部署

### 1. 创建 GitHub Personal Access Token

访问 https://github.com/settings/tokens/new?scopes=repo,workflow,read:org&description=investment-dashboard

生成 token 后保存。

### 2. 运行部署脚本

```bash
bash deploy_to_github.sh <你的GitHub_Token>
```

脚本会自动完成：
- 认证 GitHub CLI
- 创建公开仓库
- 推送所有代码
- 配置 Secrets（知识星球 Cookie 等）
- 创建 GitHub Pages
- 触发首次运行

### 3. 查看工作台

部署完成后，访问：
```
https://<你的用户名>.github.io/investment-dashboard/
```

## Cookie 更新

知识星球 Cookie 会定期过期（约 7-30 天）。过期后工作台会停止更新。

更新方法：
```bash
# 确保在 TRAE 浏览器中已登录知识星球
python3 tools/update_cookie.py --repo <用户名>/investment-dashboard
```

## 手动触发更新

在 GitHub 仓库的 Actions 页面，点击 "Update Investment Dashboard" → "Run workflow"。

## 文件结构

```
├── .github/workflows/update.yml  # GitHub Actions 工作流
├── scripts/                      # 数据抓取和处理脚本
│   ├── fetch_zsxq.py             # 知识星球数据抓取
│   ├── fetch_cls.py              # 财联社电报抓取
│   ├── fetch_eastmoney.py        # 东方财富异动监控
│   ├── update_history.py         # 历史数据合并
│   └── generate_html.py          # HTML 生成（含评分引擎）
├── templates/workspace.html      # HTML 模板
├── seed/feed_history.json        # 种子历史数据
├── tools/update_cookie.py        # Cookie 更新工具
├── run_pipeline.py               # 管道编排
└── requirements.txt              # 无外部依赖（纯标准库）
```
