"""
Scoring functions for the evaluation. No API calls here, so they are fast,
free and covered by tests (evaluation/test_metrics.py).

Three kinds of metrics, from cheapest to most expensive:

    Retrieval        did the right document come back?          hit rate, MRR
    Rule-based       does the answer contain the key facts?     keyword recall, refusal, citations
    Reference-based  how close is it to the expected answer?    ROUGE-L, embedding similarity

The LLM-as-a-judge grading lives in judge.py.
"""

import math
import re

# Phrases the assistant uses when it can't answer (see the system prompt and
# NOT_FOUND_ANSWER in rag.py). ['’] matches both straight and curly apostrophes.
REFUSAL_PATTERN = re.compile(
    r"(could ?n[o'’]t|can ?n[o'’]t|can[’']t|unable to|was ?n[o'’]t able to|did ?n[o'’]t) (find|locate)"
    r"|no (relevant )?(information|details|mention)"
    r"|(is|are) not (mentioned|included|specified|available) in the (company |provided )?(documents|sources)"
    r"|(documents|sources) do ?n[o'’]t (contain|include|mention|specify|provide)",
    re.IGNORECASE,
)


# --- Retrieval -----------------------------------------------------------

def retrieval_hit(retrieved_titles, expected_titles):
    """1 if any expected document is among the retrieved chunks, else 0."""
    return int(any(title in expected_titles for title in retrieved_titles))


def reciprocal_rank(retrieved_titles, expected_titles):
    """1 / position of the first chunk from an expected document (0 if none).

    1.0 = the best chunk was from the right document, 0.5 = the second one, ...
    """
    for position, title in enumerate(retrieved_titles, start=1):
        if title in expected_titles:
            return 1 / position
    return 0.0


# --- Rule-based checks ---------------------------------------------------

def contains(text, alternatives):
    """True if text contains one of the "|"-separated alternatives as a whole word.

    contains("Within 5 working days", "five|5") -> True
    contains("Within 15 days", "5")             -> False ("5" is part of "15")
    """
    for alternative in alternatives.split("|"):
        pattern = r"(?<!\w)" + re.escape(alternative.strip()) + r"(?!\w)"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def keyword_recall(answer, must_include):
    """Share of the required facts that appear in the answer (1.0 if none required)."""
    if not must_include:
        return 1.0
    return sum(contains(answer, keyword) for keyword in must_include) / len(must_include)


def forbidden_found(answer, must_not_include):
    """Facts that must NOT appear, e.g. a price from the outdated 2021 catalog."""
    return [keyword for keyword in must_not_include or [] if contains(answer, keyword)]


def is_refusal(answer):
    """True if the answer says it couldn't find the information.

    An answer with citations is not a refusal, even if it says e.g. "I couldn't
    find a replacement SKU": it still answered the question from the sources.
    """
    return bool(REFUSAL_PATTERN.search(answer)) and not has_citation(answer)


def has_citation(answer):
    return bool(re.search(r"\[\d+\]", answer))


# --- Reference-based -----------------------------------------------------

def tokens(text):
    return re.findall(r"\w+", text.lower())


def rouge_l(prediction, reference):
    """ROUGE-L F1: overlap of the longest common subsequence of words (0-1).

    Rewards answers that use the same words in the same order as the reference.
    Good wording that differs from the reference scores low, so read it together
    with the semantic similarity and the judge's grade.
    """
    pred, ref = tokens(prediction), tokens(reference)
    if not pred or not ref:
        return 0.0
    # Classic dynamic programming table for the longest common subsequence.
    previous = [0] * (len(ref) + 1)
    for p in pred:
        current = [0]
        for j, r in enumerate(ref, start=1):
            current.append(previous[j - 1] + 1 if p == r else max(previous[j], current[j - 1]))
        previous = current
    lcs = previous[-1]
    if lcs == 0:
        return 0.0
    precision, recall = lcs / len(pred), lcs / len(ref)
    return 2 * precision * recall / (precision + recall)


def cosine_similarity(a, b):
    """Similarity of two embedding vectors: 1 = same meaning, ~0 = unrelated."""
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
