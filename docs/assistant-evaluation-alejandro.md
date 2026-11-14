# Research Assistant: evidence guards and evaluation

Owner: Alejandro (Research Assistant / RAG / hallucination testing).
Scope: `AskResearchAssistant`, `KeywordRetriever`, `AnthropicExplainer`, `OfflineExplainer`
and the test battery in `apps/backend/tests/assistant/`. No HTTP contract, DTO, domain,
data, frontend or configuration file was changed.

## 1. What the assistant guarantees

The guarantees live in deterministic Python, not in the prompt. They hold for any
`ExplanationGenerator` (offline, Claude, or a future model).

| # | Guarantee | Where | Test that breaks if it regresses |
|---|---|---|---|
| G1 | Facts come only from trials that EvidenceRank keeps, and only from **reportable** results (`measured`, or `derived` with a method; traceable source; never synthetic). `extracted` and `unavailable` values are never printed as facts. | `_reportable`, `_fact` | `test_unreviewed_extracted_values_are_neither_evidence_nor_facts`, `test_without_a_metric_only_reviewed_results_of_usable_trials_are_printed`, `mixed-quality` ground truth |
| G2 | A conclusion needs EvidenceRank coverage (`overall_tier`, unchanged: at least 2 usable trials) **and** at least 2 usable trials that are comparable under the Physics Validator (same fuel, geometry, thermal regime and flow direction). Only comparable trials reach the model. | `comparable_groups` | `test_refuses_to_conclude_across_incompatible_trials[*]`, `test_only_comparable_trials_reach_the_explainer` |
| G3 | When the tier is `insufficient` or the question is out of scope, the model is **never called**, `answer` is `null`, and `refusal_reason` names what is missing (filter, metric, traceability, comparability). | `execute`, `_insufficiency_reason` | refusal battery (`test_refusals.py`) |
| G4 | **Scope guard.** Questions asking for certification, safety verdicts, probabilities or "% confidence", partial-gravity or full-scale transfer, predictions, or new materials are refused even when the evidence is good. | `out_of_scope_reason` | `test_refuses_out_of_scope_questions_even_with_good_evidence[*]` |
| G5 | The model writes **only the Interpretation**. Code renders *Observed evidence* and *Limitations* around it, so the model cannot change them. | `compose_answer` | `test_model_cannot_rewrite_observed_evidence_or_limitations` |
| G6 | **Number audit.** Every number in the model's text must appear in the packet (or be that number rounded to the decimals written). Conversions, ratios and averages fail the audit, and the interpretation is replaced by the deterministic one. | `unsupported_numbers`, `audit_explanation` | `test_invented_numbers_trigger_deterministic_fallback[*]` |
| G7 | **Citation audit.** A citation that does not resolve to a retrieved document or a packet trial is dropped, and a limitation records the removal. Claude citations are resolved by `document_index` to the chunk we sent, never by free-text title. | `audit_explanation`, `_resolve_citation` | `test_unknown_citation_is_removed_and_reported`, `test_anthropic_citations_resolve_by_document_index_only` |
| G8 | Offline by default. Missing credentials, API errors and model refusals degrade to the deterministic interpretation, and the `model` field says why. CI never needs network or keys. | `AnthropicExplainer.explain` | `test_anthropic_api_failure_degrades_to_deterministic_text`, `test_anthropic_refusal_degrades_to_deterministic_text` |

### Answer format (the `answer` string; `AskResponse` is unchanged)

```
Observed evidence            <- code: one line per audited trial: value, unit, quality, source, conditions
Interpretation               <- model (or deterministic text): observation vs mechanism vs what is unsupported
Limitations                  <- code: standing limits, comparable sets, excluded trials, audit notes
```

`computed_facts`, `limitations` and `cited_sources` hold the same audited content in
structured form. The frontend already renders `answer` with `white-space: pre-wrap`, so the
sections display without UI changes.

### Interpretation discipline: Observation / Mechanism / Limitation

The Claude system prompt asks the model to keep these three distinct, and the code enforces
what it can:

