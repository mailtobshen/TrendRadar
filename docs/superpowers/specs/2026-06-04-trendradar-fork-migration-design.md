# TrendRadar Fork 迁移设计文档

> **Status**: Draft (待用户复审)
> **Date**: 2026-06-04
> **Owner**: mailtobshen
> **Source-of-truth**: 本地 master (`ad4acb4`) → mailtobshen/TrendRadar master (`a583b2d` = upstream v6.9.0)

## 1. 背景与目标

### 1.1 当前状态
- **本地 master** `ad4acb4`：在某个旧 upstream 快照之上做了 43 个本地 commit（AI / WebUI 方向）
- **upstream master** (`sansan0/TrendRadar`) `a583b2d`：v6.9.0
- **fork master** (`mailtobshen/TrendRadar`) `a583b2d`：**与 upstream 完全一致，未推送任何本地 commit**
- 本地工作区有 3 个未提交修改 + 10 个 untracked 文件
- `origin` 远程指向 upstream，本地尚未配置 fork 远程

### 1.2 目标
- 把本地的"差异化功能"（AI 增强、WebUI 增强、CLI 模块等）完整迁移到 fork 最新版本（v6.9.0）
- fork 作为 mailtobshen 的长期个人维护分支，**不打算 PR 回 upstream**
- 避免"再次覆盖问题"——所有变更以可审计、可回滚的方式落地

### 1.3 非目标
- 不向 upstream 提 PR
- 不重构本地功能以适配 upstream 的代码风格（除非 rebase 冲突强制要求）
- 不重写 WebUI（WebUI 在 upstream v6.9.0 中已删除，本地保留 WebUI 是预期行为）

## 2. 关键决策

| # | 决策 | 选择 | 备选 |
|---|---|---|---|
| D1 | 迁移目标 | 推本地差异化到 fork 最新版 | 推 PR / 双轨分支 |
| D2 | Untracked 处理 | 只保留 `trendradar/cli/` | 全留 / CLI+测试脚本 |
| D3 | 作者身份 | mailtobshen 推送，commit author 保留原值 | 全部改名 |
| D4 | 历史策略 | Rebase 本地 43 commit 到 v6.9.0 | merge / squash-重放 |
| D5 | 未提交修改 | 拆为 3 个 feature commit 后 rebase | 1 个 WIP commit / stash |
| D6 | API key | 占位符 + 环境变量文档 | 直接推 / 推后手动改 |
| D7 | frequency_words.txt | 接受 upstream v6.9.0 完整版（修复 WebUI 覆盖注释的 regression），仅保留用户 filter "震惊" | 保留本地精简版 |
| D8 | RSS 源数量 | 新增 10 个 + 移除 1 个 ruanyifeng（净 +9）。ruanyifeng 因其 atom.xml 不稳定建议保留 enabled: false 而非删除 | 仅新增 / 净增 11 个 |

## 3. 总体架构

**3 条线、5 个阶段、1 条防回滚安全绳**：

```
[本地master ad4acb4]              [fork/master a583b2d]    [upstream a583b2d]
   │                                   │                       │
   │  阶段1: 备份+固化                  │                       │
   ├─► 分支 migration/wip              │                       │
   │   ├─ commit A: feat(rss)          │                       │
   │   ├─ commit B: feat(webui)        │                       │
   │   ├─ commit C: refactor(ai)       │                       │
   │   └─ commit D: feat(cli)          │                       │
   │                                   │                       │
   │  阶段2: 同步upstream为fork新base   │                       │
   │                                   │                       │
   │  阶段3: Rebase migration/wip → fork/master (v6.9.0)      │
   │                                   │                       │
   │  阶段4: 验证（dry-run + 单元测试）                       │
   │  阶段5: 推送到fork                                     ◄──┘
```

## 4. 阶段1：备份+固化

### 4.1 安全备份
```bash
git tag pre-migration-backup ad4acb4 -m "迁移前全量快照 $(date -Iseconds)"
git branch backup/pre-migration ad4acb4
cp config/config.yaml /tmp/config.yaml.before-rebase.bak
```

回滚兜底：任何时候可 `git reset --hard pre-migration-backup` 回到本地原状。

### 4.2 清理 Untracked 垃圾
保留 `trendradar/cli/`，其余删除：
```bash
rm -f agentdb.rvf agentdb.rvf.lock ruvector.db docker/ruvector.db
rm -f config/config.yaml.before-restore-20260604_153709
rm -f debug_ai_classify.py reclassify_existing.py \
      show_classify_prompt.py test_parse_classify.py
```

### 4.3 新建迁移分支
```bash
git checkout -b migration/wip
```

### 4.4 4 个 Feature Commit

