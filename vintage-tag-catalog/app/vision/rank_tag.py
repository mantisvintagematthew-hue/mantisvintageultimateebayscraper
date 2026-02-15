from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np


def score_tag_image(path: Path) -> float:
    img = cv2.imread(str(path))
    if img is None:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    edges = cv2.Canny(gray, 80, 160)
    edge_density = float(np.mean(edges > 0))
    center = gray[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
    center_var = float(np.var(center)) / 255.0
    score = min(1.0, 0.45 * min(lap_var / 2000.0, 1.0) + 0.35 * edge_density * 4 + 0.2 * min(center_var / 50, 1.0))
    return float(score)