- **Observation:** only the *Observed evidence* lines (code-rendered, audited values).
- **Mechanism:** only what a retrieved document states. A lexical match is not experimental
  validation, and the model may not turn a sentence from a paper into a coefficient (G6).
- **Limitation:** code-rendered. It always includes microgravity ≠ partial gravity, small
  sample ≠ full scale, and no certification. It adds which variables vary inside each
  comparable set, and which trials were excluded.

Worked example (sources verified, §5). Link et al. 2018 report, for BASS-II opposed-flow
PMMA rods:
- *Observation:* "the flame spread rate first increases, and then decreases" as opposed
  flow increases, and no spread was observed below 0.6 cm/s.
- *Mechanism (as proposed by the authors):* a thermal regime, where faster flow means
  faster spread, competes with a chemical/kinetic regime, where cooling near blow-off slows
  spread.
- *Limitation:* the authors say the data points "were not systematically taken"
  (limited samples, crew time and O₂ supply). Flame position comes from the luminous edge
  in imagery. Microgravity ≠ lunar/Martian gravity.

### Not confusing BASS-II, FLEX and SAFFIRE

- Trials from different investigations get a limitation saying they are not one dataset.
  The Physics Validator also flags the investigation difference. The model is told never to
  merge them.
- Grouping is by physical comparability, not by program. A FLEX droplet and a BASS-II rod
  can never land in the same comparable set, because their geometry differs (blocking).
- Every fact line starts with `[trial-id] INVESTIGATION`, so the program is visible beside
  every value.

## 2. Retrieval (`KeywordRetriever`)

Same API (`retrieve(query, limit=8)`), offline, no new dependencies.

- **Scoring:** IDF-weighted term coverage (85 %) plus adjacent-term phrase matches (15 %),
  in [0, 1].
- **Normalization:** NFKD folding (`O₂` → `o2`, accents stripped), a short stopword list,
  plural folding, and a tiny documented vocabulary map (ventilation/airflow → flow,
  oxygen → o2, velocity → speed). Short tokens that carry digits (`o2`, `1g`) are kept.
- **Defensive loading:** entries without an id, text or provenance reference, duplicate
  ids, duplicate (text, reference) pairs and stopword-only chunks are skipped and listed in
  `rejected`. A non-list file raises.
- **Provenance:** copied verbatim. Blank DOI, page or URL values become `None`. Nothing is
  synthesized.
- **Deterministic:** ties break on matched-term count, then chunk id.
- **Honesty:** the score measures word overlap, not evidence quality. Every answer with
  documents carries that limitation.

## 3. Evaluation battery

`apps/backend/tests/assistant/` (all fixtures are labelled TEST FIXTURE / `example.invalid`;
none are NASA data):

| File | What it proves |
|---|---|
| `test_refusals.py` | 27 tests, 22 of them abstention cases: zero data, filter not matched, synthetic-only, documents-only, single trial, synthetic does not complete a pair, missing metric, extracted-only, untraceable source, O₂ not recorded, 3 incompatible pairs, 9 out-of-scope questions, plus 4 in-scope controls against over-refusal and a "refusals carry no measured values" check |
| `test_output_guards.py` | 20 tests. Citation and number audits with simulated model outputs: invented citation, invented value, ratio, unit conversion, average; faithful copies accepted; section order; the Anthropic adapter with a fake client (citation index mapping, request shape, API error, refusal) |
| `test_ground_truth.py` | Table of 7 expected behaviours: flow variation, missing O₂, incompatible comparison, missing source, citation control, unsupported question, mixed quality |
| `test_keyword_retriever.py` | Ranking, vocabulary variants, verbatim provenance, blank metadata, rejection of incomplete/duplicate entries, deterministic ties, empty queries, limit |
| `test_curated_corpus.py` | Invariants on whatever is in `data/curated` (empty on `main`): chunks index cleanly; the demo question is refused or fully grounded; out-of-scope questions are refused on real data |

Plus 8 new unit tests in `tests/unit/application/test_research_assistant.py`.