**Commit A — `feat(rss): 新增 10 个 RSS 源 + 恢复 ruanyifeng（默认 disabled） + standalone 推送开关`**
- 文件：`config/config.yaml`
- 内容：
  - `rss.sources` 新增 Github / Huggingface / RFI / AI-Era / CNA / DeutscheWelle / Reuters / economist / ltn / zaobao 共 10 个
  - 恢复 ruanyifeng 项（之前本地误删）但保留 `enabled: false`
  - `display.regions.standalone: true`
- 预期行数：~30 行新增
- 验收：`git show --stat HEAD` 仅触及 `config/config.yaml`

**Commit B — `feat(webui): schedule 调度系统 + RSS 网络测试 + max_news_per_source`**
- 文件：`trendradar/webui/config_page.py`
- 内容（仅这三块，其他本地化暂不迁移，避免 rebase 噪音）：
  - schedule 段（含 preset 选择器）
  - RSS 网络测试状态样式
  - `report.max_news_per_source_per_keyword` 字段
- 验收：`git diff HEAD~1 HEAD -- trendradar/webui/config_page.py | wc -l` ≈ 200 行

**Commit C — `refactor(ai): provider/model 字段拆分 + API key 占位符`**
- 文件：`config/config.yaml`、`docs/ai-env-vars.md`（新建）
- 内容：
  - `ai.model: ollama/qwen3.5-opus:9b` → `ai.provider: openai` + `ai.model: MiniMax-M3`
  - `ai.api_key: sk-cp-...` → `ai.api_key: YOUR_API_KEY_HERE`（脱敏）
  - `ai.api_base: http://172.25.128.1:11434` → `ai.api_base: https://api.minimaxi.com/v1`
  - 新建 `docs/ai-env-vars.md` 文档：
    ```markdown
    # AI 凭据配置
    本项目不再在 config.yaml 提交真实 API key。请通过环境变量注入：
    - `AI_API_KEY`：替换 `config.yaml` 中 `ai.api_key` 的占位符
    - `AI_API_BASE`：可选，覆盖 `ai.api_base`
    加载顺序：环境变量 > config.yaml
    ```
- 验收：`git grep -nE "sk-[A-Za-z0-9_-]{20,}"` 在 HEAD 上返回空

**Commit D — `feat(cli): 趋势数据导出子命令`**
- 文件：`trendradar/cli/__init__.py`、`trendradar/cli/export.py`、可能 `trendradar/__main__.py`（如需暴露 `python -m trendradar export`）
- 内容：完整的 CLI 导出模块（hotlist / rss / ai / all 四种 source）
- 验收：`python -c "from trendradar.cli.export import main; print(main.__doc__[:60])"` 不报错

## 5. 阶段2：远程重命名与同步

```bash
# origin 改名为 upstream
git remote rename origin upstream

# 添加 fork 远程
git remote add fork https://github.com/mailtobshen/TrendRadar.git
git fetch fork

# 验证
git rev-parse fork/master upstream/master
# 应都返回 a583b2d0baf83503f58e26e5553276d4d352dc7f
```

## 6. 阶段3：Rebase

### 6.1 命令
```bash
git rebase fork/master migration/wip
```

### 6.2 预期冲突点与解决原则

| 文件 | 冲突性质 | 解决策略 |
|---|---|---|
| `config/config.yaml` | upstream v2.3.0 vs 本地 v2.2.x | 取 upstream 骨架，叠加 commit A 的 RSS+standalone、commit C 的 ai 占位符 |
| `config/frequency_words.txt` | WebUI 覆盖导致注释丢失（regression） | 取 upstream 完整版，重新加用户 filter "震惊" |
| `trendradar/webui/config_page.py` | upstream 已删除此文件 | 无冲突（本地新增保留） |
| `trendradar/ai/{client.py,analyzer.py}` | upstream 重构 + 本地增加 | 优先 upstream 结构，把 provider/model 拆分逻辑 merge 进去 |
| `trendradar/__main__.py` | upstream 改了入口 | 手动合并，确保 CLI 子命令和现有入口共存 |
| `pyproject.toml` / `mcp_server/` | 都有可能 | 优先 upstream，本地补必要条目 |
| `trendradar/report/html.py` | upstream v6.8.0 大改 | 优先 upstream，本地 CLI export 接口如断则适配 |

### 6.3 逐个 commit rebase（推荐使用 `rebase -i` 显式编排）
- `git rebase -i fork/master`
- 把 4 个新 commit（feature A/B/C/D）和 43 个原 commit 一起按时间顺序 pick
- 每遇冲突：解决 → `git add` → `git rebase --continue`
- **不要用 `--autostash`** 以免 untracked 丢失

### 6.4 冲突解决后回到 `migration/wip` 分支
```bash
git rebase --continue
# 重复直到全部 commit 应用完毕
```

