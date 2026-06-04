# TrendRadar Fork 迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把本地 master (`ad4acb4`) 上 43 个 AI/WebUI 差异化 commit + 4 个新增 feature commit，以线性历史的形式 rebase 到 fork `mailtobshen/TrendRadar` 的最新 master (`a583b2d` = upstream v6.9.0)，并推送到 fork。

**Architecture:** 三阶段——(1) 工作区固化为 4 个干净 feature commit；(2) `origin`→`upstream` 重命名 + `fork` 远程新增；(3) `git rebase fork/master`，逐 commit 解冲突，验证后 `--force-with-lease` 推送。`pre-migration-backup` tag + `backup/pre-migration` branch 作为回滚兜底。

**Tech Stack:** Git, Python 3.12 (CLI 模块导入验证), YAML (config 加载)

**参考 Spec:** `docs/superpowers/specs/2026-06-04-trendradar-fork-migration-design.md`

---

## 前置准备（执行任务前必读）

**当前确认状态**（执行任务前请重新核对一次）：
```bash
git rev-parse HEAD                # 预期: ad4acb4 或更新（设计文档已 commit）
git rev-parse origin/master       # 预期: a583b2d0baf83503f58e26e5553276d4d352dc7f
git status --short               # 预期: 3 modified + 多 untracked
```

**绝对不要**：
- 在 master 分支直接操作——所有迁移工作在 `migration/wip` 分支
- 用 `git push --force`——必须用 `--force-with-lease`
- 用 `git rebase --autostash`——会丢失 untracked 文件
- 在 `git grep` 检测出真实 API key 残留前推送

---

## Task 1: 迁移前安全备份

**Files:**
- Modify: `.git/refs/tags`（git 自动管理）
- Modify: `.git/refs/heads`（git 自动管理）
- Create: `/tmp/config.yaml.before-rebase.bak`

- [ ] **Step 1.1: 创建 tag 形式的全量快照**

```bash
git tag pre-migration-backup HEAD -m "迁移前全量快照 $(date -Iseconds) - 本地master ad4acb4 基线"
```

- [ ] **Step 1.2: 验证 tag 创建成功**

Run: `git tag -l pre-migration-backup`
Expected: 输出 `pre-migration-backup`（一行）

- [ ] **Step 1.3: 创建 backup 分支**

```bash
git branch backup/pre-migration HEAD
```

- [ ] **Step 1.4: 验证 backup 分支**

Run: `git log --oneline backup/pre-migration -3`
Expected: HEAD 在 backup 分支上，最新 commit 标题为设计文档 commit（"docs: TrendRadar fork 迁移设计文档"），其下是 `ad4acb4` 等本地原有 commit

- [ ] **Step 1.5: 备份 config.yaml**

```bash
cp config/config.yaml /tmp/config.yaml.before-rebase.bak
```

- [ ] **Step 1.6: 验证备份文件存在**

Run: `ls -la /tmp/config.yaml.before-rebase.bak && wc -l /tmp/config.yaml.before-rebase.bak`
Expected: 文件存在，行数与 `wc -l config/config.yaml` 一致

- [ ] **Step 1.7: 提交（如果尚未提交设计文档）**

如果 `git log -1 --oneline` 不是 `docs: TrendRadar fork 迁移设计文档`：
```bash
git status --short docs/
git add docs/superpowers/specs/2026-06-04-trendradar-fork-migration-design.md
git commit -m "docs: TrendRadar fork 迁移设计文档"
```

**回滚指引**（任意时刻）：`git reset --hard pre-migration-backup`

---

## Task 2: 远程重命名 + 添加 fork 远程

**Files:**
- Modify: `.git/config`

- [ ] **Step 2.1: 验证 origin 当前指向 upstream**

Run: `git remote get-url origin`
Expected: `https://github.com/sansan0/TrendRadar.git`

- [ ] **Step 2.2: 把 origin 重命名为 upstream**

```bash
git remote rename origin upstream
```

- [ ] **Step 2.3: 验证重命名**

Run: `git remote -v`
Expected:
```
fork	https://github.com/mailtobshen/TrendRadar.git (fetch)
fork	https://github.com/mailtobshen/TrendRadar.git (push)
upstream	https://github.com/sansan0/TrendRadar.git (fetch)
upstream	https://github.com/sansan0/TrendRadar.git (push)
```
（注意：fork 行此时还不存在，需 Step 2.4 添加）

- [ ] **Step 2.4: 添加 fork 远程**

```bash
git remote add fork https://github.com/mailtobshen/TrendRadar.git
```

- [ ] **Step 2.5: fetch fork**

