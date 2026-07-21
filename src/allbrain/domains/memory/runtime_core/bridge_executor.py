from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from time import perf_counter

from pydantic import BaseModel, ValidationError

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="allbrain-bridge")


def execute_bridge[BridgeModel: BaseModel](
    call: Callable[[], object],
    *,
    fallback: Callable[[], object],
    model_type: type[BridgeModel],
    engine_id: str,
    timeout_ms: int,
) -> dict[str, object]:
    """Run and validate a bridge, falling back to a deterministic implementation."""
    started = perf_counter()
    future = _EXECUTOR.submit(call)
    reason: str | None = None
    try:
        raw = future.result(timeout=timeout_ms / 1000)
        result = model_type.model_validate(raw)
    except TimeoutError:
        future.cancel()
        reason = "timeout"
    except ValidationError:
        reason = "invalid_output"
    except Exception:  # A bridge is an extension boundary; internal details must not escape.
        reason = "engine_error"

    if reason is not None:
        result = model_type.model_validate(fallback())
    duration_ms = max(0, int((perf_counter() - started) * 1000))
    data = result.model_dump()
    data.update(
        {
            "engine_id": engine_id if reason is None else "deterministic-fallback",
            "duration_ms": duration_ms,
            "fallback_used": reason is not None,
            "fallback_reason": reason,
        }
    )
    return data
