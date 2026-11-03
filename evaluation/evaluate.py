"""
Evaluate the assistant on a fixed set of test questions.

    python -m evaluation.evaluate                     # everything (about $0.05, 1-2 minutes)
    python -m evaluation.evaluate --no-judge          # skip the LLM judge (cheaper, faster)
    python -m evaluation.evaluate --category product  # only one category
    python -m evaluation.evaluate --ids fin-mileage,oos-capital

Each question in dataset.json goes through the real pipeline (rag.ask) and is scored on:

    Retrieval     hit rate, MRR            did the right document come back?
    Rules         keyword recall,          are the key facts (numbers, names) in the answer?
                  refusal, citations       does it say "I couldn't find it" only when it should?
    Reference     ROUGE-L, semantic sim.   how close is it to the expected answer?
    LLM judge     correctness 1-5,         graded by a stronger model (judge.py)
                  grounded yes/no

Results are saved to evaluation/results/ (JSON with every answer + a Markdown
report) and compared with the previous run, so you can see whether a change
to the prompt, chunking or config actually helped.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from statistics import mean

sys.path.append(str(Path(__file__).resolve().parent.parent))  # make rag.py importable

import config  # noqa: E402
from evaluation import judge, metrics  # noqa: E402
from rag import ask, format_sources, retrieve  # noqa: E402
from vector_store import get_embeddings  # noqa: E402

EVAL_DIR = Path(__file__).parent
DATASET = EVAL_DIR / "dataset.json"
RESULTS_DIR = EVAL_DIR / "results"

# Shown in the summary, in this order. Higher is better for all of them.
SUMMARY_METRICS = [
    ("pass_rate", "Pass rate"),
    ("retrieval_hit", "Retrieval hit rate"),
    ("mrr", "Retrieval MRR"),
    ("keyword_recall", "Keyword recall"),
    ("refusal_accuracy", "Refusal accuracy"),
    ("citation_rate", "Citation rate"),
    ("rouge_l", "ROUGE-L"),
    ("semantic_similarity", "Semantic similarity"),
    ("correctness", "Judge correctness (1-5)"),
    ("grounded", "Judge grounded"),
]


def evaluate_case(case, use_judge):
    """Run one test question through the assistant and score the answer."""
    expected = case.get("expected_sources", [])
    should_refuse = case.get("should_refuse", False)

    started = time.perf_counter()
    result = ask(case["question"], case.get("history"))
    latency = time.perf_counter() - started

    answer, docs = result["answer"], result["sources"]
    titles = [doc.metadata["title"] for doc in docs]

    # The best match before the MIN_RELEVANCE cut-off, to help tune that setting.
    best = retrieve(result["search_query"], min_relevance=0)
    top_score = best[0].metadata["score"] if best else 0.0

    refused = metrics.is_refusal(answer)
    forbidden = metrics.forbidden_found(answer, case.get("must_not_include"))
    keyword_recall = metrics.keyword_recall(answer, case.get("must_include"))
    answer_vector, reference_vector = get_embeddings().embed_documents([answer, case["reference_answer"]])

    row = {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "search_query": result["search_query"],
        "answer": answer,
        "retrieved": [
            {"title": d.metadata["title"], "page": d.metadata["page"], "score": d.metadata["score"]} for d in docs
        ],
        "top_score": top_score,
        "latency_s": round(latency, 2),
        "should_refuse": should_refuse,
        "refused": refused,
        "refusal_ok": refused == should_refuse,
        "forbidden_found": forbidden,
        # Retrieval and citations only make sense when there is something to find.
        "retrieval_hit": metrics.retrieval_hit(titles, expected) if expected else None,
        "mrr": metrics.reciprocal_rank(titles, expected) if expected else None,
        "cited": metrics.has_citation(answer) if not should_refuse else None,
        "keyword_recall": keyword_recall,
        "rouge_l": round(metrics.rouge_l(answer, case["reference_answer"]), 3),
        "semantic_similarity": round(metrics.cosine_similarity(answer_vector, reference_vector), 3),
    }

    rules_ok = row["refusal_ok"] and not forbidden and keyword_recall == 1.0
    row["passed"] = rules_ok

    if use_judge:
        grade = judge.grade(case["question"], case["reference_answer"], format_sources(docs), answer)
        row.update(correctness=grade.correctness, grounded=grade.grounded, judge_reasoning=grade.reasoning)
        row["passed"] = rules_ok and grade.correctness >= 4 and grade.grounded
    return row


def safe_evaluate(case, use_judge):
    try:
        return evaluate_case(case, use_judge)
    except Exception as error:  # one broken case shouldn't stop the whole run
        return {"id": case["id"], "category": case["category"], "question": case["question"],
                "error": repr(error), "passed": False}


def average(rows, key):
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return round(mean(values), 3) if values else None


def summarize(rows):
    ok = [row for row in rows if "error" not in row]
    summary = {
        "cases": len(rows),
        "errors": len(rows) - len(ok),
        "pass_rate": average(rows, "passed"),
        "retrieval_hit": average(ok, "retrieval_hit"),
        "mrr": average(ok, "mrr"),
        "keyword_recall": average(ok, "keyword_recall"),
        "refusal_accuracy": average(ok, "refusal_ok"),
        "citation_rate": average(ok, "cited"),
        "rouge_l": average(ok, "rouge_l"),
        "semantic_similarity": average(ok, "semantic_similarity"),
        "correctness": average(ok, "correctness"),
        "grounded": average(ok, "grounded"),
        "avg_latency_s": average(ok, "latency_s"),
        "by_category": {},
    }
    for category in sorted({row["category"] for row in rows}):
        in_category = [row for row in rows if row["category"] == category]
        summary["by_category"][category] = {
            "cases": len(in_category),
            "passed": sum(row["passed"] for row in in_category),
        }

    # Helps tune MIN_RELEVANCE: answerable questions should score above it,
    # questions the documents can't answer below it.
    answerable = [row["top_score"] for row in ok if not row["should_refuse"]]
    unanswerable = [row["top_score"] for row in ok if row["should_refuse"]]
    summary["lowest_top_score_answerable"] = min(answerable) if answerable else None
    summary["highest_top_score_unanswerable"] = max(unanswerable) if unanswerable else None
    return summary


def previous_run(filters, use_judge):
    """The latest earlier run on the same questions, to compare against."""
    for path in sorted(RESULTS_DIR.glob("run-*.json"), reverse=True):
        run = json.loads(path.read_text())
        if run["filters"] == filters and run["judge"] == use_judge:
            return run
    return None


def format_value(value):
    return "–" if value is None else f"{value:.2f}"


def summary_lines(summary, previous=None):
    lines = ["| Metric | Score | vs previous run |", "|---|---:|---:|"]
    for key, label in SUMMARY_METRICS:
        value = summary[key]
        before = previous["summary"].get(key) if previous else None
        delta = "" if value is None or before is None else f"{value - before:+.2f}"
        lines.append(f"| {label} | {format_value(value)} | {delta} |")
    lines.append(f"| Avg. latency (s) | {format_value(summary['avg_latency_s'])} | |")
    return lines


def write_report(path, run, previous):
    summary, rows = run["summary"], run["results"]
    lines = [
        f"# Evaluation run {run['timestamp']}",
        "",
        f"{summary['cases']} cases · {summary['errors']} errors · judge: "
        f"{run['config']['JUDGE_MODEL'] if run['judge'] else 'off'}",
        "",
        "## Summary",
        "",
        *summary_lines(summary, previous),
        "",
        "## By category",
        "",
        "| Category | Passed |",
        "|---|---:|",
        *[f"| {name} | {c['passed']}/{c['cases']} |" for name, c in summary["by_category"].items()],
        "",
        "## Relevance threshold",
        "",
        f"`MIN_RELEVANCE` = {config.MIN_RELEVANCE}. Lowest best-match score for an answerable question: "
        f"{format_value(summary['lowest_top_score_answerable'])}; highest for an unanswerable one: "
        f"{format_value(summary['highest_top_score_unanswerable'])}.",
        "",
        "## All cases",
        "",
        "| | ID | Category | Keywords | Refusal OK | Correctness | Grounded | Top score |",
        "|---|---|---|---:|---|---:|---|---:|",
    ]
    for row in rows:
        if "error" in row:
            lines.append(f"| ❌ | {row['id']} | {row['category']} | error: {row['error'][:80]} | | | | |")
            continue
        lines.append(
            f"| {'✅' if row['passed'] else '❌'} | {row['id']} | {row['category']} | "
            f"{row['keyword_recall']:.2f} | {'yes' if row['refusal_ok'] else 'no'} | "
            f"{row.get('correctness', '–')} | {row.get('grounded', '–')} | {row['top_score']:.2f} |"
        )

    failed = [row for row in rows if not row["passed"]]
    if failed:
        lines += ["", "## Failed cases", ""]
        for row in failed:
            lines += [f"### {row['id']}", "", f"**Question:** {row['question']}", ""]
            if "error" in row:
                lines += [f"**Error:** `{row['error']}`", ""]
                continue
            if row["search_query"] != row["question"]:
                lines += [f"**Searched for:** {row['search_query']}", ""]
            lines += ["**Answer:**", "", "> " + row["answer"].replace("\n", "\n> "), ""]
            if row.get("judge_reasoning"):
                lines += [f"**Judge:** {row['judge_reasoning']}", ""]
            if row["forbidden_found"]:
                lines += [f"**Must not mention:** {', '.join(row['forbidden_found'])}", ""]
    path.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Evaluate the IronStore assistant.")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM-as-a-judge grading")
    parser.add_argument("--category", help="only run one category, e.g. policy or follow_up")
    parser.add_argument("--ids", help="comma-separated case IDs to run")
    parser.add_argument("--workers", type=int, default=4, help="questions answered in parallel")
    parser.add_argument("--fail-under", type=float, help="exit with an error if the pass rate is lower (for CI)")
    args = parser.parse_args()

    cases = json.loads(DATASET.read_text())
    if args.category:
        cases = [case for case in cases if case["category"] == args.category]
    if args.ids:
        wanted = set(args.ids.split(","))
        cases = [case for case in cases if case["id"] in wanted]
    if not cases:
        sys.exit("No test cases match these filters.")

    use_judge = not args.no_judge
    print(f"Evaluating {len(cases)} questions ({'with' if use_judge else 'without'} LLM judge)...\n")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda case: safe_evaluate(case, use_judge), cases))

    for row in rows:
        mark = "PASS" if row["passed"] else "FAIL"
        detail = row.get("error") or row.get("judge_reasoning") or ""
        print(f"  {mark}  {row['id']:<32} {detail[:90]}")

    filters = {"category": args.category, "ids": args.ids}
    previous = previous_run(filters, use_judge)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run = {
        "timestamp": timestamp,
        "judge": use_judge,
        "filters": filters,
        "config": {
            key: getattr(config, key)
            for key in ["VECTOR_STORE", "CHAT_MODEL", "EMBEDDING_MODEL", "JUDGE_MODEL", "TOP_K",
                        "MIN_RELEVANCE", "CHUNK_SIZE", "CHUNK_OVERLAP", "HISTORY_MESSAGES"]
        },
        "summary": summarize(rows),
        "results": rows,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    json_path = RESULTS_DIR / f"run-{timestamp}.json"
    report_path = RESULTS_DIR / f"run-{timestamp}.md"
    json_path.write_text(json.dumps(run, indent=2, ensure_ascii=False))
    write_report(report_path, run, previous)

    print()
    print("\n".join(summary_lines(run["summary"], previous)))
    print(f"\nSaved {json_path.relative_to(config.PROJECT_DIR)} and {report_path.name}")

    if args.fail_under is not None and run["summary"]["pass_rate"] < args.fail_under:
        sys.exit(f"Pass rate {run['summary']['pass_rate']:.2f} is below {args.fail_under}")


if __name__ == "__main__":
    main()
