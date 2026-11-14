# Ignition workbench — current frontend direction

## Audit and primary journey

Prometeo helps a researcher move from a combustion question to an experiment record, test whether two conditions can be compared, inspect any available flame media, and read a cited answer with explicit limits. The Evidence Gateway remains the only runtime data source for trials, comparisons, coverage and answers. FlameVision also reads its existing published processed-run artifacts. The atmospheric landing video is separate from experimental evidence.

The earlier interface repeated large headers, cards, decorative instrument elements and several ways to restate the same record. Those layers hid the user's next action, consumed narrow-screen space and made the routes feel unrelated.

## Route map

1. `/`: moving, off-center fire against black; one central evidence search and a direct experiment entry.
2. `/explorer`: recorded-trial ledger with one contextual inspector. Filters open when needed; selecting two trial IDs carries them into `/compare`.
3. `/compare`: A/B setup, physics verdict, condition differences, recorded values and interactive evidence maps. Source identity is a disclosure. A result can lead to available media or a material-specific question.
4. `/flamevision`: frame-scrubbable luminous-edge plot first; source keyframes and exported artifacts on demand. Trial-linked video appears only when supplied by a trial. No unrelated record is assigned to the static run.
5. `/assistant`: a question field, evidence tier, answer or refusal, citations, limitations and links back to assessed trials.

The four research routes share a numbered path, a next-step link, the same page width and the same reading hierarchy. The post-MVP mission route remains directly addressable but is omitted from the primary path.

## Design system

- Black canvas, warm ivory type, ember accents and ruled separators. Sage, ochre and terracotta are reserved for evidence and validation states.
- One outer page margin; internal spacing expresses hierarchy. Long tables and plots can scroll within their own region on small screens.
- Data units, quality, source, missing values and scientific limits stay adjacent to the measurements they qualify.
- Interactive areas are a trial ledger, observation chart, coverage map and frame scrubber. Decorative dashboard cards, the animated thermal field and the empty faux viewer were removed.
- Keyboard focus, semantic labels and reduced-motion fallback remain. The landing video is labelled as atmospheric footage, not NASA evidence.

## Verification and current limit

On 14 November 2026, `pnpm check` passed with the local `uv` binary and `UV_NO_SYNC=1`: Ruff, mypy, three import contracts, 275 tests passed and 3 skipped, frontend ESLint and TypeScript. `pnpm build:web` passed for every route. The local frontend was restarted on port 3000. Browser Use continues to deny observation of localhost, so this revision has no claimed desktop, tablet or mobile screenshots or measured visual QA.
