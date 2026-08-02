"""Local embeddings. No paid API, ever.

Primary: sentence-transformers `all-MiniLM-L6-v2` (384-d, normalised).
Fallback: a deterministic hashing vectoriser over word + character n-grams.

The fallback exists because the primary path needs a ~90 MB model download and a
working torch install, which is not guaranteed on a constrained machine. It is
noticeably weaker at synonym matching but keeps lexical retrieval working, so a
demo still answers from the knowledge base instead of erroring out. `/api/health`
reports which one is live.
"""

from __future__ import annotations

import hashlib
import math
import re
import threading

from app.core.config import settings
from app.core.logging_config import get_logger

log = get_logger("rag.embed")

FALLBACK_DIM = 384
_TOKEN = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    """a an and are as at be by for from has have how i in is it its of on or that the
    to was were what when where which who will with you your we our us this these those
    do does did can could should would""".split()
)


class BaseEmbedder:
    name = "base"
    dimension = FALLBACK_DIM

    # Relevance floor appropriate to this embedder's score distribution. Cosine
    # scores are not comparable across embedders, so the threshold belongs to the
    # embedder rather than to a single global setting.
    score_floor = 0.18

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class SentenceTransformerEmbedder(BaseEmbedder):
    score_floor = 0.18          # MiniLM: related text lands around 0.3-0.7

    def __init__(self, model_name: str, device: str = "cpu"):
        from sentence_transformers import SentenceTransformer

        log.info("Loading embedding model %s (first run downloads ~90MB)…", model_name)
        self._model = SentenceTransformer(model_name, device=device)
        self.name = model_name
        self.dimension = int(self._model.get_sentence_embedding_dimension())
        log.info("Embedding model ready (dim=%d)", self.dimension)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]


class HashingEmbedder(BaseEmbedder):
    """Dependency-free lexical fallback: hashed word unigrams/bigrams + char 4-grams,
    sublinear term frequency, L2-normalised so cosine == dot product."""

    name = "local-hashing-fallback"

    # Lexical overlap between a short query and a long chunk produces much lower
    # cosines than a semantic model does — a genuine match often lands near 0.10
    # rather than 0.40. Using MiniLM's floor here would discard real hits.
    score_floor = 0.06

    def __init__(self, dimension: int = FALLBACK_DIM):
        self.dimension = dimension

    @staticmethod
    def _bucket(token: str, dimension: int) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % dimension

    def _features(self, text: str) -> list[tuple[str, float]]:
        words = [w for w in _TOKEN.findall(text.lower()) if w not in _STOPWORDS]
        features: list[tuple[str, float]] = [(w, 1.0) for w in words]
        features += [(f"{a}_{b}", 1.4) for a, b in zip(words, words[1:])]
        for word in words:
            if len(word) > 5:
                padded = f"#{word}#"
                features += [(padded[i:i + 4], 0.35) for i in range(len(padded) - 3)]
        return features

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            counts: dict[int, float] = {}
            for token, weight in self._features(text or ""):
                counts[self._bucket(token, self.dimension)] = (
                    counts.get(self._bucket(token, self.dimension), 0.0) + weight
                )
            for index, raw in counts.items():
                vector[index] = 1.0 + math.log(raw) if raw > 0 else 0.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors


_embedder: BaseEmbedder | None = None
_lock = threading.Lock()


def get_embedder() -> BaseEmbedder:
    """Lazy singleton — the model loads on first use, not at import time, so the
    API starts instantly and only pays the cost when something is actually indexed."""
    global _embedder
    if _embedder is not None:
        return _embedder

    with _lock:
        if _embedder is not None:
            return _embedder
        try:
            _embedder = SentenceTransformerEmbedder(
                settings.embedding_model, settings.embedding_device
            )
        except Exception as exc:  # noqa: BLE001 - any failure must degrade, not crash
            log.warning(
                "sentence-transformers unavailable (%s). "
                "Falling back to the local hashing embedder — retrieval will be "
                "lexical rather than semantic.",
                exc,
            )
            _embedder = HashingEmbedder()
        return _embedder


def embedder_info() -> dict:
    """Reported by /api/health without forcing the model to load."""
    if _embedder is None:
        return {"loaded": False, "configured_model": settings.embedding_model}
    return {
        "loaded": True,
        "model": _embedder.name,
        "dimension": _embedder.dimension,
        "semantic": not isinstance(_embedder, HashingEmbedder),
    }
