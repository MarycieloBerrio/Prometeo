"""04 · Prometeo Research Assistant — the Evidence Engine pipeline.

Order is mandatory:
  1. Evidence Retrieval   (structured trials + documents)
  2. Physics Validator    (compatibility of the retrieved trials)
  3. Scientific Analysis  (deterministic computations only)
  4. Evidence Audit       (EvidenceRank tiers, coverage, limitations)
  5. Explanation          (LLM writes prose ONLY from the audited packet)

If the audit says evidence is insufficient, the engine refuses to extrapolate and never
asks the LLM to invent a value.

Guarantees enforced here, in deterministic code, whatever explainer is wired in:

* **Observed evidence** comes only from trials that EvidenceRank keeps, and only from
  measurements that are reportable: `measured`, or `derived` with a recorded method, with a
  traceable source, never synthetic. `extracted` (unreviewed) and `unavailable` values are
  never printed as facts.
* **A conclusion needs coverage AND comparability.** EvidenceRank's coverage rule
  (`overall_tier`, owned by the physics/evidence team) is applied unchanged; on top of it,
  at least two usable trials must also be comparable under the Physics Validator (same fuel,
  geometry, thermal regime and flow direction). Otherwise the engine refuses.
* **`direct` means a controlled comparison.** The answer is `direct` only when, inside every
  interpreted comparable set, at most one condition differs, none is unknown and the trials
  are not a series on one physical sample. Otherwise it is capped at `partial`, in line with
  the Comparison Lab calling the same pairs "partially comparable".
* **Scope guard.** Questions asking for certification, safety verdicts, probabilities or
  "% confidence", partial-gravity or full-scale transfer, or predictions for untested
  conditions/materials are refused before any explainer runs.
* **The explainer writes only the Interpretation.** "Observed evidence" and "Limitations"
  are rendered from the audited packet by this module, so the model cannot alter them.
* **Retrieved documents are de-duplicated and ordered by investigation.** Repeated
  boilerplate (the same paragraph on several pages or in several reports) is collapsed to its
  best-ranked copy. Excerpts from the investigations of the usable trials come first, then
  those of investigations the catalog lists as related, then the rest: text similarity alone
  ranks generic microgravity prose about other fuels above the trials' own report.
* **Quoted passages are verbatim.** A citation is kept only if its text is a slice of the
  retrieved chunk it points at (whitespace aside), so a highlighted passage always exists in
  the source.
* **The interpretation is audited.** Citations not traceable to a retrieved document or a
  packet trial are dropped; any number absent from the packet replaces the interpretation
  with the deterministic one (the model output is not trusted to be "mostly right").
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from prometeo.application.ports.outbound import (
    Citation,
    DocumentChunk,
    DocumentRetriever,
    EvidencePacket,
    Explanation,
    ExplanationGenerator,
    TrialRepository,
)
from prometeo.domain.evidence.ranking import (
    MIN_TRIALS_FOR_COMPARISON,
    EvidenceAssessment,
    EvidenceTier,
    assess_trial,
    overall_tier,
)
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import (
    DataQuality,
    FlowDirection,
    Measurement,
    ThermalRegime,
    Trial,
)
from prometeo.domain.knowledge.similarity import is_near_duplicate
from prometeo.domain.physics.compatibility import (
    Comparability,
    Severity,
    Variable,
    assess_compatibility,
)
from prometeo.domain.shared.quantity import Quantity


@dataclass(frozen=True, slots=True)
class AssistantQuery:
    question: str
    criteria: TrialFilter
    metric: str | None = None  # e.g. "flame_spread_rate"
    model: str | None = None  # explanation model for this question; None = configured default


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    tier: EvidenceTier
    explanation: Explanation | None  # None when the engine refuses to conclude
    refusal_reason: str | None
    trials: tuple[Trial, ...]
    assessments: tuple[EvidenceAssessment, ...]
    documents: tuple[DocumentChunk, ...]
    computed_facts: tuple[str, ...]
    limitations: tuple[str, ...]
    # Trials whose facts were given to the explainer (members of a comparable set). Empty on
    # a refusal. A usable trial left out of it had no comparable counterpart.
    interpreted_trial_ids: frozenset[str] = frozenset()
    # Passages of the retrieved documents that the interpretation quotes (verbatim slices).
    citations: tuple[Citation, ...] = ()
    # Investigations of the usable trials: what "same investigation" means for a document.
    evidence_investigations: frozenset[str] = frozenset()


STANDING_LIMITATIONS = (
    "Microgravity results do not transfer directly to partial gravity (Moon, Mars).",
    "Small-sample results do not predict full-scale fires without validation.",
    "Prometeo does not certify materials or predict fire risk.",
)

DOCUMENTS_ARE_CONTEXT = (
    "Document excerpts are retrieved by text similarity to the question and shown as context; "
    "excerpts from the investigations of the assessed trials are listed first. Their order "
    "says nothing about experimental quality, and no value is computed from them."
)

ABSENCE_IS_NOT_SAFETY = (
    "No recorded evidence is not evidence of safety: it means the condition is untested "
    "or not yet curated."
)

SECTION_OBSERVED = "Observed evidence"
SECTION_INTERPRETATION = "Interpretation"
SECTION_LIMITATIONS = "Limitations"

DETERMINISTIC_MODEL = "offline-template"

DOCUMENT_LIMIT = 8  # excerpts shown and given to the explainer
# Retrieved before near-duplicates are dropped and the trials' investigations are preferred.
_DOCUMENT_CANDIDATES = 3 * DOCUMENT_LIMIT

SAME_INVESTIGATION = "same"
RELATED_INVESTIGATION = "related"
OTHER_INVESTIGATION = "other"
_RELATION_RANK = {SAME_INVESTIGATION: 0, RELATED_INVESTIGATION: 1, OTHER_INVESTIGATION: 2}

_TIER_RANK = {EvidenceTier.INSUFFICIENT: 0, EvidenceTier.PARTIAL: 1, EvidenceTier.DIRECT: 2}
_REPORTABLE_QUALITY = frozenset({DataQuality.MEASURED, DataQuality.DERIVED})


class AskResearchAssistant:
    def __init__(
        self,
        trials: TrialRepository,
        documents: DocumentRetriever,
        explainer: ExplanationGenerator,
    ) -> None:
        self._trials = trials
        self._documents = documents
        self._explainer = explainer

    def execute(self, query: AssistantQuery) -> AssistantAnswer:
        # 1. Retrieval
        trials = self._trials.search(query.criteria)
        candidates = distinct_documents(
            self._documents.retrieve(query.question, limit=_DOCUMENT_CANDIDATES)
        )

        # 2 + 4. Validation & audit: per-trial relevance/quality, coverage, comparability
        assessments = [assess_trial(t, query.criteria, query.metric) for t in trials]
        usable = [
            t
            for t, a in zip(trials, assessments, strict=True)
            if a.tier is not EvidenceTier.INSUFFICIENT
        ]
        investigations = frozenset(t.investigation.value for t in usable)
        docs = prioritize_documents(candidates, investigations)[:DOCUMENT_LIMIT]
        groups = comparable_groups(usable)
        grouped = [t for g in groups for t in g]
        grouped_ids = {t.id for t in grouped}

        tier = overall_tier(assessments)
        if tier is not EvidenceTier.INSUFFICIENT:
            tier = _weakest(
                tier, overall_tier([a for a in assessments if a.trial_id in grouped_ids])
            )
            if any(control_gaps(g) for g in groups):
                tier = _weakest(tier, EvidenceTier.PARTIAL)

        refusal = out_of_scope_reason(query.question)
        if refusal is None and tier is EvidenceTier.INSUFFICIENT:
            refusal = _insufficiency_reason(trials, assessments, usable, query, docs)

        # 3. Deterministic analysis — facts are built from audited, recorded values only
        if refusal is not None:
            return AssistantAnswer(
                tier=EvidenceTier.INSUFFICIENT,
                explanation=None,
                refusal_reason=refusal,
                trials=tuple(trials),
                assessments=tuple(assessments),
                documents=tuple(docs),
                computed_facts=tuple(_fact(t, query.metric) for t in usable),
                limitations=tuple(_limitations(usable, [], docs)),
                evidence_investigations=investigations,
            )

        facts = [_fact(t, query.metric) for t in grouped]
        limitations = _limitations(usable, groups, docs)

        # 5. Explanation — the model writes the Interpretation only; its output is audited
        packet = EvidencePacket(query.question, grouped, facts, docs, limitations)
        interpretation, audit_notes = audit_explanation(
            self._explainer.explain(packet, query.model), packet
        )
        limitations += audit_notes
        sources = _dedupe([*_fact_sources(grouped, query.metric), *interpretation.cited_sources])
        explanation = Explanation(
            compose_answer(facts, interpretation.text, limitations),
            sources,
            interpretation.model,
            interpretation.citations,
        )
        return AssistantAnswer(
            tier=tier,
            explanation=explanation,
            refusal_reason=None,
            trials=tuple(trials),
            assessments=tuple(assessments),
            documents=tuple(docs),
            computed_facts=tuple(facts),
            limitations=tuple(limitations),
            interpreted_trial_ids=frozenset(grouped_ids),
            citations=interpretation.citations,
            evidence_investigations=investigations,
        )


# ---- documents -----------------------------------------------------------------------------


def distinct_documents(docs: Sequence[DocumentChunk]) -> list[DocumentChunk]:
    """`docs` in rank order without near-duplicates: the best-ranked copy of a text is kept."""
    kept: list[DocumentChunk] = []
    for doc in docs:
        if not any(is_near_duplicate(doc.text, other.text) for other in kept):
            kept.append(doc)
    return kept


def document_relation(doc: DocumentChunk, investigations: frozenset[str]) -> str:
    """How a document's investigation relates to the investigations of the usable trials."""
    if doc.investigation is None or not investigations:
        return OTHER_INVESTIGATION
    if doc.investigation in investigations:
        return SAME_INVESTIGATION
    if investigations.intersection(doc.related_investigations):
        return RELATED_INVESTIGATION
    return OTHER_INVESTIGATION


