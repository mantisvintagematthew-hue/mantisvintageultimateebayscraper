from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_READER = None


def ocr_tag_image(path: Path, max_retries: int = 2, backoff_s: float = 0.5) -> str:
    reader = _get_reader()
    if reader is None:
        return ""

    wait = backoff_s
    for attempt in range(max_retries):
        try:
            result = reader.readtext(str(path), detail=0)
            return " ".join(result)
        except Exception as exc:
            if attempt + 1 >= max_retries:
                logger.warning("ocr failed path=%s err=%s", path, exc)
                return ""
            time.sleep(wait)
            wait *= 2
    return ""


def _get_reader():
    global _READER
    if _READER is not None:
        return _READER
    try:
        import easyocr  # type: ignore
    except Exception:
        return None
    _READER = easyocr.Reader(["en"], gpu=False)
    return _READER
