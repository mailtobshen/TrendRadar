# coding=utf-8
"""
配置管理页面生成模块（结构化表单版本）

生成 config.html 的完整 HTML 内容，纯 HTML + CSS + JS，无外部依赖。
提供完全结构化的表单配置界面。
"""


def render_config_page() -> str:
    """返回配置管理页面的完整 HTML 字符串"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrendRadar 配置管理</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: #f5f5f7;
            color: #333;
            line-height: 1.6;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 20px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header-title { font-size: 18px; font-weight: 600; }
        .header-back {
            color: white; text-decoration: none; font-size: 14px;
            background: rgba(255,255,255,0.15); padding: 8px 16px;
            border-radius: 6px; transition: background 0.2s;
        }
        .header-back:hover { background: rgba(255,255,255,0.25); }
        .container {
            max-width: 960px; margin: 0 auto; padding: 24px;
        }
        .nav-tabs {
            display: flex; gap: 4px; margin-bottom: 20px;
            background: white; padding: 4px; border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            flex-wrap: wrap;
        }
        .nav-tab {
            flex: 1; min-width: 100px; padding: 10px 8px;
            border: none; background: transparent; border-radius: 6px;
            cursor: pointer; font-size: 13px; font-weight: 500;
            color: #666; transition: all 0.2s; text-align: center;
        }
        .nav-tab:hover { background: #f5f5f7; }
        .nav-tab.active { background: #4f46e5; color: white; }
        .panel { display: none; }
        .panel.active { display: block; }
        .section {
            background: white; border-radius: 12px;
            padding: 24px; margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        .section-title {
            font-size: 16px; font-weight: 600;
            margin-bottom: 16px; color: #1a1a1a;
            display: flex; align-items: center; gap: 8px;
        }
        .section-desc {
            font-size: 13px; color: #888;
            margin-bottom: 16px; margin-top: -8px;
        }
        .form-row {
            display: flex; flex-wrap: wrap;
            gap: 16px; margin-bottom: 16px;
        }
        .form-group {
            flex: 1; min-width: 200px;
        }
        .form-group.full { min-width: 100%; }
        .form-group.half { min-width: 45%; }
        .form-label {
            display: block; font-size: 13px;
            font-weight: 500; color: #555;
            margin-bottom: 6px;
        }
        .form-label .optional {
            font-weight: 400; color: #999; font-size: 12px;
        }
        input[type="text"], input[type="number"], input[type="password"],
        input[type="url"], input[type="email"],
        select, textarea {
            width: 100%; padding: 10px 12px;
            border: 1px solid #e5e5e5; border-radius: 8px;
            font-size: 14px; background: #fafafa;
            transition: border-color 0.2s, background 0.2s;
        }
        input:focus, select:focus, textarea:focus {
            outline: none; border-color: #4f46e5;
            background: white;
        }
        select { cursor: pointer; }
        textarea { resize: vertical; min-height: 80px; font-family: monospace; }
        input[type="checkbox"] {
            width: 18px; height: 18px; cursor: pointer;
            accent-color: #4f46e5;
        }
        .checkbox-row {
            display: flex; align-items: center;
            gap: 8px; padding: 8px 0;
        }
        .checkbox-row label {
            font-size: 14px; color: #444; cursor: pointer;
        }
        .switch-row {
            display: flex; align-items: center;
            justify-content: space-between;
            padding: 10px 0; border-bottom: 1px solid #f0f0f0;
        }
        .switch-row:last-child { border-bottom: none; }
        .switch-label { font-size: 14px; color: #444; }
        .switch-desc { font-size: 12px; color: #999; margin-top: 2px; }
        .toggle-switch {
            position: relative; width: 44px; height: 24px;
            background: #e5e5e5; border-radius: 12px;
            cursor: pointer; transition: background 0.2s;
            flex-shrink: 0;
        }
        .toggle-switch.on { background: #4f46e5; }
        .toggle-switch::after {
            content: ''; position: absolute; top: 2px; left: 2px;
            width: 20px; height: 20px; background: white;
            border-radius: 50%; transition: transform 0.2s;
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }
        .toggle-switch.on::after { transform: translateX(20px); }
        .platform-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 10px;
        }
        .platform-card {
            display: flex; align-items: center; gap: 8px;
            padding: 10px 12px; background: #fafafa;
            border: 1px solid #e5e5e5; border-radius: 8px;
            cursor: pointer; transition: all 0.2s;
        }
        .platform-card:hover { border-color: #4f46e5; background: #f5f3ff; }
        .platform-card.disabled { opacity: 0.5; background: #f5f5f5; }
        .platform-card input { flex-shrink: 0; }
        .platform-card span { font-size: 13px; }
        .tag-input {
            display: flex; flex-wrap: wrap; gap: 6px;
            padding: 6px; border: 1px solid #e5e5e5;
            border-radius: 8px; background: #fafafa;
            min-height: 42px; align-items: center;
        }
        .tag-input:focus-within { border-color: #4f46e5; background: white; }
        .tag {
            display: inline-flex; align-items: center; gap: 4px;
            padding: 4px 10px; background: #ede9fe;
            color: #4f46e5; border-radius: 16px;
            font-size: 13px; font-weight: 500;
        }
        .tag-remove {
            cursor: pointer; font-size: 14px; line-height: 1;
            padding: 0 2px; border-radius: 50%;
        }
        .tag-remove:hover { background: rgba(79,70,229,0.15); }
        .tag-input input {
            flex: 1; min-width: 80px; border: none;
            background: transparent; padding: 4px;
        }
        .tag-input input:focus { outline: none; }
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
        .list-table {
            width: 100%; border-collapse: collapse;
        }
        .list-table th {
            text-align: left; font-size: 12px;
            font-weight: 600; color: #888;
            padding: 8px 12px; border-bottom: 1px solid #e5e5e5;
            background: #fafafa;
        }
        .list-table td {
            padding: 8px 12px; border-bottom: 1px solid #f0f0f0;
            font-size: 14px;
        }
        .list-table tr:hover td { background: #fafafa; }
        .list-table input {
            padding: 6px 8px; font-size: 13px;
        }
        .btn {
            display: inline-flex; align-items: center; gap: 6px;
            padding: 8px 16px; border: none; border-radius: 8px;
            font-size: 13px; font-weight: 500; cursor: pointer;
            transition: all 0.2s;
        }
        .btn-sm { padding: 6px 12px; font-size: 12px; }
        .btn-primary {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
        }
        .btn-primary:hover { opacity: 0.92; transform: translateY(-1px); }
        .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .btn-secondary {
            background: #f5f5f7; color: #333;
            border: 1px solid #e5e5e5;
        }
        .btn-secondary:hover { background: #ebebef; }
        .btn-danger { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
        .btn-danger:hover { background: #fee2e2; }
        .btn-icon {
            width: 32px; height: 32px; padding: 0;
            justify-content: center; border-radius: 6px;
        }
        .actions-bar {
            display: flex; gap: 12px; align-items: center;
            flex-wrap: wrap;
            position: sticky; bottom: 0;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            padding: 16px 24px; margin: 0 -24px -24px;
            border-top: 1px solid #e5e5e5;
        }
        .status-bar {
            display: flex; align-items: center; gap: 16px;
            margin-left: auto; font-size: 13px; color: #666;
        }
        .status-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: #22c55e;
        }
        .status-dot.running { background: #f59e0b; animation: pulse 1.5s infinite; }
        .status-dot.error { background: #ef4444; }
        @keyframes pulse {
            0%, 100% { opacity: 1; } 50% { opacity: 0.4; }
        }
        .toast {
            position: fixed; top: 20px; right: 20px;
            padding: 14px 20px; border-radius: 10px;
            font-size: 14px; font-weight: 500; color: white;
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
            transform: translateX(120%);
            opacity: 0;
            pointer-events: none;
            transition: transform 0.3s ease, opacity 0.3s ease;
            z-index: 1000; max-width: 360px; word-break: break-word;
            cursor: pointer;
        }
        .toast.show {
            transform: translateX(0);
            opacity: 1;
            pointer-events: auto;
        }
        .toast.success { background: #22c55e; }
        .toast.error { background: #ef4444; }
        .rss-test-status { font-size: 12px; margin-left: 6px; }
        .rss-test-status.testing { color: #888; }
        .rss-test-status.success { color: #22c55e; }
        .rss-test-status.error { color: #ef4444; }
        .btn-icon-refresh {
            width: 28px; height: 28px; padding: 0;
            border-radius: 6px; font-size: 14px;
            background: #f3f4f6; border: 1px solid #e5e5e5;
            cursor: pointer;
            display: inline-flex; align-items: center; justify-content: center;
        }
        .btn-icon-refresh:hover { background: #e5e7eb; }
        .btn-icon-refresh:disabled { opacity: 0.5; cursor: not-allowed; }
        .toast.info { background: #4f46e5; }
        .validation-errors {
            background: #fef2f2; border: 1px solid #fecaca;
            border-radius: 8px; padding: 14px 16px;
            margin-bottom: 16px; display: none;
        }
        .validation-errors.show { display: block; }
        .validation-errors-title {
            font-size: 13px; font-weight: 600;
            color: #b91c1c; margin-bottom: 8px;
        }
        .validation-error-item {
            font-size: 13px; color: #991b1b;
            padding: 3px 0; font-family: monospace;
        }
        .word-group {
            background: #fafafa; border: 1px solid #e5e5e5;
            border-radius: 10px; padding: 16px;
            margin-bottom: 12px;
        }
        .word-group-header {
            display: flex; align-items: center;
            gap: 10px; margin-bottom: 12px;
        }
        .word-group-header input {
            flex: 1; font-weight: 500;
        }
        .word-group-header .btn-icon {
            flex-shrink: 0;
        }
        .keyword-row {
            display: flex; align-items: center;
            gap: 8px; margin-bottom: 8px;
        }
        .keyword-row select {
            width: auto; min-width: 100px; flex-shrink: 0;
        }
        .keyword-row input {
            flex: 1;
        }
        .keyword-row .btn-icon {
            flex-shrink: 0;
        }
        .empty-state {
            text-align: center; padding: 40px;
            color: #999; font-size: 14px;
        }
        @media (max-width: 640px) {
            .container { padding: 12px; }
            .header { padding: 16px; }
            .header-title { font-size: 16px; }
            .form-row { flex-direction: column; gap: 12px; }
            .form-group { min-width: 100% !important; }
            .platform-grid { grid-template-columns: repeat(2, 1fr); }
            .actions-bar { flex-direction: column; align-items: stretch; }
            .status-bar { margin-left: 0; margin-top: 8px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-title">TrendRadar 配置管理</div>
        <a href="/index.html" class="header-back">返回报告</a>
    </div>

    <div class="container">
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="switchPanel('platforms')">平台与RSS</button>
            <button class="nav-tab" onclick="switchPanel('ai')">AI 模型</button>
            <button class="nav-tab" onclick="switchPanel('report')">报告与筛选</button>
            <button class="nav-tab" onclick="switchPanel('display')">显示与推送</button>
            <button class="nav-tab" onclick="switchPanel('storage')">存储与高级</button>
            <button class="nav-tab" onclick="switchPanel('keywords')">关键词</button>
            <button class="nav-tab" onclick="switchPanel('tags')">标签配置</button>
        </div>

        <!-- 平台与 RSS -->
        <div class="panel active" id="panel-platforms">
            <div class="section">
                <div class="section-title">热榜平台</div>
                <div class="section-desc">选择要监控的热榜平台</div>
                <div class="checkbox-row">
                    <input type="checkbox" id="platforms-enabled" onchange="updateConfig('platforms.enabled', this.checked)">
                    <label for="platforms-enabled">启用热榜抓取</label>
                </div>
                <div id="platforms-list" class="platform-grid" style="margin-top:12px;"></div>
            </div>

            <div class="section">
                <div class="section-title">RSS 订阅</div>
                <div class="section-desc">添加 RSS 订阅源，获取博客、新闻等订阅内容</div>
                <div class="checkbox-row" style="margin-bottom:12px;">
                    <input type="checkbox" id="rss-enabled" onchange="updateConfig('rss.enabled', this.checked)">
                    <label for="rss-enabled">启用 RSS 抓取</label>
                </div>
                <div class="form-row">
                    <div class="form-group half">
                        <label class="form-label">文章新鲜度过滤</label>
                        <div class="checkbox-row">
                            <input type="checkbox" id="rss-freshness-enabled" onchange="updateConfig('rss.freshness_filter.enabled', this.checked)">
                            <label for="rss-freshness-enabled">启用新鲜度过滤</label>
                        </div>
                    </div>
                    <div class="form-group half">
                        <label class="form-label">最大文章年龄（天）</label>
                        <input type="number" id="rss-freshness-days" min="0"
                            onchange="updateConfig('rss.freshness_filter.max_age_days', parseInt(this.value)||0)">
                    </div>
                </div>
                <table class="list-table" style="margin-top:12px;">
                    <thead>
                        <tr><th>ID</th><th>名称</th><th>URL</th><th>启用</th><th>RSS网络测试</th><th></th></tr>
                    </thead>
                    <tbody id="rss-feeds-list"></tbody>
                </table>
                <button class="btn btn-secondary btn-sm" style="margin-top:12px;" onclick="addRssFeed()">+ 添加 RSS 源</button>
            </div>
            <div class="section">
                <div class="section-title">调度系统</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">启用调度</label>
                        <div class="toggle-switch" id="schedule-enabled-toggle" onclick="toggleSwitch('schedule.enabled')"></div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">预设模板</label>
                        <select id="schedule-preset" onchange="updateConfig('schedule.preset', this.value)">
                            <option value="always_on">全天候</option>
                            <option value="morning_evening">早晚模式（推荐）</option>
                            <option value="office_hours">工作日三段式</option>
                            <option value="night_owl">夜间模式</option>
                            <option value="custom">完全自定义</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">自动爬取频率</label>
                        <select id="schedule-crawl-interval" onchange="updateConfig('schedule.crawl_interval_hours', parseInt(this.value))">
                            <option value="1">每1小时</option>
                            <option value="2">每2小时</option>
                            <option value="3">每3小时</option>
                            <option value="4">每4小时</option>
                            <option value="5">每5小时</option>
                            <option value="6">每6小时</option>
                        </select>
                    </div>
                </div>
            </div>
        </div>

        <!-- AI 模型 -->
        <div class="panel" id="panel-ai">
            <div class="section">
                <div class="section-title">AI 模型配置</div>
                <div class="section-desc">ai_analysis / ai_translation / ai_filter 共用此模型配置</div>
                <div class="form-row">
                    <div class="form-group half">
                        <label class="form-label">Provider <span class="optional">LiteLLM 协议路由</span></label>
                        <select id="ai-provider" onchange="updateConfig('ai.provider', this.value)">
                            <option value="openai">openai (OpenAI 原生/兼容)</option>
                            <option value="anthropic">anthropic (Anthropic 原生/兼容)</option>
                            <option value="gemini">gemini (Gemini 原生/兼容)</option>
                            <option value="bedrock">bedrock (AWS Bedrock)</option>
                            <option value="vertex_ai">vertex_ai (Google Cloud)</option>
                            <option value="azure">azure (Azure OpenAI)</option>
                            <option value="ollama">ollama (本地 Ollama)</option>
                        </select>
                    </div>
                    <div class="form-group half">
                        <label class="form-label">模型名称</label>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <select id="ai-model" onchange="updateConfig('ai.model', this.value)" style="flex: 1;">
                                <option value="">点 ↻ 从 api_base 拉取</option>
                            </select>
                            <button type="button" class="btn-icon-refresh" id="ai-model-refresh" onclick="refreshAiModels()" title="从 api_base/models 拉取模型列表（无 api_base 时回退到 LiteLLM catalog）">↻</button>
                        </div>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group half">
                        <label class="form-label">API Key <span id="ai-api-key-status" style="font-size:11px;font-weight:400;color:#059669;margin-left:6px;"></span></label>
                        <input type="password" id="ai-api-key" placeholder="sk-..."
                            onchange="updateConfig('ai.api_key', this.value)">
                        <div style="font-size:11px;color:#6b7280;margin-top:2px;">
                            真实 key 会被自动写入 <code>docker/.env</code>（gitignored），表单仅显示占位符
                        </div>
                    </div>
                    <div class="form-group half">
                        <label class="form-label">API 基础地址 <span class="optional">可选</span></label>
                        <input type="url" id="ai-api-base" placeholder="https://api.example.com/v1"
                            onchange="updateConfig('ai.api_base', this.value)">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">超时时间（秒）</label>
                        <input type="number" id="ai-timeout" min="10" max="600"
                            onchange="updateConfig('ai.timeout', parseInt(this.value)||120)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">温度 (0.0-2.0)</label>
                        <input type="number" id="ai-temperature" min="0" max="2" step="0.1"
                            onchange="updateConfig('ai.temperature', parseFloat(this.value)||1.0)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">最大 Token 数</label>
                        <input type="number" id="ai-max-tokens" min="0"
                            onchange="updateConfig('ai.max_tokens', parseInt(this.value)||5000)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">重试次数</label>
                        <input type="number" id="ai-num-retries" min="0" max="10"
                            onchange="updateConfig('ai.num_retries', parseInt(this.value)||1)">
                    </div>
                </div>
                <div style="display: flex; justify-content: flex-end; align-items: center; gap: 6px;">
                    <span id="ai-test-status" class="rss-test-status"></span>
                    <button class="btn btn-sm btn-secondary" id="ai-test-btn" onclick="testAiConnection()">测试连接</button>
                </div>
            </div>

            <div class="section">
                <div class="section-title">AI 分析</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">启用 AI 分析</label>
                        <div class="toggle-switch" id="ai-analysis-enabled-toggle" onclick="toggleSwitch('ai_analysis.enabled')"></div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">分析模式</label>
                        <select id="ai-analysis-mode" onchange="updateConfig('ai_analysis.mode', this.value)">
                            <option value="follow_report">跟随报告模式</option>
                            <option value="daily">当日汇总</option>
                            <option value="current">当前榜单</option>
                            <option value="incremental">增量更新</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">分析语言</label>
                        <input type="text" id="ai-analysis-language"
                            onchange="updateConfig('ai_analysis.language', this.value)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">最大分析条数</label>
                        <input type="number" id="ai-analysis-max-news" min="0"
                            onchange="updateConfig('ai_analysis.max_news_for_analysis', parseInt(this.value)||150)">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <div class="checkbox-row">
                            <input type="checkbox" id="ai-analysis-include-rss" onchange="updateConfig('ai_analysis.include_rss', this.checked)">
                            <label for="ai-analysis-include-rss">包含 RSS 内容</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="checkbox-row">
                            <input type="checkbox" id="ai-analysis-include-standalone" onchange="updateConfig('ai_analysis.include_standalone', this.checked)">
                            <label for="ai-analysis-include-standalone">包含独立展示区</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="checkbox-row">
                            <input type="checkbox" id="ai-analysis-include-timeline" onchange="updateConfig('ai_analysis.include_rank_timeline', this.checked)">
                            <label for="ai-analysis-include-timeline">包含排名时间线</label>
                        </div>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">AI 翻译</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">启用翻译</label>
                        <div class="toggle-switch" id="ai-translation-enabled-toggle" onclick="toggleSwitch('ai_translation.enabled')"></div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">目标语言</label>
                        <input type="text" id="ai-translation-language"
                            onchange="updateConfig('ai_translation.language', this.value)">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <div class="checkbox-row">
                            <input type="checkbox" id="ai-translation-scope-hotlist" onchange="updateConfig('ai_translation.scope.hotlist', this.checked)">
                            <label for="ai-translation-scope-hotlist">翻译热榜</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="checkbox-row">
                            <input type="checkbox" id="ai-translation-scope-rss" onchange="updateConfig('ai_translation.scope.rss', this.checked)">
                            <label for="ai-translation-scope-rss">翻译 RSS</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="checkbox-row">
                            <input type="checkbox" id="ai-translation-scope-standalone" onchange="updateConfig('ai_translation.scope.standalone', this.checked)">
                            <label for="ai-translation-scope-standalone">翻译独立展示区</label>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 报告与筛选 -->
        <div class="panel" id="panel-report">
            <div class="section">
                <div class="section-title">报告模式</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">报告模式</label>
                        <select id="report-mode" onchange="updateConfig('report.mode', this.value)">
                            <option value="daily">全天汇总（信息最全）</option>
                            <option value="current">当前榜单（实时热度）</option>
                            <option value="incremental">增量更新（最少打扰）</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">显示模式</label>
                        <select id="report-display-mode" onchange="updateConfig('report.display_mode', this.value)">
                            <option value="keyword">按关键词分组</option>
                            <option value="platform">按平台分组</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">排名高亮阈值</label>
                        <input type="number" id="report-rank-threshold" min="0"
                            onchange="updateConfig('report.rank_threshold', parseInt(this.value)||5)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">每关键词最大条数 <span class="optional">0=不限</span></label>
                        <input type="number" id="report-max-news" min="0"
                            onchange="updateConfig('report.max_news_per_keyword', parseInt(this.value)||0)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">同源最大条数 <span class="optional">每个关键词每个来源最多显示条数，默认3</span></label>
                        <input type="number" id="report-max-news-per-source" min="0"
                            onchange="updateConfig('report.max_news_per_source_per_keyword', parseInt(this.value)||0)">
                    </div>
                </div>
                <div class="checkbox-row">
                    <input type="checkbox" id="report-sort-position" onchange="updateConfig('report.sort_by_position_first', this.checked)">
                    <label for="report-sort-position">按 frequency_words 定义顺序排序（仅 keyword 模式）</label>
                </div>
            </div>

            <div class="section">
                <div class="section-title">筛选策略</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">筛选方法</label>
                        <select id="filter-method" onchange="updateConfig('filter.method', this.value)">
                            <option value="keyword">关键词匹配</option>
                            <option value="ai">AI 智能筛选</option>
                        </select>
                    </div>
                </div>
                <div class="checkbox-row">
                    <input type="checkbox" id="filter-priority-sort" onchange="updateConfig('filter.priority_sort_enabled', this.checked)">
                    <label for="filter-priority-sort">AI 模式按标签优先级排序</label>
                </div>
            </div>

            <div class="section">
                <div class="section-title">AI 智能筛选配置</div>
                <div class="section-desc">当筛选方法为 "AI" 时生效</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">每批标题数</label>
                        <input type="number" id="ai-filter-batch-size" min="1"
                            onchange="updateConfig('ai_filter.batch_size', parseInt(this.value)||200)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">批次间隔（秒）</label>
                        <input type="number" id="ai-filter-batch-interval" min="0"
                            onchange="updateConfig('ai_filter.batch_interval', parseInt(this.value)||2)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">最低分数阈值 (0.0-1.0)</label>
                        <input type="number" id="ai-filter-min-score" min="0" max="1" step="0.1"
                            onchange="updateConfig('ai_filter.min_score', parseFloat(this.value)||0.7)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">重分类阈值 (0.0-1.0)</label>
                        <input type="number" id="ai-filter-reclassify" min="0" max="1" step="0.1"
                            onchange="updateConfig('ai_filter.reclassify_threshold', parseFloat(this.value)||0.6)">
                    </div>
                </div>
            </div>
        </div>

        <!-- 显示与推送 -->
        <div class="panel" id="panel-display">
            <div class="section">
                <div class="section-title">显示区域控制</div>
                <div class="section-desc">控制推送消息中显示哪些区域</div>
                <div id="display-regions-list"></div>
            </div>

            <div class="section">
                <div class="section-title">独立展示区</div>
                <div class="section-desc">将指定平台的完整热榜独立展示，不受关键词过滤影响</div>
                <div class="form-row">
                    <div class="form-group half">
                        <label class="form-label">展示平台</label>
                        <div id="standalone-platforms" class="checkbox-group"></div>
                    </div>
                    <div class="form-group half">
                        <label class="form-label">展示 RSS 源</label>
                        <div id="standalone-rss" class="checkbox-group"></div>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">每源最大条数 <span class="optional">0=不限</span></label>
                        <input type="number" id="standalone-max-items" min="0"
                            onchange="updateConfig('display.standalone.max_items', parseInt(this.value)||20)">
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">推送通知渠道</div>
                <div class="section-desc">配置消息推送渠道（Webhook 等敏感信息建议通过环境变量配置）</div>
                <div class="checkbox-row" style="margin-bottom:16px;">
                    <input type="checkbox" id="notification-enabled" onchange="updateConfig('notification.enabled', this.checked)">
                    <label for="notification-enabled">启用推送通知</label>
                </div>
                <div id="notification-channels"></div>
            </div>
        </div>

        <!-- 存储与高级 -->
        <div class="panel" id="panel-storage">
            <div class="section">
                <div class="section-title">存储配置</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">存储后端</label>
                        <select id="storage-backend" onchange="updateConfig('storage.backend', this.value)">
                            <option value="auto">自动选择</option>
                            <option value="local">本地存储</option>
                            <option value="remote">远程存储（S3 兼容）</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">数据目录</label>
                        <input type="text" id="storage-data-dir"
                            onchange="updateConfig('storage.local.data_dir', this.value)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">本地保留天数 <span class="optional">0=永久</span></label>
                        <input type="number" id="storage-local-retention" min="0"
                            onchange="updateConfig('storage.local.retention_days', parseInt(this.value)||0)">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <div class="checkbox-row">
                            <input type="checkbox" id="storage-format-sqlite" onchange="updateConfig('storage.formats.sqlite', this.checked)">
                            <label for="storage-format-sqlite">启用 SQLite 存储</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="checkbox-row">
                            <input type="checkbox" id="storage-format-txt" onchange="updateConfig('storage.formats.txt', this.checked)">
                            <label for="storage-format-txt">生成 TXT 快照</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="checkbox-row">
                            <input type="checkbox" id="storage-format-html" onchange="updateConfig('storage.formats.html', this.checked)">
                            <label for="storage-format-html">生成 HTML 报告</label>
                        </div>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">爬虫参数</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">请求间隔（毫秒）</label>
                        <input type="number" id="crawler-interval" min="100"
                            onchange="updateConfig('advanced.crawler.request_interval', parseInt(this.value)||2000)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">启用代理</label>
                        <div class="toggle-switch" id="advanced-crawler-use_proxy-toggle" onclick="toggleSwitch('advanced.crawler.use_proxy')"></div>
                    </div>
                </div>
                <div class="section-subtitle">RSS 代理</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">启用 RSS 代理</label>
                        <div class="toggle-switch" id="advanced-rss-use_proxy-toggle" onclick="toggleSwitch('advanced.rss.use_proxy')"></div>
                    </div>
                    <div class="form-group half">
                        <label class="form-label">RSS代理服务URL</label>
                        <input type="text" id="rss-proxy-url" placeholder="http://proxy:port"
                            onchange="updateConfig('advanced.rss.proxy_url', this.value)">
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">基础设置</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">时区</label>
                        <input type="text" id="app-timezone"
                            onchange="updateConfig('app.timezone', this.value)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">显示版本更新提示</label>
                        <div class="toggle-switch" id="app-version-toggle" onclick="toggleSwitch('app.show_version_update')"></div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">调试模式</label>
                        <div class="toggle-switch" id="advanced-debug-toggle" onclick="toggleSwitch('advanced.debug')"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 关键词 -->
        <div class="panel" id="panel-keywords">
            <div class="section">
                <div class="section-title">全局过滤词</div>
                <div class="section-desc">包含这些词的新闻会被自动排除</div>
                <div id="global-filters"></div>
                <div style="margin-top:8px; display:flex; gap:8px;">
                    <input type="text" id="new-global-filter" placeholder="输入过滤词，按回车添加"
                        style="flex:1;" onkeydown="if(event.key==='Enter'){addGlobalFilter();}">
                    <button class="btn btn-secondary btn-sm" onclick="addGlobalFilter()">添加</button>
                </div>
            </div>

            <div class="section">
                <div class="section-title">关键词组</div>
                <div class="section-desc">同一词组内的关键词是"或"的关系</div>
                <div id="word-groups"></div>
                <button class="btn btn-secondary btn-sm" style="margin-top:12px;" onclick="addWordGroup()">+ 添加词组</button>
            </div>
        </div>

        <!-- 标签配置 -->
        <div class="panel" id="panel-tags">
            <div class="section">
                <div class="section-title">标签配置</div>
                <div class="section-desc">控制新闻分类标签的来源和定义</div>

                <div class="form-row" style="margin-bottom:16px;">
                    <div class="form-group half">
                        <label class="form-label">标签来源</label>
                        <select id="tags-mode" onchange="updateConfig('tags.mode', this.value); renderTagsPanel();">
                            <option value="auto">AI 自动提取</option>
                            <option value="manual">手动配置</option>
                        </select>
                    </div>
                </div>

                <div id="tags-auto-info" style="display:none;">
                    <div class="section-desc">当前从 <code>ai_interests.txt</code> 自动提取标签</div>
                    <div id="tags-current-list" style="margin-top:12px;"></div>
                    <div style="margin-top:16px; display:flex; gap:12px;">
                        <button class="btn btn-secondary btn-sm" id="btn-regenerate-tags" onclick="regenerateTagsPreview()">
                            重新生成推荐
                        </button>
                        <button class="btn btn-primary btn-sm" id="btn-switch-manual" onclick="switchToManualTags()">
                            转为手动配置
                        </button>
                    </div>
                </div>

                <div id="tags-manual-editor" style="display:none;">
                    <div class="section-desc">手动定义标签列表，AI 将按这些标签对新闻分类</div>
                    <div id="tags-manual-list" style="margin-top:12px;"></div>
                    <div style="margin-top:12px; display:flex; gap:12px;">
                        <button class="btn btn-secondary btn-sm" onclick="addManualTag()">+ 添加标签</button>
                        <button class="btn btn-secondary btn-sm" onclick="switchToAutoTags()">恢复 AI 自动</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- 底部操作栏 -->
        <div class="actions-bar">
            <button class="btn btn-primary" id="btn-save" onclick="saveConfig()">
                <span>保存配置</span>
            </button>
            <button class="btn btn-secondary" id="btn-regenerate-report" onclick="regenerateReport()">
                <span>重新生成报告</span>
            </button>
            <span id="regenerate-status" style="color:#666;font-size:13px;"></span>
            <button class="btn btn-secondary" id="btn-trigger" onclick="triggerCrawl()">
                <span>立即爬取</span>
            </button>
            <div class="status-bar">
                <div style="display:flex; align-items:center; gap:6px;">
                    <span class="status-dot" id="status-dot"></span>
                    <span id="status-text">加载中...</span>
                </div>
                <span id="last-run">上次爬取: --</span>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        // ═══════════════════════════════════════════════════════════
        // 状态管理
        // ═══════════════════════════════════════════════════════════
        let config = {};
        let frequencyWords = { global_filters: [], word_groups: [] };
        let isSaving = false;
        let isTriggering = false;

        // ═══════════════════════════════════════════════════════════
        // 初始化
        // ═══════════════════════════════════════════════════════════
        document.addEventListener('DOMContentLoaded', () => {
            loadConfig();
            pollStatus();
            setInterval(pollStatus, 5000);
        });

        // ═══════════════════════════════════════════════════════════
        // 面板切换
        // ═══════════════════════════════════════════════════════════
        function switchPanel(id) {
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('panel-' + id).classList.add('active');
        }

        // ═══════════════════════════════════════════════════════════
        // 配置路径读写工具
        // ═══════════════════════════════════════════════════════════
        function getValue(path) {
            const keys = path.split('.');
            let obj = config;
            for (const key of keys) {
                if (obj == null) return undefined;
                obj = obj[key];
            }
            return obj;
        }
        function setValue(path, value) {
            const keys = path.split('.');
            let obj = config;
            for (let i = 0; i < keys.length - 1; i++) {
                if (obj[keys[i]] == null) obj[keys[i]] = {};
                obj = obj[keys[i]];
            }
            obj[keys[keys.length - 1]] = value;
        }

        // ═══════════════════════════════════════════════════════════
        // 加载配置
        // ═══════════════════════════════════════════════════════════
        async function loadConfig() {
            try {
                const res = await fetch('/api/config');
                const data = await res.json();
                if (data.success) {
                    config = data.config || {};
                    frequencyWords = data.frequency_words || { global_filters: [], word_groups: [] };
                    renderAll();
                } else {
                    showToast(data.message || '加载配置失败', 'error');
                }
            } catch (e) {
                showToast('网络错误: ' + e.message, 'error');
            }
        }

        // ═══════════════════════════════════════════════════════════
        // 渲染所有表单
        // ═══════════════════════════════════════════════════════════
        function renderAll() {
            // 平台
            const platforms = getValue('platforms') || {};
            setCheckbox('platforms-enabled', platforms.enabled);
            renderPlatforms(platforms.sources || []);

            // RSS
            const rss = getValue('rss') || {};
            setCheckbox('rss-enabled', rss.enabled);
            const freshness = rss.freshness_filter || {};
            setCheckbox('rss-freshness-enabled', freshness.enabled);
            setInput('rss-freshness-days', freshness.max_age_days);
            renderRssFeeds(rss.feeds || []);

            // AI
            const ai = getValue('ai') || {};
            setInput('ai-api-key', ai.api_key);
            // 真实 key 在 .env，config.yaml 只含占位符；当 AI_API_KEY 环境变量已配置时显示"已加载"提示
            const statusEl = document.getElementById('ai-api-key-status');
            if (statusEl) {
                if (ai.api_key === 'YOUR_API_KEY_HERE' || !ai.api_key) {
                    statusEl.textContent = '（当前从环境变量加载，真实 key 不会显示在表单中）';
                    statusEl.style.color = '#059669';
                } else {
                    statusEl.textContent = '（当前 key 直接写在 config.yaml 中）';
                    statusEl.style.color = '#b45309';
                }
            }
            setInput('ai-api-base', ai.api_base);
            setInput('ai-timeout', ai.timeout);
            setInput('ai-temperature', ai.temperature);
            setInput('ai-max-tokens', ai.max_tokens);
            setInput('ai-num-retries', ai.num_retries);

            // Provider + Model 下拉（无自动加载，等用户点 ↻）
            const pSel = document.getElementById('ai-provider');
            const mSel = document.getElementById('ai-model');
            if (ai.provider && [...pSel.options].some(o => o.value === ai.provider)) {
                pSel.value = ai.provider;
            } else {
                pSel.value = 'openai';  // 默认
            }
            if (ai.model) {
                mSel.innerHTML = `<option value="${esc(ai.model)}">${esc(ai.model)} (已保存)</option>`;
                mSel.value = ai.model;
            }

            // AI 分析
            const aiAnalysis = getValue('ai_analysis') || {};
            setToggle('ai-analysis-enabled-toggle', aiAnalysis.enabled);
            setSelect('ai-analysis-mode', aiAnalysis.mode);
            setInput('ai-analysis-language', aiAnalysis.language);
            setInput('ai-analysis-max-news', aiAnalysis.max_news_for_analysis);
            setCheckbox('ai-analysis-include-rss', aiAnalysis.include_rss);
            setCheckbox('ai-analysis-include-standalone', aiAnalysis.include_standalone);
            setCheckbox('ai-analysis-include-timeline', aiAnalysis.include_rank_timeline);

            // AI 翻译
            const aiTrans = getValue('ai_translation') || {};
            setToggle('ai-translation-enabled-toggle', aiTrans.enabled);
            setInput('ai-translation-language', aiTrans.language);
            const transScope = aiTrans.scope || {};
            setCheckbox('ai-translation-scope-hotlist', transScope.hotlist);
            setCheckbox('ai-translation-scope-rss', transScope.rss);
            setCheckbox('ai-translation-scope-standalone', transScope.standalone);

            // 报告
            const report = getValue('report') || {};
            setSelect('report-mode', report.mode);
            setSelect('report-display-mode', report.display_mode);
            setInput('report-rank-threshold', report.rank_threshold);
            setInput('report-max-news', report.max_news_per_keyword);
            setInput('report-max-news-per-source', report.max_news_per_source_per_keyword);
            setCheckbox('report-sort-position', report.sort_by_position_first);

            // 筛选
            const filter = getValue('filter') || {};
            setSelect('filter-method', filter.method);
            setCheckbox('filter-priority-sort', filter.priority_sort_enabled);

            // AI 筛选
            const aiFilter = getValue('ai_filter') || {};
            setInput('ai-filter-batch-size', aiFilter.batch_size);
            setInput('ai-filter-batch-interval', aiFilter.batch_interval);
            setInput('ai-filter-min-score', aiFilter.min_score);
            setInput('ai-filter-reclassify', aiFilter.reclassify_threshold);

            // 调度
            const schedule = getValue('schedule') || {};
            setToggle('schedule-enabled-toggle', schedule.enabled);
            setSelect('schedule-preset', schedule.preset);
            setSelect('schedule-crawl-interval', schedule.crawl_interval_hours || 3);

            // 显示
            const display = getValue('display') || {};
            renderDisplayRegions(display.regions || {});
            const standalone = display.standalone || {};
            const allPlatforms = (getValue('platforms.sources') || []).map(s => ({id: s.id, name: s.name}));
            const allRssFeeds = (getValue('rss.feeds') || []).map(f => ({id: f.id, name: f.name || f.id}));
            renderCheckboxGroup('standalone-platforms', allPlatforms, standalone.platforms || [], (v) => updateConfig('display.standalone.platforms', v));
            renderCheckboxGroup('standalone-rss', allRssFeeds, standalone.rss_feeds || [], (v) => updateConfig('display.standalone.rss_feeds', v));
            setInput('standalone-max-items', standalone.max_items);

            // 通知
            const notification = getValue('notification') || {};
            setCheckbox('notification-enabled', notification.enabled);
            renderNotificationChannels(notification.channels || {});

            // 存储
            const storage = getValue('storage') || {};
            setSelect('storage-backend', storage.backend);
            setInput('storage-data-dir', (storage.local || {}).data_dir);
            setInput('storage-local-retention', (storage.local || {}).retention_days);
            const formats = storage.formats || {};
            setCheckbox('storage-format-sqlite', formats.sqlite);
            setCheckbox('storage-format-txt', formats.txt);
            setCheckbox('storage-format-html', formats.html);

            // 爬虫
            const crawler = (getValue('advanced') || {}).crawler || {};
            setInput('crawler-interval', crawler.request_interval);
            setToggle('advanced-crawler-use_proxy-toggle', crawler.use_proxy);

            // RSS 代理
            const rssProxy = (getValue('advanced') || {}).rss || {};
            setToggle('advanced-rss-use_proxy-toggle', rssProxy.use_proxy);
            setInput('rss-proxy-url', rssProxy.proxy_url || '');

            // 基础
            const app = getValue('app') || {};
            setInput('app-timezone', app.timezone);
            setToggle('app-version-toggle', app.show_version_update);
            setToggle('advanced-debug-toggle', (getValue('advanced') || {}).debug);

            // 关键词
            renderGlobalFilters();
            renderWordGroups();

            // 标签
            renderTagsPanel();
        }

        // ═══════════════════════════════════════════════════════════
        // 标签配置面板渲染
        // ═══════════════════════════════════════════════════════════
        function renderTagsPanel() {
            const tags = getValue('tags') || { mode: 'auto', items: [] };
            setSelect('tags-mode', tags.mode);
            const autoInfo = document.getElementById('tags-auto-info');
            const manualEditor = document.getElementById('tags-manual-editor');
            if (tags.mode === 'manual') {
                autoInfo.style.display = 'none';
                manualEditor.style.display = 'block';
                renderManualTags(tags.items || []);
            } else {
                autoInfo.style.display = 'block';
                manualEditor.style.display = 'none';
                loadCurrentTags();
            }
        }

        async function loadCurrentTags() {
            const container = document.getElementById('tags-current-list');
            try {
                const res = await fetch('/api/tags');
                const data = await res.json();
                if (data.success && data.tags.length > 0) {
                    container.innerHTML = '<div style="display:flex; flex-wrap:wrap; gap:8px;">' +
                        data.tags.map((t, i) =>
                            `<div style="padding:8px 12px; background:#f5f5f7; border-radius:8px; border-left:3px solid #4f46e5;">
                                <strong>${esc(t.tag)}</strong>
                                <div style="font-size:12px; color:#666; margin-top:2px;">${esc(t.description || '')}</div>
                            </div>`
                        ).join('') + '</div>';
                } else {
                    container.innerHTML = '<div style="color:#999;">暂无标签，请先运行一次爬取</div>';
                }
            } catch (e) {
                container.innerHTML = '<div style="color:#999;">加载标签失败</div>';
            }
        }

        // 存储最近一次预览的AI推荐标签，用于转为手动配置时填充
        let _previewedTags = null;

        async function regenerateTagsPreview() {
            const btn = document.getElementById('btn-regenerate-tags');
            btn.disabled = true; btn.textContent = '生成中...';
            try {
                const res = await fetch('/api/tags/preview', { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}' });
                const data = await res.json();
                if (data.success) {
                    _previewedTags = data.tags || [];
                    const tagsHtml = data.tags.map((t, i) => `${i+1}. <strong>${esc(t.tag)}</strong>: ${esc(t.description || '')}`).join('<br>');
                    const container = document.getElementById('tags-current-list');
                    container.innerHTML = '<div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:12px; margin-bottom:12px;">' +
                        '<div style="font-weight:600; color:#166534; margin-bottom:8px;">AI 推荐标签预览（未保存）</div>' +
                        '<div style="font-size:13px; line-height:1.8;">' + tagsHtml + '</div>' +
                        '</div>';
                } else {
                    showToast(data.message || '生成失败', 'error');
                }
            } catch (e) {
                showToast('网络错误: ' + e.message, 'error');
            } finally {
                btn.disabled = false; btn.textContent = '重新生成推荐';
            }
        }

        function switchToManualTags() {
            const currentItems = [];
            // 优先使用最近一次预览的AI推荐标签
            if (_previewedTags && _previewedTags.length > 0) {
                _previewedTags.forEach(t => currentItems.push({ name: t.tag, description: t.description || '' }));
                updateConfig('tags.items', currentItems);
                updateConfig('tags.mode', 'manual');
                renderTagsPanel();
                showToast('已转为手动配置，请编辑标签后保存', 'success');
                return;
            }
            // 回退：从数据库读取当前标签
            fetch('/api/tags').then(r => r.json()).then(data => {
                if (data.success && data.tags.length > 0) {
                    data.tags.forEach(t => currentItems.push({ name: t.tag, description: t.description || '' }));
                }
                updateConfig('tags.items', currentItems);
                updateConfig('tags.mode', 'manual');
                renderTagsPanel();
                showToast('已转为手动配置，请编辑标签后保存', 'success');
            }).catch(() => {
                updateConfig('tags.mode', 'manual');
                renderTagsPanel();
                showToast('已转为手动配置', 'success');
            });
        }

        function switchToAutoTags() {
            if (!confirm('确定要恢复 AI 自动提取吗？当前手动配置的标签将被丢弃。')) return;
            _previewedTags = null;
            updateConfig('tags.mode', 'auto');
            updateConfig('tags.items', []);
            renderTagsPanel();
            showToast('已恢复 AI 自动提取', 'success');
        }

        function renderManualTags(items) {
            const container = document.getElementById('tags-manual-list');
            if (!items.length) {
                container.innerHTML = '<div style="color:#999; padding:12px; text-align:center;">暂无标签，请点击"添加标签"</div>';
                return;
            }
            container.innerHTML = items.map((item, idx) => `
                <div style="display:flex; gap:8px; align-items:flex-start; margin-bottom:8px; padding:10px; background:#f9f9fb; border-radius:8px;">
                    <div style="font-weight:600; color:#4f46e5; min-width:24px; padding-top:6px;">${idx + 1}</div>
                    <div style="flex:1; display:flex; flex-direction:column; gap:6px;">
                        <input type="text" value="${esc(item.name || '')}" placeholder="标签名称"
                            onchange="updateTagItem(${idx}, 'name', this.value)"
                            style="padding:6px 8px; border:1px solid #ddd; border-radius:6px;">
                        <textarea placeholder="标签描述（帮助 AI 准确分类）" rows="2"
                            onchange="updateTagItem(${idx}, 'description', this.value)"
                            style="padding:6px 8px; border:1px solid #ddd; border-radius:6px; resize:vertical;"
                        >${esc(item.description || '')}</textarea>
                    </div>
                    <div style="display:flex; flex-direction:column; gap:4px;">
                        <button class="btn btn-secondary btn-sm" onclick="moveTagItem(${idx}, -1)" ${idx === 0 ? 'disabled' : ''} title="上移">↑</button>
                        <button class="btn btn-secondary btn-sm" onclick="moveTagItem(${idx}, 1)" ${idx === items.length - 1 ? 'disabled' : ''} title="下移">↓</button>
                        <button class="btn btn-secondary btn-sm" onclick="removeTagItem(${idx})" title="删除">×</button>
                    </div>
                </div>
            `).join('');
        }

        function updateTagItem(idx, field, value) {
            const items = [...(getValue('tags.items') || [])];
            if (items[idx]) {
                items[idx][field] = value;
                updateConfig('tags.items', items);
                renderTagsPanel();
            }
        }

        function moveTagItem(idx, delta) {
            const items = [...(getValue('tags.items') || [])];
            const newIdx = idx + delta;
            if (newIdx >= 0 && newIdx < items.length) {
                [items[idx], items[newIdx]] = [items[newIdx], items[idx]];
                updateConfig('tags.items', items);
                renderTagsPanel();
            }
        }

        function removeTagItem(idx) {
            const items = [...(getValue('tags.items') || [])];
            items.splice(idx, 1);
            updateConfig('tags.items', items);
            renderTagsPanel();
        }

        function addManualTag() {
            const items = [...(getValue('tags.items') || [])];
            items.push({ name: '', description: '' });
            updateConfig('tags.items', items);
            renderTagsPanel();
        }

        // ═══════════════════════════════════════════════════════════
        // 辅助渲染函数
        // ═══════════════════════════════════════════════════════════
        function setInput(id, value) {
            const el = document.getElementById(id);
            if (el) el.value = value !== undefined && value !== null ? value : '';
        }
        function setSelect(id, value) {
            const el = document.getElementById(id);
            if (el) el.value = value || '';
        }
        function setCheckbox(id, checked) {
            const el = document.getElementById(id);
            if (el) el.checked = !!checked;
        }
        function setToggle(id, on) {
            const el = document.getElementById(id);
            if (el) el.classList.toggle('on', !!on);
        }

        // 平台列表
        function renderPlatforms(sources) {
            const container = document.getElementById('platforms-list');
            const allPlatforms = [
                {id:'toutiao',name:'今日头条'},{id:'baidu',name:'百度热搜'},
                {id:'wallstreetcn-hot',name:'华尔街见闻'},{id:'thepaper',name:'澎湃新闻'},
                {id:'bilibili-hot-search',name:'bilibili 热搜'},{id:'cls-hot',name:'财联社热门'},
                {id:'ifeng',name:'凤凰网'},{id:'tieba',name:'贴吧'},
                {id:'weibo',name:'微博'},{id:'douyin',name:'抖音'},{id:'zhihu',name:'知乎'}
            ];
            const enabledMap = {};
            (sources || []).forEach(s => enabledMap[s.id] = s.enabled !== false);
            container.innerHTML = allPlatforms.map(p => {
                const checked = enabledMap[p.id] !== false ? 'checked' : '';
                const disabledClass = enabledMap[p.id] === false ? 'disabled' : '';
                return `<label class="platform-card ${disabledClass}">
                    <input type="checkbox" ${checked} onchange="togglePlatform('${p.id}', this.checked)">
                    <span>${p.name}</span>
                </label>`;
            }).join('');
        }
        function togglePlatform(id, enabled) {
            const sources = getValue('platforms.sources') || [];
            const idx = sources.findIndex(s => s.id === id);
            if (idx >= 0) {
                sources[idx].enabled = enabled;
            } else {
                const all = [{id:'toutiao',name:'今日头条'},{id:'baidu',name:'百度热搜'},{id:'wallstreetcn-hot',name:'华尔街见闻'},{id:'thepaper',name:'澎湃新闻'},{id:'bilibili-hot-search',name:'bilibili 热搜'},{id:'cls-hot',name:'财联社热门'},{id:'ifeng',name:'凤凰网'},{id:'tieba',name:'贴吧'},{id:'weibo',name:'微博'},{id:'douyin',name:'抖音'},{id:'zhihu',name:'知乎'}];
                const p = all.find(x => x.id === id);
                if (p) sources.push({id: p.id, name: p.name, enabled});
            }
            updateConfig('platforms.sources', sources);
            renderPlatforms(sources);
        }

        // RSS 列表
        function renderRssFeeds(feeds) {
            const tbody = document.getElementById('rss-feeds-list');
            if (!feeds || feeds.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">暂无 RSS 源，点击下方按钮添加</td></tr>';
                return;
            }
            tbody.innerHTML = feeds.map((f, i) => `
                <tr>
                    <td><input type="text" value="${esc(f.id||'')}" onchange="updateRssFeed(${i}, 'id', this.value)" placeholder="ID"></td>
                    <td><input type="text" value="${esc(f.name||'')}" onchange="updateRssFeed(${i}, 'name', this.value)" placeholder="名称"></td>
                    <td><input type="url" value="${esc(f.url||'')}" onchange="updateRssFeed(${i}, 'url', this.value)" placeholder="URL"></td>
                    <td><input type="checkbox" ${f.enabled!==false?'checked':''} onchange="updateRssFeed(${i}, 'enabled', this.checked)"></td>
                    <td>
                        <button class="btn btn-sm btn-secondary" id="rss-test-btn-${i}" onclick="testRssConnectivity(${i})">联通测试</button>
                        <span id="rss-test-status-${i}" class="rss-test-status"></span>
                    </td>
                    <td><button class="btn btn-danger btn-icon" onclick="removeRssFeed(${i})">✕</button></td>
                </tr>
            `).join('');
        }
        function updateRssFeed(index, field, value) {
            const feeds = [...(getValue('rss.feeds') || [])];
            if (feeds[index]) {
                feeds[index][field] = value;
                updateConfig('rss.feeds', feeds);
            }
        }
        function addRssFeed() {
            const feeds = [...(getValue('rss.feeds') || [])];
            feeds.push({id: '', name: '', url: '', enabled: true});
            updateConfig('rss.feeds', feeds);
            renderRssFeeds(feeds);
        }
        function removeRssFeed(index) {
            const feeds = [...(getValue('rss.feeds') || [])];
            feeds.splice(index, 1);
            updateConfig('rss.feeds', feeds);
            renderRssFeeds(feeds);
        }

        async function testRssConnectivity(index) {
            const feeds = getValue('rss.feeds') || [];
            const feed = feeds[index];
            if (!feed || !feed.url) {
                showToast('RSS URL 为空', 'error');
                return;
            }
            const btn = document.getElementById('rss-test-btn-' + index);
            const statusEl = document.getElementById('rss-test-status-' + index);
            btn.disabled = true;
            statusEl.textContent = '测试中...';
            statusEl.className = 'rss-test-status testing';
            const advanced = (getValue('advanced') || {}).rss || {};
            try {
                const res = await fetch('/api/rss/test', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        url: feed.url,
                        use_proxy: advanced.use_proxy,
                        proxy_url: advanced.proxy_url || '',
                        timeout: advanced.timeout || 15,
                    })
                });
                const data = await res.json();
                if (data.success) {
                    statusEl.textContent = '✅ ' + data.message;
                    statusEl.className = 'rss-test-status success';
                } else {
                    statusEl.textContent = '❌ ' + data.message;
                    statusEl.className = 'rss-test-status error';
                }
            } catch (e) {
                statusEl.textContent = '❌ 网络错误';
                statusEl.className = 'rss-test-status error';
            } finally {
                btn.disabled = false;
            }
        }

        async function testAiConnection() {
            const provider = document.getElementById('ai-provider').value;
            const model = document.getElementById('ai-model').value;
            const apiKey = document.getElementById('ai-api-key').value.trim();
            const apiBase = document.getElementById('ai-api-base').value.trim();

            if (!provider) { showToast('请先选择 Provider', 'error'); return; }
            if (!model) { showToast('请先选择模型（点 ↻ 拉取）', 'error'); return; }

            const btn = document.getElementById('ai-test-btn');
            const statusEl = document.getElementById('ai-test-status');
            btn.disabled = true;
            statusEl.textContent = '测试中...';
            statusEl.className = 'rss-test-status testing';

            try {
                const res = await fetch('/api/ai/test', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({provider, model, api_key: apiKey, api_base: apiBase})
                });
                const data = await res.json();
                if (data.success) {
                    const ms = data.latency_ms != null ? `（${data.latency_ms}ms）` : '';
                    statusEl.textContent = '✅ 连接成功 ' + ms;
                    statusEl.className = 'rss-test-status success';
                } else {
                    statusEl.textContent = '❌ ' + (data.message || '测试失败');
                    statusEl.className = 'rss-test-status error';
                }
            } catch (e) {
                statusEl.textContent = '❌ 网络错误';
                statusEl.className = 'rss-test-status error';
            } finally {
                btn.disabled = false;
            }
        }

        // === AI 模型下拉相关 ===

        async function refreshAiModels() {
            const provider = document.getElementById('ai-provider').value;
            const apiKey = document.getElementById('ai-api-key').value.trim();
            const apiBase = document.getElementById('ai-api-base').value.trim();
            if (!provider) { showToast('请先选择 Provider', 'error'); return; }

            const btn = document.getElementById('ai-model-refresh');
            const sel = document.getElementById('ai-model');
            const prevValue = sel.value;
            btn.disabled = true;
            sel.innerHTML = '<option value="">拉取中...</option>';

            try {
                const res = await fetch('/api/ai/models', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({provider, api_key: apiKey, api_base: apiBase})
                });
                const data = await res.json();
                if (data.success) {
                    const models = (data.models || []).slice();
                    // 已保存的 model 若不在列表里，添加为 (已保存) 项
                    if (prevValue && !models.includes(prevValue)) {
                        models.unshift(prevValue);
                    }
                    renderModelOptions(models, prevValue);
                    if (data.provider_error) {
                        showToast('⚠ ' + data.provider_error, 'error');
                    } else if (apiBase) {
                        const added = (data.provider_count || 0);
                        const suffix = added > 0 ? `（+${added} 来自 provider）` : '';
                        showToast(`已加载 ${models.length} 个模型${suffix}`, 'success');
                    } else {
                        showToast(`LiteLLM catalog: ${models.length} 个模型`, 'info');
                    }
                } else {
                    sel.innerHTML = `<option value="${esc(prevValue)}">${esc(prevValue) || '加载失败'}</option>`;
                    showToast('❌ ' + (data.message || '加载失败'), 'error');
                }
            } catch (e) {
                sel.innerHTML = `<option value="${esc(prevValue)}">${esc(prevValue) || '加载失败'}</option>`;
                showToast('❌ 网络错误', 'error');
            } finally {
                btn.disabled = false;
            }
        }

        function renderModelOptions(models, restoreValue) {
            const sel = document.getElementById('ai-model');
            const opts = ['<option value="">-- 请选择 --</option>']
                .concat(models.map(m => `<option value="${esc(m)}">${esc(m)}</option>`));
            if (restoreValue && !models.includes(restoreValue)) {
                opts.splice(1, 0, `<option value="${esc(restoreValue)}">${esc(restoreValue)} (自定义)</option>`);
            }
            sel.innerHTML = opts.join('');
            if (restoreValue && [...sel.options].some(o => o.value === restoreValue)) {
                sel.value = restoreValue;
            }
        }

        // 显示区域
        function renderDisplayRegions(regions) {
            const container = document.getElementById('display-regions-list');
            const items = [
                {key:'hotlist', label:'热榜区域', desc:'关键词匹配 / AI 智能筛选'},
                {key:'new_items', label:'新增热点', desc:'热榜新增 + RSS 新增'},
                {key:'rss', label:'RSS 订阅', desc:'RSS 关键词分析'},
                {key:'standalone', label:'独立展示区', desc:'完整热榜/RSS，不受关键词过滤'},
                {key:'ai_analysis', label:'AI 分析', desc:'AI 深度分析'},
            ];
            container.innerHTML = items.map(item => `
                <div class="switch-row">
                    <div>
                        <div class="switch-label">${item.label}</div>
                        <div class="switch-desc">${item.desc}</div>
                    </div>
                    <div class="toggle-switch ${regions[item.key]?'on':''}" onclick="toggleRegion('${item.key}')"></div>
                </div>
            `).join('');
        }
        function toggleRegion(key) {
            const regions = {...(getValue('display.regions') || {})};
            regions[key] = !regions[key];
            updateConfig('display.regions', regions);
            renderDisplayRegions(regions);
        }

        // 通知渠道
        function renderNotificationChannels(channels) {
            const container = document.getElementById('notification-channels');
            const defs = [
                {key:'feishu', label:'飞书', fields:['webhook_url']},
                {key:'dingtalk', label:'钉钉', fields:['webhook_url']},
                {key:'wework', label:'企业微信', fields:['webhook_url','msg_type']},
                {key:'telegram', label:'Telegram', fields:['bot_token','chat_id']},
                {key:'email', label:'邮件', fields:['from','password','to','smtp_server','smtp_port']},
                {key:'ntfy', label:'ntfy', fields:['server_url','topic','token']},
                {key:'bark', label:'Bark', fields:['url']},
                {key:'slack', label:'Slack', fields:['webhook_url']},
                {key:'generic_webhook', label:'通用 Webhook', fields:['webhook_url','payload_template']},
            ];
            container.innerHTML = defs.map(ch => {
                const cfg = channels[ch.key] || {};
                const fieldsHtml = ch.fields.map(f => {
                    const labelMap = {
                        webhook_url:'Webhook URL', bot_token:'Bot Token', chat_id:'Chat ID',
                        from:'发件人', password:'密码/授权码', to:'收件人',
                        smtp_server:'SMTP 服务器', smtp_port:'SMTP 端口',
                        server_url:'服务器地址', topic:'主题', token:'令牌',
                        url:'URL', payload_template:'Payload 模板', msg_type:'消息类型'
                    };
                    const val = cfg[f] !== undefined ? cfg[f] : '';
                    const type = f.includes('password') || f.includes('token') && f !== 'bot_token' ? 'password' : 'text';
                    return `<div class="form-group" style="margin-bottom:8px;">
                        <label class="form-label" style="font-size:12px; margin-bottom:4px;">${labelMap[f] || f}</label>
                        <input type="${type}" value="${esc(val)}" onchange="updateNotificationChannel('${ch.key}', '${f}', this.value)" placeholder="${labelMap[f] || f}">
                    </div>`;
                }).join('');
                return `<div class="section" style="padding:16px; margin-bottom:12px;">
                    <div style="font-weight:600; font-size:14px; margin-bottom:10px;">${ch.label}</div>
                    <div class="form-row">${fieldsHtml}</div>
                </div>`;
            }).join('');
        }
        function updateNotificationChannel(channel, field, value) {
            const channels = {...(getValue('notification.channels') || {})};
            if (!channels[channel]) channels[channel] = {};
            channels[channel][field] = value;
            updateConfig('notification.channels', channels);
        }

        // Checkbox Group (for standalone display source selection)
        function renderCheckboxGroup(id, availableOptions, selectedValues, onChange) {
            const container = document.getElementById(id);
            if (!container) return;
            const selectedSet = new Set(selectedValues || []);
            if (!availableOptions || availableOptions.length === 0) {
                container.innerHTML = '<div class="checkbox-group-empty">无可用选项</div>';
                return;
            }
            container.innerHTML = availableOptions.map(opt => `
                <div class="checkbox-group-item">
                    <input type="checkbox" id="${id}-${opt.id}"
                        ${selectedSet.has(opt.id) ? 'checked' : ''}
                        onchange="handleCheckboxGroupChange('${id}', '${opt.id}', this.checked)">
                    <label for="${id}-${opt.id}">${esc(opt.name || opt.id)}</label>
                </div>
            `).join('');
            container._onChange = onChange;
        }
        function handleCheckboxGroupChange(id, optionId, checked) {
            const container = document.getElementById(id);
            if (!container) return;
            const checkboxes = container.querySelectorAll('input[type="checkbox"]');
            const selectedValues = [];
            checkboxes.forEach(cb => {
                if (cb.checked) {
                    const cbId = cb.id.replace(id + '-', '');
                    selectedValues.push(cbId);
                }
            });
            if (container._onChange) container._onChange(selectedValues);
        }

        // 全局过滤词
        function renderGlobalFilters() {
            const container = document.getElementById('global-filters');
            const items = frequencyWords.global_filters || [];
            if (items.length === 0) {
                container.innerHTML = '<div class="empty-state">暂无全局过滤词</div>';
                return;
            }
            container.innerHTML = items.map((kw, i) => `
                <div class="keyword-row">
                    <select onchange="updateGlobalFilter(${i}, 'type', this.value)">
                        <option value="normal" ${kw.type==='normal'?'selected':''}>普通</option>
                        <option value="regex" ${kw.type==='regex'?'selected':''}>正则</option>
                    </select>
                    <input type="text" value="${esc(kw.content||'')}" onchange="updateGlobalFilter(${i}, 'content', this.value)">
                    <input type="text" value="${esc(kw.alias||'')}" placeholder="别名（可选）" onchange="updateGlobalFilter(${i}, 'alias', this.value)">
                    <button class="btn btn-danger btn-icon" onclick="removeGlobalFilter(${i})">✕</button>
                </div>
            `).join('');
        }
        function updateGlobalFilter(index, field, value) {
            const items = [...frequencyWords.global_filters];
            if (items[index]) { items[index][field] = value; frequencyWords.global_filters = items; }
        }
        function addGlobalFilter() {
            const input = document.getElementById('new-global-filter');
            const val = input.value.trim();
            if (!val) return;
            frequencyWords.global_filters = [...frequencyWords.global_filters, {type:'normal', content:val, alias:null}];
            input.value = '';
            renderGlobalFilters();
        }
        function removeGlobalFilter(index) {
            const items = [...frequencyWords.global_filters];
            items.splice(index, 1);
            frequencyWords.global_filters = items;
            renderGlobalFilters();
        }

        // 词组
        function renderWordGroups() {
            const container = document.getElementById('word-groups');
            const groups = frequencyWords.word_groups || [];
            if (groups.length === 0) {
                container.innerHTML = '<div class="empty-state">暂无关键词组</div>';
                return;
            }
            container.innerHTML = groups.map((g, gi) => `
                <div class="word-group">
                    <div class="word-group-header">
                        <input type="text" value="${esc(g.name||'')}" placeholder="词组名称（可选）" onchange="updateWordGroup(${gi}, 'name', this.value)">
                        <input type="number" value="${g.max_count||0}" min="0" placeholder="最大条数" style="width:100px;" onchange="updateWordGroup(${gi}, 'max_count', parseInt(this.value)||0)">
                        <button class="btn btn-danger btn-icon" onclick="removeWordGroup(${gi})">✕</button>
                    </div>
                    <div style="margin-bottom:8px;">
                        ${(g.keywords||[]).map((kw, ki) => `
                            <div class="keyword-row">
                                <select onchange="updateWordGroupKeyword(${gi}, ${ki}, 'type', this.value)">
                                    <option value="normal" ${kw.type==='normal'?'selected':''}>普通</option>
                                    <option value="regex" ${kw.type==='regex'?'selected':''}>正则</option>
                                    <option value="required" ${kw.type==='required'?'selected':''}>必须</option>
                                    <option value="filter" ${kw.type==='filter'?'selected':''}>过滤</option>
                                </select>
                                <input type="text" value="${esc(kw.content||'')}" placeholder="关键词" onchange="updateWordGroupKeyword(${gi}, ${ki}, 'content', this.value)">
                                <input type="text" value="${esc(kw.alias||'')}" placeholder="别名" onchange="updateWordGroupKeyword(${gi}, ${ki}, 'alias', this.value)">
                                <button class="btn btn-danger btn-icon" onclick="removeWordGroupKeyword(${gi}, ${ki})">✕</button>
                            </div>
                        `).join('')}
                    </div>
                    <button class="btn btn-secondary btn-sm" onclick="addWordGroupKeyword(${gi})">+ 添加关键词</button>
                </div>
            `).join('');
        }
        function updateWordGroup(gi, field, value) {
            const groups = [...frequencyWords.word_groups];
            if (groups[gi]) groups[gi][field] = value;
            frequencyWords.word_groups = groups;
        }
        function removeWordGroup(gi) {
            const groups = [...frequencyWords.word_groups];
            groups.splice(gi, 1);
            frequencyWords.word_groups = groups;
            renderWordGroups();
        }
        function addWordGroup() {
            frequencyWords.word_groups = [...frequencyWords.word_groups, {name:'', max_count:0, keywords:[]}];
            renderWordGroups();
        }
        function updateWordGroupKeyword(gi, ki, field, value) {
            const groups = [...frequencyWords.word_groups];
            if (groups[gi] && groups[gi].keywords[ki]) groups[gi].keywords[ki][field] = value;
            frequencyWords.word_groups = groups;
        }
        function removeWordGroupKeyword(gi, ki) {
            const groups = [...frequencyWords.word_groups];
            if (groups[gi]) {
                groups[gi].keywords.splice(ki, 1);
                frequencyWords.word_groups = groups;
                renderWordGroups();
            }
        }
        function addWordGroupKeyword(gi) {
            const groups = [...frequencyWords.word_groups];
            if (groups[gi]) {
                groups[gi].keywords = [...groups[gi].keywords, {type:'normal', content:'', alias:null}];
                frequencyWords.word_groups = groups;
                renderWordGroups();
            }
        }

        // ═══════════════════════════════════════════════════════════
        // 配置更新
        // ═══════════════════════════════════════════════════════════
        function updateConfig(path, value) {
            setValue(path, value);
        }
        function toggleSwitch(path) {
            const current = !!getValue(path);
            setValue(path, !current);
            // 重新渲染对应 toggle
            const id = path.replace(/\\./g, '-') + '-toggle';
            setToggle(id, !current);
        }

        // ═══════════════════════════════════════════════════════════
        // 保存配置
        // ═══════════════════════════════════════════════════════════
        async function saveConfig() {
            if (isSaving) return;
            isSaving = true;
            const btn = document.getElementById('btn-save');
            btn.disabled = true; btn.innerHTML = '<span>保存中...</span>';
            document.querySelector('.validation-errors')?.classList.remove('show');

            try {
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({config, frequency_words: frequencyWords})
                });
                const data = await res.json();
                if (data.success) {
                    let msg = '配置保存成功';
                    if (data.triggered) {
                        if (data.triggered.success) {
                            msg += '，正在重新爬取...';
                            pollStatus();
                        } else {
                            msg += '（爬取触发失败: ' + data.triggered.message + '）';
                        }
                    }
                    showToast(msg, 'success');
                } else {
                    showToast('保存失败: ' + (data.message || '未知错误'), 'error');
                    if (data.errors && data.errors.length) {
                        showValidationErrors(data.errors);
                    }
                }
            } catch (e) {
                showToast('网络错误: ' + e.message, 'error');
            } finally {
                isSaving = false;
                btn.disabled = false; btn.innerHTML = '<span>保存配置</span>';
            }
        }

        function showValidationErrors(errors) {
            // 简单 toast 展示错误
            const messages = errors.slice(0, 3).map(e => `${e.section || ''}${e.field ? '.' + e.field : ''}: ${e.message}`);
            showToast('验证错误: ' + messages.join('; '), 'error');
        }

        // ═══════════════════════════════════════════════════════════
        // 触发爬取
        // ═══════════════════════════════════════════════════════════
        async function triggerCrawl() {
            if (isTriggering) return;
            isTriggering = true;
            const btn = document.getElementById('btn-trigger');
            btn.disabled = true; btn.innerHTML = '<span>启动中...</span>';
            try {
                const res = await fetch('/api/trigger', {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    showToast('爬取任务已启动', 'success');
                    pollStatus();
                } else {
                    showToast(data.message || '启动失败', 'error');
                }
            } catch (e) {
                showToast('网络错误: ' + e.message, 'error');
            } finally {
                isTriggering = false;
                btn.disabled = false; btn.innerHTML = '<span>立即爬取</span>';
            }
        }

        async function regenerateReport() {
            const statusEl = document.getElementById('regenerate-status');
            const btn = document.getElementById('btn-regenerate-report');
            if (btn) btn.disabled = true;
            statusEl.textContent = '保存配置中...';

            try {
                const saveRes = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({config, frequency_words: frequencyWords})
                });
                const saveData = await saveRes.json();
                if (!saveData.success) {
                    statusEl.textContent = '❌ 配置保存失败';
                    showToast('配置保存失败: ' + (saveData.message || '未知错误'), 'error');
                    if (btn) btn.disabled = false;
                    return;
                }

                statusEl.textContent = '生成报告中...';
                const res = await fetch('/api/regenerate-report', {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    statusEl.textContent = '✅ 已生成';
                    showToast('报告已重新生成', 'success');
                    setTimeout(() => { statusEl.textContent = ''; }, 3000);
                } else {
                    statusEl.textContent = '❌ ' + (data.message || '失败');
                    showToast(data.message || '生成失败', 'error');
                }
            } catch (e) {
                statusEl.textContent = '❌ 网络错误';
                showToast('网络错误: ' + e.message, 'error');
            } finally {
                if (btn) btn.disabled = false;
            }
        }

        // ═══════════════════════════════════════════════════════════
        // 轮询状态
        // ═══════════════════════════════════════════════════════════
        async function pollStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                const dot = document.getElementById('status-dot');
                const text = document.getElementById('status-text');
                const lastRun = document.getElementById('last-run');
                if (data.status === 'running') {
                    dot.className = 'status-dot running';
                    text.textContent = '爬取中...';
                } else if (data.last_result === 'failed') {
                    dot.className = 'status-dot error';
                    text.textContent = '上次失败';
                } else {
                    dot.className = 'status-dot';
                    text.textContent = '就绪';
                }
                lastRun.textContent = data.last_run ? '上次爬取: ' + data.last_run : '上次爬取: --';
            } catch (e) {
                document.getElementById('status-text').textContent = '状态未知';
            }
        }

        // ═══════════════════════════════════════════════════════════
        // 工具函数
        // ═══════════════════════════════════════════════════════════
        function esc(str) {
            if (str == null) return '';
            return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        }
        function showToast(message, type, duration) {
            // 默认 3 秒后自动消失（duration 可由调用方覆盖）。
            // 关键：toast 位于 top:20px right:20px，会挡住"返回报告"按钮，
            // 必须保证 3 秒后彻底不再拦截鼠标/视觉残留。
            const toast = document.getElementById('toast');
            if (!toast) return;
            toast.textContent = message;
            toast.className = 'toast ' + type;
            // 强制重排，确报连续触发时动画能播
            void toast.offsetWidth;
            requestAnimationFrame(() => toast.classList.add('show'));

            // 清理之前未完成的 timer，避免快速连发时 timer 串掉
            if (showToast._timer) clearTimeout(showToast._timer);
            const ms = (typeof duration === 'number' && duration > 0) ? duration : 3000;
            showToast._timer = setTimeout(() => {
                toast.classList.remove('show');
                // 兜底：CSS transition 0.3s 后即便 .show 残留，opacity 也归 0 + 不可点击
                setTimeout(() => {
                    if (!toast.classList.contains('show')) {
                        toast.style.opacity = '0';
                        toast.style.pointerEvents = 'none';
                    }
                }, 350);
            }, ms);
        }

        // 点击 toast 立即关闭（应急逃生口）
        document.getElementById('toast')?.addEventListener('click', () => {
            const toast = document.getElementById('toast');
            if (!toast) return;
            toast.classList.remove('show');
            toast.style.opacity = '0';
            toast.style.pointerEvents = 'none';
            if (showToast._timer) clearTimeout(showToast._timer);
        });

        // 快捷键
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                saveConfig();
            }
        });
    </script>
</body>
</html>"""
