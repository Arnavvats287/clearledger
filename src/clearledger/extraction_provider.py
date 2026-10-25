"""Provider-neutral, bounded transport. Receives sanitized text only, no DB/tool capability."""

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from clearledger.document_contract import ExtractionError

PREFLIGHT_CODES = {
    "MODEL_NOT_AVAILABLE",
    "MODEL_NOT_SUPPORTED",
    "MODEL_LIMITS_UNAVAILABLE",
    "MODEL_OUTPUT_LIMIT",
    "PROVIDER_INPUT_LIMIT",
    "INVALID_TOKEN_COUNT",
}


@dataclass(frozen=True)
class ProviderReply:
    json_text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None
    validated_model: dict[str, object] | None = None
    counted_input_tokens: int | None = None


class Transport(Protocol):
    def generate(self, pages: list[str]) -> ProviderReply: ...


class ProviderFailure(Exception):
    def __init__(self, code: str, retryable: bool = False) -> None:
        self.code, self.retryable = code, retryable
        super().__init__(code)


class ProviderRunError(ExtractionError):
    def __init__(self, code: str, metrics: dict[str, object]) -> None:
        super().__init__(code)
        self.metrics = metrics


class FakeTransport:
    """Explicitly injected in tests; no heuristic fabricated extraction or network fallback."""

    def __init__(self, replies: list[ProviderReply | ProviderFailure]) -> None:
        self.replies = deque(replies)
        self.calls: list[list[str]] = []

    def generate(self, pages: list[str]) -> ProviderReply:
        self.calls.append(pages.copy())
        if not self.replies:
            raise ProviderFailure("FAKE_NO_RESULT")
        result = self.replies.popleft()
        if isinstance(result, ProviderFailure):
            raise result
        return result


class Gateway:
    def __init__(
        self,
        transport: Transport,
        *,
        requests_per_minute: int = 10,
        attempts: int = 2,
        input_rate: int | None = None,
        output_rate: int | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        max_input_tokens: int = 8192,
        max_output_tokens: int = 4096,
    ) -> None:
        if not 1 <= requests_per_minute <= 60 or not 1 <= attempts <= 3:
            raise ValueError("Invalid provider limits")
        if (
            type(max_input_tokens) is not int
            or not 1 <= max_input_tokens <= 1_000_000
            or type(max_output_tokens) is not int
            or not 1 <= max_output_tokens <= 4096
        ):
            raise ValueError("Invalid token limits")
        if any(
            rate is not None and (type(rate) is not int or not 0 <= rate <= 1_000_000_000)
            for rate in (input_rate, output_rate)
        ):
            raise ValueError("Invalid configured paise token rates")
        self.transport = transport
        self.rpm, self.attempts = requests_per_minute, attempts
        self.input_rate, self.output_rate = input_rate, output_rate
        self.clock, self.sleep = clock, sleep
        self.max_input_tokens, self.max_output_tokens = max_input_tokens, max_output_tokens
        self._times: deque[float] = deque()
        self._lock = threading.Lock()
        self._slot = threading.Semaphore(1)

    def generate(
        self,
        pages: list[str],
        *,
        before_attempt: Callable[[], dict[str, object]] | None = None,
    ) -> tuple[ProviderReply, dict[str, object]]:
        if not self._slot.acquire(blocking=False):
            raise ExtractionError("PROVIDER_BUSY")
        started = self.clock()
        attempts_started = 0
        reservations: list[dict[str, object]] = []
        try:
            for attempt in range(1, self.attempts + 1):
                now = self.clock()
                with self._lock:
                    while self._times and now - self._times[0] >= 60:
                        self._times.popleft()
                    if len(self._times) >= self.rpm:
                        raise ExtractionError("PROVIDER_RATE_LIMIT")
                    self._times.append(now)
                try:
                    if before_attempt is not None:
                        reservations.append(before_attempt())
                    attempts_started += 1
                    reply = self.transport.generate(pages)
                    if len(reply.json_text.encode()) > 100_000:
                        raise ExtractionError("PROVIDER_OUTPUT_LIMIT")
                    for count in (
                        reply.input_tokens,
                        reply.output_tokens,
                        reply.total_tokens,
                        reply.reasoning_tokens,
                        reply.cached_input_tokens,
                    ):
                        if count is not None and (
                            type(count) is not int or not 0 <= count <= 1_000_000
                        ):
                            raise ExtractionError("INVALID_USAGE_METADATA")
                    if (
                        reply.input_tokens is not None
                        and reply.input_tokens > self.max_input_tokens
                        or reply.output_tokens is not None
                        and reply.output_tokens > self.max_output_tokens
                    ):
                        raise ExtractionError("PROVIDER_USAGE_EXCEEDS_RESERVATION")
                    cost = None
                    complete = (
                        attempt == 1
                        and reply.input_tokens is not None
                        and reply.output_tokens is not None
                        and (
                            reply.total_tokens is None
                            or reply.total_tokens == reply.input_tokens + reply.output_tokens
                        )
                    )
                    if (
                        complete
                        and reply.input_tokens is not None
                        and reply.output_tokens is not None
                        and self.input_rate is not None
                        and self.output_rate is not None
                    ):
                        cost = (
                            reply.input_tokens * self.input_rate
                            + reply.output_tokens * self.output_rate
                            + 999_999
                        ) // 1_000_000
                    return reply, {
                        "attempts": attempt,
                        "latency_ms": int((self.clock() - started) * 1000),
                        "input_tokens": reply.input_tokens,
                        "output_tokens": reply.output_tokens,
                        "usage_complete": complete,
                        "total_tokens": reply.total_tokens,
                        "reasoning_tokens": reply.reasoning_tokens,
                        "cached_input_tokens": reply.cached_input_tokens,
                        "estimated_cost_paise": cost,
                        "budget_reservations": reservations,
                        "validated_model": reply.validated_model,
                        "counted_input_tokens": reply.counted_input_tokens,
                    }
                except ProviderFailure as error:
                    if not error.retryable or attempt == self.attempts:
                        raise ExtractionError(
                            error.code if error.code in PREFLIGHT_CODES else "PROVIDER_FAILED"
                        ) from None
                    self.sleep(0.1 * attempt)
            raise ExtractionError("PROVIDER_FAILED")
        except Exception as error:
            code = str(error) if isinstance(error, ExtractionError) else "PROVIDER_FAILED"
            raise ProviderRunError(
                code,
                {
                    "attempts": attempts_started,
                    "latency_ms": int((self.clock() - started) * 1000),
                    "input_tokens": None,
                    "output_tokens": None,
                    "estimated_cost_paise": None,
                    "usage_complete": False,
                    "budget_reservations": reservations,
                },
            ) from None
        finally:
            self._slot.release()


