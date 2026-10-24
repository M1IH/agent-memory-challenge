from benchmarks.run_beam_local_answerer import render_evidence


def test_evidence_rendering_enforces_shared_context_budget():
    results = [
        {"source_id": 11, "content": "A" * 4000},
        {"source_id": 12, "content": "B" * 4000},
        {"source_id": 13, "content": "C" * 4000},
    ]
    evidence, sources = render_evidence(
        results, char_budget=1200, per_result_chars=600,
    )
    assert len(evidence) <= 1200
    assert sources == [11, 12]
    assert "[...]" in evidence