def prioritize_documents(
    docs: Sequence[DocumentChunk], investigations: frozenset[str]
) -> list[DocumentChunk]:
    """`docs` with the trials' own investigations first, then related ones, then the rest.

    The order inside each of the three groups is the retriever's, unchanged.
    """
    return sorted(docs, key=lambda d: _RELATION_RANK[document_relation(d, investigations)])


# ---- scope guard ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ScopeRule:
    pattern: re.Pattern[str]
    reason: str


# Product-scope guard (AGENTS.md "Out of scope"), not a scientific classifier. It is
# deliberately over-inclusive: a false refusal is cheap, a false answer is not.
_SCOPE_RULES = (
    _ScopeRule(
        re.compile(
            r"\b(?:certif\w*|qualif(?:y|ies|ied|ication)|flight[- ]worthy|approved? for)\b",
            re.IGNORECASE,
        ),
        "Prometeo does not certify or qualify materials; that requires standardized "
        "flammability testing and an approval authority.",
    ),
    _ScopeRule(
        re.compile(r"\b(?:un)?safe(?:ly|st|r)?\b", re.IGNORECASE),
        "Prometeo does not issue safety verdicts. " + ABSENCE_IS_NOT_SAFETY,
    ),
    _ScopeRule(
        re.compile(
            r"\b(?:probabilit\w*|likelihood|odds|how (?:likely|confident|sure)"
            r"|confidence (?:score|level|interval)|percent (?:chance|confiden\w*|safe))\b"
            r"|%\s*(?:chance|confiden|safe|probab|risk)",
            re.IGNORECASE,
        ),
        "Prometeo reports interpretable evidence tiers (direct, partial, insufficient), not "
        "probabilities or confidence percentages; no validated statistical model supports one.",
    ),
    _ScopeRule(
        re.compile(
            r"\b(?:moon|lunar|mars|martian|partial[- ]gravity|planetary surface)\b",
            re.IGNORECASE,
        ),
        "Microgravity results do not transfer to partial gravity (Moon, Mars), and no curated "
        "evidence covers those gravity levels.",
    ),
    _ScopeRule(
        re.compile(
            r"\b(?:full[- ]scale|large[- ]scale|real[- ]size"
            r"|(?:entire|whole) (?:spacecraft|module|cabin|habitat|vehicle|station))\b",
            re.IGNORECASE,
        ),
        "Small-sample experiments do not predict full-scale fires without validation.",
    ),
    _ScopeRule(
        re.compile(
            r"\b(?:predict\w*|extrapolat\w*|forecast\w*|what would happen)\b", re.IGNORECASE
        ),
        "Prometeo does not predict untested conditions; it reports recorded evidence only.",
    ),
    _ScopeRule(
        re.compile(
            r"\b(?:new|novel|hypothetical|untested|proposed|future)\s+(?:\w+\s+)?"
            r"(?:materials?|fuels?|polymers?|fabrics?)\b",
            re.IGNORECASE,
        ),
        "Prometeo will not infer the behaviour of materials outside the curated evidence.",
    ),
)


