# Prometeo: 30-second jury walkthrough

> This file preserves the earlier demo and verification record. The current interface direction and route map are in [redesign-ignition-workbench.md](redesign-ignition-workbench.md); descriptions of the old thermal field, cards and no-signal viewer below are historical.

This is a live walkthrough, not a prerecorded claim. Select only records that the current API actually returns. Use a pair with the same material, geometry, thermal regime, and flow direction when available. Check the Physics Validator verdict before speaking about a difference. Never describe `SYN-*` records as NASA experiments.

| Time | Screen / transition | English narration |
| --- | --- | --- |
| 0–4 s | Home → Ask | “What can we actually say about flame spread and ventilation in microgravity?” |
| 4–8 s | Research Assistant question and tier | “Prometeo retrieves evidence, checks the physics, and either gives a cited explanation or explains why the evidence is insufficient.” |
| 8–13 s | Explorer filter → trial sheet | “Here is a documented trial. Its material, oxygen, airflow, measurement quality, and source are visible together.” Open the source link if present. |
| 13–20 s | Select A and B → Comparison Lab | “We specify the changed variable. The validator shows controlled conditions and blocks an unsupported comparison.” Use a directly comparable pair only if the API returns that level. |
| 20–25 s | Recorded values and O₂ × airflow map | “The difference comes from the Evidence Engine, and only for a directly comparable pair. Empty map cells mean no recorded evidence.” |
| 25–30 s | Assistant limitations / FlameVision optional | “The explanation keeps its limitations and citations visible. FlameVision links a trial video only when one is recorded; a track still needs validation.” |

## If curated data are unavailable

- If the API returns no trials: “No recorded evidence is loaded yet. This is a data gap, not a safety result.” Show the empty Explorer and coverage map.
- If only one trial is loaded: show its provenance and conditions; say “A comparison requires a second compatible trial.”
- If the assistant refuses: “The system refuses unsupported conclusions and states why.” Show the refusal reason and limitations.
- If using the synthetic API: say “These are invented development fixtures, not NASA measurements,” while pointing to the **DEMO DATA — SYNTHETIC, NOT NASA** notice. A direct `SYN-001` / `SYN-002` result proves wiring only. `SYN-001` / `SYN-003` demonstrates a blocked physical comparison.
- If the API is down: show the error state and describe the data flow without claiming a live result. Do not improvise measurements, papers, or video.

## Design rationale and source checks

