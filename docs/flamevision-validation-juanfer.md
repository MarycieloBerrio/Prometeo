# FlameVision validation note (Juanfer)

**Date:** 2026-11-14 · **Branch:** `feat/juanfer-flamevision-validation`

## Status in one paragraph

The tracker was rewritten, tested on code-generated videos, and run on one real BASS-II
video from NASA PSI. The real result is **pixel-only and UNVALIDATED**: the video has no
verifiable mm/pixel scale, and no published spread rate could be tied to this exact test.
No millimetre value was produced. The video is not linked to any Prometeo `Trial.id`.

| Question | Answer |
|---|---|
| Real NASA video processed? | Yes, PSI-25 test **B9** (one video) |
| `Trial.id` associated | **None** (no curated trial matches this test) |
| Spatial calibration | **None found.** Positions in px, rates in px/s |
| Validation status | **UNVALIDATED** |
| Suitability verdict (software check) | SUITABLE inside the 9.0–28.5 s window |
| Can the derived assets be shown publicly? | Yes, with the labels in "Handoff for Marycielo" |

## 1. Source record

| Field | Value | How it was obtained |
|---|---|---|
| Repository | NASA Physical Sciences Informatics, investigation **PSI-25**, "Burning and Suppression of Solids - II" | PSI metadata API, read 2026-11-14 |
| Page | <https://psi.nasa.gov/physci/repo/data/investigations/PSI-25> | |
| DOI | `10.60555/4qc4-de67` | PSI metadata field `doi` |
| License | **CC0-1.0** (`licenseIdentifier`, `licenseName` "Creative Commons Zero v1.0 Universal") | PSI metadata |
| File | `PSI-25_Raw Data_BASS_GMT188_SAMPLE_154_TESTB9.mp4` | PSI file listing |
| Size / SHA-256 | 4 962 193 bytes / `369f30efddaeabc822c4b7a37dab9d1dde57d07b854f756bf79d1c4f3d7c2038` | computed on the download |
| Test metadata | `PSI-25_Experimental table_BASS-II.csv`, row B9 | PSI file, downloaded |
| Still images | `PSI-25_Raw Data_GMT2014_188_BASS_S154M_TPB9_ProofSheet.pdf` | PSI file, downloaded |

Raw files live in `data/raw/psi-25/` (gitignored). They are not committed and were not modified.

**Access path.** The PSI page is a JavaScript app. Its own web client calls these endpoints,
which answered without login on 2026-11-14. They are not a documented public API and may change:

- metadata and file list: `https://psi.nasa.gov/geode-py/ws/repo/investigations/PSI-25`
- one file: `https://psi.nasa.gov/geode-py/ws/studies/PSI-25/download?source=datamanager&file=<file_name>`

The listing reports 302 MP4 files and about 275 GB in total.

### What the experimental table says about test B9

Copied from the CSV row, not interpreted:

| Column | Value |
|---|---|
| PI | Bhattacharjee |
| Test # / Sample # | B9 / 154m |
| Date / GMT | 7/7/2014 / 188 |
| Fuel Sample Material | `2 cm   0.1 mm PMMA film` |
| Flow restrictor | 2 |
| Fan display | `0.6   0.35` |
| Air display | `2   <1` |
| Calibrated initial / final O₂ % by vol | 21 / 20.9 |

**Not available from these files:** flow speed in cm/s (the table gives display readings, not
a velocity, and no display-to-velocity calibration was found), flow direction relative to the
flame (opposed or concurrent), pressure, and any length scale. These stay unknown.

The fan and air readings change during the test (two values each). Conditions were therefore
not constant over the whole burn.

## 2. Video metadata (measured with OpenCV 5.0.0)

| Property | Value |
|---|---|
| Container / codec | MP4 / H.264 |
| Frame size | 720 × 480 px |
| Frame rate (container) | 29.97 fps |
| Frames / duration | 1314 / 43.8 s |
| Flame motion in the image | left → right (x increasing) |
| Spatial marks or scale | none visible |
| On-screen display | text block at the top (`FUEL AIR FAN RAD`, date and time) |
| Cuts or edits | none seen in the window: the on-screen clock advances 20 s (08:58:46 → 08:59:06) over 19.5 s of video |

Timeline by inspection: igniter glow lights the scene at about 3–7 s, a steady two-sheet
flame is visible from about 8 s to 29 s, then the image is dark.