def out_of_scope_reason(question: str) -> str | None:
    """Reason to refuse a question whatever the evidence, or None if it is in scope."""
    reasons = _dedupe(r.reason for r in _SCOPE_RULES if r.pattern.search(question))
    if not reasons:
        return None
    return "Out of scope for Prometeo: " + " ".join(reasons)


# ---- comparability -------------------------------------------------------------------------


def comparable_groups(trials: Sequence[Trial]) -> list[tuple[Trial, ...]]:
    """Sets of >= MIN_TRIALS_FOR_COMPARISON trials that are pairwise comparable.

    Uses the Physics Validator with every variable controlled: a categorical mismatch
    (fuel, geometry, thermal regime, flow direction, synthetic vs real) blocks the pair;
    numeric differences only warn. Groups are built greedily in id order as cliques, so a
    trial with an unknown flow direction never bridges an opposed and a concurrent trial.
    """
    groups: list[list[Trial]] = []
    for trial in sorted(trials, key=lambda t: t.id):
        for group in groups:
            if all(_comparable(trial, member) for member in group):
                group.append(trial)
                break
        else:
            groups.append([trial])
    return [tuple(g) for g in groups if len(g) >= MIN_TRIALS_FOR_COMPARISON]


def _comparable(a: Trial, b: Trial) -> bool:
    return assess_compatibility(a, b, frozenset()).level is not Comparability.NOT_COMPARABLE


