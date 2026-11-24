"""Provider-Agnostic LLM Gateway using pure Adapter Pattern over httpx."""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from src.core.config_manager import DEFAULT_BASE_URLS


T = TypeVar("T", bound=BaseModel)


class LLMGatewayError(RuntimeError):
    """Raised when an LLM provider call fails or returns invalid structured output."""


@dataclass
class LLMCallConfig:
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.2
    max_tokens: int = 3000
    timeout_seconds: float = 120.0
    max_retries: Optional[int] = None


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: Dict[str, Any]


def _post_with_retry(
    endpoint: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: float,
    provider: str,
    max_retries: int = 3,
) -> httpx.Response:
    """POST JSON payload with exponential backoff for 429 rate-limits (free tier friendly)."""
    backoff_schedule = (4.0, 10.0, 20.0)
    last_resp: Optional[httpx.Response] = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                resp = client.post(endpoint, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            if attempt < max_retries:
                time.sleep(backoff_schedule[min(attempt, len(backoff_schedule) - 1)])
                continue
            raise LLMGatewayError(f"[{provider}] 網路連線失敗 ({endpoint})：{exc}") from exc

        last_resp = resp
        if resp.status_code in (429, 503) and attempt < max_retries:
            retry_after = resp.headers.get("Retry-After", "").strip()
            delay = backoff_schedule[min(attempt, len(backoff_schedule) - 1)]
            if retry_after.isdigit():
                delay = min(max(float(retry_after), 2.0), 30.0)
            time.sleep(delay)
            continue
        return resp

    assert last_resp is not None
    return last_resp


def _extract_json_text(raw_text: str) -> str:
    """Strip markdown fences or surrounding commentary and extract valid JSON substring."""
    cleaned = raw_text.strip()

    # Remove <think>...</think> blocks emitted by reasoning models
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()

    # Match ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, flags=re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    # Find outermost balanced JSON object
    start = cleaned.find("{")
    if start == -1:
        return cleaned
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(cleaned)):
        ch = cleaned[idx]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return cleaned[start : idx + 1]
    return cleaned[start:]


class BaseLLMAdapter(ABC):
    """Abstract Adapter ensuring zero vendor lock-in inside Agent business logic."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        config: LLMCallConfig,
        json_mode: bool = False,
    ) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """Adapter for OpenAI, DeepSeek, Ollama (/v1), OpenRouter, Groq, and custom OpenAI-compatible APIs."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        config: LLMCallConfig,
        json_mode: bool = False,
    ) -> LLMResponse:
        base_url = (config.base_url or DEFAULT_BASE_URLS.get(config.provider, "https://api.openai.com/v1")).rstrip("/")
        if config.provider == "ollama" and not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        endpoint = f"{base_url}/chat/completions"

        api_key = config.api_key.strip().strip('"').strip("'")
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        elif config.provider != "ollama":
            raise LLMGatewayError(f"供應商 [{config.provider}] 尚未設定 API Key，請先至「API 與模型設定」填入。")

        is_reasoning_model = any(
            marker in config.model.lower()
            for marker in ("deepseek-reasoner", "o1", "o3", "o4-mini")
        )

        payload: Dict[str, Any] = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        if not is_reasoning_model:
            payload["temperature"] = config.temperature
            payload["max_tokens"] = config.max_tokens
        else:
            # Reasoning models typically reject temperature or prefer max_completion_tokens / max_tokens
            if config.provider == "deepseek":
                payload["max_tokens"] = max(config.max_tokens, 4096)
            else:
                payload["max_completion_tokens"] = max(config.max_tokens, 4096)

        if json_mode and not is_reasoning_model:
            payload["response_format"] = {"type": "json_object"}

        retries = 3 if config.max_retries is None else config.max_retries
        resp = _post_with_retry(
            endpoint, headers, payload, config.timeout_seconds, config.provider, max_retries=retries
        )

        if resp.status_code >= 400:
            # Retry once without response_format if an OpenAI-compatible server doesn't support it
            if resp.status_code == 400 and "response_format" in payload:
                payload.pop("response_format", None)
                resp = _post_with_retry(
                    endpoint, headers, payload, config.timeout_seconds, config.provider, max_retries=retries
                )

            if resp.status_code >= 400:
                raise LLMGatewayError(
                    f"[{config.provider}] API 回傳錯誤 {resp.status_code}：{resp.text[:500]}"
                )

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise LLMGatewayError(f"[{config.provider}] 回應缺少 choices 欄位：{str(data)[:400]}")

        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )

        return LLMResponse(
            text=str(content).strip(),
            provider=config.provider,
            model=config.model,
            usage=data.get("usage") or {},
        )


class AnthropicAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Claude Messages API (/v1/messages)."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        config: LLMCallConfig,
        json_mode: bool = False,
    ) -> LLMResponse:
        api_key = config.api_key.strip().strip('"').strip("'")
        if not api_key:
            raise LLMGatewayError("供應商 [anthropic] 尚未設定 API Key，請先至「API 與模型設定」填入。")

        base_url = (config.base_url or DEFAULT_BASE_URLS["anthropic"]).rstrip("/")
        endpoint = f"{base_url}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        payload: Dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        retries = 3 if config.max_retries is None else config.max_retries
        resp = _post_with_retry(
            endpoint, headers, payload, config.timeout_seconds, "anthropic", max_retries=retries
        )

        if resp.status_code >= 400:
            raise LLMGatewayError(f"[anthropic] API 回傳錯誤 {resp.status_code}：{resp.text[:500]}")

        data = resp.json()
        blocks = data.get("content") or []
        text_parts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
        text = "".join(text_parts).strip()
        if not text:
            raise LLMGatewayError(f"[anthropic] 未收到文字內容：{str(data)[:400]}")

        return LLMResponse(
            text=text,
            provider="anthropic",
            model=config.model,
            usage=data.get("usage") or {},
        )


class GeminiAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini Generative Language REST API (no vendor SDK lock-in)."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        config: LLMCallConfig,
        json_mode: bool = False,
    ) -> LLMResponse:
        api_key = config.api_key.strip().strip('"').strip("'")
        if not api_key:
            raise LLMGatewayError("供應商 [gemini] 尚未設定 API Key，請先至「API 與模型設定」填入。")

        base_url = (config.base_url or DEFAULT_BASE_URLS["gemini"]).rstrip("/")
        model_id = config.model.removeprefix("models/")
        endpoint = f"{base_url}/models/{model_id}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        is_gemma = "gemma" in model_id.lower()
        effective_max_tokens = config.max_tokens
        if any(ver in model_id.lower() for ver in ("2.5", "3.", "4.", "gemma-4")):
            effective_max_tokens = max(config.max_tokens, 8192)

        generation_config: Dict[str, Any] = {
            "temperature": config.temperature,
            "maxOutputTokens": effective_max_tokens,
        }
        if json_mode and not is_gemma:
            generation_config["responseMimeType"] = "application/json"

        if is_gemma:
            combined_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}" if system_prompt.strip() else user_prompt
            payload: Dict[str, Any] = {
                "contents": [{"role": "user", "parts": [{"text": combined_prompt}]}],
                "generationConfig": generation_config,
            }
        else:
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": generation_config,
            }

        retries = 3 if config.max_retries is None else config.max_retries
        resp = _post_with_retry(
            endpoint, headers, payload, config.timeout_seconds, "gemini", max_retries=retries
        )

        if resp.status_code == 429:
            raise LLMGatewayError(
                "[gemini] 免費版 API 觸發頻率限制 (429 Too Many Requests)，已自動重試仍超限。請稍候 30 秒再試，或切換模型。"
            )
        if resp.status_code >= 400:
            err_detail = resp.text[:600]
            try:
                err_json = resp.json()
                err_msg = (err_json.get("error") or {}).get("message")
                if err_msg:
                    err_detail = err_msg
            except Exception:
                pass

            if resp.status_code == 403:
                raise LLMGatewayError(
                    f"[gemini] API 回傳 403 權限拒絕：{err_detail}\n\n"
                    "常見原因與解法：\n"
                    "1. 若是在 Google Cloud Console 建立的 Key，請確認該專案已啟用「Generative Language API」。\n"
                    "2. 請檢查該 API Key 是否設定了「網站 (HTTP referrers)」限制（桌面程式無 Referer 會被擋，請改為「無限制」或僅限 Generative Language API）。\n"
                    "3. 若您使用學校 (.edu.tw) 或企業 Workspace 帳號，管理員可能封鎖了 Gemini API，請改用個人 @gmail.com 帳號到 https://aistudio.google.com/apikey 選擇「Create API key in new project」重新建立。\n"
                    "4. 若所在地區／VPN 受限，或剛啟用 API 尚未生效（需等 1~2 分鐘），請稍候重試。"
                )

            raise LLMGatewayError(f"[gemini] API 回傳錯誤 {resp.status_code}：{err_detail}")

        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMGatewayError(f"[gemini] 回應缺少 candidates：{str(data)[:400]}")

        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        if not text:
            raise LLMGatewayError(f"[gemini] 未收到文字內容：{str(data)[:400]}")

        return LLMResponse(
            text=text,
            provider="gemini",
            model=config.model,
            usage=data.get("usageMetadata") or {},
        )


