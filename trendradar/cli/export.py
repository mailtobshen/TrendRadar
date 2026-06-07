# coding=utf-8
"""
TrendRadar 数据导出 CLI

支持按数据源导出可推送信息：
  - hotlist : 热点排行榜（news_items + platforms）
  - rss     : RSS 订阅（rss_items + rss_feeds）
  - ai      : AI 智能分类（ai_filter_results + news_items + ai_filter_tags）
  - all     : 同时导出以上三种

示例:
  python -m trendradar export --source hotlist
  python -m trendradar export --source rss --per-source-limit 5 --limit 100
  python -m trendradar export --source ai --limit 50
  python -m trendradar export --source all --format json --pretty
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


def _find_latest_db(base_dir: Path, subdir: str) -> Optional[Path]:
    """查找最新的数据库文件（先今天，再昨天，再目录内最新）"""
    db_dir = base_dir / subdir
    if not db_dir.exists():
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    for date in [today, yesterday]:
        p = db_dir / f"{date}.db"
        if p.exists():
            return p

    # fallback: 找目录内最新的 .db 文件
    dbs = sorted(db_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    return dbs[0] if dbs else None


def _dict_factory(cursor, row):
    """sqlite3 row factory -> dict"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def export_hotlist(db_path: Path, per_source_limit: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """导出热点排行榜数据

    对每个平台单独取 TOP per_source_limit，合并后再按 limit 全局截断。
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = _dict_factory
    cur = conn.cursor()

    # 获取所有平台 ID，逐个取 TOP N
    cur.execute("SELECT DISTINCT platform_id FROM news_items")
    platform_ids = [r["platform_id"] for r in cur.fetchall()]

    items = []
    for pid in platform_ids:
        cur.execute(
            """
            SELECT n.title, n.url, n.mobile_url, n.rank, n.platform_id,
                   p.name as platform_name, n.last_crawl_time
            FROM news_items n
            JOIN platforms p ON n.platform_id = p.id
            WHERE n.platform_id = ?
            ORDER BY n.last_crawl_time DESC, n.rank ASC
            LIMIT ?
            """,
            (pid, per_source_limit),
        )
        for r in cur.fetchall():
            items.append(
                {
                    "title": r["title"],
                    "url": r["url"] or r["mobile_url"] or "",
                    "source": r["platform_name"] or r["platform_id"],
                    "platform_id": r["platform_id"],
                    "rank": r["rank"],
                    "crawl_time": r["last_crawl_time"],
                }
            )

    conn.close()

    # 最终按时间+排名重新排序，全局截断
    if limit is not None:
        items.sort(key=lambda x: (x["crawl_time"] or "", -x["rank"] if x["rank"] is not None else 0), reverse=True)
        items = items[:limit]

    return items