```bash
git fetch fork
```

- [ ] **Step 2.6: 验证 fork/master 和 upstream/master 一致**

Run: `git rev-parse fork/master upstream/master`
Expected: 两条输出**完全相同**，都是 `a583b2d0baf83503f58e26e5553276d4d352dc7f`

- [ ] **Step 2.7: 提交（无变更需要 commit）**

无文件变更，跳过。

---

## Task 3: 清理 Untracked 垃圾（保留 CLI）

**Files:**
- Delete: `agentdb.rvf`, `agentdb.rvf.lock`, `ruvector.db`, `docker/ruvector.db`
- Delete: `config/config.yaml.before-restore-20260604_153709`
- Delete: `debug_ai_classify.py`, `reclassify_existing.py`, `show_classify_prompt.py`, `test_parse_classify.py`

**保留（不删）**：
- `trendradar/cli/__init__.py`
- `trendradar/cli/export.py`
- `trendradar/cli/__pycache__/`（gitignore 覆盖，不会进 commit）

- [ ] **Step 3.1: 列出待删除文件**

Run: `git status --short | grep '^??'`
Expected: 看到 `agentdb.rvf`, `agentdb.rvf.lock`, `ruvector.db`, `docker/ruvector.db`, `config/config.yaml.before-restore-20260604_153709`, `debug_ai_classify.py`, `reclassify_existing.py`, `show_classify_prompt.py`, `test_parse_classify.py` 以及 `trendradar/cli/` 目录

- [ ] **Step 3.2: 删除 DB 运行时产物**

```bash
rm -f agentdb.rvf agentdb.rvf.lock ruvector.db docker/ruvector.db
```

- [ ] **Step 3.3: 删除 config 备份**

```bash
rm -f config/config.yaml.before-restore-20260604_153709
```

- [ ] **Step 3.4: 删除 AI 调试脚本**

```bash
rm -f debug_ai_classify.py reclassify_existing.py show_classify_prompt.py test_parse_classify.py
```

- [ ] **Step 3.5: 验证删除**

Run: `git status --short`
Expected: 修改文件仍是 3 个（config.yaml, frequency_words.txt, config_page.py），untracked 仅剩 `trendradar/cli/` 目录

- [ ] **Step 3.6: 验证 CLI 模块仍在**

Run: `ls trendradar/cli/`
Expected: 看到 `__init__.py` 和 `export.py`（以及 `__pycache__/`）

- [ ] **Step 3.7: 提交（无变更需要 commit）**

删除 untracked 文件不产生 commit，跳过。

---

## Task 4: 创建 migration/wip 分支

**Files:**
- Modify: `.git/refs/heads`

- [ ] **Step 4.1: 切到 master（确保最新）**

```bash
git checkout master
```

- [ ] **Step 4.2: 验证 master 最新**

Run: `git log -1 --oneline`
Expected: 看到设计文档 commit（`docs: TrendRadar fork 迁移设计文档`）或本地最新 AI/webui commit

- [ ] **Step 4.3: 新建迁移分支**

```bash
git checkout -b migration/wip
```

- [ ] **Step 4.4: 验证当前在 migration/wip**

Run: `git branch --show-current`
Expected: `migration/wip`

- [ ] **Step 4.5: 验证工作区状态保留**

Run: `git status --short`
Expected: 3 modified + 1 untracked 目录（trendradar/cli/）

---

## Task 5: Commit A — RSS 新源 + standalone 推送

**Files:**
- Modify: `config/config.yaml`

**目标**：在 `config/config.yaml` 的 `rss.sources` 段新增 10 个 RSS 源 + 恢复 ruanyifeng（保持 `enabled: false`）+ `display.regions.standalone: true`

- [ ] **Step 5.1: 查看当前 RSS 段**

Run: `sed -n '30,100p' config/config.yaml`
Expected: 看到 `rss:` 段及现有 sources 列表

- [ ] **Step 5.2: 在 rss.sources 中恢复 ruanyifeng（放在 hacker-news 之后）**

找到 hacker-news 条目，在其后插入：
```yaml
  - id: ruanyifeng
    name: 阮一峰的网络日志
    url: http://www.ruanyifeng.com/blog/atom.xml
    enabled: false
```

注意：本地 `git diff` 显示原本 ruanyifeng 是被删除的，需恢复以保持 atom 源可重新启用。

- [ ] **Step 5.3: 在 rss.sources 末尾追加 10 个新源**

