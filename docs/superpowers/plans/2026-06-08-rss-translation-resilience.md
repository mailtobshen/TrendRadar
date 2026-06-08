# RSS 翻译鲁棒性增强 实现 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 MiniMax API 触发内容审核（400 new_sensitive）时让 RSS 翻译和报告分析不被拖崩：单批数据量变小 + 整批失败不抛 + 报告"分析完成"文案不误导用户

**Architecture:** 改 2 个文件、共约 10 行。
- `trendradar/ai/translator.py:56` — 修大小写 bug（yaml 用小写，代码读大写）+ 把默认 BATCH_SIZE 从 30 改为 5
- `trendradar/__main__.py:549-555` — 通过 `result.rss_insights == "" and result.standalone_summaries == {}` 判定段 B 是否被跳过，相应改 print 文案

**Tech Stack:** Python 3.12 / LiteLLM / dataclass

**Spec:** `docs/superpowers/specs/2026-06-08-rss-translation-resilience.md`（commit c5451c2）

---

## 文件清单

| 文件 | 改动 | 理由 |
|------|------|------|
| `trendradar/ai/translator.py:56` | 1 行 | 修大小写 bug + 默认 30→5 |
| `trendradar/__main__.py:549-555` | ~7 行 | 段 B 跳过的判定 + 文案 |

**不改**：`analyzer.py`（段 B 跳过信号已隐含在 result 字段里）、`config.yaml`（修了 translator 默认后无需再动 yaml）、`webui` / `dispatcher` / `prompt` 文件

---

### Task 1: 修 translator.py 默认 BATCH_SIZE + 修大小写 bug

**Files:**
- Modify: `trendradar/ai/translator.py:56`

- [ ] **Step 1: 打开文件确认上下文**

读 `trendradar/ai/translator.py:50-60`，确认当前行内容：
```python
        self.batch_size = max(1, int(translation_config.get("BATCH_SIZE", 30)))
```

- [ ] **Step 2: 修改这一行**

把 `"BATCH_SIZE", 30` 改成 `"batch_size", 5`：

```python
        self.batch_size = max(1, int(translation_config.get("batch_size", 5)))
```

- [ ] **Step 3: 用 python 自检默认值生效**

```bash
cd /home/administrator/TrendRadar
python3 -c "
from trendradar.ai.translator import AITranslator
t = AITranslator({}, {'api_key': 'x'})
assert t.batch_size == 5, f'expected 5, got {t.batch_size}'
print('✓ batch_size default =', t.batch_size)
"
```

预期输出：`✓ batch_size default = 5`

- [ ] **Step 4: Commit**

```bash
cd /home/administrator/TrendRadar
git add trendradar/ai/translator.py
git commit -m "fix(translator): BATCH_SIZE 30→5 + 修 yaml key 大小写不匹配

BATCH_SIZE 默认 30 太大，一批里任意一条触发内容审核会拖累
整批 30 条。改 5 条/批以减少 400 new_sensitive 触发面。

同时修一个隐性 bug：translator.py 读大写 BATCH_SIZE，
但 config.yaml 用小写 batch_size——之前 yaml 调 batch_size
永远不生效。本 commit 把代码改成读小写 key（与 yaml 风格一致）。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 改 __main__.py "分析完成" 文案区分段 B 跳过

**Files:**
- Modify: `trendradar/__main__.py:549-555`

- [ ] **Step 1: 打开文件确认上下文**

读 `trendradar/__main__.py:547-567`，确认当前结构：
```python
            # 设置 AI 分析使用的模式
            if result.success:
                result.ai_mode = ai_mode
                if result.error:
                    # 成功但有警告（如 JSON 解析问题但使用了原始文本）
                    print(f"[AI] 分析完成（有警告: {result.error}）")
                else:
                    print("[AI] 分析完成")
                ...
```

- [ ] **Step 2: 修改 if/elif 链**

把现有的 if/elif 块：
```python
                if result.error:
                    # 成功但有警告（如 JSON 解析问题但使用了原始文本）
                    print(f"[AI] 分析完成（有警告: {result.error}）")
                else:
                    print("[AI] 分析完成")
```

替换成：
```python
                # 判定：段 A 成功 + 段 B 整段被跳过
                # rss_insights/standalone_summaries 全空 且 用户实际启用了段 B → 被跳过
                b_skipped = (not result.rss_insights) and (not result.standalone_summaries)
                if b_skipped and (result.rss_count > 0 or result.standalone_analyzed > 0):
                    print("[AI] 分析完成（RSS+独立展示区段因内容审核被跳过，详见上方日志）")
                elif result.error:
                    # 成功但有警告（如 JSON 解析问题但使用了原始文本）
                    print(f"[AI] 分析完成（有警告: {result.error}）")
                else:
                    print("[AI] 分析完成")
