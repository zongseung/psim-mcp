"""Hybrid intent resolver: sampling first, regex fallback."""

from __future__ import annotations

from typing import Any

from .resolver import IntentResolver, RegexResolver
from .sampling_resolver import SamplingResolver


class HybridResolver(IntentResolver):
    """Use sampling when available, falling back to regex on unsafe failures."""

    def __init__(
        self,
        sampling_resolver: IntentResolver | None = None,
        fallback_resolver: RegexResolver | None = None,
    ) -> None:
        self._sampling = sampling_resolver or SamplingResolver()
        self._fallback = fallback_resolver or RegexResolver()

    async def resolve(self, text: str, ctx: Any | None = None) -> dict | None:
        try:
            result = await self._sampling.resolve(text, ctx=ctx)
            if result is not None:
                result["resolution_version"] = "v2_hybrid"
                result["intent_resolution_fallback"] = False
            return result
        except Exception as exc:
            fallback = await self._fallback.resolve(text, ctx=ctx)
            if fallback is not None:
                fallback["resolution_version"] = "v2_hybrid_regex_fallback"
                fallback["intent_resolution_fallback"] = True
                fallback["fallback_reason"] = type(exc).__name__
            return fallback
