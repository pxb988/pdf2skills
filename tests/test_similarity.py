"""Tests for text similarity computation."""

import pytest
from src.nlp.similarity import (
    tokenize,
    compute_similarity_matrix,
    find_buckets,
    tag_overlap_ratio,
)


class TestTokenize:
    def test_english(self):
        tokens = tokenize("Hello World, this is a test!")
        assert "hello" in tokens
        assert "world" in tokens

    def test_camel_case_split(self):
        tokens = tokenize("CamelCaseWord")
        assert "camel" in tokens
        assert "case" in tokens

    def test_chinese(self):
        tokens = tokenize("你好世界")
        assert len(tokens) > 0


class TestSimilarityMatrix:
    def test_identity(self):
        texts = ["hello world", "hello world"]
        matrix = compute_similarity_matrix(texts)
        assert abs(matrix[0][1] - 1.0) < 0.01

    def test_different_texts(self):
        texts = ["the cat sat on the mat", "quantum physics equations"]
        matrix = compute_similarity_matrix(texts)
        assert matrix[0][1] < 0.5

    def test_symmetric(self):
        texts = ["apple banana", "banana cherry", "date elderberry"]
        matrix = compute_similarity_matrix(texts)
        for i in range(3):
            for j in range(3):
                assert abs(matrix[i][j] - matrix[j][i]) < 0.001


class TestFindBuckets:
    def test_similar_grouped(self):
        texts = [
            "financial ratio analysis profit margin",
            "financial ratio analysis return on equity",
            "quantum physics particle wave duality",
        ]
        ids = ["a", "b", "c"]
        buckets = find_buckets(texts, ids, threshold=0.3)
        # a and b should be in the same bucket, c separate
        assert len(buckets) >= 1
        # Check that a and b are together
        for bucket in buckets:
            if "a" in bucket:
                assert "b" in bucket

    def test_all_different(self):
        texts = ["aaa bbb ccc", "xxx yyy zzz", "111 222 333"]
        ids = ["1", "2", "3"]
        buckets = find_buckets(texts, ids, threshold=0.9)
        assert len(buckets) == 3

    def test_empty(self):
        assert find_buckets([], [], threshold=0.5) == []

    def test_single(self):
        buckets = find_buckets(["hello"], ["a"], threshold=0.5)
        assert buckets == [["a"]]


class TestTagOverlap:
    def test_identical(self):
        assert tag_overlap_ratio({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint(self):
        assert tag_overlap_ratio({"a"}, {"b"}) == 0.0

    def test_partial(self):
        ratio = tag_overlap_ratio({"a", "b"}, {"b", "c"})
        assert abs(ratio - 1 / 3) < 0.01

    def test_empty(self):
        assert tag_overlap_ratio(set(), set()) == 0.0
