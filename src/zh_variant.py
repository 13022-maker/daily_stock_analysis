# -*- coding: utf-8 -*-
"""Optional Simplified -> Traditional Chinese conversion for pushed reports.

Enabled by ``REPORT_ZH_VARIANT=tw`` (Taiwan Traditional, with Taiwan phrasing)
or ``REPORT_ZH_VARIANT=hk`` (Hong Kong Traditional). Leave it empty to keep the
default Simplified Chinese output. Conversion is best-effort: if OpenCC is not
installed the text is returned unchanged.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_VARIANT_TO_OPENCC = {
    "tw": "s2twp",
    "zh-tw": "s2twp",
    "zh_tw": "s2twp",
    "hant": "s2twp",
    "hk": "s2hk",
    "zh-hk": "s2hk",
    "zh_hk": "s2hk",
}


def _configured_variant() -> str:
    return (os.getenv("REPORT_ZH_VARIANT") or "").strip().lower()


@lru_cache(maxsize=4)
def _get_converter(profile: str):
    try:
        from opencc import OpenCC
    except ImportError:
        logger.warning("REPORT_ZH_VARIANT is set but opencc is not installed; skipping conversion")
        return None
    return OpenCC(profile)


def is_traditional_enabled() -> bool:
    return _configured_variant() in _VARIANT_TO_OPENCC


def to_report_variant(text: Optional[str]) -> Optional[str]:
    """Convert report text to the configured Chinese variant (no-op by default)."""
    if not text:
        return text
    profile = _VARIANT_TO_OPENCC.get(_configured_variant())
    if not profile:
        return text
    converter = _get_converter(profile)
    if converter is None:
        return text
    try:
        converted = converter.convert(text)
        if profile == "s2twp":
            # Everyday Taiwan usage prefers 台 (台積電, 台股) over the formal 臺.
            converted = converted.replace("臺", "台")
        return converted
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Chinese variant conversion failed: %s", exc)
        return text