### Identity problems found (read before linking anything)

1. **"B16" means two different things.** In PSI-25, `TESTB16` is a Bhattacharjee thin-film
   test (100 µm PMMA, 17.3 % O₂ in the table). In Link et al. 2018, Table S1, "B16" is a
   PMMA **rod**. Yulian's branch curates the rod records as `BASS-II-B16-*`. Do **not** attach
   the PSI `TESTB16` or `TESTB19` videos to those trials on the name alone.
2. **Day mismatch.** File name and table say GMT 188 (7 July 2014). The on-screen clock and
   the proof sheet say 07/08/14, GMT 189. The proof sheet notes "Date/Time set to BASS Video
   Display". Unresolved; the test label B9 and sample 154 agree in all three files.
3. **`..._2ND_VIEW.mp4` is not usable.** It is a hand-held recording of the glovebox monitors,
   oblique and with people moving in frame.

## 3. Method

Code: `apps/backend/src/prometeo/adapters/outbound/vision/opencv_flame_detector.py`.
CLI: `tools/flamevision/track_video.py`.

Per analysed frame:

1. Crop to the ROI (optional). Optional Gaussian blur.
2. Mask: gray level ≥ threshold, or an HSV colour range.
3. Morphological opening removes specks.
4. Connected components. A region is a candidate only if its area is between `min_area_px`
   and `max_area_fraction` of the ROI. A region that fills the ROI is treated as glare.
5. Selection. First detection: largest candidate. After that: the candidate nearest to the
   previous one. A larger reflection appearing later does not take over the track.
6. Edge: the outermost pixel of the region along the chosen axis (x or y) and direction
   (increasing or decreasing).
7. Jump check (optional): an edge that moves more than `max_jump_px_per_frame` is stored as
   `spurious_jump` and is not used as a sample.

Every analysed frame is exported with a status (`detected`, `no_detection`,
`spurious_jump`). Nothing is removed to improve a fit. Monotonicity is reported, not enforced.

### NOT SUITABLE verdict

`diagnose()` marks a track NOT SUITABLE, and no velocity is derived, when any of these holds:

| Condition | Default limit |
|---|---|
| Too few detections | < 5 |
| Low coverage (flame invisible, occluded, outside ROI) | < 80 % of analysed frames |
| Unstable region | spurious jumps > 10 % of frames |
| Saturation | median saturated share of the region > 50 % |
| Scene change outside the ROI (camera motion, lighting) | > 8 gray levels, 95th percentile |

Camera stability is only assessed when an ROI is set. Without one the output carries a warning.

Through the port, `OpenCvFlameDetector.track(trial_id, video_uri, calibration)` keeps its
signature. A NOT SUITABLE video returns `validation = rejected` with the reasons in
`validation_note`, and `AnalyzeFlameVideo` then returns no velocity and a `withheld_reason`.

## 4. Result on PSI-25 test B9

Parameters: ROI `x=0, y=180, w=720, h=240`, luminance threshold 100, blur 3, opening 3,
axis x, direction increasing, max jump 15 px/frame, window 9.0–28.5 s. The window was chosen
by the analyst to leave out the igniter transient and the dark tail.

| Quantity | Value | Quality |
|---|---|---|
| Frames analysed / detected | 585 / 585 (coverage 100 %) | computed |
| Spurious jumps | 0 | computed |
| Edge advance (least-squares slope) | **9.95 px/s** along +x | computed, uncalibrated |
| R² / RMS residual | 0.997 / 3.1 px | computed |
| Steps advancing or holding | 94 % | computed |
| Saturated share of region (median) | 0 % | computed |
| Scene change outside ROI (p95) | 0.5 gray levels | computed |
| Spread rate in mm/s | **not available** | no calibration |

Threshold sensitivity (same ROI and window):

| Threshold | Coverage | Advance |
|---|---|---|
| 60 | 100 % | 10.08 px/s |
| 100 | 100 % | 9.95 px/s |
| 140 | 95 % | 10.03 px/s |

The original settings (threshold 200, no ROI, whole video) detect 17 % of frames: the steady
flame peaks near gray level 180 and only the igniter glow passes 200. That run is reported
NOT SUITABLE.

What the overlay shows: the tracked region is the lower of two red luminous sheets. A fainter
blue zone extends further ahead of the tracked edge and is below the threshold. The tracked
edge is therefore behind the visible flame tip by an amount that depends on the threshold.

