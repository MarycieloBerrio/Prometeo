"""Composition root — the ONLY module that instantiates adapters and injects them into use cases."""

from __future__ import annotations

from dataclasses import dataclass

from prometeo.adapters.outbound.cfd.json_cfd_repository import JsonCfdRepository
from prometeo.adapters.outbound.llm.offline_explainer import OfflineExplainer
from prometeo.adapters.outbound.persistence.json_trial_repository import JsonTrialRepository
from prometeo.adapters.outbound.persistence.postgres_trial_repository import (
    PostgresTrialRepository,
)
from prometeo.adapters.outbound.persistence.source_file_store import NoSourceFiles
from prometeo.adapters.outbound.retrieval.keyword_retriever import KeywordRetriever
from prometeo.application.ports.outbound import (
    DocumentRetriever,
    ExplainerModel,
    ExplanationGenerator,
    SourceFileStore,
    TextEmbedder,
    TrialRepository,
)
from prometeo.application.use_cases.ask_research_assistant import AskResearchAssistant
from prometeo.application.use_cases.build_knowledge_base import BuildKnowledgeBase
from prometeo.application.use_cases.cfd_simulations import GetCfdSimulation, ListCfdSimulations
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.application.use_cases.coverage_map import BuildCoverageMap
from prometeo.application.use_cases.derive_bass2_flow import DeriveBass2FlowSpeeds
from prometeo.application.use_cases.explore_experiments import ExploreExperiments
from prometeo.application.use_cases.locate_source_document import LocateSourceDocument
from prometeo.bootstrap.settings import Settings


@dataclass(frozen=True)
class Container:
    settings: Settings
    explore: ExploreExperiments
    compare: CompareTrials
    coverage: BuildCoverageMap
    assistant: AskResearchAssistant
    list_cfd: ListCfdSimulations
    get_cfd: GetCfdSimulation
    source_document: LocateSourceDocument
    # Models a question may ask for, default first. Empty when no language model is wired in.
    explainer_models: tuple[ExplainerModel, ...] = ()


def build_container(
    settings: Settings,
    *,
    trials: TrialRepository | None = None,
    documents: DocumentRetriever | None = None,
    explainer: ExplanationGenerator | None = None,
    source_files: SourceFileStore | None = None,
) -> Container:
    """Build the object graph. Keyword overrides exist for tests."""
    trials = trials or _trial_repository(settings)
    documents = documents or document_retriever(settings)
    # An injected explainer is a test double: it offers no model choice.
    models = _explainer_models(settings) if explainer is None else ()
    explainer = explainer or _explainer(settings)
    cfd_repo = JsonCfdRepository(settings.data_dir / "simulations" / "cfd" / "manifests")
    return Container(
        settings=settings,
        explore=ExploreExperiments(trials),
        compare=CompareTrials(trials),
        coverage=BuildCoverageMap(trials),
        assistant=AskResearchAssistant(trials, documents, explainer),
        list_cfd=ListCfdSimulations(cfd_repo),
        get_cfd=GetCfdSimulation(cfd_repo, settings.data_dir),
        source_document=LocateSourceDocument(source_files or _source_files(settings)),
        explainer_models=models,
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


def _source_files(settings: Settings) -> SourceFileStore:
    if settings.document_store == "postgres":
        from prometeo.adapters.outbound.persistence.source_file_store import (
            PostgresSourceFileStore,
        )

        return PostgresSourceFileStore(settings.database_url, settings.raw_dir)
    return NoSourceFiles()


def _explainer_models(settings: Settings) -> tuple[ExplainerModel, ...]:
    if settings.explainer != "anthropic":
        return ()
    from prometeo.adapters.outbound.llm.anthropic_explainer import explainer_models

    return explainer_models(settings.anthropic_model_choices())


def _explainer(settings: Settings) -> ExplanationGenerator:
    if settings.explainer == "anthropic":
        import anthropic

        from prometeo.adapters.outbound.llm.anthropic_explainer import AnthropicExplainer

        # A key from settings (env or .env) is passed explicitly, because pydantic-settings
        # does not export .env values to os.environ. Without one, the SDK resolves its own
        # credentials (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN or an `ant auth login` profile).
        key = settings.anthropic_key()
        client = anthropic.Anthropic(api_key=key) if key else None
        return AnthropicExplainer(
            settings.anthropic_model, settings.anthropic_effort, client=client
        )
    return OfflineExplainer()
