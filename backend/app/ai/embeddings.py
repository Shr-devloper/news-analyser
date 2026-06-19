"""Embedding provider with graceful degradation.

Primary: SentenceTransformers (``EMBEDDING_MODEL``).
Fallback: a deterministic hashing embedding so the pipeline (and tests) run
without downloading model weights or hitting the network.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_FALLBACK_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer

        log.info("loading_embedding_model", model=settings.EMBEDDING_MODEL)
        return SentenceTransformer(settings.EMBEDDING_MODEL)
    except Exception as exc:  # noqa: BLE001
        log.warning("embedding_model_unavailable_using_fallback", error=str(exc))
        return None


def _hashing_embedding(text: str) -> list[float]:
    """Cheap bag-of-words hashing vector, L2-normalized."""
    vec = np.zeros(_FALLBACK_DIM, dtype=np.float32)
    for token in _TOKEN_RE.findall(text.lower()):
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[h % _FALLBACK_DIM] += 1.0
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _load_model()
    if model is None:
        return [_hashing_embedding(t) for t in texts]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
