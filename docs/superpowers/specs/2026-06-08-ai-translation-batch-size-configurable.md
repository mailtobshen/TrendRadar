# AI 翻译 batch_size 暴露为可配置项

**日期：** 2026-06-08
**目标：** 让用户能在 config.yaml 和 WebUI 配置管理页里手工调整 `ai_translation.batch_size`

---

## 用户视角的成功标准

1. **yaml 调整生效**：在 `config/config.yaml` 的 `ai_translation` 段改 `batch_size: 10`，容器重启后，AI 翻译日志显示"分 X 批发送（每批 10 条）"
2. **WebUI 调整生效**：在 WebUI 配置管理页的"AI 翻译"面板里改"每批翻译条数"输入框，保存后 yaml 自动更新
3. **schema 一致性**：config_schema.py 的 ai_translation 默认值包含 `batch_size: 5`，避免校验时字段被剥掉

---

## 现状

| 位置 | 状态 |
|------|------|
| `trendradar/ai/translator.py:56` | 已读 yaml `batch_size`（小写），默认 5（commit 09de799） |
| `config/config.yaml` `ai_translation` 段 | 无 `batch_size` 字段 |
| `config_schema.py:205-211` `ai_translation` 默认值 | 无 `batch_size` 字段 |
| `config_page.py:560-593` AI 翻译 UI 面板 | 无 batch_size 输入框 |
| `config_page.py:1031-1038` JS load 函数 | 无 aiTrans.batch_size 加载 |
| `ai_filter.batch_size` | **完整对称实现**（schema 235-238、UI 661-662、JS 1056）——可直接参考 |

**ai_filter 是模板**——`ai_filter.batch_size` 怎么做的，照搬即可。

---

## 改动清单

### 1. `config/config.yaml` — `ai_translation` 段加 `batch_size`

```yaml
ai_translation:
  enabled: true
  language: 中文
  prompt_file: ai_translation_prompt.txt
  scope:
    hotlist: false
    rss: true
    standalone: true
  batch_size: 5   # 新增：每批翻译条数。值越小越不易触发内容审核拖累整批
```

### 2. `trendradar/webui/config_schema.py:205-211` — 默认值加 batch_size

```python
"ai_translation": {
    "enabled": False,
    "language": "中文",
    "prompt_file": "ai_translation_prompt.txt",
    "scope": {"hotlist": False, "rss": True, "standalone": True},
    "pre_translate_on_crawl": True,
    "batch_size": 5,   # 新增
},
```

### 3. `trendradar/webui/config_page.py:560-593` — AI 翻译 UI 加 batch_size 输入

**位置：** 在第 568-571 行"目标语言"输入框后，加一个 form-row：

```html
<div class="form-row">
    <div class="form-group">
        <label class="form-label">每批翻译条数</label>
        <input type="number" id="ai-translation-batch-size" min="1"
            onchange="updateConfig('ai_translation.batch_size', parseInt(this.value)||5)">
        <div class="form-hint">每批发给 AI 的标题数（值越小越不易触发内容审核拖累整批，建议 5-30）</div>
    </div>
</div>
```

### 4. `trendradar/webui/config_page.py:1031-1038` — JS load 加一行

```javascript
// AI 翻译
const aiTrans = getValue('ai_translation') || {};
setToggle('ai-translation-enabled-toggle', aiTrans.enabled);
setInput('ai-translation-language', aiTrans.language);
setInput('ai-translation-batch-size', aiTrans.batch_size);   // 新增
const transScope = aiTrans.scope || {};
setCheckbox('ai-translation-scope-hotlist', transScope.hotlist);
...
```

### 5. 不改 `trendradar/ai/translator.py`

commit 09de799 已经让 translator 读 yaml `batch_size`。**完全不动**。

---

## 不做什么

- 不改默认值大小（仍 5）
- 不加复杂的范围校验（min=1 足够）
- 不在 webui 加 hover tooltip（`.form-hint` 足够）
- 不动 dispatcher / 报告生成 / RSS schema

---

## 验证标准

1. **yaml 改后能 load**：`python3 -c "import yaml; print(yaml.safe_load(open('config/config.yaml'))['ai_translation']['batch_size'])"` 输出 `5`
2. **schema 默认值存在**：`python3 -c "from trendradar.webui.config_schema import DEFAULT_CONFIG; print(DEFAULT_CONFIG['ai_translation']['batch_size'])"` 输出 `5`
3. **WebUI 输入框出现**：浏览器打开 config 页，AI 翻译面板应显示"每批翻译条数"输入框，默认值 5
4. **改 WebUI 后 yaml 更新**：把输入框改 10，点保存，yaml 里 `ai_translation.batch_size: 10`
5. **改 yaml 后 AI 翻译生效**：手动把 yaml 改 7，重启容器跑一次翻译，stdout 应见"分 N 批发送（每批 7 条）"
6. **HTML 不破坏**：用 Playwright 截图确认整个 AI 翻译 section 布局没乱

---

## 范围

4 个文件、~15 行改动。无需子项目分解。