# Recorded value of each numeric condition the Physics Validator controls.
_NUMERIC_CONDITIONS: dict[Variable, Callable[[Trial], Quantity | None]] = {
    Variable.THICKNESS: lambda t: t.geometry.thickness,
    Variable.OXYGEN: lambda t: t.oxygen,
    Variable.FLOW_SPEED: lambda t: t.ventilation.speed,
    Variable.PRESSURE: lambda t: t.pressure,
}


def _is_unknown(variable: Variable, trial: Trial) -> bool:
    if variable is Variable.THERMAL_REGIME:
        return trial.geometry.thermal_regime is ThermalRegime.UNKNOWN
    if variable is Variable.FLOW_DIRECTION:
        return trial.ventilation.direction is FlowDirection.UNKNOWN
    recorded = _NUMERIC_CONDITIONS.get(variable)
    return recorded is not None and recorded(trial) is None


def _uncontrolled_conditions(group: tuple[Trial, ...]) -> tuple[list[str], list[str]]:
    """(conditions that differ, conditions unknown for a trial) within a comparable set.

    "Differ" and "unknown" are kept apart: a pressure nobody recorded is not a pressure
    that changed, and saying it "differs" would overstate what is known.
    """
    differ: set[Variable] = set()
    unknown: set[Variable] = set()
    for i, a in enumerate(group):
        for b in group[i + 1 :]:
            for issue in assess_compatibility(a, b, frozenset()).issues:
                # FUEL warnings are the validator's "different investigations" notice; fuel
                # mismatches themselves are blocking and never reach a group.
                if issue.severity is not Severity.WARNING or issue.variable is Variable.FUEL:
                    continue
                variable = issue.variable
                if _is_unknown(variable, a) or _is_unknown(variable, b):
                    unknown.add(variable)
                    continue
                recorded = _NUMERIC_CONDITIONS.get(variable)
                # The validator files its same-sample notice under flow_speed; equal recorded
                # values mean the pair carries only that notice, not a difference.
                if recorded is None or recorded(a) != recorded(b):
                    differ.add(variable)
    return sorted(v.value for v in differ), sorted(v.value for v in unknown)


