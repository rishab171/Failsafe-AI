"""LiteLLM gateway: key pool, ordered failover, built-in response cache."""
import asyncio
import logging
from dataclasses import dataclass

import litellm
from litellm.caching.caching import Cache

from .config import Settings

log = logging.getLogger("llm")
litellm.suppress_debug_info = True
litellm.set_verbose = False

SIMULATABLE = {429, 500, 502, 503}


class AllProvidersUnavailable(Exception):
    pass


@dataclass
class LLMResult:
    reply: str
    source: str  # LIVE_INFERENCE | LLM_CACHE
    model: str
    input_tokens: int
    output_tokens: int
    key_id: str | None
    fallback_attempts: int


def parse_simulation(header: str | None) -> dict[str, int]:
    """'key_1=429,key_2=500' or '*=429' -> {'key_1': 429, ...}. Invalid pairs are ignored."""
    out: dict[str, int] = {}
    if not header:
        return out
    for part in header.split(","):
        if "=" not in part:
            continue
        k, v = (s.strip() for s in part.split("=", 1))
        if v.isdigit() and int(v) in SIMULATABLE and k:
            out[k] = int(v)
    return out


class LLMGateway:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        # LiteLLM built-in in-memory cache. Key = model + messages (+ sampling params, which we fix).
        litellm.cache = Cache(type="local")
        self.keys = {f"key_{i}": k for i, k in enumerate(settings.api_keys, start=1)}

    @property
    def cache_enabled(self) -> bool:
        return litellm.cache is not None

    def _simulated(self, key_id: str, sim: dict[str, int]) -> int | None:
        return sim.get(key_id, sim.get("*"))

    async def complete(self, messages: list[dict], sim: dict[str, int]) -> LLMResult:
        failures = 0
        for key_id, api_key in self.keys.items():
            status = self._simulated(key_id, sim)
            if status is not None:
                log.warning("simulated failure %s on %s", status, key_id)
                failures += 1
                continue
            try:
                kwargs = dict(
                    model=self.s.model,
                    messages=messages,
                    api_key=api_key,
                    timeout=self.s.request_timeout,
                    num_retries=0,  # we do the failover ourselves, key by key
                    caching=True,
                    temperature=0.7,
                )
                if self.s.mock_llm:
                    kwargs["mock_response"] = "Mock reply to: " + messages[-1]["content"][:200]
                resp = await litellm.acompletion(**kwargs)
                reply = (resp.choices[0].message.content or "").strip()
                if not reply:
                    raise ValueError("empty completion")
            except Exception as exc:  # 429 / quota / 5xx / timeout / auth -> next key
                log.warning("%s failed: %s", key_id, type(exc).__name__)
                failures += 1
                continue

            hit = bool((getattr(resp, "_hidden_params", None) or {}).get("cache_hit"))
            usage = getattr(resp, "usage", None)
            inp = int(getattr(usage, "prompt_tokens", 0) or 0)
            out = int(getattr(usage, "completion_tokens", 0) or 0)
            if inp == 0 and out == 0:  # defensive: usage missing on cached object
                inp = int(litellm.token_counter(model=self.s.model, messages=messages))
                out = int(litellm.token_counter(model=self.s.model, text=reply))
            if not hit:
                await asyncio.sleep(0.05)  # LiteLLM writes its cache in a background task; let it land
            return LLMResult(
                reply=reply,
                source="LLM_CACHE" if hit else "LIVE_INFERENCE",
                model=self.s.model,
                input_tokens=inp,
                output_tokens=out,
                key_id=None if hit else key_id,
                fallback_attempts=0 if hit else failures,
            )
        raise AllProvidersUnavailable()
