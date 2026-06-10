# coding=utf-8
"""
AI 分析器模块

调用 AI 大模型对热点新闻进行深度分析
基于 LiteLLM 统一接口，支持 100+ AI 提供商
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from trendradar.ai.client import AIClient
from trendradar.ai.prompt_loader import load_prompt_template


@dataclass
class AIAnalysisResult:
    """AI 分析结果"""
    # 新版 5 核心板块
    core_trends: str = ""                # 核心热点与舆情态势
    sentiment_controversy: str = ""      # 舆论风向与争议
    signals: str = ""                    # 异动与弱信号
    rss_insights: str = ""               # RSS 深度洞察
    outlook_strategy: str = ""           # 研判与策略建议
    standalone_summaries: Dict[str, str] = field(default_factory=dict)  # 独立展示区概括 {源ID: 概括}

    # 基础元数据
    raw_response: str = ""               # 原始响应
    success: bool = False                # 是否成功
    skipped: bool = False                # 是否因无内容跳过（非失败）
    error: str = ""                      # 错误信息

    # 新闻数量统计
    total_news: int = 0                  # 总新闻数（热榜+RSS）
    analyzed_news: int = 0               # 实际分析的新闻数
    max_news_limit: int = 0              # 分析上限配置值
    hotlist_count: int = 0               # 热榜新闻数（总数）
    rss_count: int = 0                   # RSS 新闻数（总数）
    hotlist_analyzed: int = 0            # 热榜实际分析数
    rss_analyzed: int = 0               # RSS 实际分析数
    standalone_analyzed: int = 0        # 独立展示区实际分析数
    ai_mode: str = ""                    # AI 分析使用的模式 (daily/current/incremental)
    include_rss: bool = True             # 是否启用 RSS 分析
    include_standalone: bool = False     # 是否启用独立展示区分析

    # 缓存标记（不是真实 AI 输出，是上一次跑批的复用）
    cached: bool = False                 # 是否为复用缓存
    cached_at: str = ""                  # 原始生成时间 HH:MM


class AIAnalyzer:
    """AI 分析器"""

    def __init__(
        self,
        ai_config: Dict[str, Any],
        analysis_config: Dict[str, Any],
        get_time_func: Callable,
        debug: bool = False,
    ):
        """
        初始化 AI 分析器

        Args:
            ai_config: AI 模型配置（LiteLLM 格式）
            analysis_config: AI 分析功能配置（language, prompt_file 等）
            get_time_func: 获取当前时间的函数
            debug: 是否开启调试模式
        """
        self.ai_config = ai_config
        self.analysis_config = analysis_config
        self.get_time_func = get_time_func
        self.debug = debug

        # 创建 AI 客户端（基于 LiteLLM）
        self.client = AIClient(ai_config)

        # 验证配置
        valid, error = self.client.validate_config()
        if not valid:
            print(f"[AI] 配置警告: {error}")

        # 从分析配置获取功能参数
        self.max_news = analysis_config.get("MAX_NEWS_FOR_ANALYSIS", 50)
        self.include_rss = analysis_config.get("INCLUDE_RSS", True)
        self.include_rank_timeline = analysis_config.get("INCLUDE_RANK_TIMELINE", False)
        self.include_standalone = analysis_config.get("INCLUDE_STANDALONE", False)
        self.language = analysis_config.get("LANGUAGE", "Chinese")

        # 加载提示词模板
        self.system_prompt, self.user_prompt_template = load_prompt_template(
            analysis_config.get("PROMPT_FILE", "ai_analysis_prompt.txt"),
            label="AI",
        )

    def analyze(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
        report_mode: str = "daily",
        report_type: str = "当日汇总",
        platforms: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        standalone_data: Optional[Dict] = None,
    ) -> AIAnalysisResult:
        """
        执行 AI 分析

        Args:
            stats: 热榜统计数据
            rss_stats: RSS 统计数据
            report_mode: 报告模式
            report_type: 报告类型
            platforms: 平台列表
            keywords: 关键词列表

        Returns:
            AIAnalysisResult: 分析结果
        """
        
        # 打印配置信息方便调试
        model = self.ai_config.get("MODEL", "unknown")
        api_key = self.client.api_key or ""
        api_base = self.ai_config.get("API_BASE", "")
        masked_key = f"{api_key[:5]}******" if len(api_key) >= 5 else "******"
        model_display = model.replace("/", "/\u200b") if model else "unknown"

        print(f"[AI] 模型: {model_display}")
        print(f"[AI] Key : {masked_key}")

        if api_base:
            print(f"[AI] 接口: 存在自定义 API 端点")

        timeout = self.ai_config.get("TIMEOUT", 120)
        max_tokens = self.ai_config.get("MAX_TOKENS", 5000)
        print(f"[AI] 参数: timeout={timeout}, max_tokens={max_tokens}")

        if not self.client.api_key:
            return AIAnalysisResult(
                success=False,
                error="未配置 AI API Key，请在 config.yaml 或环境变量 AI_API_KEY 中设置"
            )

        # 准备新闻内容并获取统计数据
        news_content, rss_content, hotlist_total, rss_total, analyzed_count, hotlist_analyzed, rss_analyzed = self._prepare_news_content(stats, rss_stats)
        total_news = hotlist_total + rss_total

        if not news_content and not rss_content:
            return AIAnalysisResult(
                success=False,
                skipped=True,
                error="本轮无新增热点内容，跳过 AI 分析",
                total_news=total_news,
                hotlist_count=hotlist_total,
                rss_count=rss_total,
                analyzed_news=0,
                max_news_limit=self.max_news
            )

        # 构建提示词
        current_time = self.get_time_func().strftime("%Y-%m-%d %H:%M:%S")

        # 提取关键词
        if not keywords:
            keywords = [s.get("word", "") for s in stats if s.get("word")] if stats else []

        # 使用安全的字符串替换，避免模板中其他花括号（如 JSON 示例）被误解析
        user_prompt = self.user_prompt_template
        user_prompt = user_prompt.replace("{report_mode}", report_mode)
        user_prompt = user_prompt.replace("{report_type}", report_type)
        user_prompt = user_prompt.replace("{current_time}", current_time)
        user_prompt = user_prompt.replace("{news_count}", str(hotlist_total))
        user_prompt = user_prompt.replace("{rss_count}", str(rss_total))
        user_prompt = user_prompt.replace("{platforms}", ", ".join(platforms) if platforms else "多平台")
        user_prompt = user_prompt.replace("{keywords}", ", ".join(keywords[:20]) if keywords else "无")
        user_prompt = user_prompt.replace("{news_content}", news_content)
        user_prompt = user_prompt.replace("{rss_content}", rss_content)
        user_prompt = user_prompt.replace("{language}", self.language)

        # 构建独立展示区内容
        standalone_content = ""
        standalone_count = 0
        if self.include_standalone and standalone_data:
            standalone_content, standalone_count = self._prepare_standalone_content(standalone_data)
        user_prompt = user_prompt.replace("{standalone_content}", standalone_content)

        if self.debug:
            print("\n" + "=" * 80)
            print("[AI 调试] 发送给 AI 的完整提示词")
            print("=" * 80)
            if self.system_prompt:
                print("\n--- System Prompt ---")
                print(self.system_prompt)
            print("\n--- User Prompt ---")
            print(user_prompt)
            print("=" * 80 + "\n")

        # 调用 AI API（使用 LiteLLM）— 按板块独立发送 + 降级策略
        # 将 6 个板块（4 个热榜板块 + RSS 洞察 + 独立展示区概括）拆为独立调用，
        # 单个板块失败（含 new_sensitive 等内容审核拒绝、网络异常、JSON 解析失败）
        # 不影响其他板块，AI 区域整体只在 6 个板块全部失败时才报错。
        # 任一板块触发内容审核时，使用 1.0/0.5/0.25 三档降级策略按行数裁剪数据后重试。
        try:
            result = self._analyze_per_board(
                user_prompt_template=self.user_prompt_template,
                hotlist_news=news_content,
                rss_news=rss_content,
                standalone_data=standalone_data if self.include_standalone else None,
                report_mode=report_mode,
                report_type=report_type,
                current_time=current_time,
                news_count=hotlist_total,
                rss_count=rss_total,
                platforms=platforms,
                keywords=keywords,
                language=self.language,
            )

            # JSON 解析失败时的重试兜底（仅重试一次）
            if result.error and "JSON 解析错误" in result.error:
                print(f"[AI] JSON 解析失败，尝试让 AI 修复...")
                retry_result = self._retry_fix_json(result.raw_response, result.error)
                if retry_result and retry_result.success and not retry_result.error:
                    print("[AI] JSON 修复成功")
                    result = retry_result

            # 如果配置未启用 RSS 分析，强制清空 AI 返回的 RSS 洞察
            if not self.include_rss:
                result.rss_insights = ""

            # 如果配置未启用 standalone 分析，强制清空
            if not self.include_standalone:
                result.standalone_summaries = {}

            # 填充统计数据
            result.total_news = total_news
            result.hotlist_count = hotlist_total
            result.rss_count = rss_total
            result.analyzed_news = analyzed_count
            result.hotlist_analyzed = hotlist_analyzed
            result.rss_analyzed = rss_analyzed
            result.standalone_analyzed = standalone_count
            result.max_news_limit = self.max_news
            result.include_rss = self.include_rss
            result.include_standalone = self.include_standalone
            return result
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # 截断过长的错误消息
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            friendly_msg = f"AI 分析失败 ({error_type}): {error_msg}"

            return AIAnalysisResult(
                success=False,
                error=friendly_msg
            )

    def _prepare_news_content(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
    ) -> tuple:
        """
        准备新闻内容文本（增强版）

        热榜新闻包含：来源、标题、排名范围、时间范围、出现次数
        RSS 包含：来源、标题、发布时间

        Returns:
            tuple: (news_content, rss_content, hotlist_total, rss_total, analyzed_count, hotlist_analyzed, rss_analyzed)
        """
        news_lines = []
        rss_lines = []
        news_count = 0
        rss_count = 0

        # 计算总新闻数
        hotlist_total = sum(len(s.get("titles", [])) for s in stats) if stats else 0
        rss_total = sum(len(s.get("titles", [])) for s in rss_stats) if rss_stats else 0

        # 热榜内容
        if stats:
            for stat in stats:
                word = stat.get("word", "")
                titles = stat.get("titles", [])
                if word and titles:
                    news_lines.append(f"\n**{word}** ({len(titles)}条)")
                    for t in titles:
                        if not isinstance(t, dict):
                            continue
                        title = t.get("title", "")
                        if not title:
                            continue

                        # 来源
                        source = t.get("source_name", t.get("source", ""))

                        # 构建行
                        if source:
                            line = f"- [{source}] {title}"
                        else:
                            line = f"- {title}"

                        # 始终显示简化格式：排名范围 + 时间范围 + 出现次数
                        ranks = t.get("ranks", [])
                        if ranks:
                            min_rank = min(ranks)
                            max_rank = max(ranks)
                            rank_str = f"{min_rank}" if min_rank == max_rank else f"{min_rank}-{max_rank}"
                        else:
                            rank_str = "-"

                        first_time = t.get("first_time", "")
                        last_time = t.get("last_time", "")
                        time_str = self._format_time_range(first_time, last_time)

                        appear_count = t.get("count", 1)

                        line += f" | 排名:{rank_str} | 时间:{time_str} | 出现:{appear_count}次"

                        # 开启完整时间线时，额外添加轨迹
                        if self.include_rank_timeline:
                            rank_timeline = t.get("rank_timeline", [])
                            timeline_str = self._format_rank_timeline(rank_timeline)
                            line += f" | 轨迹:{timeline_str}"

                        news_lines.append(line)

                        news_count += 1
                        if news_count >= self.max_news:
                            break
                if news_count >= self.max_news:
                    break

        # RSS 内容（仅在启用时构建）
        if self.include_rss and rss_stats:
            remaining = self.max_news - news_count
            for stat in rss_stats:
                if rss_count >= remaining:
                    break
                word = stat.get("word", "")
                titles = stat.get("titles", [])
                if word and titles:
                    rss_lines.append(f"\n**{word}** ({len(titles)}条)")
                    for t in titles:
                        if not isinstance(t, dict):
                            continue
                        title = t.get("title", "")
                        if not title:
                            continue

                        # 来源
                        source = t.get("source_name", t.get("feed_name", ""))

                        # 发布时间
                        time_display = t.get("time_display", "")

                        # 构建行：[来源] 标题 | 发布时间
                        if source:
                            line = f"- [{source}] {title}"
                        else:
                            line = f"- {title}"
                        if time_display:
                            line += f" | {time_display}"
                        rss_lines.append(line)

                        rss_count += 1
                        if rss_count >= remaining:
                            break

        news_content = "\n".join(news_lines) if news_lines else ""
        rss_content = "\n".join(rss_lines) if rss_lines else ""
        total_count = news_count + rss_count

        return news_content, rss_content, hotlist_total, rss_total, total_count, news_count, rss_count

    def _call_ai(self, user_prompt: str) -> str:
        """调用 AI API（使用 LiteLLM）"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        return self.client.chat(messages)

    # === 分段发送 + 降级策略 ===

    _SENSITIVE_MARKERS = ("new_sensitive", "sensitive", "input_new", "content_filter")

    def _is_content_moderation_error(self, error_msg: str) -> bool:
        """判断是否为内容审核拒绝（区分于网络/配置错误）"""
        if not error_msg:
            return False
        lower = error_msg.lower()
        return any(marker in lower for marker in self._SENSITIVE_MARKERS)

    def _build_segment_prompt(
        self,
        user_prompt_template: str,
        news_override: str,
        rss_override: str,
        standalone_override: str,
        report_mode: str,
        report_type: str,
        current_time: str,
        news_count: int,
        rss_count: int,
        platforms,
        keywords,
        language: str,
    ) -> str:
        """用变量替换构造单段的 user prompt"""
        prompt = user_prompt_template
        prompt = prompt.replace("{report_mode}", report_mode)
        prompt = prompt.replace("{report_type}", report_type)
        prompt = prompt.replace("{current_time}", current_time)
        prompt = prompt.replace("{news_count}", str(news_count))
        prompt = prompt.replace("{rss_count}", str(rss_count))
        prompt = prompt.replace("{platforms}", ", ".join(platforms) if platforms else "多平台")
        prompt = prompt.replace("{keywords}", ", ".join(keywords[:20]) if keywords else "无")
        prompt = prompt.replace("{news_content}", news_override)
        prompt = prompt.replace("{rss_content}", rss_override)
        prompt = prompt.replace("{standalone_content}", standalone_override)
        prompt = prompt.replace("{language}", language)
        return prompt

    def _truncate_lines(self, content: str, keep_ratio: float) -> str:
        """按行数比例裁剪内容，保留前 N 行"""
        if not content or keep_ratio >= 1.0:
            return content
        lines = [ln for ln in content.split("\n") if ln.strip()]
        keep = max(1, int(len(lines) * keep_ratio))
        return "\n".join(lines[:keep])

    # === 单板块独立发送：颗粒度更细，失败不互相牵连 ===

    # 板块常量：key=AIAnalysisResult 字段名，scope=数据来源（"hotlist" | "rss" | "standalone"）
    _BOARD_SPECS: tuple = (
        ("core_trends", "hotlist"),
        ("sentiment_controversy", "hotlist"),
        ("signals", "hotlist"),
        ("outlook_strategy", "hotlist"),
        ("rss_insights", "rss"),
        ("standalone_summaries", "standalone"),
    )

    def _build_board_prompt(
        self,
        user_prompt_template: str,
        board_key: str,
        news_override: str,
        rss_override: str,
        standalone_override: str,
        report_mode: str,
        report_type: str,
        current_time: str,
        news_count: int,
        rss_count: int,
        platforms,
        keywords,
        language: str,
    ) -> str:
        """构造单板块的 user prompt：在原模板基础上追加"只输出该字段 JSON"的约束。"""
        base = self._build_segment_prompt(
            user_prompt_template=user_prompt_template,
            news_override=news_override,
            rss_override=rss_override,
            standalone_override=standalone_override,
            report_mode=report_mode,
            report_type=report_type,
            current_time=current_time,
            news_count=news_count,
            rss_count=rss_count,
            platforms=platforms,
            keywords=keywords,
            language=language,
        )
        # 追加单字段约束，限制 AI 一次只返回一个字段，缩小 payload/审核面
        constraint = (
            "\n\n---\n本调用只分析「"
            f"{board_key}"
            "」一个板块。请严格按以下 JSON 格式返回（其他字段一律不要输出，"
            "也不要输出 Markdown 之外的解释文字）：\n\n"
            "```json\n"
            "{\n"
            f'  "{board_key}": "...（按原板块说明的写法输出，可空字符串但字段必须存在）"\n'
            "}\n"
            "```\n"
        )
        return base + constraint

    def _parse_board_response(self, board_key: str, response: str) -> Optional[str]:
        """
        从 AI 响应中仅提取指定板块字段。

        成功（字段非空字符串且解析成功）→ 返回字符串。
        失败（响应空 / JSON 解析失败 / 字段缺失或为空）→ 返回 None，调用方按降级重试。
        """
        if not response or not response.strip():
            return None

        # 去掉 markdown 代码块标记
        json_str = response
        if "```json" in response:
            code_block = response.split("```json", 1)[1]
            end_idx = code_block.find("```")
            json_str = code_block[:end_idx] if end_idx != -1 else code_block
        elif "```" in response:
            parts = response.split("```", 2)
            json_str = parts[1] if len(parts) >= 2 else response

        json_str = json_str.strip()
        if not json_str:
            return None

        # 第一步：标准 JSON 解析
        data = None
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # 第二步：json_repair 本地修复
            try:
                from json_repair import repair_json
                repaired = repair_json(json_str, return_objects=True)
                if isinstance(repaired, dict):
                    data = repaired
            except Exception:
                return None

        if not isinstance(data, dict):
            return None

        value = data.get(board_key)
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return str(value) if not isinstance(value, str) else value

    def _try_board_with_degradation(
        self,
        board_key: str,
        scope: str,
        user_prompt_template: str,
        hotlist_news: str,
        rss_news: str,
        standalone_content: str,
        report_mode: str,
        report_type: str,
        current_time: str,
        news_count: int,
        rss_count: int,
        platforms,
        keywords,
        language: str,
    ) -> Optional[str]:
        """
        尝试发送单个板块；失败时按 [1.0, 0.5, 0.25] 降级裁剪重试。
        成功 → 返回字段字符串；所有档失败 → 返回 None。
        """
        # 根据 scope 决定每段数据是否要喂给 AI
        if scope == "hotlist":
            news_override, rss_override, standalone_override = hotlist_news, "（本板块不含 RSS 数据）", "（本板块不含独立展示区数据）"
            eff_news_count, eff_rss_count = news_count, 0
        elif scope == "rss":
            news_override, rss_override, standalone_override = "（本板块不含热榜数据）", rss_news or "（无 RSS 数据）", "（本板块不含独立展示区数据）"
            eff_news_count, eff_rss_count = 0, rss_count
        else:  # standalone
            news_override, rss_override, standalone_override = "（本板块不含热榜数据）", "（本板块不含 RSS 数据）", standalone_content or "（无独立展示区数据）"
            eff_news_count, eff_rss_count = 0, 0

        degradation_steps = [1.0, 0.5, 0.25]
        last_error: Optional[str] = None

        for step, ratio in enumerate(degradation_steps, start=1):
            user_prompt = self._build_board_prompt(
                user_prompt_template=user_prompt_template,
                board_key=board_key,
                news_override=self._truncate_lines(news_override, ratio),
                rss_override=self._truncate_lines(rss_override, ratio),
                standalone_override=self._truncate_lines(standalone_override, ratio),
                report_mode=report_mode,
                report_type=report_type,
                current_time=current_time,
                news_count=eff_news_count if ratio == 1.0 else max(0, int(eff_news_count * ratio)),
                rss_count=eff_rss_count if ratio == 1.0 else max(0, int(eff_rss_count * ratio)),
                platforms=platforms,
                keywords=keywords,
                language=language,
            )

            if self.debug:
                print(f"\n[AI 调试] [{board_key}] 降级档 {step}/{len(degradation_steps)} (ratio={ratio})")

            try:
                response = self._call_ai(user_prompt)
                value = self._parse_board_response(board_key, response)
                if value is not None:
                    if ratio < 1.0:
                        print(f"[AI] [{board_key}] 降级档 {step} (ratio={ratio}) 成功")
                    return value
                last_error = "字段解析失败或为空"
            except Exception as e:
                err = str(e)
                last_error = err
                is_sensitive = self._is_content_moderation_error(err)

                if is_sensitive and step < len(degradation_steps):
                    print(
                        f"[AI] [{board_key}] 内容审核拒绝 (step {step}/{len(degradation_steps)}): "
                        f"{err[:120]}... → 降级重试"
                    )
                    continue
                if is_sensitive:
                    print(
                        f"[AI] [{board_key}] 内容审核拒绝，已降至最低档仍失败: {err[:120]}..."
                    )
                    return None
                # 非内容审核错误：网络/配置类，不重试
                print(f"[AI] [{board_key}] 调用失败（非内容审核）: {err[:200]}")
                return None

            # 字段解析失败：仅在还有降级档时重试
            if step < len(degradation_steps):
                print(
                    f"[AI] [{board_key}] 字段解析失败 (step {step}/{len(degradation_steps)}): "
                    f"{last_error} → 降级重试"
                )
                continue
            return None

        print(f"[AI] [{board_key}] 所有降级档失败: {last_error[:200] if last_error else 'unknown'}")
        return None

    def _analyze_per_board(
        self,
        user_prompt_template: str,
        hotlist_news: str,
        rss_news: str,
        standalone_data,
        report_mode: str,
        report_type: str,
        current_time: str,
        news_count: int,
        rss_count: int,
        platforms,
        keywords,
        language: str,
    ) -> AIAnalysisResult:
        """
        按板块独立调用 AI：每个板块是独立调用 + 独立降级，单板块失败不影响其他板块。

        6 个板块（按 _BOARD_SPECS 顺序）：
          core_trends / sentiment_controversy / signals / outlook_strategy — 热榜 4 板块
          rss_insights                                                    — RSS 洞察
          standalone_summaries                                            — 独立展示区概括

        任意 ≥1 个板块成功 → 整体 success=True，缺失板块字段为空。
        6 个板块全失败 → 整体 success=False。
        """
        standalone_content = ""
        if standalone_data:
            standalone_content, _ = self._prepare_standalone_content(standalone_data)

        board_results: Dict[str, str] = {}

        for board_key, scope in self._BOARD_SPECS:
            # 跳过用户未启用的板块
            if board_key == "rss_insights" and not self.include_rss:
                continue
            if board_key == "standalone_summaries" and not self.include_standalone:
                continue

            value = self._try_board_with_degradation(
                board_key=board_key,
                scope=scope,
                user_prompt_template=user_prompt_template,
                hotlist_news=hotlist_news,
                rss_news=rss_news,
                standalone_content=standalone_content,
                report_mode=report_mode,
                report_type=report_type,
                current_time=current_time,
                news_count=news_count,
                rss_count=rss_count,
                platforms=platforms,
                keywords=keywords,
                language=language,
            )
            if value is not None:
                board_results[board_key] = value

        return self._merge_board_results(board_results)

    def _merge_board_results(
        self,
        board_results: Dict[str, str],
    ) -> AIAnalysisResult:
        """
        合并各板块结果。

        - 任一板块成功 → 整体 success=True，缺失字段留空
        - 全部板块失败 → 整体 success=False，error 提示"全部板块均未成功"
        - raw_response 汇总所有成功板块，便于调试
        """
        if not board_results:
            return AIAnalysisResult(
                success=False,
                error=(
                    "AI 分析失败：所有 6 个板块（核心热点/舆论风向/异动信号/研判策略/"
                    "RSS 洞察/独立展示区）均未成功（可能触发内容审核或网络异常）"
                ),
            )

        merged = AIAnalysisResult(success=True)
        for key, value in board_results.items():
            if key == "standalone_summaries":
                # 安全地把字符串/字典都接受；这里 AI 应返回 dict，但兜底接受 string
                try:
                    parsed = json.loads(value) if isinstance(value, str) and value.strip().startswith(("{", "[")) else value
                    if isinstance(parsed, dict):
                        merged.standalone_summaries = {str(k): str(v) for k, v in parsed.items()}
                    else:
                        # 不是 dict 时尝试按行解析 "源: 概括" 简写
                        merged.standalone_summaries = {f"源{i+1}": line.strip() for i, line in enumerate(value.splitlines()) if line.strip()}
                except Exception:
                    merged.standalone_summaries = {f"源{i+1}": line.strip() for i, line in enumerate(value.splitlines()) if line.strip()}
            else:
                setattr(merged, key, value)

        merged.raw_response = "\n\n".join(
            f"[{key}]\n{value}" for key, value in board_results.items()
        )
        return merged

    def _retry_fix_json(self, original_response: str, error_msg: str) -> Optional[AIAnalysisResult]:
        """
        JSON 解析失败时，请求 AI 修复 JSON（仅重试一次）

        使用轻量 prompt，不重复原始分析的 system prompt，节省 token。

        Args:
            original_response: AI 原始响应（JSON 格式有误）
            error_msg: JSON 解析的错误信息

        Returns:
            修复后的分析结果，失败时返回 None
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个 JSON 修复助手。用户会提供一段格式有误的 JSON 和错误信息，"
                    "你需要修复 JSON 格式错误并返回正确的 JSON。\n"
                    "常见问题：字符串值内的双引号未转义、缺少逗号、字符串未正确闭合等。\n"
                    "只返回纯 JSON，不要包含 markdown 代码块标记（如 ```json）或任何说明文字。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"以下 JSON 解析失败：\n\n"
                    f"错误：{error_msg}\n\n"
                    f"原始内容：\n{original_response}\n\n"
                    f"请修复以上 JSON 中的格式问题（如值中的双引号改用中文引号「」或转义 \\\"、"
                    f"缺少逗号、不完整的字符串等），保持原始内容语义不变，只修复格式。"
                    f"直接返回修复后的纯 JSON。"
                ),
            },
        ]

        try:
            response = self.client.chat(messages)
            return self._parse_response(response)
        except Exception as e:
            print(f"[AI] 重试修复 JSON 异常: {type(e).__name__}: {e}")
            return None

    def _format_time_range(self, first_time: str, last_time: str) -> str:
        """格式化时间范围（简化显示，只保留时分）"""
        def extract_time(time_str: str) -> str:
            if not time_str:
                return "-"
            # 尝试提取 HH:MM 部分
            if " " in time_str:
                parts = time_str.split(" ")
                if len(parts) >= 2:
                    time_part = parts[1]
                    if ":" in time_part:
                        return time_part[:5]  # HH:MM
            elif ":" in time_str:
                return time_str[:5]
            # 处理 HH-MM 格式
            result = time_str[:5] if len(time_str) >= 5 else time_str
            if len(result) == 5 and result[2] == '-':
                result = result.replace('-', ':')
            return result

        first = extract_time(first_time)
        last = extract_time(last_time)

        if first == last or last == "-":
            return first
        return f"{first}~{last}"

    def _format_rank_timeline(self, rank_timeline: List[Dict]) -> str:
        """格式化排名时间线"""
        if not rank_timeline:
            return "-"

        parts = []
        for item in rank_timeline:
            time_str = item.get("time", "")
            if len(time_str) == 5 and time_str[2] == '-':
                time_str = time_str.replace('-', ':')
            rank = item.get("rank")
            if rank is None:
                parts.append(f"0({time_str})")
            else:
                parts.append(f"{rank}({time_str})")

        return "→".join(parts)

    def _prepare_standalone_content(self, standalone_data: Dict) -> tuple:
        """
        将独立展示区数据转为文本，注入 AI 分析 prompt

        Args:
            standalone_data: 独立展示区数据 {"platforms": [...], "rss_feeds": [...]}

        Returns:
            tuple: (格式化的文本内容, 独立展示区条目数)
        """
        lines = []

        # 热榜平台
        for platform in standalone_data.get("platforms", []):
            platform_id = platform.get("id", "")
            platform_name = platform.get("name", platform_id)
            items = platform.get("items", [])
            if not items:
                continue

            lines.append(f"### [{platform_name}]")
            for item in items:
                title = item.get("title", "")
                if not title:
                    continue

                line = f"- {title}"

                # 排名信息
                ranks = item.get("ranks", [])
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)
                    rank_str = f"{min_rank}" if min_rank == max_rank else f"{min_rank}-{max_rank}"
                    line += f" | 排名:{rank_str}"

                # 时间范围
                first_time = item.get("first_time", "")
                last_time = item.get("last_time", "")
                if first_time:
                    time_str = self._format_time_range(first_time, last_time)
                    line += f" | 时间:{time_str}"

                # 出现次数
                count = item.get("count", 1)
                if count > 1:
                    line += f" | 出现:{count}次"

                # 排名轨迹（如果启用）
                if self.include_rank_timeline:
                    rank_timeline = item.get("rank_timeline", [])
                    if rank_timeline:
                        timeline_str = self._format_rank_timeline(rank_timeline)
                        line += f" | 轨迹:{timeline_str}"

                lines.append(line)
            lines.append("")

        # RSS 源
        for feed in standalone_data.get("rss_feeds", []):
            feed_id = feed.get("id", "")
            feed_name = feed.get("name", feed_id)
            items = feed.get("items", [])
            if not items:
                continue

            lines.append(f"### [{feed_name}]")
            for item in items:
                title = item.get("title", "")
                if not title:
                    continue

                line = f"- {title}"
                published_at = item.get("published_at", "")
                if published_at:
                    line += f" | {published_at}"

                lines.append(line)
            lines.append("")

        standalone_count = sum(
            len(p.get("items", [])) for p in standalone_data.get("platforms", [])
        ) + sum(
            len(f.get("items", [])) for f in standalone_data.get("rss_feeds", [])
        )
        return "\n".join(lines), standalone_count

    def _parse_response(self, response: str) -> AIAnalysisResult:
        """解析 AI 响应"""
        result = AIAnalysisResult(raw_response=response)

        if not response or not response.strip():
            result.error = "AI 返回空响应"
            return result

        # 提取 JSON 文本（去掉 markdown 代码块标记）
        json_str = response

        if "```json" in response:
            parts = response.split("```json", 1)
            if len(parts) > 1:
                code_block = parts[1]
                end_idx = code_block.find("```")
                if end_idx != -1:
                    json_str = code_block[:end_idx]
                else:
                    json_str = code_block
        elif "```" in response:
            parts = response.split("```", 2)
            if len(parts) >= 2:
                json_str = parts[1]

        json_str = json_str.strip()
        if not json_str:
            result.error = "提取的 JSON 内容为空"
            result.core_trends = response[:500] + "..." if len(response) > 500 else response
            result.success = True
            return result

        # 第一步：标准 JSON 解析
        data = None
        parse_error = None

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            parse_error = e

        # 第二步：json_repair 本地修复
        if data is None:
            try:
                from json_repair import repair_json
                repaired = repair_json(json_str, return_objects=True)
                if isinstance(repaired, dict):
                    data = repaired
                    print("[AI] JSON 本地修复成功（json_repair）")
            except Exception:
                pass

        # 两步都失败，记录错误（后续由 analyze 方法的重试机制处理）
        if data is None:
            if parse_error:
                error_context = json_str[max(0, parse_error.pos - 30):parse_error.pos + 30] if json_str and parse_error.pos else ""
                result.error = f"JSON 解析错误 (位置 {parse_error.pos}): {parse_error.msg}"
                if error_context:
                    result.error += f"，上下文: ...{error_context}..."
            else:
                result.error = "JSON 解析失败"
            # 兜底：使用已提取的 json_str（不含 markdown 标记），避免推送中出现 ```json
            result.core_trends = json_str[:500] + "..." if len(json_str) > 500 else json_str
            result.success = True
            return result

        # 解析成功，提取字段
        try:
            result.core_trends = data.get("core_trends", "")
            result.sentiment_controversy = data.get("sentiment_controversy", "")
            result.signals = data.get("signals", "")
            result.rss_insights = data.get("rss_insights", "")
            result.outlook_strategy = data.get("outlook_strategy", "")

            # 解析独立展示区概括
            summaries = data.get("standalone_summaries", {})
            if isinstance(summaries, dict):
                result.standalone_summaries = {
                    str(k): str(v) for k, v in summaries.items()
                }

            result.success = True
        except (KeyError, TypeError, AttributeError) as e:
            result.error = f"字段提取错误: {type(e).__name__}: {e}"
            result.core_trends = json_str[:500] + "..." if len(json_str) > 500 else json_str
            result.success = True

        return result
