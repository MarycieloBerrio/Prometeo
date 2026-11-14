# tools/flamevision

Offline FlameVision tracking. One script: `track_video.py`.

It tracks the **luminous leading edge** of a flame in a video and writes an auditable track.
That edge is not the reaction front. See `docs/flamevision-validation-juanfer.md`.

## Run

From `apps/backend`:

```
uv sync --extra vision
uv run --extra vision python ../../tools/flamevision/track_video.py VIDEO --out-dir OUT --roi 0,180,720,240 --threshold 100 --direction increasing
uv run --extra vision python ../../tools/flamevision/track_video.py --help
```

## Outputs

| File | Content |
|---|---|
| `track.csv` | one row per analysed frame, including frames with no detection |
| `track.json` | observations, source hash, parameters, OpenCV version, diagnostics, verdict |
| `curve.png` | edge position vs time with the fitted line |
| `keyframes.jpg` | overlay contact sheet (`--keyframes N`) |
| `overlay.mp4` | overlay video (`--overlay`); `*.mp4` is gitignored |
| `manifest.json` | file list, units and status for the UI |

The input video is only read.

## Rules the script enforces

- No `--mm-per-pixel` → pixels and px/s only. Millimetres never appear.
- `--mm-per-pixel` needs `--calibration-source`. `--reference-mm-s` needs `--reference-source`
  and a calibration.
- A NOT SUITABLE video (low coverage, saturation, unstable region, scene change outside the
  ROI) gets no velocity.
- Status is `UNVALIDATED` unless a reference is given. Then it is `VALIDATED` or `REJECTED`
  by `--tolerance-pct`.
- `--trial-id` is recorded as given. Pass it only when the video-to-trial link was verified.

## Choosing parameters

- `--roi x,y,w,h`: exclude on-screen text, reflections and hardware. Also enables the
  camera-stability check.
- `--axis x|y` and `--direction increasing|decreasing`: where the flame is heading in the
  image. `increasing` is right or down.
- `--threshold` or `--mask color_hsv --hsv-lower h,s,v --hsv-upper h,s,v`.
- `--start-s`, `--end-s`: analysis window. Coverage is computed inside it.
- `--max-jump`: pixels per frame; larger moves are stored as `spurious_jump`.

Record why you chose a window or ROI in `--notes`. It is written to `track.json`.