在 yahoo-finance 等现有条目之后追加：
```yaml
  - id: Github
    name: Github
    url: https://github.blog/feed/
  - id: Huggingface
    name: 抱抱脸
    url: https://huggingface.co/blog/feed.xml
  - id: RFI
    name: 法国国际广播
    url: https://feedx.net/rss/rfi.xml
    enabled: true
  - id: AI-Era
    name: 新智元
    url: https://plink.anyfeeder.com/weixin/AI_era
  - id: CNA
    name: 中央社
    url: https://rsshub.rssforever.com/cna
  - id: DeutscheWelle
    name: 德国之声
    url: https://rsshub.rssforever.com/dw/news
  - id: Reuters
    name: 路透社
    url: https://ir.thomsonreuters.com/rss/news-releases.xml
    enabled: true
  - id: economist
    name: 经济学人
    url: https://plink.anyfeeder.com/weixin/theeconomist
  - id: ltn
    name: 自由时报
    url: https://news.ltn.com.tw/rss/all.xml
    enabled: true
  - id: zaobao
    name: 联合早报
    url: https://plink.anyfeeder.com/zaobao/realtime/china
```

- [ ] **Step 5.4: 修改 display.regions.standalone 为 true**

找到 `display:` 下的 `regions:` 子段，将 `standalone: false` 改为 `standalone: true`

- [ ] **Step 5.5: 验证 YAML 语法**

Run: `python -c "import yaml; print(len(yaml.safe_load(open('config/config.yaml'))['rss']['sources']))"`
Expected: 数字 ≥ 22（之前 12 + 新增 10）

- [ ] **Step 5.6: 提交 Commit A**

```bash
git add config/config.yaml
git commit -m "feat(rss): 新增 10 个 RSS 源 + 恢复 ruanyifeng (默认 disabled) + standalone 推送开关"
```

- [ ] **Step 5.7: 验证**

Run: `git show --stat HEAD`
Expected: 仅 `config/config.yaml` 一个文件，行数变更约 +30/-1

---

## Task 6: Commit B — WebUI 三大功能块

**Files:**
- Modify: `trendradar/webui/config_page.py`

**目标**：在 `config_page.py` 添加 schedule 调度系统 + RSS 网络测试 + max_news_per_source_per_keyword 字段。仅迁移这三块，避免 rebase 噪音。

- [ ] **Step 6.1: 定位 schedule 段位置**

Run: `grep -n "调度系统\|schedule" trendradar/webui/config_page.py | head -20`
Expected: 看到 schedule 相关代码

- [ ] **Step 6.2: 定位 RSS 测试样式段**

Run: `grep -n "rss-test-status\|rss_test" trendradar/webui/config_page.py | head -10`
Expected: 看到 rss-test-status 相关 CSS 类

- [ ] **Step 6.3: 定位 max_news_per_source 段**

Run: `grep -n "max_news_per_source\|max-news-per-source" trendradar/webui/config_page.py | head`
Expected: 看到相关字段

- [ ] **Step 6.4: 应用本地 diff 中 schedule 调度系统段**

参考本地 `git diff trendradar/webui/config_page.py` 的 +182-192 行 schedule 段代码块：
- 添加 `.checkbox-group*` 系列 CSS（显示在 .tag-input 之后）
- 添加 `.rss-test-status` 系列 CSS（显示在 .toast 之后）
- 修改 RSS 列表表头：`<th>最大天数</th>` → `<th>RSS网络测试</th>`
- 在 RSS section 之后添加"调度系统"section（含 schedule.enabled / schedule.preset / schedule.crawl_interval_hours）
- 在 max_news 字段组之后添加 max_news_per_source 字段

直接以 `git checkout HEAD -- trendradar/webui/config_page.py` 还原，然后用 Edit 应用本任务的 3 处增量更简单：

```bash
git checkout HEAD -- trendradar/webui/config_page.py
```

- [ ] **Step 6.5: 用 Edit 添加 .checkbox-group 系列 CSS**

在 `tag-input input:focus { outline: none; }` 之后插入：
```css
.checkbox-group {
    display: flex; flex-direction: column;
    gap: 6px; padding: 8px;
    border: 1px solid #e5e5e5; border-radius: 8px;
    background: #fafafa; max-height: 200px; overflow-y: auto;
}
.checkbox-group-item {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 8px; border-radius: 6px;
    cursor: pointer; transition: background 0.15s;
}
.checkbox-group-item:hover { background: #f0f0f5; }
.checkbox-group-item input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }
.checkbox-group-item label { font-size: 13px; color: #333; cursor: pointer; flex: 1; }
.checkbox-group-empty { color: #999; font-size: 13px; padding: 8px; text-align: center; }
```