**Mutation check.** 13 hand-made mutants each disable one guard: the scope guard, the
facts filter, the number audit, the citation filter, the comparability gate, the reportable
filter, the synthetic filter, "the model is called on refusal", retriever dedupe, retriever
empty-text rejection, retriever tie-break, Claude title-based citations, and swallowed API
errors. The suite kills all 13.

**Corpus readiness.** `test_curated_corpus.py` passes on `main` (empty corpus, so every
question is refused). It also passes against the BASS-II corpus on
`feat/yulian-bass2-evidence-data` (695e96f), run locally by setting the environment
variable `PROMETEO_EVAL_DATA_DIR` to a folder holding a copy of that branch's `curated/`
files. No data file was edited.

### Example on the BASS-II curated corpus (offline explainer, abbreviated)

Question: *How does flame spread over a solid change with ventilation speed in
microgravity?* (material=PMMA, flow_direction=opposed, metric=flame_spread_rate) → `direct`

```
Observed evidence
- [BASS-II-B16-Vg072] BASS-II · flame_spread_rate = 0.0568 mm/s (measured) · source: Link et al. Sci. Rep. 8:120 (2018) Table S1 sample B16 … · conditions: O2 18.2 %, flow 0.72 cm/s (opposed), PMMA cylinder 6.4 mm (thick)
- … 5 more B16/B19 lines …
Interpretation
No language model was used for this interpretation. … compare two trials from the same comparable set in the Comparison Lab …
Limitations
- … Comparable set 1 [6 trials] shares PMMA, cylinder (thick), opposed flow. Within it these conditions differ or are unknown: flow_speed …
- Excluded from the interpretation (no comparable counterpart): BASS-II-FILM-100um-SR-extinction-context.
```

Refusal, same corpus: *Concurrent flame spread rate of PMMA rods?* (flow_direction=concurrent)
→ `insufficient`: "No curated trial matches the requested conditions (material=PMMA,
flow_direction=concurrent, metric=flame_spread_rate). No recorded evidence is not evidence of
safety … 7 related document excerpt(s) are returned as context only …"

## 4. Questions Prometeo can answer and must refuse

**Answerable once the right corpus exists** (each needs ≥2 measured, comparable trials):

| Question | Filters / varied variable | Status with the BASS-II data PR |
|---|---|---|
| How does opposed-flow spread rate over thick PMMA rods change with flow speed at fixed O₂? | PMMA, cylinder, opposed, `flame_spread_rate`; varied `flow_speed` | Answerable (B16 series) |
| At the same opposed flow, how does spread rate differ between two O₂ levels? | as above; varied `oxygen` (Comparison Lab) | Data present (B16 vs B19). See the O₂ tolerance note in §6 |
| How does rod diameter affect opposed-flow spread rate? | PMMA, cylinder, opposed; varied `thickness` | Needs 9.5 / 12.7 mm trials curated |
| What extinction flow was recorded for thin PMMA films in opposed flow? | PMMA, sheet, opposed, an extinction metric | Documents only today, so refused quantitatively |
| How do the concurrent-flow blowoff and quenching limits of PMMA rods vary with O₂? | PMMA, cylinder, concurrent, limit records | Olson & Ferkul 2015 report limits, not spread rates; needs curated limit records |

**Must refuse, whatever the evidence** (scope guard G4, each covered by a test):

1. *How would this material burn on the Moon / Mars?* Partial gravity is untested.
2. *How would a new composite material burn under these flows?* No evidence for untested
   materials.
3. *Can Prometeo certify PMMA for flight? Is it safe?* No certification and no safety
   verdicts. Absence of evidence ≠ safety.
4. *What would happen in a full-scale cabin fire?* Small samples do not predict full-scale
   fires.
5. *What is the % confidence / probability that it ignites?* No validated statistical model.

## 5. Sources consulted (2026-11-14)

