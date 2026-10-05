import os
import re
import time
import json
import random
import threading
from typing import Any, Dict, Optional, List
from groq import Groq
from backend.config import settings

# --- Typed Exceptions for FinSight LLM Operations ---

class FinSightLLMError(Exception):
    """Base exception for all FinSight LLM errors."""
    pass

class AuthenticationError(FinSightLLMError):
    """Raised when API credentials are missing, invalid, or unauthorized (401/403)."""
    pass

class RateLimitExhaustedError(FinSightLLMError):
    """Raised when rate limits or account quotas (TPD/RPD) are exhausted."""
    def __init__(self, message: str, reset_seconds: Optional[float] = None):
        super().__init__(message)
        self.reset_seconds = reset_seconds

class ProviderTemporaryError(FinSightLLMError):
    """Raised on transient provider issues (500, 503, connection timeouts)."""
    pass

class InvalidRequestError(FinSightLLMError):
    """Raised on malformed requests or invalid model arguments (400/422)."""
    pass

class LLMOutputParseError(FinSightLLMError):
    """Raised when LLM output cannot be parsed into expected format."""
    pass

class BudgetExceededError(FinSightLLMError):
    """Raised when report-level call or token budgets are exceeded."""
    pass

# --- Telemetry & Token Tracking ---

class ReportTelemetryTracker:
    """Thread-safe telemetry tracking per report run."""
    def __init__(self):
        self._lock = threading.Lock()
        self._runs: Dict[str, Dict[str, Any]] = {}

    def get_run_metrics(self, run_id: str) -> Dict[str, Any]:
        with self._lock:
            if run_id not in self._runs:
                self._runs[run_id] = {
                    "run_id": run_id,
                    "logical_calls": 0,
                    "http_requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "retries": 0,
                    "rate_limit_events": 0,
                    "failed_requests": 0,
                    "total_wait_duration_s": 0.0,
                    "calls_by_component": {},
                    "models_used": set(),
                    "finish_reasons": [],
                    "json_repairs": 0,
                    "fallbacks": 0,
                    "start_time": time.time(),
                    "active_model": settings.MODEL_PLANNER,
                    "fallback_active": False
                }
            res = dict(self._runs[run_id])
            res["models_used"] = list(res["models_used"])
            res["finish_reasons"] = list(res.get("finish_reasons", []))
            res["fallback_active"] = (res.get("fallbacks", 0) > 0)
            if res["fallback_active"]:
                res["active_model"] = settings.MODEL_FALLBACK
            elif res["models_used"]:
                res["active_model"] = res["models_used"][-1]
            else:
                res["active_model"] = settings.MODEL_PLANNER
            return res

    def get_active_model(self, run_id: Optional[str]) -> str:
        target_id = run_id or "global"
        with self._lock:
            if target_id not in self._runs:
                return settings.MODEL_PLANNER
            entry = self._runs[target_id]
            if entry.get("fallbacks", 0) > 0:
                return settings.MODEL_FALLBACK
            models = list(entry.get("models_used", []))
            if models:
                return models[-1]
            return settings.MODEL_PLANNER

    def record_http_request(self, run_id: Optional[str]):
        target_id = run_id or "global"
        with self._lock:
            if target_id not in self._runs:
                self._init_run_locked(target_id)
            self._runs[target_id]["http_requests"] += 1

    def record_failed_request(self, run_id: Optional[str]):
        target_id = run_id or "global"
        with self._lock:
            if target_id not in self._runs:
                self._init_run_locked(target_id)
            self._runs[target_id]["failed_requests"] += 1

    def record_json_repair(self, run_id: Optional[str]):
        target_id = run_id or "global"
        with self._lock:
            if target_id not in self._runs:
                self._init_run_locked(target_id)
            self._runs[target_id]["json_repairs"] += 1

    def record_fallback(self, run_id: Optional[str]):
        target_id = run_id or "global"
        with self._lock:
            if target_id not in self._runs:
                self._init_run_locked(target_id)
            self._runs[target_id]["fallbacks"] += 1
            self._runs[target_id]["fallback_active"] = True
            self._runs[target_id]["active_model"] = settings.MODEL_FALLBACK

    def _init_run_locked(self, target_id: str):
        self._runs[target_id] = {
            "run_id": target_id,
            "logical_calls": 0,
            "http_requests": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "retries": 0,
            "rate_limit_events": 0,
            "failed_requests": 0,
            "total_wait_duration_s": 0.0,
            "calls_by_component": {},
            "models_used": set(),
            "finish_reasons": [],
            "json_repairs": 0,
            "fallbacks": 0,
            "start_time": time.time(),
            "active_model": settings.MODEL_PLANNER,
            "fallback_active": False
        }

    def record_call(
        self,
        run_id: Optional[str],
        component: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_s: float,
        is_retry: bool = False,
        is_429: bool = False,
        wait_s: float = 0.0,
        finish_reason: Optional[str] = None
    ):
        target_id = run_id or "global"
        with self._lock:
            if target_id not in self._runs:
                self._init_run_locked(target_id)
            entry = self._runs[target_id]
            if not is_retry:
                entry["logical_calls"] += 1
            else:
                entry["retries"] += 1
            
            if is_429:
                entry["rate_limit_events"] += 1
                entry["total_wait_duration_s"] += wait_s

            entry["prompt_tokens"] += prompt_tokens
            entry["completion_tokens"] += completion_tokens
            entry["total_tokens"] += (prompt_tokens + completion_tokens)
            entry["models_used"].add(model)
            entry["calls_by_component"][component] = entry["calls_by_component"].get(component, 0) + 1
            entry["active_model"] = model
            if finish_reason:
                entry["finish_reasons"].append(finish_reason)