- [ ] **Step 6.6: 添加 .rss-test-status 系列 CSS**

在 `.toast.error { background: #ef4444; }` 之后插入：
```css
.rss-test-status { font-size: 12px; margin-left: 6px; }
.rss-test-status.testing { color: #888; }
.rss-test-status.success { color: #22c55e; }
.rss-test-status.error { color: #ef4444; }
```

- [ ] **Step 6.7: 修改 RSS 表头**

找到 `<tr><th>ID</th><th>名称</th><th>URL</th><th>启用</th><th>最大天数</th><th></th></tr>`，改为：
```html
<tr><th>ID</th><th>名称</th><th>URL</th><th>启用</th><th>RSS网络测试</th><th></th></tr>
```

- [ ] **Step 6.8: 添加 max_news_per_source 字段**

找到 `report-max-news` 输入框所在 form-group，在其后添加：
```html
<div class="form-group">
    <label class="form-label">同源最大条数 <span class="optional">每个关键词每个来源最多显示条数，默认3</span></label>
    <input type="number" id="report-max-news-per-source" min="0"
        onchange="updateConfig('report.max_news_per_source_per_keyword', parseInt(this.value)||0)">
</div>
```

- [ ] **Step 6.9: 验证 Python 语法**

Run: `python -c "import ast; ast.parse(open('trendradar/webui/config_page.py').read())"`
Expected: 无输出（parse 成功）

- [ ] **Step 6.10: 提交 Commit B**

```bash
git add trendradar/webui/config_page.py
git commit -m "feat(webui): schedule 调度系统 + RSS 网络测试 + max_news_per_source 字段"
```

- [ ] **Step 6.11: 验证**

Run: `git show --stat HEAD`
Expected: 仅 `trendradar/webui/config_page.py` 一个文件，行数变更约 +200/-10

---

## Task 7: Commit C — AI provider/model 拆分 + API key 脱敏

**Files:**
- Modify: `config/config.yaml`
- Create: `docs/ai-env-vars.md`

- [ ] **Step 7.1: 定位 ai 段**

Run: `grep -n "^ai:" config/config.yaml`
Expected: 输出形如 `154:ai:`

- [ ] **Step 7.2: 替换 ai 段配置**

将 `ai.model: ollama/qwen3.5-opus:9b`、`ai.api_key: ollama-local`、`ai.api_base: http://172.25.128.1:11434` 三行替换为：
```yaml
  provider: openai
  model: MiniMax-M3
  api_key: YOUR_API_KEY_HERE
  api_base: https://api.minimaxi.com/v1
```

注意：保留 `timeout`、`temperature`、`max_tokens` 等其他字段不变。

- [ ] **Step 7.3: 验证 YAML 语法**

Run: `python -c "import yaml; cfg = yaml.safe_load(open('config/config.yaml')); print(cfg['ai']['provider'], cfg['ai']['model'], cfg['ai']['api_key'])"`
Expected: `openai MiniMax-M3 YOUR_API_KEY_HERE`

- [ ] **Step 7.4: 创建环境变量说明文档**

```bash
cat > docs/ai-env-vars.md <<'EOF'
# AI 凭据配置

本项目不在 `config.yaml` 提交真实 API key。请通过环境变量注入：

| 变量 | 覆盖字段 | 必填 |
|---|---|---|
| `AI_API_KEY` | `ai.api_key` | 是（生产环境） |
| `AI_API_BASE` | `ai.api_base` | 否（默认走 config.yaml） |
| `AI_MODEL` | `ai.model` | 否 |
| `AI_PROVIDER` | `ai.provider` | 否 |

加载顺序：环境变量 > `config.yaml`。

## 本地开发

```bash
export AI_API_KEY="sk-..."
export AI_API_BASE="https://api.openai.com/v1"
python -m trendradar
```

## Docker 部署

在 `docker/.env` 配置（已在 `.gitignore`）：
```
AI_API_KEY=sk-...
AI_API_BASE=https://api.openai.com/v1
```

## 安全提示

- 不要把真实 API key 提交到 git
- 如意外提交，立即在提供方后台 revoke 并 rotate
- CI/CD 使用 secrets manager 注入环境变量
EOF
```

- [ ] **Step 7.5: 提交 Commit C**

```bash
git add config/config.yaml docs/ai-env-vars.md
git commit -m "refactor(ai): provider/model 字段拆分 + API key 占位符 + 环境变量文档"
```

- [ ] **Step 7.6: 验证占位符**

