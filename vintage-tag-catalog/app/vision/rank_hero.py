from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np


def score_hero_image(path: Path) -> float:
    img = cv2.imread(str(path))
    if img is None:
        return 0.0
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    area_ratio = float(np.mean(mask > 0))
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return 0.0
    cx, cy = np.mean(xs) / w, np.mean(ys) / h
    center_penalty = abs(cx - 0.5) + abs(cy - 0.5)
    score = max(0.0, min(1.0, 0.8 * (1 - abs(area_ratio - 0.45)) - 0.6 * center_penalty))
    return float(score)