telemetry_tracker = ReportTelemetryTracker()

# --- Provider Client Management ---

_groq_client = None
_client_lock = threading.Lock()

def get_groq_client() -> Groq:
    global _groq_client
    with self_lock if 'self_lock' in globals() else _client_lock:
        if _groq_client is None:
            key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
            if not key or key.strip() == "":
                raise AuthenticationError(
                    "Missing GROQ_API_KEY. Please set GROQ_API_KEY in your .env or environment. "
                    "Gemini API keys cannot be used for Groq requests."
                )
            _groq_client = Groq(api_key=key.strip())
    return _groq_client

# Provider-aware rate limiter state
_last_call_time = 0.0
_limiter_lock = threading.Lock()
_MIN_CALL_INTERVAL = 0.15

# Default component token budgets (tuned for low-latency and on-demand OTPM quotas)
COMPONENT_TOKEN_BUDGETS = {
    "planner": 1200,
    "gap_fill": 800,
    "risk": 1500,
    "synthesis": 1200,
    "critic": 1200,
    "replanner": 800,
    "general": 1000
}

def call_llm(
    prompt: str,
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    max_retries: Optional[int] = None,
    max_tokens: Optional[int] = None,
    run_id: Optional[str] = None,
    component: Optional[str] = None,
    return_metadata: bool = False
) -> Any:
    """
    Centralized Groq LLM Invocation with:
    - Primary model (120b/20b) with automatic fallback to Qwen (qwen3.8-27b) on rate limit (429/TPD)
    - Per-run call budget checked for all components
    - Detailed HTTP request, logical call, retry, failed request, and token telemetry
    - Provider finish reason recording and inspection
    """
    global _last_call_time

    comp_name = component or "general"
    target_model = model or settings.MODEL_PLANNER
    current_model = target_model
    client = get_groq_client()

    # Verify per-run logical call budget across ALL components
    if run_id:
        current_metrics = telemetry_tracker.get_run_metrics(run_id)
        if current_metrics["logical_calls"] >= settings.MAX_LLM_CALLS_PER_RUN:
            raise BudgetExceededError(
                f"Run {run_id} exceeded maximum LLM call budget of {settings.MAX_LLM_CALLS_PER_RUN} calls."
            )

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    # Token budget calculation
    effective_max_tokens = max_tokens or COMPONENT_TOKEN_BUDGETS.get(comp_name, 600)
    if "qwen" in current_model.lower():
        effective_max_tokens = min(effective_max_tokens, 1500)
    retries_allowed = max_retries if max_retries is not None else settings.LLM_CLIENT_MAX_RETRIES

    attempt = 0
    while attempt <= retries_allowed:
        with _limiter_lock:
            elapsed = time.time() - _last_call_time
            if elapsed < _MIN_CALL_INTERVAL:
                time.sleep(_MIN_CALL_INTERVAL - elapsed)
            _last_call_time = time.time()

        telemetry_tracker.record_http_request(run_id)
        t_start = time.time()
        try:
            response = client.chat.completions.create(
                model=current_model,
                messages=messages,
                temperature=0.1,
                max_tokens=effective_max_tokens
            )
            latency = time.time() - t_start

            prompt_tokens = 0
            completion_tokens = 0
            if response and hasattr(response, "usage") and response.usage:
                prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
                completion_tokens = getattr(response.usage, "completion_tokens", 0) or 0

            finish_reason = "stop"
            content = ""
            if response and response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                finish_reason = getattr(choice, "finish_reason", "stop") or "stop"
                if choice.message and choice.message.content:
                    content = choice.message.content.strip()

            is_fallback_active = (current_model == settings.MODEL_FALLBACK)
            
            # Trace and log model ID, requested output-token limit, finish reason, response length, and fallback activation
            print(
                f"[LLM Trace] run_id={run_id or 'global'} | comp={comp_name} | model={current_model} | "
                f"max_tokens={effective_max_tokens} | finish_reason={finish_reason} | "
                f"chars={len(content)} | fallback={is_fallback_active}"
            )

            # Requirement 1: Correctly handle empty response content - do not silently treat as success
            if not content:
                if current_model != settings.MODEL_FALLBACK:
                    print(f"Empty content received from {current_model}. Activating fallback to {settings.MODEL_FALLBACK}.")
                    telemetry_tracker.record_fallback(run_id)
                    current_model = settings.MODEL_FALLBACK
                    if "qwen" in current_model.lower():
                        effective_max_tokens = min(effective_max_tokens, 1500)
                    time.sleep(0.5)
                    attempt += 1
                    continue
                else:
                    raise LLMOutputParseError(f"Model {current_model} returned empty response content (finish_reason={finish_reason}).")

            # Requirement 1: Handle finish_reason="length" - do not silently treat incomplete output as complete
            if finish_reason == "length":
                print(f"[LLM Notice] Output truncated (finish_reason='length') from {current_model} for {comp_name}. Requested max_tokens={effective_max_tokens}.")

            telemetry_tracker.record_call(
                run_id=run_id,
                component=comp_name,
                model=current_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_s=latency,
                is_retry=(attempt > 0),
                finish_reason=finish_reason
            )

            if return_metadata:
                return content, {
                    "finish_reason": finish_reason,
                    "model": current_model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "is_truncated": (finish_reason == "length"),
                    "is_fallback": is_fallback_active
                }
            return content

        except Exception as e:
            latency = time.time() - t_start
            err_str = str(e).lower()
            telemetry_tracker.record_failed_request(run_id)

            # Permanent Authentication / Authorization errors (Do NOT retry)
            if "401" in err_str or "unauthorized" in err_str or "invalid api key" in err_str:
                raise AuthenticationError(f"Authentication failed with provider: {e}") from e

            # Permanent Bad Request / Invalid Parameter errors (Do NOT retry)
            if "400" in err_str or "invalid_request" in err_str or "model_not_found" in err_str:
                raise InvalidRequestError(f"Invalid model request parameters: {e}") from e

            # Rate Limit / Quota Exhaustion (429)
            if "429" in err_str or "rate_limit" in err_str or "tokens per day" in err_str or "tpd" in err_str:
                is_daily_quota = ("tpd" in err_str or "tokens per day" in err_str or "limit 200000" in err_str)
                
                wait_sec = 2.0
                match = re.search(r"try again in ([\d\.]+)s", err_str)
                if match:
                    wait_sec = float(match.group(1))
                elif "m" in err_str and "s" in err_str:
                    m_match = re.search(r"in (\d+)m([\d\.]+)s", err_str)
                    if m_match:
                        wait_sec = float(m_match.group(1)) * 60 + float(m_match.group(2))

                telemetry_tracker.record_call(
                    run_id=run_id,
                    component=comp_name,
                    model=current_model,
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_s=latency,
                    is_retry=(attempt > 0),
                    is_429=True,
                    wait_s=wait_sec
                )

                # Fallback Ladder: if primary model (120b or 20b) hits rate limit or quota, fall back to Qwen
                # Do not retry identical prompts repeatedly against saturated primary model
                if current_model != settings.MODEL_FALLBACK:
                    print(f"Rate limit / quota reached for primary model {current_model}. Activating fallback to {settings.MODEL_FALLBACK}.")
                    telemetry_tracker.record_fallback(run_id)
                    current_model = settings.MODEL_FALLBACK
                    if "qwen" in current_model.lower():
                        effective_max_tokens = min(effective_max_tokens, 1500)
                    time.sleep(0.5)
                    attempt += 1
                    continue
                else:
                    # Saturated fallback model - do not retry repeatedly
                    raise RateLimitExhaustedError(
                        f"Provider quota / rate limit exhausted on fallback model {current_model}: {e}",
                        reset_seconds=wait_sec
                    ) from e

            # Transient Provider Error (500, 502, 503, 504, timeout, connection)
            if attempt < retries_allowed and any(code in err_str for code in ["500", "502", "503", "504", "timeout", "connection"]):
                backoff = (1.5 ** attempt) + random.uniform(0.2, 0.6)
                time.sleep(backoff)
                attempt += 1
                continue

            # Non-retryable or retries exhausted
            raise ProviderTemporaryError(f"Provider request failed ({current_model}): {e}") from e

    raise ProviderTemporaryError(f"Exhausted retries ({retries_allowed}) calling model {current_model}")