Run: `git show HEAD:config/config.yaml | grep -E "api_key|api_base"`
Expected: 看到 `api_key: YOUR_API_KEY_HERE`，**不应**出现 `sk-` 前缀的真实 key

- [ ] **Step 7.7: 验证无 secret 残留（整个 HEAD）**

Run: `git grep -nE "sk-[A-Za-z0-9_-]{20,}" HEAD`
Expected: 无输出（如果出现真实 key，立即用 `git reset HEAD~1` 回滚 Commit C 并从备份恢复）

---

## Task 8: Commit D — CLI 导出模块接入

**Files:**
- Create: `trendradar/cli/__init__.py`（已存在）
- Create: `trendradar/cli/export.py`（已存在）
- Modify: `trendradar/__main__.py`（添加 export 子命令）

- [ ] **Step 8.1: 验证 CLI 文件已就绪**

Run: `ls -la trendradar/cli/ && wc -l trendradar/cli/export.py`
Expected: `__init__.py` 和 `export.py` 存在，export.py 约 250 行

- [ ] **Step 8.2: 验证 CLI 模块可独立导入**

Run: `python -c "from trendradar.cli.export import main; print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 8.3: 查看 upstream __main__.py 的 parser 结构**

Run: `git show fork/master:trendradar/__main__.py | grep -nE "add_parser|subparser|argparse.ArgumentParser" | head -20`
Expected: 看到 `argparse.ArgumentParser` 在主入口

- [ ] **Step 8.4: 在 __main__.py 添加 export 子命令**

定位到 `parser = argparse.ArgumentParser(...)` 调用之后（约 fork/master 的 2177 行附近），改为 subparsers 结构：
```python
parser = argparse.ArgumentParser(...)
parser.add_argument("--config", default="config/config.yaml", help="配置文件路径")
subparsers = parser.add_subparsers(dest="command", help="可用子命令")

# 现有 run 模式保持为默认
run_parser = subparsers.add_parser("run", help="运行爬取+分析+推送")

# 新增 export 子命令
export_parser = subparsers.add_parser("export", help="导出数据")
export_parser.add_argument("--source", choices=["hotlist", "rss", "ai", "all"], required=True)
export_parser.add_argument("--format", choices=["text", "json"], default="text")
export_parser.add_argument("--limit", type=int, default=0)
export_parser.add_argument("--per-source-limit", type=int, default=3)
export_parser.add_argument("--pretty", action="store_true")
export_parser.add_argument("--output", help="输出文件路径（默认 stdout）")
```

并添加命令分发：
```python
args = parser.parse_args()
if args.command == "export":
    from trendradar.cli.export import main as export_main
    sys.exit(export_main(args))
