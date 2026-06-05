# coding=utf-8
"""
TrendRadar WebUI HTTP 服务器

基于 Python 标准库 http.server，提供：
- 静态文件服务（/app/output 目录）
- 配置管理页面（/config.html）
- REST API（/api/*）

使用方法：
    python -m trendradar.webui.server [port] [document_root]

默认端口 8080，默认文档根目录 /app/output。
"""

import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

from trendradar.webui.config_page import render_config_page
from trendradar.webui.config_schema import (
    load_structured_config,
    save_structured_config,
    load_structured_frequency_words,
    save_structured_frequency_words,
    get_default_config,
)
from trendradar.webui.validator import validate_structured_config, validate_structured_frequency_words

# === 配置 ===
DEFAULT_PORT = int(os.environ.get("WEBSERVER_PORT", "8080"))
DEFAULT_DOC_ROOT = "/app/output"
CONFIG_DIR = "/app/config"
STATUS_FILE = "/tmp/trendradar_webui_status.json"
TRIGGER_LOCK = threading.Lock()

# 配置文件的绝对路径
CONFIG_YAML_PATH = Path(CONFIG_DIR) / "config.yaml"
FREQUENCY_WORDS_PATH = Path(CONFIG_DIR) / "frequency_words.txt"


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """支持多线程并发的 HTTP 服务器"""
    daemon_threads = True
    allow_reuse_address = True


