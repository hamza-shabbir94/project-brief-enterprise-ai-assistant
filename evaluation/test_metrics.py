"""
Tests for the scoring functions and the test set itself. No API keys needed:

    python -m pytest evaluation
"""

import json
from pathlib import Path

import pytest

from evaluation import metrics
from ingest import describe_file, find_pdfs
from rag import NOT_FOUND_ANSWER


def test_contains_matches_whole_words_only():
    assert metrics.contains("Respond within 5 working days", "five|5")
    assert metrics.contains("Respond within five working days", "five|5")
    assert not metrics.contains("Respond within 15 working days", "5")
    assert metrics.contains("It costs €649.00", "649")
    assert metrics.contains("Use PEOPLEHUB", "PeopleHub")


def test_keyword_recall():
    assert metrics.keyword_recall("€649.00, 18 units in stock", ["649", "18"]) == 1.0
    assert metrics.keyword_recall("€649.00", ["649", "18"]) == 0.5
    assert metrics.keyword_recall("anything", []) == 1.0


def test_forbidden_found():
    assert metrics.forbidden_found("It was €149.99 in 2021", ["149.99"]) == ["149.99"]
    assert metrics.forbidden_found("Not found", ["149.99"]) == []


@pytest.mark.parametrize("answer", [
    NOT_FOUND_ANSWER,
    "I could not find this in the company documents. Please ask HR.",
    "I couldn’t find any information about that.",
    "The company documents don't mention a parental bonus.",
])
def test_refusals_are_detected(answer):
    assert metrics.is_refusal(answer)


@pytest.mark.parametrize("answer", [
    "Hybrid employees attend the office two days per week [1].",
    # Partly unknown, but it answered from the sources, so it is not a refusal.
    "The lantern is discontinued [1]. I couldn't find a replacement SKU.",
])
def test_answers_are_not_refusals(answer):
    assert not metrics.is_refusal(answer)


def test_retrieval_metrics():
    retrieved = ["Employee Handbook", "Remote Work Policy", "Remote Work Policy"]
    assert metrics.retrieval_hit(retrieved, ["Remote Work Policy"]) == 1
    assert metrics.retrieval_hit(retrieved, ["Sales Playbook"]) == 0
    assert metrics.reciprocal_rank(retrieved, ["Remote Work Policy"]) == 0.5
    assert metrics.reciprocal_rank(retrieved, ["Sales Playbook"]) == 0.0


def test_rouge_l():
    assert metrics.rouge_l("the cat sat on the mat", "the cat sat on the mat") == 1.0
    assert metrics.rouge_l("completely different words", "the cat sat") == 0.0
    assert 0 < metrics.rouge_l("the cat is on the mat", "the cat sat on the mat") < 1
    assert metrics.rouge_l("", "the cat") == 0.0


def test_cosine_similarity():
    assert metrics.cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert metrics.cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)


def test_dataset_is_valid():
    """Every case is well-formed and only expects documents that really exist."""
    cases = json.loads((Path(__file__).parent / "dataset.json").read_text())
    titles = {describe_file(path)["title"] for path in find_pdfs()}

    assert len({case["id"] for case in cases}) == len(cases), "duplicate IDs"
    for case in cases:
        assert case["question"] and case["reference_answer"], case["id"]
        assert set(case.get("expected_sources", [])) <= titles, case["id"]
        if case.get("should_refuse"):
            assert not case.get("expected_sources"), case["id"]
        else:
            assert case.get("expected_sources"), case["id"]
        for turn in case.get("history", []):
            assert turn["role"] in {"user", "assistant"}, case["id"]
