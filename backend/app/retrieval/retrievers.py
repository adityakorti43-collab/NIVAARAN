"""Keyword baseline (Okapi BM25), semantic retrieval, hybrid fusion, and optional cross-encoder reranking.

Scores are *retrieval relevance* only. They are never interpreted as a probability of coverage; evidence
verification (app.verification) decides what a clause actually establishes.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np

from app.config import EMBEDDING_BACKEND, EMBEDDING_MODEL, RERANKER_ENABLED, RERANKER_MODEL, log
from app.models import Clause
from app.retrieval.text import tokens


def clause_text(c: Clause) -> str:
    return f"{c.heading}. {c.text}"


@dataclass
class Hit:
    clause_id: str
    score: float
    rank: int


class BM25:
    """Okapi BM25 (k1=1.5, b=0.75) implemented directly so the baseline is transparent."""

    name = "bm25"

    def __init__(self, clauses: list[Clause], k1: float = 1.5, b: float = 0.75):
        self.ids = [c.clause_id for c in clauses]
        self.docs = [tokens(clause_text(c)) for c in clauses]
        self.k1, self.b = k1, b
        self.avgdl = (sum(len(d) for d in self.docs) / len(self.docs)) if self.docs else 0.0
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def search(self, query: str, k: int = 10) -> list[Hit]:
        q = tokens(query)
        scores = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
            scores.append(s)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [Hit(self.ids[i], round(scores[i], 4), r + 1) for r, i in enumerate(order[:k]) if scores[i] > 0]


def _load(cls, name: str):
    """Prefer the local model cache (no network); download only if the model is not cached yet."""
    try:
        return cls(name, local_files_only=True)
    except Exception:
        return cls(name)


@lru_cache(maxsize=1)
def _st_model():
    from sentence_transformers import SentenceTransformer
    return _load(SentenceTransformer, EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def _cross_encoder():
    from sentence_transformers import CrossEncoder
    return _load(CrossEncoder, RERANKER_MODEL)


def embedding_backend() -> str:
    if EMBEDDING_BACKEND == "lsa":
        return "lsa"
    try:
        import sentence_transformers  # noqa: F401
        return "sentence-transformers"
    except ImportError:
        if EMBEDDING_BACKEND == "sentence-transformers":
            raise
        return "lsa"


class Semantic:
    """Dense retrieval with a sentence-embedding model (cosine similarity, exact search).

    Exact numpy search is used deliberately: policy corpora are a few hundred clauses, where an
    approximate index such as FAISS adds infrastructure without measurable benefit.
    Fallback (no sentence-transformers): TF-IDF + truncated SVD (LSA). This is labelled as such
    everywhere and is NOT a neural embedding model.
    """

    name = "semantic"

    def __init__(self, clauses: list[Clause]):
        self.ids = [c.clause_id for c in clauses]
        texts = [clause_text(c) for c in clauses]
        self.backend = embedding_backend()
        if self.backend == "sentence-transformers":
            self.model_name = EMBEDDING_MODEL
            self.matrix = self._encode(texts)
        else:
            from sklearn.decomposition import TruncatedSVD
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.model_name = "lsa-tfidf-svd (fallback, not neural)"
            self.vec = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), min_df=1)
            x = self.vec.fit_transform(texts)
            n_comp = max(2, min(64, x.shape[0] - 1, x.shape[1] - 1))
            self.svd = TruncatedSVD(n_components=n_comp, random_state=42)
            m = self.svd.fit_transform(x)
            self.matrix = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-12)

    def _encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(_st_model().encode(texts, normalize_embeddings=True, show_progress_bar=False))

    def embed_query(self, query: str) -> np.ndarray:
        if self.backend == "sentence-transformers":
            return self._encode([query])[0]
        v = self.svd.transform(self.vec.transform([query]))[0]
        return v / (np.linalg.norm(v) + 1e-12)

    def search(self, query: str, k: int = 10) -> list[Hit]:
        if not self.ids:
            return []
        sims = self.matrix @ self.embed_query(query)
        order = np.argsort(-sims, kind="stable")[:k]
        return [Hit(self.ids[i], round(float(sims[i]), 4), r + 1) for r, i in enumerate(order)]


def rrf(runs: list[list[Hit]], k: int = 10, c: int = 60) -> list[Hit]:
    """Reciprocal rank fusion of several ranked lists."""
    scores: dict[str, float] = {}
    for run in runs:
        for h in run:
            scores[h.clause_id] = scores.get(h.clause_id, 0.0) + 1.0 / (c + h.rank)
    order = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    return [Hit(cid, round(s, 5), r + 1) for r, (cid, s) in enumerate(order)]


def reranker_available() -> bool:
    if RERANKER_ENABLED == "off":
        return False
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def warm_up() -> None:
    """Load the embedding model and reranker ahead of the first request (they take several seconds to load)."""
    if embedding_backend() == "sentence-transformers":
        _st_model()
    if reranker_available():
        _cross_encoder()


class Retriever:
    """Holds all retrievers over one clause set (e.g. the clauses active in one policy version)."""

    def __init__(self, clauses: list[Clause]):
        self.clauses = {c.clause_id: c for c in clauses}
        self.bm25 = BM25(clauses)
        self.semantic = Semantic(clauses)

    def search(self, query: str, method: str = "hybrid", k: int = 8, pool: int = 15) -> list[Hit]:
        if method == "bm25":
            return self.bm25.search(query, k)
        if method == "semantic":
            return self.semantic.search(query, k)
        fused = rrf([self.bm25.search(query, pool), self.semantic.search(query, pool)], k=pool)
        if method == "hybrid":
            return fused[:k]
        if method == "hybrid_rerank":
            return self.rerank(query, fused)[:k]
        raise ValueError(f"Unknown retrieval method {method}")

    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        if not hits or not reranker_available():
            return hits
        pairs = [(query, clause_text(self.clauses[h.clause_id])) for h in hits]
        try:
            scores = _cross_encoder().predict(pairs, show_progress_bar=False)
        except Exception as exc:  # model unavailable offline etc.
            log.warning("Reranker unavailable (%s); returning fused order", type(exc).__name__)
            return hits
        order = sorted(range(len(hits)), key=lambda i: (-float(scores[i]), i))
        return [Hit(hits[i].clause_id, round(float(scores[i]), 4), r + 1) for r, i in enumerate(order)]

    def all_scores(self, query: str, pool: int = 15) -> dict[str, dict[str, Optional[float]]]:
        """Per-clause relevance scores from each method, for display in the Evidence Explorer."""
        out: dict[str, dict[str, Optional[float]]] = {}
        for name, run in (("bm25", self.bm25.search(query, pool)), ("semantic", self.semantic.search(query, pool))):
            for h in run:
                out.setdefault(h.clause_id, {})[name] = h.score
        return out

    def config(self) -> dict:
        return {"keyword": "Okapi BM25 (k1=1.5, b=0.75)", "semantic_backend": self.semantic.backend,
                "semantic_model": self.semantic.model_name, "fusion": "reciprocal rank fusion (c=60)",
                "reranker": RERANKER_MODEL if reranker_available() else "not available"}
