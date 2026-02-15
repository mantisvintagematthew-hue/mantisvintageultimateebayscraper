from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np


def detect_single_stitch(path: Path) -> bool:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return False
    edges = cv2.Canny(img, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60, minLineLength=30, maxLineGap=8)
    if lines is None:
        return False
    horizontal = [ln for ln in lines[:, 0, :] if abs(ln[1] - ln[3]) < 5]
    return 1 <= len(horizontal) <= 20
