"""Apply a local paired rubric diagnostic after BEAM answer generation.

This loads author rubrics only after a separate answer report already exists.
The local Qwen judge is an exploratory proxy, not the BEAM author judge or AML.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import urllib.request
from pathlib import Path

from benchmarks.probe_beam_100k import SOURCE_SHA256, load_rows
from benchmarks.run_beam_local_answerer import MODEL, model_digest


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
JUDGE_SYSTEM = (
    "Evaluate an answer against each independent rubric criterion. "
    "Score each criterion 1.0 if fully satisfied, 0.5 if partially satisfied, "
    "or 0.0 if missing or wrong. Accept accurate paraphrases. A response must "
    "address the question; avoid giving credit for unsupported extra details. "
    "Return only a JSON object with a scores array in rubric order."
)


def judge(question: str, rubric: list[str], answer: str) -> list[float]:
    prompt = json.dumps({
        "question": question, "rubric": rubric, "answer": answer,
        "required_output": "JSON object with scores array, one number per rubric item",
    }, ensure_ascii=False)
    payload = json.dumps({
        "model": MODEL,
        "system": JUDGE_SYSTEM,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 0, "num_ctx": 8192, "num_predict": 384},
    }).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        raw = json.load(response)["response"]
    scores = json.loads(raw)["scores"]
    if len(scores) != len(rubric) or any(value not in (0, 0.5, 1) for value in scores):
        raise ValueError(f"invalid judge scores: {scores!r}")
    return [float(value) for value in scores]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("data/beam-100k.parquet"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    answer_bytes = args.answers.read_bytes()
    answer_report = json.loads(answer_bytes)
    if answer_report.get("kind") != "beam_local_answer_diagnostic":
        raise ValueError("unexpected answer report kind")
    if answer_report.get("model_digest") != model_digest():
        raise ValueError("answer and judge model digest differ")
    conversations = {str(row["conversation_id"]): row for row in load_rows(args.source)}
    scores = []
    for item in answer_report["rows"]:
        conversation = conversations[item["conversation_id"]]
        probes = ast.literal_eval(conversation["probing_questions"])
        source_item = probes[item["category"]][item["question_index"]]
        if source_item["question"] != item["question"]:
            raise ValueError("question mismatch between answer report and source")
        rubric = source_item["rubric"]
        methods = {}
        for method in ("baseline", "candidate"):
            values = judge(item["question"], rubric, item[method]["answer"])
            methods[method] = {
                "scores": values,
                "mean": round(sum(values) / len(values), 4),
            }
        scores.append({
            "conversation_id": item["conversation_id"],
            "category": item["category"],
            "question_index": item["question_index"],
            **methods,
        })
    output = {
        "kind": "beam_local_rubric_diagnostic",
        "source_sha256": SOURCE_SHA256,
        "answers_sha256": hashlib.sha256(answer_bytes).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "judge_system_sha256": hashlib.sha256(JUDGE_SYSTEM.encode()).hexdigest(),
        "judge_model": MODEL,
        "judge_model_digest": model_digest(),
        "rows": scores,
        "baseline_mean": round(sum(row["baseline"]["mean"] for row in scores) / len(scores), 4),
        "candidate_mean": round(sum(row["candidate"]["mean"] for row in scores) / len(scores), 4),
        "note": "Local same-model paired rubric proxy; not author BEAM or AML score.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "cases": len(scores), "baseline_mean": output["baseline_mean"],
        "candidate_mean": output["candidate_mean"],
    }))


if __name__ == "__main__":
    main()