def _group_limitation(index: int, group: tuple[Trial, ...]) -> str:
    head = group[0]
    label = (
        f"{head.fuel.material}, {head.geometry.type} ({head.geometry.thermal_regime}), "
        f"{head.ventilation.direction} flow"
    )
    differ, unknown = _uncontrolled_conditions(group)
    ids = ", ".join(t.id for t in group)
    text = f"Comparable set {index} [{ids}] shares {label}."
    if differ:
        text += f" Within it these conditions differ: {', '.join(differ)}."
    if unknown:
        text += (
            f" These conditions are unknown for at least one trial: {', '.join(unknown)}; "
            "unknown is not the same as equal."
        )
    if differ or unknown:
        text += (
            " A difference in a result cannot be attributed to one variable while others "
            "also change or are unknown; use the Comparison Lab with an explicit varied "
            "variable."
        )
    return text


def _same_sample_series(group: tuple[Trial, ...]) -> dict[str, list[str]]:
    """sample_id -> trial ids, for samples that carry more than one trial of the set."""
    by_sample: dict[str, list[str]] = {}
    for trial in group:
        if trial.sample_id:
            by_sample.setdefault(trial.sample_id, []).append(trial.id)
    return {sample: ids for sample, ids in by_sample.items() if len(ids) > 1}


def control_gaps(group: tuple[Trial, ...]) -> list[str]:
    """Why a comparable set is not a controlled comparison; empty when it is one.

    A controlled comparison changes at most one condition, records the others, and does not
    reuse one physical sample. Anything else supports a description, not an isolated effect,
    so the answer's tier is capped at `partial`.
    """
    differ, unknown = _uncontrolled_conditions(group)
    gaps: list[str] = []
    if len(differ) > 1:
        gaps.append(f"more than one condition differs ({', '.join(differ)})")
    if unknown:
        gaps.append(f"{', '.join(unknown)} is unknown for at least one trial")
    if _same_sample_series(group):
        gaps.append("several trials are condition points on one physical sample")
    return gaps


def _same_sample_limitation(group: tuple[Trial, ...]) -> str | None:
    """Flag condition points taken on one physical sample: a series, not replicates."""
    series = _same_sample_series(group)
    if not series:
        return None
    listed = "; ".join(
        f"sample {sample} [{', '.join(ids)}]" for sample, ids in sorted(series.items())
    )
    return (
        f"Same physical sample: {listed}. Trials on one sample are condition points from a "
        "single experimental sequence, not independent replicates. A trend across them is a "
        "descriptive series only; it is not statistical replication and carries no "
        "uncertainty estimate."
    )