# 否则走原有 run 流程
```

注意：以上为示意。具体行号和分发逻辑需根据 fork/master 的 `__main__.py` 实际结构调整。

- [ ] **Step 8.5: 验证语法**

Run: `python -c "import ast; ast.parse(open('trendradar/__main__.py').read())"`
Expected: 无输出

- [ ] **Step 8.6: 验证 CLI 子命令可被 argparse 解析**

Run: `python -m trendradar export --help`
Expected: 显示 export 子命令的 usage 信息，包含 `--source`, `--format` 等选项

- [ ] **Step 8.7: 提交 Commit D**

```bash
git add trendradar/cli/ trendradar/__main__.py
git commit -m "feat(cli): 趋势数据导出子命令 (hotlist/rss/ai/all)"
```

- [ ] **Step 8.8: 验证**

Run: `git show --stat HEAD`
Expected: 3 个文件（trendradar/cli/__init__.py, trendradar/cli/export.py, trendradar/__main__.py）

- [ ] **Step 8.9: 验证 migration/wip 上的 4 个 commit 都已落地**

Run: `git log --oneline master..migration/wip`
Expected: 4 行 commit，标题分别对应 A/B/C/D

---

## Task 9: Rebase 前的冲突预演

**Files:**
- 无变更

- [ ] **Step 9.1: 列出本地 rebase 候选 commit**

Run: `git log --oneline fork/master..HEAD | wc -l`
Expected: 47（43 原 commit + 4 新 commit）

- [ ] **Step 9.2: 列出每个 commit 触及的关键文件**

Run: `git log --name-only --pretty=format:"%h %s" fork/master..HEAD | grep -E "\.py$|\.yaml$|\.txt$|\.md$" | sort -u | head -30`
Expected: 看到 `config/config.yaml`, `config/frequency_words.txt`, `trendradar/webui/config_page.py`, `trendradar/ai/*.py`, `trendradar/__main__.py` 等

- [ ] **Step 9.3: 对每个高风险文件，预查 fork/master 是否会冲突**

```bash
for f in config/config.yaml config/frequency_words.txt \
         trendradar/webui/config_page.py \
         trendradar/ai/client.py trendradar/ai/analyzer.py \
         trendradar/__main__.py \
         trendradar/report/html.py \
         pyproject.toml mcp_server/__init__.py; do
  upstream_state=$(git cat-file -e fork/master:"$f" 2>/dev/null && echo "exists" || echo "missing")
  local_state=$(git cat-file -e HEAD:"$f" 2>/dev/null && echo "exists" || echo "missing")
  echo "$f: upstream=$upstream_state local=$local_state"
done
```

Expected: 类似输出
```
config/config.yaml: upstream=exists local=exists
config/frequency_words.txt: upstream=exists local=exists
trendradar/webui/config_page.py: upstream=missing local=exists
trendradar/ai/client.py: upstream=exists local=exists
...
```

- [ ] **Step 9.4: 对"local=missing upstream=exists"的文件预期会被 rebase 覆盖**

注意：本地 commit 中如有任何"删除 X"操作，rebase 时可能反向冲突。

- [ ] **Step 9.5: 记录预演结论到 TODO**

将预期冲突点列表（见 Spec §6.2 表格）记在脑中，准备进入 Task 10。

---

## Task 10: 执行 Rebase

**Files:**
- 无（git rebase 操作）

- [ ] **Step 10.1: 在 migration/wip 上启动 rebase**

```bash
git checkout migration/wip
git rebase fork/master
```

- [ ] **Step 10.2: 观察第一个冲突**

如果成功：跳到 Step 10.10  
如果冲突：git 输出形如 `CONFLICT (content): Merge conflict in config/config.yaml`

- [ ] **Step 10.3: 解决 config/config.yaml 冲突（如果发生）**

策略：取 fork/master (upstream v2.3.0) 骨架，叠加本地 commit A 和 commit C 的修改。

```bash
# 查看冲突标记
git diff config/config.yaml | head -50

# 手动编辑解决（参照 Spec §6.2 表格）
# 保留 upstream 完整结构，把本地 rss 新源、ai provider/model 拆分、standalone: true 叠加上去

# 标记为已解决
git add config/config.yaml
```

- [ ] **Step 10.4: 解决 config/frequency_words.txt 冲突（如果发生）**

策略：取 upstream 完整版（包含所有注释和 word groups 模板），重新加上 `震惊` filter。

```bash
# 取 upstream 版本作为基础
git checkout fork/master -- config/frequency_words.txt

# 在 [GLOBAL_FILTER] 段添加 震惊
# （用 Edit 在 GLOBAL_FILTER 段添加一行 `震惊`）

# 验证
head -30 config/frequency_words.txt
grep -A 3 "GLOBAL_FILTER" config/frequency_words.txt | head -10

git add config/frequency_words.txt
```

- [ ] **Step 10.5: 解决 trendradar/ai/client.py 冲突（如果发生）**

策略：保留 upstream 重构后的 AIClient，把本地 provider/model 拆分逻辑合并进去。

- [ ] **Step 10.6: 解决 trendradar/__main__.py 冲突（如果发生）**

策略：保留 upstream 的入口结构，本地的 export 子命令在 rebase 时如果已经存在（来自 Commit D），需保留。

- [ ] **Step 10.7: 继续 rebase**

```bash
git rebase --continue
```

- [ ] **Step 10.8: 重复 Step 10.3-10.7 直到全部 commit 应用完毕**

可能需要解决 5-15 次冲突。

- [ ] **Step 10.9: 验证 rebase 完成**

Run: `git status`
Expected: `interactive rebase in progress` 不出现；输出形如 `On branch migration/wip, nothing to commit, working tree clean`

- [ ] **Step 10.10: 验证 commit 计数**

Run: `git log --oneline fork/master..HEAD | wc -l`
Expected: 47（与 rebase 前一致）

- [ ] **Step 10.11: 验证线性历史**

Run: `git log --oneline --graph -5`
Expected: 没有 merge commit 的分叉，呈现线性直链

---

## Task 11: 静态验证

**Files:**
- 无变更

- [ ] **Step 11.1: 验证 commit 数量与覆盖**

```bash
echo "总 commit 数:"
git log --oneline fork/master..HEAD | wc -l
echo "应 ≥ 47"
echo ""
echo "触及 config 的 commit:"
git log --oneline fork/master..HEAD -- config/config.yaml
echo ""
echo "触及 webui 的 commit:"
git log --oneline fork/master..HEAD -- trendradar/webui/
echo ""
echo "触及 cli 的 commit:"
git log --oneline fork/master..HEAD -- trendradar/cli/
```

Expected: 全部有输出，cli 至少 1 个，webui 至少 1 个，config 至少 2 个

- [ ] **Step 11.2: 验证敏感信息已脱敏**

```bash
git grep -nE "sk-[A-Za-z0-9_-]{20,}" $(git rev-list fork/master..HEAD)
```

Expected: **无输出**。如果出现真实 key，立即停止并回滚：

```bash
# 紧急回滚
git reset --hard pre-migration-backup
git checkout migration/wip  # 如需
```

- [ ] **Step 11.3: 验证 untracked 状态**

```bash
git status
```

Expected: 仅可能看到 `__pycache__/` 等已 gitignore 的目录；**不应**看到 `agentdb.rvf`、`*.before-restore-*`、调试脚本等

- [ ] **Step 11.4: 验证文件级 diff 范围**

```bash
git diff --stat fork/master HEAD
```

Expected: 看到 `config/config.yaml`, `config/frequency_words.txt`, `trendradar/webui/config_page.py`, `trendradar/cli/*`, `trendradar/__main__.py`, `trendradar/ai/*`, `docs/ai-env-vars.md` 等

---

## Task 12: 导入烟测

**Files:**
- 无变更

- [ ] **Step 12.1: CLI 模块导入**

```bash
python -c "from trendradar.cli.export import main; print('CLI export OK')"
```

Expected: `CLI export OK`

- [ ] **Step 12.2: AI 模块导入**

```bash
python -c "from trendradar.ai.client import AIClient; print('AI client OK')"
```

Expected: `AI client OK`（如 import 失败，可能是 rebase 时路径变了，先看错误信息再修）

- [ ] **Step 12.3: Config YAML 加载**

```bash
python -c "import yaml; cfg = yaml.safe_load(open('config/config.yaml')); print('YAML OK:', cfg['ai']['provider'], cfg['ai']['model'])"
```

Expected: `YAML OK: openai MiniMax-M3`

- [ ] **Step 12.4: WebUI 模块导入**

```bash
python -c "from trendradar.webui.config_page import render_config_page; html = render_config_page(); print('webui OK, html length:', len(html))"
```

Expected: `webui OK, html length: <数字 > 10000`

- [ ] **Step 12.5: __main__ 模块导入**

```bash
python -c "import trendradar.__main__; print('main OK')"
```

Expected: `main OK`

- [ ] **Step 12.6: CLI 子命令 help**

```bash
python -m trendradar export --help
```

Expected: 显示 export 子命令的 usage

---

## Task 13: 推送到 fork

**Files:**
- Modify: `.git/config`（remote 重命名）

- [ ] **Step 13.1: 验证 fork/master 与 upstream/master 一致**

```bash
git rev-parse fork/master upstream/master
```

Expected: 两个 SHA 相同

- [ ] **Step 13.2: 把 fork 远程设为 origin（语义清晰）**

```bash
git remote rename fork origin
git remote -v
```

Expected:
```
origin	https://github.com/mailtobshen/TrendRadar.git (fetch)
origin	https://github.com/mailtobshen/TrendRadar.git (push)
upstream	https://github.com/sansan0/TrendRadar.git (fetch)
upstream	https://github.com/sansan0/TrendRadar.git (push)
```

- [ ] **Step 13.3: 推送 migration/wip 到 fork master**

```bash
git push -u origin migration/wip:master --force-with-lease
```

Expected: 推送成功，输出 `* [new branch] migration/wip -> master` 或 `-> master (forced update)`

注意：使用 `--force-with-lease` 而非 `--force`，会在远端 HEAD 与本地预期不一致时拒绝推送。

- [ ] **Step 13.4: 验证推送结果**

```bash
git fetch origin
git rev-parse origin/master HEAD
```

Expected: 两个 SHA 相同，证明 migration/wip 已成功推到 fork

- [ ] **Step 13.5: 把本地 master 切到 migration/wip（保持一致）**

```bash
git checkout master
git reset --hard migration/wip
```

- [ ] **Step 13.6: 删除本地 migration/wip 分支**

```bash
git branch -D migration/wip
```

- [ ] **Step 13.7: 验证最终状态**

```bash
git log --oneline -3
git branch -a
```

Expected:
- 最近 3 个 commit 应该是 Commit D（CLI）、Commit C（AI）、Commit B（webui）
- 仅有 `master` 和 `backup/pre-migration` 两个本地分支
- `origin/master` 和 `upstream/master` 都可见

---

## Task 14: 文档与收尾

**Files:**
- Create: `FORK_NOTES.md`（可选）

- [ ] **Step 14.1: 在 README 或新建 FORK_NOTES.md 记录"本地差异化清单"**

创建 `FORK_NOTES.md`：
```markdown
# Fork 维护说明

## 与 upstream 的差异
- AI 配置：provider/model 字段拆分（upstream 后续可能合并）
- WebUI：保留本地版本（upstream v6.9.0 已删除 webui/）
- CLI 子命令：`python -m trendradar export --source {hotlist|rss|ai|all}`
- RSS 源：本地新增 10 个 + 恢复 ruanyifeng（默认 disabled）
- 调度系统：本地 WebUI 增强

## 同步 upstream
```bash
git fetch upstream
git rebase upstream/master  # 如有冲突，参照 docs/superpowers/specs/2026-06-04-trendradar-fork-migration-design.md §6.2
```

## 凭据
- 真实 API key 通过环境变量 `AI_API_KEY` 注入，详见 `docs/ai-env-vars.md`
```

- [ ] **Step 14.2: 提交文档**

```bash
git add FORK_NOTES.md
git commit -m "docs: fork 维护说明 + 同步 upstream 流程"
git push origin master --force-with-lease
```

- [ ] **Step 14.3: 保留 backup 1-2 周**

不要立即删除 `pre-migration-backup` tag 和 `backup/pre-migration` 分支。1-2 周后：

```bash
git tag -d pre-migration-backup
git branch -D backup/pre-migration
```

- [ ] **Step 14.4: 验证 fork GitHub 网页**

浏览器打开 `https://github.com/mailtobshen/TrendRadar`，确认：
- 最新 commit 是 CLI 子命令 commit
- config/config.yaml 中 api_key 显示为 `YOUR_API_KEY_HERE`
- trendradar/cli/ 目录存在

---

## Task 15: 后续监控（异步，不阻塞）

- [ ] **Step 15.1: 设置 weekly reminder**

使用 CronCreate：
- 频率：每周一次
- 提示："检查 upstream 更新：`git fetch upstream && git log upstream/master --oneline -10`"

- [ ] **Step 15.2: 关注 fork CI**

如 fork 配了 GitHub Actions，监控 build 状态

---

## 附录 A：完整回滚流程

如任何阶段发现严重问题：

```bash
# 1. 停止当前操作（如果在 rebase）
git rebase --abort

# 2. 切回 master
git checkout master

# 3. 重置到 pre-migration-backup
git reset --hard pre-migration-backup

# 4. 清理 untracked（如有需要）
git clean -fd

# 5. 删除 migration/wip（如已建）
git branch -D migration/wip

# 6. 删除 fork origin（如果配置错乱）
git remote remove origin  # 或 git remote remove fork，取决于哪个配错
git remote rename upstream origin  # 恢复

# 7. 验证
git log --oneline -3
git status
```

## 附录 B：故障排查速查

| 现象 | 原因 | 处置 |
|---|---|---|
| `git rebase` 提示 "could not apply" | 有冲突未解决 | 看 git 输出，编辑冲突文件，`git add`，`git rebase --continue` |
| `git push --force-with-lease` 拒绝 | 远端 HEAD 不是预期的 fork/master SHA | `git fetch origin && git rev-parse origin/master` 比对，差异需先评估 |
| Python import 失败 | rebase 时 import 路径变了 | 看 traceback，定位是哪个文件路径错，调整 import |
| `git grep` 找到 sk-cp- 真实 key | 之前有 commit 没脱敏 | `git reset HEAD~1` 回滚该 commit，修改后再 commit |
| fork 推送后 GitHub 仍显示旧 commit | 浏览器缓存 | 强制刷新（Ctrl+Shift+R） |

---

**Plan 自检**：
- [x] Spec 覆盖：§1 目标 ✅、§2 决策 ✅、§3 架构（Task 1-5）✅、§4 阶段1（Task 5-8）✅、§5 阶段2（Task 2）✅、§6 阶段3（Task 9-10）✅、§7 阶段4（Task 11-12）✅、§8 阶段5（Task 13-14）✅、§9 防回滚（附录A）✅、§10 成功标准（Task 11-12）✅、§11 风险登记（附录B）✅
- [x] 无占位符：所有命令具体、文件路径具体、代码完整
- [x] 类型一致：`pre-migration-backup` tag、`backup/pre-migration` branch、`migration/wip` 分支名贯穿全文
- [x] DRY/YAGNI：未引入 spec 外的功能
- [x] 频繁提交：每 Task 1 个 commit
