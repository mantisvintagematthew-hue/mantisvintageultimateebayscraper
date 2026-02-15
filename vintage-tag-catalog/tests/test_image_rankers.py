from pathlib import Path
import numpy as np
import cv2

from app.vision.rank_hero import score_hero_image
from app.vision.rank_tag import score_tag_image


def test_rankers_return_scores(tmp_path: Path):
    img = np.full((240, 240, 3), 255, dtype=np.uint8)
    cv2.rectangle(img, (70, 80), (170, 160), (30, 30, 30), 2)
    path = tmp_path / "sample.jpg"
    cv2.imwrite(str(path), img)

    tag_score = score_tag_image(path)
    hero_score = score_hero_image(path)

    assert 0.0 <= tag_score <= 1.0
    assert 0.0 <= hero_score <= 1.0
