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
        elif path == "/api/ai/test":
            self._api_post_ai_test()
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

        model = (data.get("model") or "").strip()
        api_key = (data.get("api_key") or "").strip()
        api_base = (data.get("api_base") or "").strip()

        if not model:
            self._send_json(200, {"success": False, "message": "模型名称不能为空"})
            return
        if "/" not in model:
            self._send_json(200, {
                "success": False,
                "message": "模型格式错误，应为 'provider/model' 格式",
            })
            return

        from trendradar.ai.tester import AITester

        try:
            tester = AITester(model=model, api_key=api_key, api_base=api_base)
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
                "latency_ms": 0,
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
