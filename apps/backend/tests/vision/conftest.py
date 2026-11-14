"""Code-generated test videos.

These clips are drawn by this file: a bright rectangle on a dark background. They are NOT
NASA footage and carry no scientific meaning. They only exercise the tracking software.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

WIDTH, HEIGHT, FPS = 320, 120, 30.0
# Bright enough for the default threshold (200), below the saturation level (250).
OBJECT_LEVEL = 230


@dataclass
class Scene:
    """A moving rectangle. Positions are the rectangle's left/top pixel at frame 0."""

    frames: int = 60
    x0: float = 40.0
    y0: float = 50.0
    vx: float = 3.0  # pixels per frame
    vy: float = 0.0
    width: int = 20
    height: int = 14
    level: int = OBJECT_LEVEL
    hidden: frozenset[int] = frozenset()  # frames where the rectangle is not drawn
    glare: tuple[int, int, int, int] | None = None  # fixed bright x, y, w, h
    glare_from_frame: int = 0
    teleport: dict[int, float] = field(default_factory=dict)  # frame -> x override
    moving_background: bool = False  # textured background that drifts (camera motion)
    frame_size: tuple[int, int] = (WIDTH, HEIGHT)
    fps: float = FPS


VideoFactory = Callable[[Scene], str]


@pytest.fixture
def make_video(tmp_path: Path) -> VideoFactory:
    cv2: Any = pytest.importorskip("cv2", reason="needs `uv sync --extra vision`")
    np: Any = pytest.importorskip("numpy")
    counter = iter(range(1000))

    def build(scene: Scene) -> str:
        path = tmp_path / f"synthetic_{next(counter)}.avi"
        width, height = scene.frame_size
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"MJPG"), scene.fps, (width, height)
        )
        assert writer.isOpened(), "OpenCV cannot write MJPG video in this environment"
        texture = np.random.default_rng(7).integers(0, 120, (height, width), dtype=np.uint8)
        for i in range(scene.frames):
            frame = np.zeros((height, width, 3), np.uint8)
            if scene.moving_background:
                frame[:] = np.roll(texture, 9 * i, axis=1)[:, :, None]
            if scene.glare is not None and i >= scene.glare_from_frame:
                gx, gy, gw, gh = scene.glare
                frame[gy : gy + gh, gx : gx + gw] = OBJECT_LEVEL
            if i not in scene.hidden:
                x = round(scene.teleport.get(i, scene.x0 + scene.vx * i))
                y = round(scene.y0 + scene.vy * i)
                frame[y : y + scene.height, x : x + scene.width] = scene.level
            writer.write(frame)
        writer.release()
        return str(path)

    return build