def export_rss(db_path: Path, per_source_limit: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """导出 RSS 订阅数据

    对每个 Feed 单独取 TOP per_source_limit，合并后再按 limit 全局截断。
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = _dict_factory
    cur = conn.cursor()

    # 获取所有活跃 Feed ID，逐个取 TOP N
    cur.execute("SELECT DISTINCT id FROM rss_feeds WHERE is_active = 1")
    feed_ids = [r["id"] for r in cur.fetchall()]

    items = []
    for fid in feed_ids:
        cur.execute(
            """
            SELECT i.title, i.url, i.summary, i.published_at,
                   i.feed_id, f.name as feed_name
            FROM rss_items i
            JOIN rss_feeds f ON i.feed_id = f.id
            WHERE f.is_active = 1 AND i.feed_id = ?
            ORDER BY i.published_at DESC
            LIMIT ?
            """,
            (fid, per_source_limit),
        )
        for r in cur.fetchall():
            # 翻译已下放到 notification 层（in-memory），rss_items 不再存 translated_title。
            # 输出 title/original_title 两个字段保持下游 Hermes 解析契约不变。
            items.append(
                {
                    "title": r["title"],
                    "original_title": r["title"],
                    "url": r["url"] or "",
                    "source": r["feed_name"] or r["feed_id"],
                    "feed_id": r["feed_id"],
                    "published_at": r["published_at"],
                    "summary": r["summary"] or "",
                }
            )

    conn.close()

    # 最终按发布时间重新排序，全局截断
    if limit is not None:
        items.sort(key=lambda x: x["published_at"] or "", reverse=True)
        items = items[:limit]

    return items


def export_ai(db_path: Path, per_source_limit: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """导出 AI 智能分类数据（按标签分组）

    对每个标签单独取 TOP per_source_limit，合并后再按 limit 全局截断。
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = _dict_factory
    cur = conn.cursor()

    # 获取所有活跃标签，按优先级排序
    cur.execute(
        """
        SELECT DISTINCT t.tag, t.priority
        FROM ai_filter_results r
        JOIN ai_filter_tags t ON t.id = r.tag_id
        WHERE r.status = 'active'
          AND t.status = 'active'
        ORDER BY t.priority ASC
        """
    )
    tag_rows = cur.fetchall()

    tags = OrderedDict()
    total = 0
    for tag_row in tag_rows:
        if limit is not None and total >= limit:
            break

        tag_name = tag_row["tag"]
        cur.execute(
            """
            SELECT n.title, n.url, n.platform_id, p.name as platform_name,
                   r.relevance_score, n.last_crawl_time, t.tag, t.priority
            FROM ai_filter_results r
            JOIN news_items n ON n.id = r.news_item_id
            JOIN ai_filter_tags t ON t.id = r.tag_id
            LEFT JOIN platforms p ON p.id = n.platform_id
            WHERE r.status = 'active'
              AND t.status = 'active'
              AND t.tag = ?
            ORDER BY t.priority ASC, r.relevance_score DESC, n.last_crawl_time DESC
            LIMIT ?
            """,
            (tag_name, per_source_limit),
        )
        rows = cur.fetchall()

        if tag_name not in tags:
            tags[tag_name] = {
                "tag": tag_name,
                "priority": None,
                "items": [],
            }

        for r in rows:
            if limit is not None and total >= limit:
                break
            tags[tag_name]["priority"] = r["priority"]
            tags[tag_name]["items"].append(
                {
                    "title": r["title"],
                    "url": r["url"] or "",
                    "source": r["platform_name"] or r["platform_id"],
                    "score": r["relevance_score"],
                    "crawl_time": r["last_crawl_time"],
                }
            )
            total += 1

    conn.close()
    # 过滤掉空标签
    return [t for t in tags.values() if t["items"]]


def _do_export(source: str, output_dir: Path, per_source_limit: int, limit: Optional[int] = None) -> Dict[str, Any]:
    """执行单个 source 的导出"""
    result: Dict[str, Any] = {
        "source": source,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }

    if source == "hotlist":
        db_path = _find_latest_db(output_dir, "news")
        if not db_path:
            result["error"] = "未找到热点数据库文件"
            result["items"] = []
        else:
            result["db_path"] = str(db_path)
            result["items"] = export_hotlist(db_path, per_source_limit, limit)

    elif source == "rss":
        db_path = _find_latest_db(output_dir, "rss")
        if not db_path:
            result["error"] = "未找到 RSS 数据库文件"
            result["items"] = []
        else:
            result["db_path"] = str(db_path)
            result["items"] = export_rss(db_path, per_source_limit, limit)

    elif source == "ai":
        db_path = _find_latest_db(output_dir, "news")
        if not db_path:
            result["error"] = "未找到 AI 分析数据库文件"
            result["tags"] = []
        else:
            result["db_path"] = str(db_path)
            result["tags"] = export_ai(db_path, per_source_limit, limit)

    else:
        raise ValueError(f"未知数据源: {source}")

    return result


def run_export(args: argparse.Namespace) -> int:
    """export 子命令入口"""
    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        print(f"输出目录不存在: {output_dir}", file=sys.stderr)
        return 1

    sources = []
    if args.source == "all":
        sources = ["hotlist", "rss", "ai"]
    else:
        sources = [args.source]

    results = []
    for source in sources:
        try:
            result = _do_export(source, output_dir, args.per_source_limit, args.limit)
            results.append(result)
        except Exception as e:
            results.append(
                {
                    "source": source,
                    "error": str(e),
                    "exported_at": datetime.now().isoformat(timespec="seconds"),
                }
            )

    if args.source == "all":
        payload = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "results": results,
        }
    else:
        payload = results[0]

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    else:
        # 预留 markdown / plain 格式扩展
        print(json.dumps(payload, ensure_ascii=False))

    # 任一结果包含 error 则返回非 0
    has_error = any("error" in r for r in results)
    return 1 if has_error else 0


def build_parser(subparsers):
    """注册 export 子命令到 argparse"""
    parser = subparsers.add_parser(
        "export",
        help="导出可推送数据（hotlist/rss/ai）",
        description="按数据源导出最新爬取的新闻标题、URL 和媒体名称。",
    )
    parser.add_argument(
        "--source",
        choices=["hotlist", "rss", "ai", "all"],
        required=True,
        help="数据源: hotlist=热点排行榜, rss=RSS订阅, ai=AI智能分类, all=全部",
    )
    parser.add_argument(
        "--per-source-limit",
        type=int,
        default=3,
        help="每个平台/Feed/标签内的最大条数 (默认: 3)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最终汇总后的总记录数上限 (默认: 不限制)",
    )
    parser.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="输出格式 (默认: json)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("TRENDRADAR_OUTPUT_DIR", "output"),
        help="输出根目录，默认当前目录下的 output/ 或环境变量 TRENDRADAR_OUTPUT_DIR",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="JSON 美化输出（默认紧凑）",
    )
    parser.set_defaults(func=run_export)
    return parser