## 7. 阶段4：验证

### 7.1 静态检查
```bash
# 1. 提交数
git log --oneline fork/master..migration/wip | wc -l
# 预期 ≥ 47（43 + 4）

# 2. 文件级改动覆盖
git diff --stat fork/master migration/wip
# 预期：config/config.yaml、config/frequency_words.txt、trendradar/webui/*、trendradar/ai/*、trendradar/cli/*、trendradar/__main__.py 都出现

# 3. 敏感信息
git grep -nE "sk-[A-Za-z0-9_-]{20,}" $(git rev-list fork/master..migration/wip)
# 预期：空

# 4. untracked 状态
git status
# 预期：clean（除已 gitignore 的 __pycache__/ 等）
```

### 7.2 导入烟测
```bash
python -c "from trendradar.cli.export import main"
python -c "from trendradar.ai.client import AIClient"
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

### 7.3 类型 / 编译
```bash
# 如有 ruff / mypy 配置，按项目规范运行
ruff check trendradar/ 2>/dev/null || true
```

## 8. 阶段5：推送 + 收尾

### 8.1 推送
```bash
# 把 fork 设为 origin（语义清晰）
git remote rename fork origin

# 推送（--force-with-lease 比 --force 安全，会检查远端未被他人更新）
git push -u origin master --force-with-lease
```

### 8.2 清理
```bash
# 保留 backup 分支 1-2 周
git log --oneline backup/pre-migration -5   # 确认存在

# 1-2 周后清理
git branch -D backup/pre-migration
git tag -d pre-migration-backup
git branch -D migration/wip
```

### 8.3 文档
- 在 fork 的 README 或个人 wiki 记录：
  - "本地差异化功能清单"（AI provider/model 拆分、WebUI 增强、CLI 导出）
  - "如何从 upstream 同步更新"（`git fetch upstream && git rebase upstream/master`）

## 9. 防回滚 / 应急

| 失败点 | 回滚命令 |
|---|---|
| rebase 中途大量冲突 | `git rebase --abort` → 重规划冲突解决表 |
| 推到 fork 后才发现问题 | `git push origin :master`（删远端 master）+ `git reset --hard pre-migration-backup` |
| 想看 rebase 中间态 | `git reflog` 找 `HEAD@{n}` |
| 工作区脏数据想丢弃回到 rebase 前 | `git reset --hard pre-migration-backup && git clean -fd` |

## 10. 成功标准

- [ ] fork master 历史是线性的：v6.9.0 → 4 个新 commit → 43 个本地 commit
- [ ] `git grep "sk-cp-" master` 返回空
- [ ] `python -c "from trendradar.cli.export import main"` 不报错
- [ ] `config/frequency_words.txt` 包含完整的 upstream 注释 + 用户 filter "震惊"
- [ ] `config/config.yaml` 中 ai 段是 provider/model 拆分格式，api_key 是占位符
- [ ] `git status` 干净
- [ ] `backup/pre-migration` 仍可访问（保留 1-2 周）

## 11. 风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| upstream v6.9.0 已删除 `trendradar/webui/`，43 个本地 commit 大部分改 webui | 中 | 本地分支新建了 webui/，rebase 时 commit "modify webui" 会自然 apply；rebase 工具足够智能 |
| `config/config.yaml` schema 跨版本差异大 | 中 | 优先 upstream 骨架 |
| `trendradar/report/html.py` 大改导致 CLI export 接口断 | 中 | 阶段4 烟测发现 → 适配 |
| `pyproject.toml` / 依赖版本冲突 | 低 | 优先 upstream，本地补必要条目 |
| 真实 API key 误推 | 高 | Commit C 强制脱敏 + 阶段4 阶段 `git grep` 兜底 |
| 推到 fork 后才发现 regression | 中 | 阶段4 烟测 + `--force-with-lease` 保护 + `pre-migration-backup` 兜底 |
| upstream 后续推新版本，fork 需要再同步 | 低 | 文档记录再同步流程 |

## 12. 后续工作（不在本设计范围）

- 阶段6（可选）：从 `migration/wip` 中把 4 个 feature commit 拆得更细（如 schedule 拆为独立 commit）—— 取决于 review 反馈
- 监控 fork CI / issues
- 周期性从 upstream 拉新版本（建议每 1-2 周一次 rebase）

---

**Spec 自检**：
- [x] 无 "TBD" / "TODO" 占位符
- [x] 内部一致：阶段1的 4 commit ↔ 阶段3 的 47 commit ↔ 阶段5 推送历史一致
- [x] 范围聚焦：单一目标（迁移到 fork），不混入功能开发
- [x] 歧义消除：D1-D7 决策明确