- The [2026 Flame in Freefall challenge](https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/) asks for an interactive dashboard that summarizes, ranks, and interprets microgravity combustion findings. The UI leads with a question, an experiment, a comparability verdict, and a traceable limit.
- NASA describes [SpaceGenes+](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/) as an interactive research dashboard, SkySense as a focused weather analysis tool, and PureFlow as an interactive systems-engineering platform. Prometeo borrows the clear task entry and visible result hierarchy; its scientific gate is the comparability verdict and refusal state. This is a design comparison, not a claim that those projects use the same data or methods.
- The [NASA BASS-II summary report record](https://ntrs.nasa.gov/citations/20210011385) identifies fuel type, thickness, geometry, oxygen, and ventilation velocity as test variables. It does not, by itself, identify a specific curated trial or authorize a UI measurement. The [NASA PSI BASS-II entry](https://psi.nasa.gov/physci/repo/data/investigations/PSI-25) is a starting point for curation; source files and per-trial provenance must be checked by the data owner.

## Integration handoff

- **Yulian:** supply reviewed `TrialOut` records with measurement-level provenance, quality, units, and verified `media.uri` where available. No frontend fallback numbers are supplied.
- **Daniel:** preserve conservative comparability levels and `issues`. The UI hides `deltas` unless `level` is `directly_comparable`, even if an earlier API implementation includes them for partial pairs.
- **Juanfer:** provide a source-linked, validated overlay artifact and its relation to a trial in a later integration PR. The current API has no overlay endpoint or validation fields.
- **Alejandro:** return citations, computed facts, assessments, and limitations through `AskResponse`; the client renders explanation text without HTML interpretation.
- An overlay or media-validation status would need a future public contract field. Until then FlameVision only links video URIs already present in `TrialOut.media` and explicitly withholds a validation claim.

## Verification on 14 November 2026

The app was exercised locally with the existing API and the four `SYN-*` development fixtures. These checks establish wiring and UI states; they do not establish any NASA measurement. The frontend uses `pnpm dev:web`. The synthetic API used the equivalent `prometeo serve --synthetic --no-reload` command because the Windows sandbox did not permit the reload subprocess; curated mode used `prometeo serve --no-reload`.

| Check | Result |
| --- | --- |
| `/explorer` and `/explorer/SYN-001` | HTTP 200; both render the synthetic-data notice. |
| `/compare?a=SYN-001&b=SYN-002&varied=flow_speed` | HTTP 200; direct result, backend-supplied delta, and coverage section render. |
| `/compare?a=SYN-001&b=SYN-003&varied=flow_speed` | HTTP 200; incompatible pair renders separate recorded values. |
| `/compare?a=SYN-001&b=SYN-002&varied=oxygen` | HTTP 200; partial pair renders separate values and no difference section. |
| `/api/v1/coverage` | 51 of 54 cells have no recorded evidence with the current fixtures. |
| `/assistant` with material `unobtanium` | HTTP 200; `insufficient` refusal and limitations render. |
| `/flamevision` | HTTP 200; synthetic notice and “No verified video available” render. |
| Curated API mode (before the data integration) | Zero trial records; Explorer and Comparison show “No recorded evidence”, Comparison still shows the coverage map, and FlameVision shows no-video state. |
| API stopped | Explorer returns HTTP 200 with an explicit “Evidence Engine not reachable” error state. |

No browser screenshot was captured: the computer-use helper stopped when it could not determine the browser URL confidently. Therefore a visual 390 px check remains unverified. CSS includes single-column home cards, wrapping form controls and actions, and horizontally scrollable comparison and coverage tables for narrow widths.

## Scientific instrument redesign

The frontend now uses a dark observatory palette, warm thermal accents, fine measurement grids, and a restrained animated thermal field. The field is explicitly marked as abstract illustration, not experiment imagery or data. A horizontal instrument rail connects Explorer, Comparison Lab, Research Assistant, and FlameVision. The home page leads into a three-step research path instead of presenting the modules as equivalent dashboard cards.

- **Explorer:** records expose material, oxygen, airflow, geometry, phenomena, measurement quality, and provenance. Filters and a comparison queue keep the research task visible.
- **Comparison Lab:** A/B selectors preview selected conditions immediately. Users declare intentional variation; the verdict distinguishes it from checked controlled conditions and lists each issue. A duplicate selection is blocked before submission. Recorded values and coverage remain visible with their existing evidence limits.
- **Research Assistant:** the question console and response register expose evidence tier, citations, computed facts, assessments, limitations, and refusal state. An AI explanation is labelled as such only when a model response exists.
- **FlameVision:** a technical viewer plays a linked media file only when the trial contains a playable video URI. Otherwise it shows an explicit no-signal state. The existing static processed-run gallery remains available and keeps its validation status, source, and pixel units visible. No live overlay API is claimed.

The layout has tablet and narrow-screen rules, keyboard focus styling, a skip link, and reduced-motion handling. CSS-only animation adds no dependency. The redesign was checked with `pnpm lint:web`, `pnpm typecheck:web`, `pnpm build:web`, and `git diff --check` on 14 November 2026. Browser visual inspection of localhost was denied by the Browser Use origin-permission gate, so no screenshot or measured viewport result is claimed for this revision.

The redesign branch is based on the later `main`, which already includes curated BASS-II records, the observed-spread chart, and the static FlameVision processed-run gallery. The earlier empty-curated-data check above describes an earlier repository state; it is retained as an empty-state verification record, not a claim about the current dataset.

## Instrument workbench iteration

The interface now supports investigation inside each major visualization. Explorer is a condition-point ledger with one synchronized trial inspector and an independent two-record comparison queue. The observed B16/B19 plot exposes each recorded point to pointer and keyboard selection, with an inspector showing the selected condition and a link to its source record. Every oxygen × airflow coverage cell can be selected; its panel shows its interval, trial IDs, observed labels, or the explicit absence of recorded evidence. FlameVision's static processed-run track has a frame scrubber over the recorded observations, synchronized to frame number, time, edge position in pixels, and detection status. The exported curve and raw log remain available behind disclosure controls.

These views read existing gateway responses or static published artifacts. Plot lines connect recorded observations for readability; they do not infer intermediate values, calibration, independent ignition replicates, or a validated flame-front track. The new client components stay inside server-rendered data boundaries, and no API or generated contract changed.

Verification for this iteration on updated `main`: `pnpm check` passed using an isolated uv environment (Ruff, mypy, three import contracts, 275 pytest tests passed, three skipped, frontend ESLint and TypeScript); `pnpm build:web` passed. Browser screenshots and measured desktop/tablet/mobile layout review remain blocked by the saved Browser Use origin permission for localhost.
