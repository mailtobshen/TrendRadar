# Fork 维护说明

> 本 fork 在 [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) v6.9.0 基础上叠加了 mailtobshen 的本地差异化功能，长期维护。

## 与 upstream 的差异

### 功能增强
- **AI 配置**: provider/model 字段拆分，支持多 provider 切换
- **WebUI**: 保留配置管理界面（upstream v6.9.0 已删除 webui/）
  - schedule 调度系统（preset + crawl_interval）
  - RSS 网络测试功能
  - 同源最大条数 (max_news_per_source)
- **CLI 子命令**: `python -m trendradar export --source {hotlist|rss|ai|all}`
- **RSS 源**: 新增 10 个（Github / Huggingface / RFI / AI-Era / CNA / DW / Reuters / economist / ltn / zaobao）+ 恢复 ruanyifeng（默认 disabled）
- **调度推送**: `display.regions.standalone: true`

### Upstream 特性已补回
- CDN 多源回退（`trendradar/core/cdn.py`）
- 11 个平台的 `expected_domain` 域名校验
- HTML 报告 Markdown 导出
- `display.regions` 开关门控

## 同步 upstream

```bash
# 1. 拉取 upstream 最新
git fetch upstream

# 2. 变基到 upstream
git rebase upstream/master

# 3. 解决冲突（参见 docs/superpowers/specs/2026-06-04-trendradar-fork-migration-design.md §6.2）
# 高风险文件: config/config.yaml, trendradar/__main__.py, trendradar/report/html.py

# 4. 推回 fork
git push origin master --force-with-lease
```

## 凭据管理

**不要把真实 API key 提交到 git。** 详见 `docs/ai-env-vars.md`。

加载顺序：环境变量 > `config.yaml` 中的占位符。

## 远程仓库

- `origin`: `mailtobshen/TrendRadar.git` (本 fork，推送目标)
- `upstream`: `sansan0/TrendRadar.git` (原始仓库，只读)

## 迁移历史

- 首次迁移日期: 2026-06-05
- 迁移时 upstream 版本: v6.9.0 (`a583b2d`)
- 迁移包含 commit 数: 50+ (含 5 个 upstream 修复补回)
- 设计文档: `docs/superpowers/specs/2026-06-04-trendradar-fork-migration-design.md`
- 实施计划: `docs/superpowers/plans/2026-06-04-trendradar-fork-migration.md`
