# TrendRadar (mailtobshen fork)

> 本项目是 [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) 的个人 fork。原始项目的功能介绍、安装部署、配置说明请参阅 [upstream README](https://github.com/sansan0/TrendRadar/blob/master/README.md)。**本 README 仅说明本 fork 相对 upstream 的差异。**

## 关于本 fork

| 项 | 值 |
|---|---|
| 上游基线 | [v6.9.0](https://github.com/sansan0/TrendRadar) (commit `a583b2d`) |
| 首次迁移日期 | 2026-06-05 |
| 维护者 | mailtobshen |
| 目标 | 在 upstream 基础上叠加个人定制功能，长期维护 |
| 计划 | 定期 rebase upstream 主线，**不**向 upstream 提 PR |

详细维护说明、凭据管理、同步流程见 [FORK_NOTES.md](./FORK_NOTES.md)。

---

## 本 fork 相对 upstream 的改动

### 🎛️ WebUI 配置管理界面

- **保留 WebUI**（upstream v6.9.0 已删除 `trendradar/webui/`，本 fork 恢复并继续增强）
- 新增 **调度系统**：preset 模板（always_on / morning_evening / office_hours / night_owl / custom）+ 爬取频率
- 新增 **RSS 网络测试**：在线验证 RSS 源可达性、状态展示
- 新增 `report.max_news_per_source_per_keyword` 字段（每个关键词每个来源最大条数）
- AI 模型下拉：provider + model 两级联动，支持 7 个 provider（openai / anthropic / gemini / deepseek / ollama / 2 个自定义）

### 🤖 AI 模块增强

- **provider / model 字段拆分**（替代老格式 `ai.model=provider/model`）
- AIClient / AITester 拆分支持多 provider
- ModelCatalog 模块：LiteLLM catalog + 自定义 model 合并 + provider API 实时刷新
- AI 测试连接端点 (`POST /api/ai/test`)
- **API key 通过环境变量注入**（不写进 `config.yaml`），详见 [docs/ai-env-vars.md](./docs/ai-env-vars.md)

### 🛠️ CLI 数据导出子命令

新增 `python -m trendradar export` 子命令：

```bash
python -m trendradar export --source hotlist --format json --pretty
python -m trendradar export --source rss --per-source-limit 5 --limit 100
python -m trendradar export --source ai --limit 50 --output ai_report.json
python -m trendradar export --source all --format json --pretty > all.json
```

支持 hotlist / rss / ai / all 四种数据源 + text / json 两种输出格式。

### 📡 RSS 源扩展

`config/config.yaml` 新增 10 个 RSS 源：

- **AI / 科技**: Github、Huggingface、AI-Era（新智元）
- **国际媒体**: Reuters、DeutscheWelle（德国之声）、RFI（法国国际广播）
- **中文媒体**: CNA（中央社）、economist（经济学人）、ltn（自由时报）、zaobao（联合早报）

同时恢复 `ruanyifeng`（atom.xml，默认 `enabled: false`）。`display.regions.standalone: true` 启用独立 RSS 推送区域。

### 🔒 安全 / 凭据管理

- **11 个热榜平台的 `expected_domain` 域名校验**（upstream v6.9.0 特性，本 fork 启用）
- **CDN 多源回退**（GitHub raw → jsdelivr fastly → jsdelivr cdn → gcore）
- **API key 强制脱敏**：committed 配置中为 `YOUR_API_KEY_HERE` 占位符，真实 key 通过 `AI_API_KEY` 环境变量注入
- 频率词配置文件 WebUI 覆盖回归修复（取 upstream 完整版本而非精简版）

### 📨 报告 / 推送

- HTML 报告新增 **Markdown 导出**按钮（upstream v6.7.0 特性）
- HTML 报告 / 邮件尊重 `display.regions` 开关（可关闭 standalone / ai_analysis 区域）
- HTML 报告暗色模式 / 搜索框 / 浮动按钮 / 宽屏模式（upstream v6.8.0 特性）

### 🔧 基础设施

- `.gitignore` 忽略运行时数据库文件（`ruvector.db` / `*.rvf` / `*.rvf.lock`），避免长跑进程污染 `git status`
- 完整 fork 维护文档（[FORK_NOTES.md](./FORK_NOTES.md)）+ 凭据注入文档（[docs/ai-env-vars.md](./docs/ai-env-vars.md)）

---

## 同步 upstream

每周自动监控 upstream 更新（本地 cron 提醒）。需要 rebase 时：

```bash
git fetch upstream
git rebase upstream/master
# 冲突解决参考 docs/superpowers/specs/2026-06-04-trendradar-fork-migration-design.md §6.2
git push origin master --force-with-lease
```

高风险冲突文件：`config/config.yaml` / `trendradar/__main__.py` / `trendradar/report/html.py` —— 通常采用"本地优先 + 后补 upstream 修复"策略。

---

## 致谢

- [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) — 原始项目作者及所有 [contributors](https://github.com/sansan0/TrendRadar/graphs/contributors)
- 迁移设计与实施计划见 `docs/superpowers/specs/` 和 `docs/superpowers/plans/`

## 许可

本 fork 与 upstream 同样使用 [GPL-3.0](./LICENSE) 协议。
