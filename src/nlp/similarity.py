"""Text similarity computation for knowledge fusion.

Provides TF-IDF based cosine similarity to group related SKUs
without requiring external embedding APIs.
"""

from __future__ import annotations

import re
from collections import Counter
from math import sqrt
from typing import Sequence


def tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for both Chinese and English."""
    # Split CamelCase
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    # Remove punctuation, keep alphanumeric and CJK
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    return tokens


def _build_idf(docs: Sequence[list[str]]) -> dict[str, float]:
    """Compute inverse document frequency."""
    from math import log

    n = len(docs)
    df: dict[str, int] = Counter()
    for doc in docs:
        for token in set(doc):
            df[token] += 1
    return {term: log((n + 1) / (freq + 1)) + 1 for term, freq in df.items()}


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Compute TF-IDF vector for a document."""
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {term: (count / total) * idf.get(term, 1.0) for term, count in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    norm_a = sqrt(sum(v * v for v in a.values()))
    norm_b = sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_similarity_matrix(texts: list[str]) -> list[list[float]]:
    """Compute pairwise TF-IDF cosine similarity matrix.

    Args:
        texts: list of text documents

    Returns:
        NxN similarity matrix (list of lists)
    """
    tokenized = [tokenize(t) for t in texts]
    idf = _build_idf(tokenized)
    vectors = [_tfidf_vector(doc, idf) for doc in tokenized]

    n = len(vectors)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            sim = _cosine(vectors[i], vectors[j])
            matrix[i][j] = sim
            matrix[j][i] = sim
    return matrix


def find_buckets(texts: list[str], ids: list[str],
                 threshold: float = 0.5) -> list[list[str]]:
    """Group texts into buckets by similarity.

    Uses single-linkage clustering: if any member of a bucket has
    similarity >= threshold with a new text, add it to that bucket.

    Args:
        texts: list of text documents (e.g. SKU summaries)
        ids: corresponding identifiers
        threshold: minimum similarity to join a bucket

    Returns:
        list of id groups (buckets)
    """
    if not texts:
        return []

    matrix = compute_similarity_matrix(texts)
    n = len(texts)
    assigned = [False] * n
    buckets: list[list[str]] = []

    for i in range(n):
        if assigned[i]:
            continue
        bucket = [i]
        assigned[i] = True
        for j in range(i + 1, n):
            if assigned[j]:
                continue
            if any(matrix[j][k] >= threshold for k in bucket):
                bucket.append(j)
                assigned[j] = True
        buckets.append([ids[idx] for idx in bucket])

    return buckets


def tag_overlap_ratio(tags_a: set[str], tags_b: set[str]) -> float:
    """Compute Jaccard-like overlap ratio between two tag sets."""
    if not tags_a and not tags_b:
        return 0.0
    intersection = tags_a & tags_b
    union = tags_a | tags_b
    return len(intersection) / len(union) if union else 0.0
