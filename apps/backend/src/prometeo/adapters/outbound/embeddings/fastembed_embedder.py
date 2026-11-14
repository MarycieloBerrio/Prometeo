"""Local text embeddings with fastembed (ONNX runtime). No API key, no network at query time.

Default model: BAAI/bge-small-en-v1.5 (384 dimensions), the one `document_chunks.embedding` is
sized for (docs/adr/0002-evidence-store.md). The model file is downloaded once, on first use,
into fastembed's cache. Needs the `knowledge` extra (`uv sync --extra knowledge`).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384

# BGE v1.5 retrieval instruction: prepended to short queries, never to passages.
_BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class FastEmbedEmbedder:
    def __init__(self, model: str = DEFAULT_EMBEDDING_MODEL, batch_size: int = 32) -> None:
        self._model_name = model
        self._batch_size = batch_size
        self._engine: Any = None  # loaded lazily: importing the API must not load a model

    @property
    def model(self) -> str:
        return self._model_name

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(list(texts))

    def embed_query(self, text: str) -> list[float]:
        prefix = _BGE_QUERY_INSTRUCTION if "bge" in self._model_name.lower() else ""
        return self._embed([prefix + text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = [
            [float(x) for x in vector]
            for vector in self._load().embed(texts, batch_size=self._batch_size)
        ]
        for vector in vectors:
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise RuntimeError(
                    f"{self._model_name} produced {len(vector)} dimensions; the schema expects "
                    f"{EMBEDDING_DIMENSIONS}. Changing the model needs a migration and a re-index."
                )
        return vectors

    def _load(self) -> Any:
        if self._engine is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:  # pragma: no cover - depends on the optional extra
                raise RuntimeError(
                    "Embeddings need the `knowledge` extra: run `uv sync --extra knowledge`."
                ) from exc
            self._engine = TextEmbedding(model_name=self._model_name)
        return self._engine