| Source | Verified | Notes |
|---|---|---|
| NTRS 20210011385: Olson, Ferkul, Bhattacharjee, Miller, Fernandez-Pello, Link, T'ien, Wichman, *BASS-II Summary Report*, NASA TM (E-19939), Oct 2021 | Yes (landing page) | ISS MSG flow duct; varied O₂ (N₂ dilution), flow, fuel type/thickness/geometry; heat release from O₂ consumption at 13.1 kJ/g O₂, mostly well below 100 W |
| Link, Huang, Fernandez-Pello, Olson, Ferkul, *The Effect of Gravity on Flame Spread over PMMA Cylinders*, Sci. Rep. 8:120 (2018), doi:10.1038/s41598-017-18398-4 | Yes (article) | Black cast PMMA rods 6.4/9.5/12.7 mm; O₂ 16–21 %; opposed flow 0.4–8 cm/s; non-monotonic spread vs flow; no spread below 0.6 cm/s; microgravity spread at lower O₂ than 1 g; authors note unsystematic sampling |
| NTRS 20150008961: Olson & Ferkul, *Microgravity Flammability of PMMA Rods in Concurrent Flow* (2015 conference paper) | Yes (landing page) | 24 BASS-II concurrent tests; flammability limits (blowoff/quenching) and Damköhler interpretation, **not** spread rates |
| NASA PSI-25 (BASS-II) | Not readable here | JavaScript page returned no content to the fetcher |
| Space Apps 2026 challenge resources | Not readable here | TLS certificate verification failed from this environment; not bypassed |

No values from these sources were added to code or data. The numbers above only document
what was checked. Curated values are the data owner's responsibility.

## 6. Limitations and open items

- **Lexical retrieval** finds words, not evidence. Paraphrased curated chunks help, and
  pgvector hybrid search (on the `database` branch) can replace it behind the same port.
- **The scope guard is over-inclusive by design.** Any mention of "safe", "predict",
  "Moon", "% confidence"… refuses. For example, "Why can't microgravity results be applied
  to lunar gravity?" is refused. "Fire safety" and "oxygen percentage" are allowed (tested).
- **The number audit is strict.** A model that rounds 18.2 % to "18 %" is replaced by the
  deterministic text. This is intentional; the prompt asks for verbatim copies.
- **Tier semantics:** out-of-scope refusals also return `tier = insufficient`, because the
  contract has no separate refusal kind.
- **Document-only questions** are refused quantitatively; documents are still returned as
  context. A *single-paper reading mode* is a possible future PR. It would add a separate
  response kind (e.g. `mode: "document"`) with `tier` fixed to `insufficient`, an answer
  limited to quoting cited spans, and no numbers outside quoted text. That needs a DTO
  change, so it belongs in an integration PR.
- **No live Claude call was made.** `ANTHROPIC_API_KEY` was not set in this environment;
  the adapter is covered by a simulated client.

## 7. Integration handoff

- **Daniel (physics / EvidenceRank):** `overall_tier`, `assess_trial`, `MIN_TRIALS_FOR_COMPARISON`
  and `assess_compatibility` are consumed unchanged. *TODO(science):* with the default 5 %
  relative tolerance, B16 (18.2 % O₂) and B19 (17.5 % O₂) count as the same O₂
  condition (3.8 %). Link et al. place the 1 g / µg crossover near 18–19 % O₂, so a tighter
  O₂ tolerance near limits may be warranted. Your call. The assistant reflects any change
  automatically.
- **Yulian (data):** no files edited. Requests: (1) keep `provenance.reference` unique per
  source text, because duplicate (text, reference) chunks are dropped; (2) curate extinction
  and flammability-limit results as trial records if the assistant should answer those
  questions quantitatively.
- **Marycielo (UI):** `AskResponse` shape unchanged. `answer` now contains three headed
  sections (pre-wrap renders them). `model` can read
  `offline-template (fallback; rejected output from …)`; consider a badge for it.
- **Juanfer (FlameVision):** no dependency. Tracks stay `unvalidated`/non-measured, so the
  assistant will not print them as facts until they are curated as `measured`/`derived` with
  a method.
