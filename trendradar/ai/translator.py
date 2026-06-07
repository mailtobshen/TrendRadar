# coding=utf-8
"""
AI 翻译器模块

对推送内容进行多语言翻译
基于 LiteLLM 统一接口，支持 100+ AI 提供商
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from trendradar.ai.client import AIClient
from trendradar.ai.prompt_loader import load_prompt_template


@dataclass
class TranslationResult:
    """翻译结果"""
    translated_text: str = ""       # 翻译后的文本
    original_text: str = ""         # 原始文本
    success: bool = False           # 是否成功
    error: str = ""                 # 错误信息


@dataclass
class BatchTranslationResult:
    """批量翻译结果"""
    results: List[TranslationResult] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0
    total_count: int = 0
    prompt: str = ""                # debug: 发送给 AI 的完整 prompt
    raw_response: str = ""          # debug: AI 原始响应
    parsed_count: int = 0           # debug: AI 响应解析出的条目数


class AITranslator:
    """AI 翻译器"""

    def __init__(self, translation_config: Dict[str, Any], ai_config: Dict[str, Any]):
        """
        初始化 AI 翻译器

        Args:
            translation_config: AI 翻译配置 (AI_TRANSLATION)
            ai_config: AI 模型配置（LiteLLM 格式）
        """
        self.translation_config = translation_config
        self.ai_config = ai_config

        # 翻译配置
        self.enabled = translation_config.get("ENABLED", False)
        self.target_language = translation_config.get("LANGUAGE", "English")
        self.scope = translation_config.get("SCOPE", {"HOTLIST": True, "RSS": True, "STANDALONE": True})
        # 每批翻译条数上限：避免单次 prompt 过大导致 AI 输出截断
        self.batch_size = max(1, int(translation_config.get("BATCH_SIZE", 30)))

        # 创建 AI 客户端（基于 LiteLLM）
        self.client = AIClient(ai_config)

        # 加载提示词模板
        self.system_prompt, self.user_prompt_template = load_prompt_template(
            translation_config.get("PROMPT_FILE", "ai_translation_prompt.txt"),
            label="翻译",
        )

    def translate(self, text: str) -> TranslationResult:
        """
        翻译单条文本

        Args:
            text: 要翻译的文本

        Returns:
            TranslationResult: 翻译结果
        """
        result = TranslationResult(original_text=text)

        if not self.enabled:
            result.error = "翻译功能未启用"
            return result

        if not self.client.api_key:
            result.error = "未配置 AI API Key"
            return result

        if not text or not text.strip():
            result.translated_text = text
            result.success = True
            return result

        try:
            # 构建提示词
            user_prompt = self.user_prompt_template
            user_prompt = user_prompt.replace("{target_language}", self.target_language)
            user_prompt = user_prompt.replace("{content}", text)

            # 调用 AI API
            response = self._call_ai(user_prompt)
            result.translated_text = response.strip()
            result.success = True

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            result.error = f"翻译失败 ({error_type}): {error_msg}"

        return result

    def translate_batch(self, texts: List[str]) -> BatchTranslationResult:
        """
        批量翻译文本（按 self.batch_size 自动分批，避免单次 prompt 过大被截断）

        Args:
            texts: 要翻译的文本列表

        Returns:
            BatchTranslationResult: 批量翻译结果
        """
        batch_result = BatchTranslationResult(total_count=len(texts))

        if not self.enabled:
            for text in texts:
                batch_result.results.append(TranslationResult(
                    original_text=text,
                    error="翻译功能未启用"
                ))
            batch_result.fail_count = len(texts)
            return batch_result

        if not self.client.api_key:
            for text in texts:
                batch_result.results.append(TranslationResult(
                    original_text=text,
                    error="未配置 AI API Key"
                ))
            batch_result.fail_count = len(texts)
            return batch_result

        if not texts:
            return batch_result

        # 过滤空文本
        non_empty_indices = []
        non_empty_texts = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_indices.append(i)
                non_empty_texts.append(text)

        # 初始化结果列表
        for text in texts:
            batch_result.results.append(TranslationResult(original_text=text))

        # 空文本直接标记成功
        for i, text in enumerate(texts):
            if not text or not text.strip():
                batch_result.results[i].translated_text = text
                batch_result.results[i].success = True
                batch_result.success_count += 1

        if not non_empty_texts:
            return batch_result

        # 按 batch_size 分批调用（避免 AI 输出截断）
        import copy
        batch_size = max(1, self.batch_size)
        total_non_empty = len(non_empty_texts)
        if total_non_empty > batch_size:
            print(f"[翻译] 共 {total_non_empty} 条，分 {((total_non_empty + batch_size - 1) // batch_size)} 批发送（每批 {batch_size} 条）")

        for batch_start in range(0, total_non_empty, batch_size):
            batch_end = min(batch_start + batch_size, total_non_empty)
            batch_indices = non_empty_indices[batch_start:batch_end]
            batch_texts = non_empty_texts[batch_start:batch_end]
            self._translate_one_chunk(
                batch_texts, batch_indices, batch_result,
                batch_no=batch_start // batch_size + 1,
                total_batches=(total_non_empty + batch_size - 1) // batch_size,
            )

        return batch_result

    def _translate_one_chunk(
        self,
        chunk_texts: List[str],
        chunk_indices: List[int],
        batch_result: BatchTranslationResult,
        batch_no: int = 1,
        total_batches: int = 1,
    ) -> None:
        """单批翻译的实际调用（内部使用，会填充 batch_result）"""
        try:
            # 构建批量翻译内容（使用编号格式）
            batch_content = self._format_batch_content(chunk_texts)

            # 构建提示词
            user_prompt = self.user_prompt_template
            user_prompt = user_prompt.replace("{target_language}", self.target_language)
            user_prompt = user_prompt.replace("{content}", batch_content)

            # 记录 debug 信息（仅首条）
            if batch_no == 1:
                if self.system_prompt:
                    batch_result.prompt = f"[system]\n{self.system_prompt}\n\n[user]\n{user_prompt}"
                else:
                    batch_result.prompt = user_prompt

            # 调用 AI API
            response = self._call_ai(user_prompt)

            # 记录 AI 原始响应（仅首条；多条响应太长不记录）
            if batch_no == 1:
                batch_result.raw_response = response

            # 解析批量翻译结果
            translated_texts, raw_parsed_count = self._parse_batch_response(response, len(chunk_texts))
            batch_result.parsed_count += raw_parsed_count

            # 诊断：parsed_count < 期望时打印 AI 响应尾部
            if raw_parsed_count < len(chunk_texts):
                print(f"[翻译][DEBUG] 批 {batch_no}/{total_batches} AI 解析 {raw_parsed_count}/{len(chunk_texts)} 条；响应尾部 500 字符: ...{response[-500:]!r}")

            # 填充结果（跳过空翻译，避免用空字符串覆盖原始标题）
            for idx, translated in zip(chunk_indices, translated_texts):
                if translated and translated.strip():
                    original = batch_result.results[idx].original_text or ""
                    # 关键：若翻译 == 原文（AI 把英文标题原样返回 / 把中文标题原样返回），
                    # 视为失败，避免 dispatcher 误判为"已翻译"但实际显示未翻译的内容
                    if translated.strip() == original.strip():
                        batch_result.results[idx].error = "AI 返回原文未翻译"
                        batch_result.fail_count += 1
                    else:
                        batch_result.results[idx].translated_text = translated
                        batch_result.results[idx].success = True
                        batch_result.success_count += 1
                else:
                    batch_result.results[idx].error = "AI 未返回该条翻译"
                    batch_result.fail_count += 1

        except Exception as e:
            error_msg = f"批量翻译失败: {type(e).__name__}: {str(e)[:100]}"
            for idx in chunk_indices:
                batch_result.results[idx].error = error_msg
            batch_result.fail_count += len(chunk_indices)

    def _format_batch_content(self, texts: List[str]) -> str:
        """格式化批量翻译内容"""
        lines = []
        for i, text in enumerate(texts, 1):
            lines.append(f"[{i}] {text}")
        return "\n".join(lines)

    def _parse_batch_response(self, response: str, expected_count: int) -> tuple:
        """
        解析批量翻译响应

        Args:
            response: AI 响应文本
            expected_count: 期望的翻译数量

        Returns:
            tuple: (翻译结果列表, AI 原始解析出的条目数)
        """
        results = []
        lines = response.strip().split("\n")

        current_idx = None
        current_text = []

        for line in lines:
            # 尝试匹配 [数字] 格式
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                bracket_end = stripped.index("]")
                try:
                    idx = int(stripped[1:bracket_end])
                    # 保存之前的内容
                    if current_idx is not None:
                        results.append((current_idx, "\n".join(current_text).strip()))
                    current_idx = idx
                    current_text = [stripped[bracket_end + 1:].strip()]
                except ValueError:
                    if current_idx is not None:
                        current_text.append(line)
            else:
                if current_idx is not None:
                    current_text.append(line)

        # 保存最后一条
        if current_idx is not None:
            results.append((current_idx, "\n".join(current_text).strip()))

        # 按索引排序并提取文本
        results.sort(key=lambda x: x[0])
        translated = [text for _, text in results]
        raw_parsed_count = len(translated)

        # 如果解析结果数量不匹配，尝试简单按行分割
        if len(translated) != expected_count:
            # 回退：按行分割（去除编号）
            translated = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("[") and "]" in stripped:
                    bracket_end = stripped.index("]")
                    translated.append(stripped[bracket_end + 1:].strip())
                elif stripped:
                    translated.append(stripped)
            raw_parsed_count = len(translated)

        # 确保返回正确数量
        while len(translated) < expected_count:
            translated.append("")

        return translated[:expected_count], raw_parsed_count

    def _call_ai(self, user_prompt: str) -> str:
        """调用 AI API（使用 LiteLLM）"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        return self.client.chat(messages)
