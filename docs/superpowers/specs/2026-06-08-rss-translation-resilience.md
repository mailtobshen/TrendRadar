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

**最终 2 个文件，~10 行改动。**

### 1. `trendradar/ai/translator.py:56` — 修大小写不匹配 + 默认 5

```python
# 改前
self.batch_size = max(1, int(translation_config.get("BATCH_SIZE", 30)))
# 改后
self.batch_size = max(1, int(translation_config.get("batch_size", 5)))
```

**Bug 现状：** yaml 用小写 `batch_size`，但 `translator.py` 读大写 `BATCH_SIZE`——之前 yaml 改 batch_size 永远不生效。**这次顺手把 default 也从 30 改 5。**

### 2. `trendradar/__main__.py:549-555` — 段 B 跳过的判定与文案

```python
# 改前
if result.success:
    result.ai_mode = ai_mode
    if result.error:
        print(f"[AI] 分析完成（有警告: {result.error}）")
    else:
        print("[AI] 分析完成")
    ...

# 改后
if result.success:
    result.ai_mode = ai_mode
    # 段 B (RSS+独立展示) 字段全空 + 用户配置启用了段 B → 段 B 被跳过
    # 用 include_rss/include_standalone 判定"用户启用",避免当日 RSS 抓取为空时漏报
    b_user_enabled = result.include_rss or result.include_standalone
    b_empty = not result.rss_insights and not result.standalone_summaries
    if b_user_enabled and b_empty:
        print("[AI] 分析完成（RSS+独立展示区段已跳过，详见上方日志）")
    elif result.error:
        print(f"[AI] 分析完成（有警告: {result.error}）")
    else:
        print("[AI] 分析完成")
    ...
```

**判定为何不误伤：** SCOPE.RSS=false 或 STANDALONE=false 时 rss_count=0 / standalone_analyzed=0——`result.rss_count > 0 or result.standalone_analyzed > 0` 这条件会跳过误伤，只在"用户启用但被跳"时打提示。

### 3. 不改 `config/config.yaml` —— 默认值 5 已生效

`config.yaml` 的 `ai_translation` 段没 `batch_size` key——因为 `translator.py` 读不到 yaml（大小写 bug），之前写也没用。**这次修了 translator 的 key，将来用户想在 yaml 调，加一行 `batch_size: 5` 即可；本 PR 不强加 yaml 改动。**

### 4. 不改 `trendradar/ai/analyzer.py` —— 段 B 跳过信号已隐含

`_merge_segment_results` 已经把"段 A 接管 + 段 B 失败"映射成 `success=True, rss_insights="", standalone_summaries={}`。`__main__.py` 用这两个字段判定足矣，不需要新加 `skipped_segments` 字段。

---

## 不做什么（YAGNI）

- 不换 AI provider / prompt
- 不重写降级策略（1.0/0.5/0.25 三档够用）
- 不在 HTML 报告里加"本批 N 条跳过"提示（用户没要求；print 日志已够用）
- 不动 dispatcher / webui
- 不引入消息队列 / 重试调度
- 不在 yaml 加 `batch_size: 5`（修了 translator.py 后默认已是 5；用户未来想调再加）

---

## 验证标准

1. **默认 batch_size 生效：**
   ```python
   from trendradar.ai.translator import AITranslator
   t = AITranslator({}, {"api_key": "x"})
   assert t.batch_size == 5
   ```
2. **代码加载无错：** `python -c "from trendradar.ai.translator import AITranslator; from trendradar.ai.analyzer import AIAnalysisResult; print('ok')"`
3. **手工注入测试：** 在 `_pre_translate_rss_titles` 的 `titles` 里塞入一条 `litellm` 必拒的敏感标题（例如 "How the Drive to Find a Conspiracy Against Trump Rocked the CIA" 已知会触发）→ 跑 `python -m trendradar` → 看到日志 `[翻译][DEBUG] 批 X/N AI 解析 ...` 标错 + DB 仍有该标题原样入库
4. **跳批不崩：** 同上，预期 `[AI] 分析完成（RSS+独立展示区段因内容审核被跳过，详见上方日志）` 出现，**不抛 traceback**
5. **结果可入 DB：** DB 查询 `SELECT title FROM rss_items WHERE date(timestamp)=date('now')` 既有中文也有英文（未翻译的）

---

---

## 范围

单次实现 plan 即可（4 个文件、~30 行）。无子项目分解。
