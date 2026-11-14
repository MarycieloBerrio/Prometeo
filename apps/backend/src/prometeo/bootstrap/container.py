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
    TextEmbedder,
    TrialRepository,
)
from prometeo.application.use_cases.ask_research_assistant import AskResearchAssistant
from prometeo.application.use_cases.build_knowledge_base import BuildKnowledgeBase
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.application.use_cases.coverage_map import BuildCoverageMap
from prometeo.application.use_cases.derive_bass2_flow import DeriveBass2FlowSpeeds
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
    documents = documents or document_retriever(settings)
    explainer = explainer or _explainer(settings)
    return Container(
        settings=settings,
        explore=ExploreExperiments(trials),
        compare=CompareTrials(trials),
        coverage=BuildCoverageMap(trials),
        assistant=AskResearchAssistant(trials, documents, explainer),
    )


def document_retriever(settings: Settings) -> DocumentRetriever:
    if settings.document_store == "postgres":
        from prometeo.adapters.outbound.retrieval.pgvector_retriever import PgVectorRetriever

        return PgVectorRetriever(settings.database_url, _embedder(settings))
    return KeywordRetriever(settings.data_dir / settings.document_chunks_file)


def build_knowledge_base_job(settings: Settings) -> BuildKnowledgeBase:
    """Offline ingestion job (CLI only). Kept out of `Container`: the API never runs it."""
    from prometeo.adapters.outbound.documents.text_extractor import DocumentTextExtractor
    from prometeo.adapters.outbound.nasa.psi_client import PsiClient
    from prometeo.adapters.outbound.persistence.postgres_knowledge_store import (
        PostgresKnowledgeStore,
    )

    return BuildKnowledgeBase(
        catalog=PsiClient(
            settings.psi_base_url,
            cache_dir=settings.raw_dir / "psi",
            cache_root=settings.raw_dir,
        ),
        store=PostgresKnowledgeStore(settings.database_url),
        embedder=_embedder(settings),
        extractor=DocumentTextExtractor(),
    )


def derive_bass2_flow_job(settings: Settings) -> DeriveBass2FlowSpeeds:
    """Offline curation aid (CLI only): reads the PSI-25 table, needs no database."""
    from prometeo.adapters.outbound.nasa.psi_client import PsiClient

    return DeriveBass2FlowSpeeds(
        PsiClient(
            settings.psi_base_url,
            cache_dir=settings.raw_dir / "psi",
            cache_root=settings.raw_dir,
        )
    )


def _embedder(settings: Settings) -> TextEmbedder:
    from prometeo.adapters.outbound.embeddings.fastembed_embedder import FastEmbedEmbedder

    return FastEmbedEmbedder(settings.embedding_model)


def _trial_repository(settings: Settings) -> TrialRepository:
    if settings.trial_store == "postgres":
        return PostgresTrialRepository(settings.database_url)
    return JsonTrialRepository(settings.trial_paths())


def _explainer(settings: Settings) -> ExplanationGenerator:
    if settings.explainer == "anthropic":
        from prometeo.adapters.outbound.llm.anthropic_explainer import AnthropicExplainer

        return AnthropicExplainer(settings.anthropic_model, settings.anthropic_effort)
    return OfflineExplainer()