# ---- facts and limitations -----------------------------------------------------------------


def _is_reportable(m: Measurement) -> bool:
    if m.quality not in _REPORTABLE_QUALITY or not m.provenance.is_traceable:
        return False
    return m.quality is not DataQuality.DERIVED or bool(m.method)


def _reportable(trial: Trial, metric: str | None) -> list[Measurement]:
    if trial.is_synthetic:
        return []
    return [
        m for m in trial.results if (metric is None or m.name == metric) and _is_reportable(m)
    ]


def _conditions(t: Trial) -> str:
    def known(q: object) -> str:
        return str(q) if q is not None else "unknown"

    geometry = f"{t.geometry.type}"
    if t.geometry.thickness is not None:
        geometry += f" {t.geometry.thickness}"
    parts = [
        f"O2 {known(t.oxygen)}",
        f"flow {known(t.ventilation.speed)} ({t.ventilation.direction})",
        f"{t.fuel.material} {geometry} ({t.geometry.thermal_regime})",
    ]
    if t.pressure is not None:
        parts.append(f"pressure {t.pressure}")
    return ", ".join(parts)


def _source(ref: str, page: str | None) -> str:
    return f"{ref} — {page}" if page else ref


def _fact(t: Trial, metric: str | None) -> str:
    head = f"[{t.id}] {t.investigation}"
    measurements = _reportable(t, metric)
    if not measurements:
        wanted = f"'{metric}'" if metric else "reviewed"
        return f"{head} · no {wanted} result reportable · conditions: {_conditions(t)}"
    values = "; ".join(
        f"{m.name} = {m.value} ({m.quality}"
        + (f", method: {m.method}" if m.quality is DataQuality.DERIVED else "")
        + f") · source: {_source(m.provenance.reference, m.provenance.page)}"
        for m in measurements
    )
    return f"{head} · {values} · conditions: {_conditions(t)}"


def _fact_sources(trials: Iterable[Trial], metric: str | None) -> list[str]:
    out: list[str] = []
    for t in trials:
        out.append(t.provenance.reference)
        out.extend(m.provenance.reference for m in _reportable(t, metric))
    return out


def _limitations(
    usable: Sequence[Trial], groups: Sequence[tuple[Trial, ...]], docs: Sequence[DocumentChunk]
) -> list[str]:
    out = list(STANDING_LIMITATIONS)
    in_scope = [t for g in groups for t in g] or list(usable)
    investigations = sorted({t.investigation.value for t in in_scope})
    if len(investigations) > 1:
        out.append(
            f"Trials come from different investigations ({', '.join(investigations)}): "
            "facilities, scales and methods differ; they are not one dataset."
        )
    for index, group in enumerate(groups, start=1):
        out.append(_group_limitation(index, group))
        same_sample = _same_sample_limitation(group)
        if same_sample:
            out.append(same_sample)
        gaps = control_gaps(group)
        if gaps:
            out.append(
                f"Evidence tier is partial, not direct: comparable set {index} is not a "
                f"controlled comparison ({'; '.join(gaps)})."
            )
    grouped_ids = {t.id for g in groups for t in g}
    excluded = [t.id for t in usable if t.id not in grouped_ids]
    if groups and excluded:
        out.append(
            "Excluded from the interpretation (no comparable counterpart): "
            + ", ".join(sorted(excluded))
            + "."
        )
    if docs:
        out.append(DOCUMENTS_ARE_CONTEXT)
    return out


# ---- refusal reasons -----------------------------------------------------------------------


def _describe_filter(f: TrialFilter, metric: str | None) -> str:
    fields: tuple[tuple[str, object], ...] = (
        ("investigation", f.investigation),
        ("material", f.material),
        ("geometry", f.geometry),
        ("phenomenon", f.phenomenon),
        ("flow_direction", f.flow_direction),
        ("oxygen_min", f.oxygen_min),
        ("oxygen_max", f.oxygen_max),
        ("flow_min", f.flow_min),
        ("flow_max", f.flow_max),
        ("metric", metric),
    )
    return ", ".join(f"{name}={value}" for name, value in fields if value is not None)