class LLMGateway:
    """Unified provider-agnostic router used by all Agents."""

    def __init__(self) -> None:
        openai_compat = OpenAICompatibleAdapter()
        self._adapters: Dict[str, BaseLLMAdapter] = {
            "openai": openai_compat,
            "deepseek": openai_compat,
            "ollama": openai_compat,
            "openai_compatible": openai_compat,
            "anthropic": AnthropicAdapter(),
            "gemini": GeminiAdapter(),
        }

    def _resolve_adapter(self, provider: str) -> BaseLLMAdapter:
        adapter = self._adapters.get(provider.lower())
        if adapter is None:
            raise LLMGatewayError(f"不支援的 LLM 供應商：{provider}")
        return adapter

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        config: LLMCallConfig,
    ) -> LLMResponse:
        adapter = self._resolve_adapter(config.provider)
        return adapter.complete(system_prompt, user_prompt, config, json_mode=False)

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_cls: Type[T],
        config: LLMCallConfig,
        max_retries: int = 2,
    ) -> T:
        adapter = self._resolve_adapter(config.provider)
        schema_json = json.dumps(schema_cls.model_json_schema(), ensure_ascii=False, indent=2)

        structured_system = (
            f"{system_prompt}\n\n"
            "【嚴格輸出格式要求】\n"
            "你必須只輸出一個合法的 JSON 物件，禁止任何 Markdown 說明文字或前後綴。\n"
            "輸出必須完全符合以下 JSON Schema（包含欄位名稱、型別與列舉值）：\n"
            f"{schema_json}"
        )

        current_prompt = user_prompt
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            response = adapter.complete(
                structured_system,
                current_prompt,
                config,
                json_mode=True,
            )
            extracted = _extract_json_text(response.text)
            try:
                return schema_cls.model_validate_json(extracted)
            except (ValidationError, ValueError) as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                current_prompt = (
                    f"{user_prompt}\n\n"
                    f"【系統校正提醒（第 {attempt + 1} 次）】\n"
                    f"你前一次輸出的 JSON 驗證失敗，錯誤原因：\n{exc}\n\n"
                    f"前次輸出片段：\n{extracted[:1200]}\n\n"
                    "請修正欄位格式與型別，只輸出合法 JSON。"
                )

        raise LLMGatewayError(
            f"[{config.provider}/{config.model}] 無法產出符合 {schema_cls.__name__} 的 JSON：{last_error}"
        )

    def test_connection(self, config: LLMCallConfig) -> Tuple[bool, str]:
        try:
            resp = self.generate_text(
                system_prompt="You are a connection health check assistant.",
                user_prompt="Reply with exact word: OK",
                config=LLMCallConfig(
                    provider=config.provider,
                    model=config.model,
                    api_key=config.api_key,
                    base_url=config.base_url,
                    temperature=0.0,
                    max_tokens=64,
                    timeout_seconds=15.0,
                    max_retries=0,
                ),
            )
            return True, f"連線成功 ({config.provider} / {config.model}) -> 回應：{resp.text[:40]}"
        except Exception as exc:
            return False, str(exc)
