"""Per-product vector index.

FAISS `IndexFlatIP` over L2-normalised vectors == exact cosine similarity. Flat
is the right call here: a product's knowledge base is thousands of chunks, not
millions, and exact search removes a whole class of recall bugs.

If `faiss` is not installed, a NumPy brute-force store with identical semantics
takes over. Same file format for the sidecar metadata either way, so switching
does not invalidate anything except the raw vectors.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.logging_config import get_logger

log = get_logger("rag.vectors")

try:  # pragma: no cover - environment dependent
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]
    NUMPY_AVAILABLE = False

try:  # pragma: no cover - environment dependent
    import faiss

    FAISS_AVAILABLE = True
except ImportError:  # pragma: no cover
    faiss = None  # type: ignore[assignment]
    FAISS_AVAILABLE = False


@dataclass
class SearchHit:
    chunk_id: str
    score: float
    content: str
    source_label: str
    source_kind: str
    metadata: dict


class ProductVectorIndex:
    """One index per product, persisted to `data/faiss/<product_id>.*`."""

    def __init__(self, product_id: str, dimension: int):
        self.product_id = product_id
        self.dimension = dimension
        self.records: list[dict] = []
        self._index = None
        self._matrix = None          # NumPy fallback
        self._lock = threading.Lock()
        self._reset_backend()

    # -- paths --------------------------------------------------------------

    @property
    def _base(self) -> Path:
        return settings.faiss_path / self.product_id

    @property
    def _meta_file(self) -> Path:
        return self._base.with_suffix(".meta.json")

    @property
    def _index_file(self) -> Path:
        return self._base.with_suffix(".faiss")

    @property
    def _vectors_file(self) -> Path:
        return self._base.with_suffix(".npy")

    # -- backend ------------------------------------------------------------

    def _reset_backend(self) -> None:
        if FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(self.dimension)
            self._matrix = None
        elif NUMPY_AVAILABLE:
            self._index = None
            self._matrix = np.zeros((0, self.dimension), dtype="float32")
        else:
            self._index = None
            self._matrix = []          # list-of-lists, pure Python

    @property
    def backend(self) -> str:
        if FAISS_AVAILABLE:
            return "faiss"
        return "numpy" if NUMPY_AVAILABLE else "python"

    @property
    def size(self) -> int:
        return len(self.records)

    # -- mutation -----------------------------------------------------------

    def replace_all(self, vectors: list[list[float]], records: list[dict]) -> None:
        """Rebuild from scratch. Indexing is always a full rebuild — a product's
        knowledge base is small, and it removes every stale-vector failure mode."""
        if len(vectors) != len(records):
            raise ValueError("vectors and records must be the same length")

        with self._lock:
            self._reset_backend()
            self.records = list(records)

            if vectors:
                if FAISS_AVAILABLE:
                    self._index.add(np.array(vectors, dtype="float32"))
                elif NUMPY_AVAILABLE:
                    self._matrix = np.array(vectors, dtype="float32")
                else:
                    self._matrix = [list(v) for v in vectors]
            self._persist()

        log.info(
            "Indexed %d chunks for product %s via %s",
            len(records), self.product_id, self.backend,
        )

    def clear(self) -> None:
        with self._lock:
            self._reset_backend()
            self.records = []
            for path in (self._index_file, self._vectors_file, self._meta_file):
                path.unlink(missing_ok=True)

    # -- search -------------------------------------------------------------

    def search(self, query_vector: list[float], top_k: int = 6) -> list[SearchHit]:
        if not self.records:
            return []
        k = min(top_k, len(self.records))

        if FAISS_AVAILABLE and self._index is not None:
            scores, indices = self._index.search(
                np.array([query_vector], dtype="float32"), k
            )
            pairs = list(zip(indices[0].tolist(), scores[0].tolist()))
        elif NUMPY_AVAILABLE and self._matrix is not None and len(self._matrix):
            sims = self._matrix @ np.array(query_vector, dtype="float32")
            order = np.argsort(-sims)[:k]
            pairs = [(int(i), float(sims[i])) for i in order]
        else:
            sims = [
                (i, sum(a * b for a, b in zip(row, query_vector)))
                for i, row in enumerate(self._matrix or [])
            ]
            sims.sort(key=lambda p: -p[1])
            pairs = sims[:k]

        hits: list[SearchHit] = []
        for position, score in pairs:
            if position < 0 or position >= len(self.records):
                continue
            record = self.records[position]
            hits.append(
                SearchHit(
                    chunk_id=record.get("chunk_id", ""),
                    score=round(float(score), 4),
                    content=record.get("content", ""),
                    source_label=record.get("source_label", ""),
                    source_kind=record.get("source_kind", "document"),
                    metadata=record.get("metadata") or {},
                )
            )
        return hits

    # -- persistence --------------------------------------------------------

    def _persist(self) -> None:
        settings.faiss_path.mkdir(parents=True, exist_ok=True)
        self._meta_file.write_text(
            json.dumps(
                {
                    "product_id": self.product_id,
                    "dimension": self.dimension,
                    "backend": self.backend,
                    "records": self.records,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if FAISS_AVAILABLE and self._index is not None and self.records:
            faiss.write_index(self._index, str(self._index_file))
        elif NUMPY_AVAILABLE and self._matrix is not None and len(self._matrix):
            np.save(self._vectors_file, self._matrix)

    @classmethod
    def load(cls, product_id: str, dimension: int) -> "ProductVectorIndex | None":
        index = cls(product_id, dimension)
        if not index._meta_file.exists():
            return None
        try:
            meta = json.loads(index._meta_file.read_text(encoding="utf-8"))
            records = meta.get("records") or []
            stored_dim = int(meta.get("dimension") or dimension)
            if stored_dim != dimension:
                log.warning(
                    "Index for %s was built with dim=%d but the embedder is dim=%d — "
                    "it needs a rebuild.",
                    product_id, stored_dim, dimension,
                )
                return None

            if FAISS_AVAILABLE and index._index_file.exists():
                index._index = faiss.read_index(str(index._index_file))
            elif NUMPY_AVAILABLE and index._vectors_file.exists():
                index._matrix = np.load(index._vectors_file)
            elif records:
                return None          # metadata without vectors is unusable

            index.records = records
            return index
        except Exception as exc:  # noqa: BLE001 - a corrupt index must not break startup
            log.warning("Could not load index for %s: %s", product_id, exc)
            return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_indexes: dict[str, ProductVectorIndex] = {}
_registry_lock = threading.Lock()


def get_index(product_id: str, dimension: int) -> ProductVectorIndex:
    with _registry_lock:
        existing = _indexes.get(product_id)
        if existing is not None and existing.dimension == dimension:
            return existing
        index = ProductVectorIndex.load(product_id, dimension) or ProductVectorIndex(
            product_id, dimension
        )
        _indexes[product_id] = index
        return index


def drop_index(product_id: str) -> None:
    with _registry_lock:
        index = _indexes.pop(product_id, None)
    if index:
        index.clear()
    else:
        for suffix in (".faiss", ".npy", ".meta.json"):
            (settings.faiss_path / f"{product_id}{suffix}").unlink(missing_ok=True)


def vector_store_info() -> dict:
    from rag.embeddings.embedder import embedder_info

    return {
        "backend": "faiss" if FAISS_AVAILABLE else ("numpy" if NUMPY_AVAILABLE else "python"),
        "faiss_available": FAISS_AVAILABLE,
        "numpy_available": NUMPY_AVAILABLE,
        "loaded_indexes": len(_indexes),
        "embedder": embedder_info(),
    }
