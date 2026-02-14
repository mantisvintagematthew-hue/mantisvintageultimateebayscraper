from __future__ import annotations

from pathlib import Path


def ocr_tag_image(path: Path) -> str:
    try:
        import easyocr  # type: ignore
    except Exception:
        return ""
    reader = easyocr.Reader(["en"], gpu=False)
    result = reader.readtext(str(path), detail=0)
    return " ".join(result)