def _insufficiency_reason(
    trials: Sequence[Trial],
    assessments: Sequence[EvidenceAssessment],
    usable: Sequence[Trial],
    query: AssistantQuery,
    docs: Sequence[DocumentChunk],
) -> str:
    conditions = _describe_filter(query.criteria, query.metric)
    if not trials:
        reason = "No curated trial matches the requested conditions"
        reason += f" ({conditions})." if conditions else "."
        reason += " " + ABSENCE_IS_NOT_SAFETY
    elif all(t.is_synthetic for t in trials):
        reason = (
            f"Only synthetic development fixtures match ({len(trials)}). They are invented "
            "values, never evidence, so no conclusion is drawn."
        )
    elif len(usable) < MIN_TRIALS_FOR_COMPARISON:
        rejected = Counter(
            r for a in assessments if a.tier is EvidenceTier.INSUFFICIENT for r in a.reasons
        )
        reason = (
            f"{len(usable)} of {len(trials)} matching trials are usable evidence; a conclusion "
            f"needs at least {MIN_TRIALS_FOR_COMPARISON} comparable trials with measured, "
            "traceable results"
        )
        reason += f" for '{query.metric}'." if query.metric else "."
        if rejected:
            reason += " Missing or rejected: " + "; ".join(
                f"{text} ({count} trial{'s' if count > 1 else ''})"
                for text, count in sorted(rejected.items())
            ) + "."
    else:
        reason = (
            f"{len(usable)} usable trials were found, but no two share fuel, geometry, thermal "
            "regime and flow direction (Physics Validator), so their results cannot be "
            "compared. Narrow the question with material, geometry or flow_direction."
        )
    if docs:
        reason += (
            f" {len(docs)} related document excerpt(s) are returned as context only; documents "
            "alone do not support a quantitative conclusion here."
        )
    return reason + " Prometeo will not extrapolate beyond recorded evidence."


# ---- explanation audit ---------------------------------------------------------------------

# A number not glued to a word or a decimal point. Trial ids ("B16") and section numbers
# ("§2.2.5") are tokenized the same way on both sides, so they stay consistent.
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\d)")
_LIST_MARKER = re.compile(r"(?m)^\s*\d+[.)]\s+")


def _numbers(text: str) -> list[str]:
    return _NUMBER.findall(_LIST_MARKER.sub("", text))


def _packet_corpus(packet: EvidencePacket) -> list[str]:
    texts = [packet.question, *packet.computed_facts, *packet.limitations]
    for d in packet.documents:
        p = d.provenance
        texts += [d.id, d.text, p.reference, p.page or "", p.doi or ""]
    for t in packet.trials:
        texts += [t.id, t.sample_id or "", t.provenance.reference, t.provenance.page or ""]
        for m in t.results:
            texts += [m.provenance.reference, m.provenance.page or ""]
    return texts


def unsupported_numbers(text: str, packet: EvidencePacket) -> list[str]:
    """Numbers in `text` that do not appear in the audited packet.

    A written value is accepted if it equals a packet number, or is that number rounded to
    the decimals written (e.g. 0.07 for 0.0678). Integers must match exactly. Unit
    conversions, ratios, averages and any other computed value are therefore rejected:
    the explainer must not compute.
    """
    allowed = {float(n) for t in _packet_corpus(packet) for n in _numbers(t)}
    allowed |= {float(len(packet.trials)), float(len(packet.documents))}
    out: list[str] = []
    for token in _numbers(text):
        value = float(token)
        decimals = len(token.split(".")[1]) if "." in token else 0
        ok = any(
            abs(value - a) < 1e-9 or (decimals > 0 and abs(round(a, decimals) - value) < 1e-9)
            for a in allowed
        )
        if not ok and token not in out:
            out.append(token)
    return out