class WebUIHandler(SimpleHTTPRequestHandler):
    """自定义 HTTP 请求处理器"""

    def __init__(self, *args, document_root: str = DEFAULT_DOC_ROOT, **kwargs):
        self.document_root = document_root
        super().__init__(*args, directory=document_root, **kwargs)

    def log_message(self, format, *args):
        """重写日志输出，与 TrendRadar 风格一致"""
        print(f"[WebUI] {self.address_string()} - {format % args}")

    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/config.html":
            self._serve_config_page()
        elif path == "/api/config":
            self._api_get_config()
        elif path == "/api/tags":
            self._api_get_tags()
        elif path == "/api/status":
            self._api_get_status()
        else:
            super().do_GET()

    def do_POST(self):
        """处理 POST 请求"""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/config":
            self._api_post_config()
        elif path == "/api/tags/preview":
            self._api_post_tags_preview()
        elif path == "/api/trigger":
            self._api_trigger_crawl()
        elif path == "/api/regenerate-report":
            self._api_regenerate_report()
        elif path == "/api/rss/test":
            self._api_post_rss_test()
        elif path == "/api/ai/test":
            self._api_post_ai_test()
        elif path == "/api/ai/models":
            self._api_post_ai_models()
        elif path == "/api/ai/providers":
            self._api_post_ai_providers()
        else:
            self._send_json(404, {"success": False, "message": "Not found"})

    def _serve_config_page(self):
        """返回配置管理页面"""
        html = render_config_page()
        self._send_html(200, html)

    def _api_get_config(self):
        """API：读取当前结构化配置"""
        try:
            config = load_structured_config(CONFIG_YAML_PATH)
            frequency_words = load_structured_frequency_words(FREQUENCY_WORDS_PATH)

            self._send_json(200, {
                "success": True,
                "config": config,
                "frequency_words": frequency_words,
            })
        except Exception as e:
            self._send_json(500, {"success": False, "message": f"读取配置失败: {e}"})

    def _api_post_config(self):
        """API：保存结构化配置"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 5 * 1024 * 1024:
                self._send_json(413, {"success": False, "message": "请求体过大（最大 5MB）"})
                return

            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            config = data.get("config")
            frequency_words = data.get("frequency_words")

            # 验证
            errors = []
            if config is not None:
                config_errors = validate_structured_config(config)
                for err in config_errors:
                    errors.append({
                        "section": err.get("section", ""),
                        "field": err.get("field", ""),
                        "message": err.get("message", ""),
                    })

            if frequency_words is not None:
                words_errors = validate_structured_frequency_words(frequency_words)
                for err in words_errors:
                    errors.append({
                        "section": "frequency_words",
                        "field": err.get("field", ""),
                        "message": err.get("message", ""),
                    })

            if errors:
                self._send_json(400, {"success": False, "message": "验证失败", "errors": errors})
                return

            # 保存前读取旧配置，用于对比 tags 是否变化
            old_config = load_structured_config(CONFIG_YAML_PATH) if config is not None else {}

            # 写入文件（带锁）
            if config is not None:
                # 强制把 ai.api_key 还原为占位符，真实 key 必须走 AI_API_KEY 环境变量
                # （避免 WebUI 表单误把真实 key 写进 config.yaml 后被 git 提交）
                ai_section = config.get("ai") if isinstance(config, dict) else None
                if isinstance(ai_section, dict):
                    submitted_key = (ai_section.get("api_key") or "").strip()
                    if submitted_key and submitted_key != "YOUR_API_KEY_HERE":
                        ai_section["api_key"] = "YOUR_API_KEY_HERE"
                save_structured_config(CONFIG_YAML_PATH, config)
            if frequency_words is not None:
                save_structured_frequency_words(FREQUENCY_WORDS_PATH, frequency_words)

            # 检查 tags 是否变化，若变化则自动触发爬取
            trigger_result = None
            if config is not None:
                old_tags = old_config.get("tags", {})
                new_tags = config.get("tags", {})
                tags_changed = (
                    old_tags.get("mode") != new_tags.get("mode")
                    or old_tags.get("items") != new_tags.get("items")
                )
                if tags_changed:
                    trigger_result = self._trigger_crawl()

            response = {"success": True, "message": "配置保存成功"}
            if trigger_result:
                response["triggered"] = trigger_result

            self._send_json(200, response)
        except json.JSONDecodeError as e:
            self._send_json(400, {"success": False, "message": f"JSON 解析错误: {e}"})
        except Exception as e:
            self._send_json(500, {"success": False, "message": f"保存失败: {e}"})

    def _trigger_crawl(self) -> dict:
        """触发爬取（内部方法，返回结果字典）"""
        with TRIGGER_LOCK:
            status = self._read_status()
            if status.get("status") == "running":
                return {"success": False, "message": "爬取任务正在运行中"}

            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "trendradar"],
                    cwd="/app",
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

                self._write_status({
                    "status": "running",
                    "pid": process.pid,
                    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

                monitor = threading.Thread(target=self._monitor_crawl, args=(process,), daemon=True)
                monitor.start()

                return {"success": True, "pid": process.pid, "message": "爬取任务已启动"}
            except Exception as e:
                return {"success": False, "message": f"启动失败: {e}"}

    def _api_trigger_crawl(self):
        """API：触发立即爬取"""
        result = self._trigger_crawl()
        code = 200 if result.get("success") else 409 if "运行中" in result.get("message", "") else 500
        self._send_json(code, result)

    def _api_regenerate_report(self):
        """API：重新生成 HTML 报告（使用已存储的数据和当前配置）"""
        try:
            from trendradar.core import load_config
            from trendradar.context import AppContext
            from trendradar.storage import StorageManager

            # 加载配置
            config = load_config()
            ctx = AppContext(config)
            sm = ctx.get_storage_manager()

            # 获取已存储的数据
            all_results, id_to_name, title_info = ctx.read_today_titles(quiet=True)
            if not all_results:
                self._send_json(400, {"success": False, "message": "没有可用的数据，请先爬取"})
                return

            # 用当前配置中的名称覆盖数据库中的旧名称
            for p in ctx.platforms:
                pid = p.get("id")
                pname = p.get("name")
                if pid and pname:
                    id_to_name[pid] = pname

            # 根据筛选策略计算统计信息
            new_titles = ctx.detect_new_titles(ctx.platform_ids, quiet=True)

            if ctx.filter_method == "ai":
                # === AI 筛选策略 ===
                print("[重新生成报告] 使用 AI 智能筛选策略")
                ai_filter_result = ctx.run_ai_filter()

                if ai_filter_result and ai_filter_result.success:
                    print(f"[重新生成报告] AI 筛选完成: {ai_filter_result.total_matched} 条匹配, {len(ai_filter_result.tags)} 个标签")
                    stats, rss_items = ctx.convert_ai_filter_to_report_data(
                        ai_filter_result, mode="current", new_titles=new_titles,
                    )
                    total_titles = sum(len(titles) for titles in all_results.values())

                    # 更新 AI 筛选结果中的 source_name 为当前配置
                    feed_name_map = {f.get("id"): f.get("name") for f in ctx.rss_feeds if f.get("id") and f.get("name")}
                    for stat_list in [stats, rss_items]:
                        if stat_list:
                            for stat in stat_list:
                                for title_entry in stat.get("titles", []):
                                    sid = title_entry.get("source_id", "")
                                    if sid in id_to_name:
                                        title_entry["source_name"] = id_to_name[sid]
                                    elif sid in feed_name_map:
                                        title_entry["source_name"] = feed_name_map[sid]

                    # AI 筛选热榜无匹配时，兜底回退到关键词匹配
                    if not stats and all_results:
                        print("[重新生成报告] AI 筛选热榜无匹配，兜底回退到关键词匹配")
                        word_groups, filter_words, global_filters = ctx.load_frequency_words()
                        stats, total_titles = ctx.count_frequency(
                            all_results, word_groups, filter_words,
                            id_to_name, title_info, new_titles,
                            mode="current", global_filters=global_filters, quiet=True
                        )
                        # 回退时也用关键词方式处理 RSS
                        rss_data = sm.get_latest_rss_data()
                        if rss_data:
                            for feed in ctx.rss_feeds:
                                fid = feed.get("id")
                                fname = feed.get("name")
                                if fid and fname:
                                    rss_data.id_to_name[fid] = fname
                                    id_to_name[fid] = fname
                        rss_items = self._build_rss_items(ctx, sm, rss_data, word_groups, filter_words, global_filters)
                    else:
                        # AI 筛选成功或有结果时，也需要获取 rss_data 用于独立展示区
                        rss_data = sm.get_latest_rss_data()
                        if rss_data:
                            for feed in ctx.rss_feeds:
                                fid = feed.get("id")
                                fname = feed.get("name")
                                if fid and fname:
                                    rss_data.id_to_name[fid] = fname
                                    id_to_name[fid] = fname
                        # AI 模式也需要加载频率词配置，用于 RSS 新增检测
                        word_groups, filter_words, global_filters = ctx.load_frequency_words()
                else:
                    error_msg = ai_filter_result.error if ai_filter_result else "未知错误"
                    print(f"[重新生成报告] AI 筛选失败: {error_msg}，回退到关键词匹配")
                    word_groups, filter_words, global_filters = ctx.load_frequency_words()
                    stats, total_titles = ctx.count_frequency(
                        all_results, word_groups, filter_words,
                        id_to_name, title_info, new_titles,
                        mode="current", global_filters=global_filters, quiet=True
                    )
                    rss_data = sm.get_latest_rss_data()
                    if rss_data:
                        for feed in ctx.rss_feeds:
                            fid = feed.get("id")
                            fname = feed.get("name")
                            if fid and fname:
                                rss_data.id_to_name[fid] = fname
                                id_to_name[fid] = fname
                    rss_items = self._build_rss_items(ctx, sm, rss_data, word_groups, filter_words, global_filters)
            else:
                # === 关键词匹配策略 ===
                word_groups, filter_words, global_filters = ctx.load_frequency_words()
                stats, total_titles = ctx.count_frequency(
                    all_results, word_groups, filter_words,
                    id_to_name, title_info, new_titles,
                    mode="current", global_filters=global_filters, quiet=True
                )

                # 获取 RSS 数据（关键词模式）
                rss_data = sm.get_latest_rss_data()
                if rss_data:
                    for feed in ctx.rss_feeds:
                        fid = feed.get("id")
                        fname = feed.get("name")
                        if fid and fname:
                            rss_data.id_to_name[fid] = fname
                            id_to_name[fid] = fname
                rss_items = self._build_rss_items(ctx, sm, rss_data, word_groups, filter_words, global_filters)

            # 准备独立展示区数据
            display_config = config.get("DISPLAY", {})
            standalone_config = display_config.get("STANDALONE", {})
            platform_ids = standalone_config.get("PLATFORMS", [])
            rss_feed_ids = standalone_config.get("RSS_FEEDS", [])
            max_items = standalone_config.get("MAX_ITEMS", 20)

            standalone_data = {"platforms": [], "rss_feeds": []}

            if platform_ids or rss_feed_ids:
                # 计算 latest_time
                latest_time = None
                if title_info:
                    for source_titles in title_info.values():
                        for title_data in source_titles.values():
                            last_time = title_data.get("last_time", "")
                            if last_time and (latest_time is None or last_time > latest_time):
                                latest_time = last_time

                # 提取热榜平台数据
                for platform_id in platform_ids:
                    if platform_id not in all_results:
                        continue
                    platform_name = id_to_name.get(platform_id, platform_id)
                    platform_titles = all_results[platform_id]
                    items = []
                    for title, title_data in platform_titles.items():
                        meta = title_info.get(platform_id, {}).get(title, {})
                        if latest_time and meta and meta.get("last_time") != latest_time:
                            continue
                        current_ranks = title_data.get("ranks", [])
                        current_rank = current_ranks[-1] if current_ranks else 0
                        items.append({
                            "title": title,
                            "url": title_data.get("url", ""),
                            "mobileUrl": title_data.get("mobileUrl", ""),
                            "rank": current_rank,
                            "ranks": current_ranks,
                        })
                    items.sort(key=lambda x: x["rank"] if x["rank"] > 0 else 9999)
                    if max_items > 0:
                        items = items[:max_items]
                    if items:
                        standalone_data["platforms"].append({
                            "id": platform_id,
                            "name": platform_name,
                            "items": items,
                        })

                # 提取 RSS 数据用于独立展示区
                if rss_feed_ids and rss_data:
                    for feed_id, items in rss_data.items.items():
                        if feed_id not in rss_feed_ids:
                            continue
                        feed_name = rss_data.id_to_name.get(feed_id, feed_id)
                        feed_items = []
                        for item in items[:max_items] if max_items > 0 else items:
                            display_title = getattr(item, "translated_title", "") or item.title
                            feed_items.append({
                                "title": display_title,
                                "url": item.url or "",
                                "published_at": item.published_at or "",
                                "author": getattr(item, "author", "") or "",
                            })
                        if feed_items:
                            standalone_data["rss_feeds"].append({
                                "id": feed_id,
                                "name": feed_name,
                                "items": feed_items,
                            })

            # 计算 RSS 新增项目（用于"RSS 新增更新"区块）
            # 注意：当 AI 筛选启用时，RSS 统计已通过 AI 标签分组，
            #       此处不再用关键词方式构建 rss_new_items，保持一致性
            rss_new_items = None
            if rss_data and ctx.filter_method != "ai":
                rss_new_items = self._build_rss_new_items(ctx, sm, rss_data, word_groups, filter_words, global_filters)

            # 运行 AI 分析（如果启用）
            ai_analysis_result = None
            ai_analysis_config = config.get("AI_ANALYSIS", {})
            if ai_analysis_config.get("ENABLED", False) and stats:
                print("[重新生成报告] 正在运行 AI 分析...")
                try:
                    from trendradar.ai.analyzer import AIAnalyzer
                    ai_config = config.get("AI", {})
                    analyzer = AIAnalyzer(ai_config, ai_analysis_config, ctx.get_time, debug=False)
                    platforms = list(id_to_name.values()) if id_to_name else []
                    keywords = [s.get("word", "") for s in stats if s.get("word")] if stats else []
                    ai_analysis_result = analyzer.analyze(
                        stats=stats,
                        rss_stats=rss_items,
                        report_mode="current",
                        report_type="当前榜单",
                        platforms=platforms,
                        keywords=keywords,
                        standalone_data=standalone_data if standalone_data else None,
                    )
                    if ai_analysis_result.success:
                        print(f"[重新生成报告] AI 分析完成")
                    else:
                        print(f"[重新生成报告] AI 分析失败: {ai_analysis_result.error}")
                        ai_analysis_result = None
                except Exception as e:
                    print(f"[重新生成报告] AI 分析异常: {e}")
                    ai_analysis_result = None

            # 生成报告
            html_file = ctx.generate_html(
                stats=stats,
                total_titles=total_titles,
                failed_ids=[],
                new_titles=new_titles,
                id_to_name=id_to_name,
                mode="current",
                update_info=None,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                ai_analysis=ai_analysis_result,
                standalone_data=standalone_data if standalone_data["platforms"] or standalone_data["rss_feeds"] else None,
            )

            self._send_json(200, {"success": True, "message": "报告已重新生成", "file": html_file})
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json(500, {"success": False, "message": f"生成失败: {e}"})
    def _api_post_rss_test(self):
        """API：测试 RSS 源网络连通性"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            url = data.get("url", "")
            if not url:
                self._send_json(400, {"success": False, "message": "URL 不能为空"})
                return

            import requests
            proxies = None
            if data.get("use_proxy") and data.get("proxy_url"):
                proxies = {"http": data["proxy_url"], "https": data["proxy_url"]}

            headers = {
                "User-Agent": "TrendRadar/2.0 RSS Reader (https://github.com/trendradar)",
                "Accept": "application/feed+json, application/json, application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            }
            response = requests.get(url, timeout=data.get("timeout", 15), proxies=proxies, headers=headers)
            response.raise_for_status()
            self._send_json(200, {"success": True, "message": f"连接成功 ({response.status_code})"})
        except requests.Timeout:
            self._send_json(200, {"success": False, "message": f"请求超时 ({data.get('timeout', 15)}s)"})
        except requests.RequestException as e:
            self._send_json(200, {"success": False, "message": f"请求失败: {e}"})
        except Exception as e:
            self._send_json(500, {"success": False, "message": f"测试出错: {e}"})

    def _api_post_ai_test(self):
        """API：测试 AI 模型连通性（使用最小 ping）"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 8 * 1024:
                self._send_json(200, {"success": False, "message": "请求体过大（最大 8KB）"})
                return
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}
        except json.JSONDecodeError as e:
            self._send_json(200, {"success": False, "message": f"JSON 解析错误: {e}"})
            return
        except Exception as e:
            self._send_json(200, {"success": False, "message": f"请求解析失败: {e}"})
            return

        provider = (data.get("provider") or "openai").strip()
        model = (data.get("model") or "").strip()
        api_key = (data.get("api_key") or "").strip()
        api_base = (data.get("api_base") or "").strip()

        if not provider:
            self._send_json(200, {"success": False, "message": "provider 不能为空"})
            return
        if not model:
            self._send_json(200, {"success": False, "message": "model 不能为空"})
            return

        # api_key 占位符回退：与运行时（trendradar/core/loader.py）保持一致
        # config.yaml 中 'YOUR_API_KEY_HERE' 是不提交真实 key 的占位符（见 docs/ai-env-vars.md）
        # 若前端把占位符原样送过来（或字段为空），回退 AI_API_KEY 环境变量
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            api_key = os.environ.get("AI_API_KEY", "").strip()
            if not api_key:
                self._send_json(200, {
                    "success": False,
                    "message": "未配置 AI API Key：请在表单中填写真实 key，或设置 AI_API_KEY 环境变量",
                })
                return

        # 防御性：如果 model 仍含 '/'，自动拆分（前端不会产生，仅防老客户端）
        if "/" in model:
            parts = model.split("/", 1)
            if not data.get("provider"):
                provider = parts[0]
            model = parts[1]

        from trendradar.ai.tester import AITester

        try:
            tester = AITester(provider=provider, model=model, api_key=api_key, api_base=api_base)
            ok, message, latency_ms = tester.test()
            self._send_json(200, {
                "success": ok,
                "message": message,
                "latency_ms": latency_ms,
            })
        except Exception as e:
            # 兜底：tester 内部已捕获所有异常，这里只防 import 或非预期崩溃
            self._send_json(200, {
                "success": False,
                "message": f"测试出错: {type(e).__name__}: {str(e)[:200]}",
            })

    def _api_post_ai_models(self):
        """API：返回 provider 的模型清单（LiteLLM catalog + provider API 合并）"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 8 * 1024:
                self._send_json(200, {"success": False, "message": "请求体过大（最大 8KB）"})
                return
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}
        except json.JSONDecodeError as e:
            self._send_json(200, {"success": False, "message": f"JSON 解析错误: {e}"})
            return
        except Exception as e:
            self._send_json(200, {"success": False, "message": f"请求解析失败: {e}"})
            return

        provider = (data.get("provider") or "").strip()
        api_key = (data.get("api_key") or "").strip()
        api_base = (data.get("api_base") or "").strip()

        if not provider:
            self._send_json(200, {"success": False, "message": "provider 不能为空"})
            return

        from trendradar.ai.model_catalog import ModelCatalog

        try:
            # 单次调用：合并 LiteLLM + provider，并返回 provider 错误（如有）
            models, lite_count, provider_count, provider_error = ModelCatalog.get_merged_with_counts(
                provider=provider, api_key=api_key, api_base=api_base
            )
            response = {
                "success": True,
                "models": models,
                "lite_count": lite_count,
                "provider_count": provider_count,
                "fetched_at": int(time.time()),
            }
            if provider_error:
                response["provider_error"] = provider_error
            self._send_json(200, response)
        except Exception as e:
            self._send_json(200, {
                "success": False,
                "message": f"查询出错: {type(e).__name__}: {str(e)[:200]}",
                "models": [],
            })

    def _api_post_ai_providers(self):
        """API：返回精简后的 provider 清单（6 项，按协议家族筛选）

        与 list_providers() 不同：list_providers 返回 LiteLLM 全部 130+ provider，
        list_curated_providers 仅返回供前端下拉用的 6 项核心 adapter。
        """
        try:
            from trendradar.ai.model_catalog import ModelCatalog
            providers = ModelCatalog.list_curated_providers()
            self._send_json(200, {
                "success": True,
                "providers": providers,
            })
        except Exception as e:
            self._send_json(200, {
                "success": False,
                "message": f"加载 provider 列表失败: {type(e).__name__}: {str(e)[:200]}",
                "providers": [],
            })

    def _api_get_tags(self):
        """API：读取当前数据库中的 active 标签"""
        try:
            config = load_structured_config(CONFIG_YAML_PATH)
            tags_mode = config.get("tags", {}).get("mode", "auto")

            # 确定 interests_file
            if tags_mode == "manual":
                interests_file = "__manual__"
            else:
                interests_file = config.get("ai_filter", {}).get("interests_file") or "ai_interests.txt"

            # 查询当天数据库
            today = datetime.now().strftime("%Y-%m-%d")
            db_path = Path(DEFAULT_DOC_ROOT) / "news" / today / f"{today}.db"
            if not db_path.exists():
                db_path = Path(DEFAULT_DOC_ROOT) / "news" / f"{today}.db"

            tags = []
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT tag, description, priority FROM ai_filter_tags "
                        "WHERE status = 'active' AND interests_file = ? "
                        "ORDER BY priority ASC, id ASC",
                        (interests_file,),
                    )
                    tags = [
                        {"tag": row[0], "description": row[1], "priority": row[2]}
                        for row in cursor.fetchall()
                    ]
                    conn.close()
                except Exception as e:
                    print(f"[WebUI] 读取标签失败: {e}")

            self._send_json(200, {
                "success": True,
                "tags": tags,
                "mode": tags_mode,
            })
        except Exception as e:
            self._send_json(500, {"success": False, "message": f"读取标签失败: {e}"})

    def _api_post_tags_preview(self):
        """API：预览AI推荐标签（不写入数据库）"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 1024 * 1024:
                self._send_json(413, {"success": False, "message": "请求体过大"})
                return

            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}

            # 读取配置创建 AIFilter
            config = load_structured_config(CONFIG_YAML_PATH)
            from trendradar.ai.filter import AIFilter
            from trendradar.utils.time import get_configured_time

            raw_ai_config = config.get("ai", {})
            ai_config = {
                "MODEL": raw_ai_config.get("model", ""),
                "API_KEY": raw_ai_config.get("api_key", ""),
                "API_BASE": raw_ai_config.get("api_base", ""),
                "TIMEOUT": raw_ai_config.get("timeout", 120),
                "TEMPERATURE": raw_ai_config.get("temperature", 1.0),
                "MAX_TOKENS": raw_ai_config.get("max_tokens", 5000),
                "NUM_RETRIES": raw_ai_config.get("num_retries", 2),
                "FALLBACK_MODELS": raw_ai_config.get("fallback_models", []),
                "EXTRA_PARAMS": raw_ai_config.get("extra_params", {}),
            }
            filter_config = {
                "BATCH_SIZE": config.get("ai_filter", {}).get("batch_size", 200),
                "BATCH_INTERVAL": config.get("ai_filter", {}).get("batch_interval", 5),
                "PROMPT_FILE": config.get("ai_filter", {}).get("prompt_file", "prompt.txt"),
                "EXTRACT_PROMPT_FILE": config.get("ai_filter", {}).get("extract_prompt_file", "extract_prompt.txt"),
                "UPDATE_TAGS_PROMPT_FILE": config.get("ai_filter", {}).get("update_tags_prompt_file", "update_tags_prompt.txt"),
            }

            ai_filter = AIFilter(ai_config, filter_config, get_configured_time, debug=False)

            # 读取兴趣内容
            interests_content = data.get("interests_content")
            if not interests_content:
                interests_file = config.get("ai_filter", {}).get("interests_file")
                interests_content = ai_filter.load_interests_content(interests_file)

            if not interests_content:
                self._send_json(400, {"success": False, "message": "兴趣描述文件为空或不存在"})
                return

            try:
                tags_data = ai_filter.extract_tags(interests_content)
            except Exception as e:
                self._send_json(500, {"success": False, "message": f"标签提取失败: {e}"})
                return

            if not tags_data:
                self._send_json(500, {"success": False, "message": "标签提取返回空结果"})
                return

            self._send_json(200, {
                "success": True,
                "tags": [{"tag": t["tag"], "description": t.get("description", "")} for t in tags_data],
            })
        except Exception as e:
            self._send_json(500, {"success": False, "message": f"推荐生成失败: {e}"})

    def _api_get_status(self):
        """API：获取爬取状态"""
        status = self._read_status()
        self._send_json(200, {
            "status": status.get("status", "idle"),
            "last_run": status.get("last_run"),
            "last_result": status.get("last_result", "unknown"),
            "pid": status.get("pid"),
        })

    def _monitor_crawl(self, process):
        """监控爬取进程状态"""
        try:
            import time
            # 使用 wait() 正确等待进程结束并回收僵尸进程
            returncode = process.wait()

            result = "success" if returncode == 0 else "failed"
            self._write_status({
                "status": "idle",
                "pid": None,
                "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_result": result,
            })
        except Exception:
            pass

    def _build_rss_new_items(self, ctx, sm, rss_data, word_groups, filter_words, global_filters):
        """构建 RSS 新增项目列表（关键词模式）"""
        if not rss_data or not rss_data.items:
            return None

        # 检测新增 RSS 条目
        new_rss_dict = sm.detect_new_rss_items(rss_data)
        if not new_rss_dict:
            return None

        # 转换为列表格式
        new_rss_list = []
        for feed_id, items in new_rss_dict.items():
            for item in items:
                display_title = getattr(item, "translated_title", "") or item.title
                new_rss_list.append({
                    "title": display_title,
                    "feed_id": feed_id,
                    "feed_name": rss_data.id_to_name.get(feed_id, feed_id),
                    "url": item.url or "",
                    "published_at": item.published_at or "",
                })

        if not new_rss_list:
            return None

        from trendradar.core.analyzer import count_rss_frequency
        rss_new_items, _ = count_rss_frequency(
            rss_items=new_rss_list,
            word_groups=word_groups,
            filter_words=filter_words,
            global_filters=global_filters,
            new_items=new_rss_list,
            max_news_per_keyword=0,
            sort_by_position_first=False,
            timezone=ctx.timezone,
            rank_threshold=ctx.rank_threshold,
            quiet=True,
        )
        return rss_new_items

    def _build_rss_items(self, ctx, sm, rss_data, word_groups, filter_words, global_filters):
        """构建 RSS 项目列表（关键词模式）"""
        if not rss_data or not rss_data.items:
            return None

        rss_items_list = []
        for feed_id, items in rss_data.items.items():
            for item in items:
                display_title = getattr(item, "translated_title", "") or item.title
                rss_items_list.append({
                    "title": display_title,
                    "feed_id": feed_id,
                    "feed_name": rss_data.id_to_name.get(feed_id, feed_id),
                    "url": item.url or "",
                    "published_at": item.published_at or "",
                })

        if not rss_items_list:
            return None

        from trendradar.core.analyzer import count_rss_frequency
        rss_items, _ = count_rss_frequency(
            rss_items=rss_items_list,
            word_groups=word_groups,
            filter_words=filter_words,
            global_filters=global_filters,
            new_items=None,
            max_news_per_keyword=0,
            sort_by_position_first=False,
            timezone=ctx.timezone,
            rank_threshold=ctx.rank_threshold,
            quiet=True,
        )
        return rss_items

    def _write_file_with_lock(self, path: Path, content: str):
        """带文件锁写入"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(content)
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _read_status(self) -> dict:
        """读取状态文件"""

    def _write_file_with_lock(self, path: Path, content: str):
        """带文件锁写入"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(content)
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _read_status(self) -> dict:
        """读取状态文件"""
        try:
            if Path(STATUS_FILE).exists():
                with open(STATUS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _write_status(self, status: dict):
        """写入状态文件"""
        try:
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WebUI] 状态写入失败: {e}")

    def _send_html(self, code: int, content: str):
        """发送 HTML 响应"""
        body = content.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, data: dict):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def run_server(port: int = DEFAULT_PORT, document_root: str = DEFAULT_DOC_ROOT):
    """启动 WebUI 服务器"""
    server_address = ("0.0.0.0", port)
    handler = lambda *args, **kwargs: WebUIHandler(*args, document_root=document_root, **kwargs)
    httpd = ThreadedHTTPServer(server_address, handler)
    print(f"[WebUI] 服务器已启动: http://0.0.0.0:{port}")
    print(f"[WebUI] 文档根目录: {document_root}")
    print(f"[WebUI] 配置目录: {CONFIG_DIR}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[WebUI] 服务器已停止")
        httpd.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    doc_root = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DOC_ROOT
    run_server(port, doc_root)
