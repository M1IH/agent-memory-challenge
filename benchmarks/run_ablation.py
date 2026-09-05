from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


VARIANTS = {
    "hybrid": [],
    "lexical_only": ["--no-embeddings"],
    "dense_only": ["--disable-lexical"],
    "no_expansion": ["--disable-expansion"],
    "no_temporal": ["--disable-temporal"],
    "equal_rrf": ["--lexical-weight", "1.0", "--dense-weight", "1.0"],
}


def run_variant(name: str, flags: list[str], top_k: int, output: Path) -> dict:
    env = os.environ.copy()
    # Every variant uses the real backend unless --no-embeddings is explicit.
    env["AML_EMBED_ENABLED"] = "true"
    subprocess.run(
        [sys.executable, "-m", "benchmarks.run_benchmark", "--suite", "extended",
         "--quiet", "--top-k", str(top_k), "--json-output", str(output), *flags],
        check=True,
        env=env,
        cwd=Path(__file__).resolve().parents[1],
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    result["variant"] = name
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare retrieval components.")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        for name, flags in VARIANTS.items():
            results.append(run_variant(name, flags, 10, temp / f"{name}.json"))
        for top_k in (1, 3, 5):
            results.append(run_variant(f"hybrid_top_{top_k}", [], top_k, temp / f"top-{top_k}.json"))

    baseline = results[0]
    print("variant          top_k  hit@1  hit@3  hit@5   mrr    delta_mrr")
    for result in results:
        print(
            f"{result['variant']:<16} {result['top_k']:>5}  "
            f"{result['hit_at_1']:.3f}  {result['hit_at_3']:.3f}  "
            f"{result['hit_at_5']:.3f}  {result['mrr']:.3f}  "
            f"{result['mrr'] - baseline['mrr']:+.3f}"
        )
    if args.json_output:
        args.json_output.write_text(
            json.dumps({"baseline": "hybrid", "results": results}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