def call_gemini(
    prompt: str,
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    max_retries: Optional[int] = None,
    max_tokens: Optional[int] = None,
    run_id: Optional[str] = None,
    component: Optional[str] = None,
    return_metadata: bool = False
) -> Any:
    """Alias for backwards compatibility with existing agent code."""
    return call_llm(
        prompt=prompt,
        system_instruction=system_instruction,
        model=model,
        max_retries=max_retries,
        max_tokens=max_tokens,
        run_id=run_id,
        component=component,
        return_metadata=return_metadata
    )

def extract_json_from_llm(text: str, run_id: Optional[str] = None) -> Any:
    """Robustly extracts and parses JSON from LLM markdown output with repair tracking."""
    if not text or not text.strip():
        raise LLMOutputParseError("Cannot parse JSON from empty LLM response.")

    # Strip <think>...</think> reasoning blocks if present from models like Qwen/DeepSeek
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        raw_json = match.group(1).strip()
    else:
        brace_start = text.find("{")
        bracket_start = text.find("[")
        if brace_start != -1 and (bracket_start == -1 or brace_start < bracket_start):
            brace_end = text.rfind("}")
            raw_json = text[brace_start:brace_end + 1] if brace_end != -1 else text
        elif bracket_start != -1:
            bracket_end = text.rfind("]")
            raw_json = text[bracket_start:bracket_end + 1] if bracket_end != -1 else text
        else:
            raw_json = text

    # 1. Standard attempt
    try:
        return json.loads(raw_json)
    except Exception:
        pass

    # Repaired attempts — record repair in telemetry
    # 2. Strip invalid backslash escapes and trailing commas
    try:
        cleaned = re.sub(r'\\([^"\\/bfnrtu])', r'\1', raw_json)
        cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
        parsed = json.loads(cleaned)
        telemetry_tracker.record_json_repair(run_id)
        return parsed
    except Exception:
        pass

    # 3. Clean raw control characters/newlines inside strings
    try:
        cleaned = re.sub(r'[\r\n]+', ' ', raw_json)
        cleaned = re.sub(r'\\([^"\\/bfnrtu])', r'\1', cleaned)
        cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
        parsed = json.loads(cleaned)
        telemetry_tracker.record_json_repair(run_id)
        return parsed
    except Exception:
        pass

    # 4. Repair truncated JSON (unclosed quote, unbalanced braces/brackets)
    try:
        candidate = raw_json
        # Remove trailing incomplete key-value or dangling comma
        candidate = re.sub(r',\s*"[^"]*"?\s*:?\s*"?[^"]*$', '', candidate)
        if candidate.count('"') % 2 != 0:
            candidate += '"'
        open_braces = candidate.count('{') - candidate.count('}')
        open_brackets = candidate.count('[') - candidate.count(']')
        candidate += (']' * max(0, open_brackets)) + ('}' * max(0, open_braces))
        parsed = json.loads(candidate)
        telemetry_tracker.record_json_repair(run_id)
        return parsed
    except Exception as e:
        raise LLMOutputParseError(f"Could not parse JSON from LLM: {e}")