## 5. Why this is UNVALIDATED

- **No scale.** Nothing in the frame or in the downloaded metadata gives mm/pixel. The 2 cm
  sample width is not usable: the view is edge-on and the sample is not visible in the dark frames.
- **No matched reference.** No published spread rate was tied to PSI test B9 with a table,
  figure or page that names this test. Values from other tests or from summaries were not used.
- **Conditions changed during the burn** (fan and air readings), so one straight line over
  the window is a description of this track, not a spread rate at one condition.

To validate, all three are needed: a scale with a citable source, a reference value for this
same test, and a window with constant conditions. The CLI then reports the reference, the
computed value, and absolute and relative error (`--mm-per-pixel`, `--calibration-source`,
`--reference-mm-s`, `--reference-source`). That path is covered by tests on generated video only.

### Why luminance tracking is not a reaction-front or HRR measurement

The camera records visible light integrated along the line of sight, after the sensor's
exposure, gain and compression. In these flames most of that light comes from soot and from
excited radicals, whose brightness depends on temperature, soot loading and oxygen supply, not
only on where fuel is being consumed. A thresholded edge marks where the image crosses a
chosen gray level. It moves if the exposure, the threshold or the soot content changes, even
when the reaction zone does not. The pyrolysis front on the solid and the gas-phase reaction
zone can sit ahead of or behind that edge, and a dim blue flame can be missed entirely, as in
the B9 overlay. Heat release rate needs oxygen-consumption or mass-loss data. Image brightness
is not a calibrated measure of it. The tracked quantity is therefore named
`luminous_leading_edge`, and its rate equals a flame spread rate only after comparison with an
independent reference.

### Related NASA work on flame tracking

