# RSS 翻译 / 报告分析 鲁棒性增强（MiniMax 400 new_sensitive 场景）

**日期：** 2026-06-08
**目标：** 让报告生成在 MiniMax API 触发内容审核时"看起来几乎不丢东西"

---

## 用户视角的成功标准

1. **整批翻译任务在 AI 内容审核拒绝时仍能跑完**——失败的批次被跳过，后续批次照常处理
2. **单批数据量变小**（5 条/批）以减少 400 触发面
3. **报告生成不报"AI 分析失败"**——段 B（RSS + 独立展示区）失败时整体 success 仍为 True，HTML 报告不被"红字失败"覆盖
4. **跳过的批次在日志里清晰可见**，避免用户误以为"分析完成 = 全部成功"

---

## 现状分析

代码已具备大部分降级能力，**只缺三件事**：

| 现状 | 已实现？ | 来源 |
|------|----------|------|
| 段 B（RSS+独立展示区）内容审核拒绝时 1.0/0.5/0.25 三档降级重试 | ✅ | `analyzer.py:504-579` `_try_segment_with_degradation` |
| 三档全败后段 B 返回 None，整体 success 仍为 True（段 A 接管） | ✅ | `analyzer.py:581-620` `_merge_segment_results` |
| RSS 标题预翻译单批失败时逐条标 error，**不覆盖原标题** | ✅ | `translator.py:243-247` `except` 分支只 `batch_result.results[idx].error = ...` |
| 单批数据量 | ❌ 30 条/批（过大） | `translator.py:56` `BATCH_SIZE = 30` |
| 报告"分析完成"文案误导用户 | ❌ 不区分段失败/段 A-only | `__main__.py:549-555` |
| 跳过的批次无结构化标记 | ❌ 仅 print 不可被 HTML 消费 | `analyzer.py:563-572` 仅 stdout |

---

## 改动清单

### 1. `config/config.yaml` — 调小 BATCH_SIZE

```yaml
AI_TRANSLATION:
  ENABLED: true
  PRE_TRANSLATE_ON_CRAWL: true
  LANGUAGE: Chinese
  BATCH_SIZE: 5   # 原 30，5 条/批更易触达限速/审核容忍
  SCOPE:
    HOTLIST: true
    RSS: true
    STANDALONE: true
```

### 2. `trendradar/ai/analyzer.py` — 给段 B 失败加结构化标记

**位置：** `_merge_segment_results`（约 581-620 行）

**改动：**
- 新增 `AIAnalysisResult.skipped_segments: List[str] = field(default_factory=list)`（dataclass 字段）
- `_try_segment_with_degradation` 返回 `None` 时附带一个 marker（"rss_standalone"），由 `_merge_segment_results` 写入 `skipped_segments`
- `_merge_segment_results` 在 `primary = segment_a or segment_b` 之上，记录哪些段被跳过
- 不抛异常，不改 success 行为

**为何 dataclass 加字段：** `__main__.py` 第 549 行 `result.success` 已能区分"分析完成 / 跳过 / 失败"——只要在 `skipped` 判定里多看 `skipped_segments` 即可（见改动 3）。

### 3. `trendradar/ai/analyzer.py` — `AIAnalysisResult` dataclass 字段

**位置：** `analyzer.py:17` 附近

**改动：**
- 在 `AIAnalysisResult` 里加：
  ```python
  skipped_segments: List[str] = field(default_factory=list)
  # 取值示例: ["rss_standalone"]  → 段 B 全部降级档失败
  ```

### 4. `trendradar/__main__.py` — 文案与日志

**位置：** 第 549-555 行

**改动前：**
```python
if result.success:
    result.ai_mode = ai_mode
    if result.error:
        print(f"[AI] 分析完成（有警告: {result.error}）")
    else:
        print("[AI] 分析完成")
    ...
```

**改动后：**
```python
if result.success:
    result.ai_mode = ai_mode
    if result.skipped_segments:
        # 任一段被跳过（如 RSS+独立展示区 触发了内容审核）
        # 整体 success 仍为 True（段 A 接管），但用户需要知道
        skip_labels = "、".join(result.skipped_segments)
        print(f"[AI] 分析完成（{skip_labels} 段因内容审核被跳过，详见上方日志）")
    elif result.error:
        print(f"[AI] 分析完成（有警告: {result.error}）")
    else:
        print("[AI] 分析完成")
    ...
```

### 5. `trendradar/ai/translator.py` — 不动

`_translate_one_chunk` 的 `except` 已经只对 `chunk_indices` 标错（不抛、不影响其他 chunk）。**完全不动**。

---

## 不做什么（YAGNI）

- 不换 AI provider / prompt
- 不重写降级策略（1.0/0.5/0.25 三档够用）
- 不在 HTML 报告里加"本批 N 条跳过"提示（用户没要求；print 日志已够用）
- 不动 dispatcher / webui
- 不引入消息队列 / 重试调度

---

## 验证标准

1. **配置生效：** `python -c "import yaml; print(yaml.safe_load(open('config/config.yaml'))['AI_TRANSLATION']['BATCH_SIZE'])"` 输出 `5`
2. **代码加载无错：** `python -c "from trendradar.ai.translator import AITranslator; print('ok')"`
3. **手工注入测试：** 临时把 `BATCH_SIZE=50`，跑一次爬取（feed>10），观察 `[RSS] 入库前翻译` 日志中"分 N 批发送"对应 N≈总条数/5
4. **跳批不崩：** 故意往 prompt 注入敏感标题 → 容器内 `docker exec trendradar python -m trendradar` → 日志出现"内容审核拒绝"+"降级重试"+"分析完成（rss_standalone 段因内容审核被跳过）"，**不抛 traceback**
5. **结果可入 DB：** 跳过的批次标题保留原文入库，DB 查询 `SELECT title FROM rss_items WHERE date(timestamp)=date('now')` 既有中文也有英文（未翻译的）

---

## 范围

单次实现 plan 即可（4 个文件、~30 行）。无子项目分解。