class GeminiTransport:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_ms: int = 10_000,
        *,
        max_input_tokens: int = 8192,
        max_output_tokens: int = 4096,
    ) -> None:
        import re

        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model) or not 100 <= timeout_ms <= 30_000:
            raise ValueError("Invalid Gemini configuration")
        self._key, self.model, self.timeout_ms = api_key, model, timeout_ms
        self.max_input_tokens, self.max_output_tokens = max_input_tokens, max_output_tokens

    def generate(self, pages: list[str]) -> ProviderReply:
        from clearledger.document_runtime import run_worker

        try:
            result = run_worker(
                "clearledger.gemini_worker",
                {
                    "key": self._key,
                    "model": self.model,
                    "timeout_ms": self.timeout_ms,
                    "pages": pages,
                    "max_input_tokens": self.max_input_tokens,
                    "max_output_tokens": self.max_output_tokens,
                },
                timeout=self.timeout_ms / 1000 + 3,
            )
        except ExtractionError:
            raise ProviderFailure("TRANSPORT_TIMEOUT", retryable=True) from None
        if result.get("error"):
            code = result["error"] if result["error"] in PREFLIGHT_CODES else "GEMINI_FAILURE"
            raise ProviderFailure(code, retryable=bool(result.get("retryable")))
        return ProviderReply(
            str(result["json_text"]),
            result.get("input_tokens"),
            result.get("output_tokens"),
            result.get("total_tokens"),
            result.get("reasoning_tokens"),
            result.get("cached_input_tokens"),
            result.get("validated_model"),
            result.get("counted_input_tokens"),
        )


def decode_output(text: str) -> dict[str, Any]:
    # Reject repeated keys and non-JSON values instead of accepting last-wins model instructions.
    from clearledger.remittance_parser import unique_json

    try:
        result = unique_json(text)
        if not isinstance(result, dict):
            raise ValueError
        return cast(dict[str, Any], result)
    except (ValueError, TypeError, RecursionError, ExtractionError):
        raise ExtractionError("INVALID_MODEL_JSON") from None