A web search on 2026-11-14 did not find a NASA Task Book entry on flame edge tracking that
could be opened and read, so none is cited as a method source. The only related record found
was an NTRS listing for a 1992 NASA Lewis image-processing and object-tracking workstation
(<https://ntrs.nasa.gov/citations/19920017368>). Only its catalogue summary was seen; the
report itself was not read.

## 6. Reproduce

From `apps/backend` (PowerShell or bash):

```
uv sync --extra vision
curl.exe -L -o "../../data/raw/psi-25/PSI-25_Raw Data_BASS_GMT188_SAMPLE_154_TESTB9.mp4" "https://psi.nasa.gov/geode-py/ws/studies/PSI-25/download?source=datamanager&file=PSI-25_Raw%20Data_BASS_GMT188_SAMPLE_154_TESTB9.mp4"
uv run --extra vision python ../../tools/flamevision/track_video.py "../../data/raw/psi-25/PSI-25_Raw Data_BASS_GMT188_SAMPLE_154_TESTB9.mp4" --out-dir ../../apps/frontend/public/experiments/flamevision/psi25-test-b9 --roi 0,180,720,240 --threshold 100 --blur 3 --start-s 9 --end-s 28.5 --max-jump 15 --direction increasing --keyframes 6 --trial-key "NASA PSI-25 (BASS-II) test B9, sample 154m" --source-url "https://psi.nasa.gov/physci/repo/data/investigations/PSI-25" --source-license "CC0-1.0 (as stated by NASA PSI for PSI-25, DOI 10.60555/4qc4-de67)" --notes "Uncalibrated: no verifiable mm/pixel scale. Analysis window 9.0-28.5 s chosen by the analyst to exclude the igniter transient and the period after the flame is no longer visible. No Prometeo Trial.id is associated."
```

Create `data/raw/psi-25/` first. Check the SHA-256 above after downloading. `track.json` and
`track.csv` are byte-identical across runs on the same machine. Add `--overlay` to write
`overlay.mp4` next to the other files; the repository ignores `*.mp4`, so it is not committed.

## 7. Handoff

### Marycielo (UI) — files to consume after merge

Static files under `apps/frontend/public/experiments/flamevision/`, served at
`/experiments/flamevision/...`. No endpoint exists for them and none is promised.

| File | Content |
|---|---|
| `index.json` | list of runs |
| `psi25-test-b9/manifest.json` | file list, units, verdict, validation status |
| `psi25-test-b9/track.json` | observations, parameters, diagnostics, source (schema `prometeo.flamevision.track/v1`) |
| `psi25-test-b9/track.csv` | one row per analysed frame |
| `psi25-test-b9/curve.png` | edge position vs time, 720 × 420 |
| `psi25-test-b9/keyframes.jpg` | six overlay frames, 960 × 960 |

- **Trial.id:** none. Show the source label "NASA PSI-25 (BASS-II) test B9, sample 154m". Do
  not place this on a trial sheet.
- **Curve format:** `observations[]` in `track.json`, or the CSV. x = `time_s` [s] from the
  start of the video file, y = `edge_px` [px]. Plot only rows with `status = detected`.
- **Overlay coordinates:** pixels of the original 720 × 480 frame, origin top-left, x right,
  y down. Per frame: `bbox` = `[x, y, width, height]` of the tracked region, `edge_px` = x of
  the vertical edge line. ROI rectangle: `method.config.roi`.
- **Unit labels:** "px" and "px/s". Never "mm" or "mm/s" for this run.
- **Required labels:** "Luminous leading edge (not the reaction front)", "UNVALIDATED" and
  "Uncalibrated (pixels)". "SUITABLE" is a software check on the video, not a scientific
  validation: do not show it as a quality mark by itself.
- **Public display:** allowed. The frames derive from a CC0-1.0 NASA PSI file. Credit
  "NASA PSI, PSI-25 (BASS-II), DOI 10.60555/4qc4-de67".
- **Video:** no clip is committed. Link to the PSI page rather than hot-linking the download endpoint.

### Yulian (data)

- Working, unauthenticated PSI endpoints are listed in section 1. They return the file list
  and the files, including the experimental table CSV.
- Test B9 has no curated trial. A record would need O₂ 21 % (table), fuel "PMMA film, 2 cm
  wide, 0.1 mm" (table) and unknown flow speed, direction and pressure.
- See the "B16" naming collision in section 2 before adding any `media` entry.
- If a trial is created, `media.uri` should point to the PSI page; this run can then be
  regenerated with `--trial-id`.

### Daniel (physics)

- The pixel-rate fit lives in the adapter because `flame_spread_velocity_fit` needs a length
  and "px" is not a unit in `Quantity`. Calibrated runs call `flame_spread_velocity_fit`
  unchanged. Nothing in `domain/physics` was edited.
- Open question, `TODO(science)`: whether a straight-line fit is acceptable when fan settings
  change within the window, or whether the track must be split by setting.

### Proposed contract changes (not made here; for a later integration PR)

1. `Calibration` cannot express "no scale", so an uncalibrated video cannot pass through the
   `FlameFrontDetector` port. Proposal: a second port method or result type for pixel tracks
   (`PixelTrack` in the adapter is a candidate shape), instead of a fake scale.
2. `FlameFrontTrack` has no place for coverage, parameters or reasons, so they are packed into
   `validation_note`. Proposal: structured fields.
3. No HTTP route exposes FlameVision and `bootstrap/container.py` does not wire the detector.
   Proposal: `GET /api/v1/flamevision/tracks/{key}` serving the `track.json` schema.
4. `position_mm` is measured along the configured direction of advance, so it increases for a
   flame moving left as well as right. This is a behaviour change for leftward flames only;
   the previous code always used `x + w`.

## 8. Tests

`apps/backend/tests/vision/` (60 tests). The videos are drawn by the test code: a gray
rectangle on a dark background. They are not NASA data and validate software only.

Covered: known speed within 2 %; left→right and right→left; vertical axis; fixed glare with
and without ROI; a larger reflection appearing mid-track; a region filling the ROI; occlusion
gap and intermittent flame with exact coverage; dark video; saturation; drifting background;
spurious jump; time window and frame step; HSV mask; metadata; calibrated conversion; FPS
mismatch; missing file; invalid FPS (override and container); invalid calibration; ROI outside
the frame; invalid parameters; CLI outputs, units, reproducibility, validation against a
reference, and argument errors.

The OpenCV tests are skipped when the `vision` extra is not installed (the CI case). The use
case tests always run.

## 9. Limitations

- One real video, uncalibrated, single analyst-chosen window and ROI.
- The suitability limits are engineering defaults, not derived from data.
- Saturation is judged at gray level 250 after H.264 decoding; clipping in the original
  camera signal below that level would not be seen.
- The camera-stability check compares consecutive frames outside the ROI. A slow drift can
  stay under the limit.
- No sub-pixel edge, lens distortion or perspective correction.
- Auto-exposure or gain changes in the source video move a thresholded edge and are not corrected.
