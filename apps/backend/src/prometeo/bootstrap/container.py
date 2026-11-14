"""Composition root — the ONLY module that instantiates adapters and injects them into use cases."""

from __future__ import annotations

from dataclasses import dataclass

from prometeo.adapters.outbound.llm.offline_explainer import OfflineExplainer
from prometeo.adapters.outbound.persistence.json_trial_repository import JsonTrialRepository
from prometeo.adapters.outbound.persistence.postgres_trial_repository import (
    PostgresTrialRepository,
)
from prometeo.adapters.outbound.retrieval.keyword_retriever import KeywordRetriever
from prometeo.application.ports.outbound import (
    DocumentRetriever,
    ExplanationGenerator,
    TrialRepository,
)
from prometeo.application.use_cases.ask_research_assistant import AskResearchAssistant
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.application.use_cases.coverage_map import BuildCoverageMap
from prometeo.application.use_cases.explore_experiments import ExploreExperiments
from prometeo.bootstrap.settings import Settings


@dataclass(frozen=True)
class Container:
    settings: Settings
    explore: ExploreExperiments
    compare: CompareTrials
    coverage: BuildCoverageMap
    assistant: AskResearchAssistant


def build_container(
    settings: Settings,
    *,
    trials: TrialRepository | None = None,
    documents: DocumentRetriever | None = None,
    explainer: ExplanationGenerator | None = None,
) -> Container:
    """Build the object graph. Keyword overrides exist for tests."""
    trials = trials or _trial_repository(settings)
    documents = documents or KeywordRetriever(settings.data_dir / settings.document_chunks_file)
    explainer = explainer or _explainer(settings)
    return Container(
        settings=settings,
        explore=ExploreExperiments(trials),
        compare=CompareTrials(trials),
        coverage=BuildCoverageMap(trials),
        assistant=AskResearchAssistant(trials, documents, explainer),
    )


def _trial_repository(settings: Settings) -> TrialRepository:
    if settings.trial_store == "postgres":
        return PostgresTrialRepository(settings.database_url)
    return JsonTrialRepository(settings.trial_paths())


def _explainer(settings: Settings) -> ExplanationGenerator:
    if settings.explainer == "anthropic":
        from prometeo.adapters.outbound.llm.anthropic_explainer import AnthropicExplainer

        return AnthropicExplainer(settings.anthropic_model, settings.anthropic_effort)
    return OfflineExplainer()