def allowed_sources(packet: EvidencePacket) -> set[str]:
    refs = {d.provenance.reference for d in packet.documents}
    for t in packet.trials:
        refs.add(t.provenance.reference)
        refs.update(m.provenance.reference for m in t.results)
    return refs


def deterministic_interpretation(packet: EvidencePacket) -> str:
    """Interpretation written without a model; safe fallback for any explainer failure."""
    parts = [
        "No language model was used for this interpretation.",
        "The observed evidence lists recorded values exactly as curated, each with its data "
        "quality and source. The assistant does not fit trends or compute differences from "
        "them; to quantify the effect of one variable, compare two trials from the same "
        "comparable set in the Comparison Lab, which withholds deltas when controlled "
        "variables differ.",
    ]
    refs = _dedupe(d.provenance.reference for d in packet.documents)
    if refs:
        parts.append(
            "Retrieved document excerpts (background context, not measurements): "
            + "; ".join(refs)
            + "."
        )
    return " ".join(parts)


def audit_explanation(raw: Explanation, packet: EvidencePacket) -> tuple[Explanation, list[str]]:
    """Validate an explainer's output against the packet. Returns (interpretation, notes)."""
    notes: list[str] = []
    known = allowed_sources(packet)
    cited = _dedupe(s for s in raw.cited_sources if s in known)
    dropped = _dedupe(s for s in raw.cited_sources if s not in known)
    if dropped:
        notes.append(
            f"Removed {len(dropped)} citation(s) that match no retrieved document or trial "
            "record; they are not presented as sources."
        )

    text = raw.text.strip()
    unsupported = unsupported_numbers(text, packet)
    if text and not unsupported:
        return Explanation(text, cited, raw.model, verbatim_citations(raw.citations, packet)), notes

    if unsupported:
        notes.append(
            f"The explanation model stated {len(unsupported)} number(s) that are not in the "
            "audited evidence; its text was replaced by the deterministic interpretation."
        )
    model = (
        raw.model
        if raw.model == DETERMINISTIC_MODEL
        else f"{DETERMINISTIC_MODEL} (fallback; rejected output from {raw.model})"
    )
    doc_refs = _dedupe(d.provenance.reference for d in packet.documents)
    return Explanation(deterministic_interpretation(packet), doc_refs, model), notes


def _squash(text: str) -> str:
    return " ".join(text.split())


def verbatim_citations(
    citations: Iterable[Citation], packet: EvidencePacket
) -> tuple[Citation, ...]:
    """Citations that quote a retrieved chunk word for word (whitespace aside), de-duplicated.

    Anything else is dropped silently: a passage that is not in the chunk it names cannot be
    shown as a highlighted quotation of the source.
    """
    chunks = {d.id: _squash(d.text) for d in packet.documents}
    kept: dict[tuple[str, str], Citation] = {}
    for citation in citations:
        quoted = _squash(citation.cited_text)
        if quoted and quoted in chunks.get(citation.chunk_id, ""):
            kept.setdefault((citation.chunk_id, quoted), Citation(citation.chunk_id, quoted))
    return tuple(kept.values())


def compose_answer(facts: Sequence[str], interpretation: str, limitations: Sequence[str]) -> str:
    lines = [SECTION_OBSERVED]
    lines += [f"- {f}" for f in facts] or ["- (none)"]
    lines += ["", SECTION_INTERPRETATION, interpretation, "", SECTION_LIMITATIONS]
    lines += [f"- {lim}" for lim in limitations]
    return "\n".join(lines)


# ---- helpers -------------------------------------------------------------------------------


def _weakest(a: EvidenceTier, b: EvidenceTier) -> EvidenceTier:
    return a if _TIER_RANK[a] <= _TIER_RANK[b] else b


def _dedupe(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))