```

- [ ] **Step 3: Python 自检——模块能 import、不破坏现有逻辑**

```bash
cd /home/administrator/TrendRadar
python3 -c "
from trendradar.__main__ import TrendRadar
print('✓ import ok')

# 用 dataclass 模拟一个 段 B 跳过 的 result
from trendradar.ai.analyzer import AIAnalysisResult
r = AIAnalysisResult(success=True, rss_insights='', standalone_summaries={}, rss_count=5, standalone_analyzed=2)
b_skipped = (not r.rss_insights) and (not r.standalone_summaries)
hit = b_skipped and (r.rss_count > 0 or r.standalone_analyzed > 0)
assert hit, 'should be detected as b skipped'
print('✓ b_skipped detected')

# 模拟 rss_count=0 的边界（用户没启用 RSS）——不应被误判
r2 = AIAnalysisResult(success=True, rss_insights='', standalone_summaries={'a': 'ok'}, rss_count=0, standalone_analyzed=2)
b_skipped2 = (not r2.rss_insights) and (not r2.standalone_summaries)
hit2 = b_skipped2 and (r2.rss_count > 0 or r2.standalone_analyzed > 0)
assert not hit2, 'should NOT be detected as b skipped (user disabled RSS)'
print('✓ no false positive')
"
```

预期输出：
```
✓ import ok
✓ b_skipped detected
✓ no false positive
```

- [ ] **Step 4: 容器内端到端验证（可选，需要 docker 跑起来）**

```bash
cd /home/administrator/TrendRadar
docker exec trendradar python3 -c "
from trendradar.__main__ import TrendRadar
from trendradar.ai.analyzer import AIAnalysisResult
print('✓ 容器内 import ok')
"
```

预期：`✓ 容器内 import ok`

- [ ] **Step 5: Commit**

```bash
cd /home/administrator/TrendRadar
git add trendradar/__main__.py
git commit -m "fix(main): 段 B 整段跳过时换打印文案

之前段 A 成功 + 段 B 因内容审核被跳过时，打印的是
'分析完成'——会误导用户以为全部成功。

改为检测 rss_insights 和 standalone_summaries 同时为空
且 rss_count/standalone_analyzed 表明用户启用了段 B
时，打印'分析完成（RSS+独立展示区段因内容审核被跳过）'。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 端到端验证（手工 + 容器内）

**Files:**
- 不改文件，只是验证

- [ ] **Step 1: 跑现有测试（如有）**

```bash
cd /home/administrator/TrendRadar
find . -name "test_*.py" -not -path "./output/*" | head -5
```

预期：列出 0-2 个文件。这个项目原本就没什么 pytest 测试（grep 没找到 tests/ 目录），不强求通过。

- [ ] **Step 2: 容器内跑一次完整流程触发 400 new_sensitive**

确认改动生效的最强信号：实际跑一次看 `[翻译] 共 N 条，分 M 批发送（每批 5 条）` 和 `[AI] 分析完成（RSS+独立展示区段因内容审核被跳过...）`：

```bash
cd /home/administrator/TrendRadar
docker exec trendradar python3 -c "
from trendradar.ai.translator import AITranslator
# 模拟 RSS 10 条
titles = [f'Foreign news headline {i}' for i in range(10)]
t = AITranslator({'enabled': True, 'language': 'Chinese', 'batch_size': 5}, {'api_key': 'fake'})
print('batch_size =', t.batch_size)
print('will send', len(titles) // t.batch_size + 1, 'batches of', t.batch_size)
"
```

预期：
```
batch_size = 5
will send 2 batches of 5
```

（"2 batches of 5" —— 证明改完生效）

- [ ] **Step 3: 检查工作树**

```bash
cd /home/administrator/TrendRadar
git status
git log --oneline -3
```

预期：工作树干净；HEAD 在 Task 2 的 commit 上；最近 3 个 commit 包含 BATCH_SIZE 改动 + main.py 改动。

- [ ] **Step 4: push**

```bash
cd /home/administrator/TrendRadar
git push origin master
```

---

## Self-Review

**1. Spec 覆盖：**
- ✅ 任务 1：默认 BATCH_SIZE 30→5（spec 改动 1）
- ✅ 任务 2：段 B 跳过的判定与文案（spec 改动 2）
- ✅ 任务 3：手工验证（spec 验证标准）
- ⏭ 任务不写：config.yaml / analyzer.py 改动（spec 明确说不改）

**2. 占位符扫描：** grep "TODO|TBD|fill in|Similar to Task" — 0 hit

**3. 类型一致性：** `result.rss_count`、`result.standalone_analyzed`、`result.rss_insights`、`result.standalone_summaries` 在 `AIAnalysisResult` dataclass（analyzer.py:18-45）里都已定义；`result.batch_size` 改名后只在 `translator.py` 内部用，无外部消费方。
