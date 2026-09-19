from __future__ import annotations

from qa.score import extract_final_answer, match_answer, score_answer


def test_extracts_last_final_answer_outside_think_tags() -> None:
    text = (
        '<think>FINAL ANSWER: wrong</think>\n'
        'FINAL ANSWER: C50\nFINAL ANSWER: C60'
    )
    assert extract_final_answer(text) == "C60"


def test_extract_matches_parent_when_final_answer_is_inside_think_tags() -> None:
    assert extract_final_answer("<think>reasoning\nFINAL ANSWER: 否</think>") == "否"
    assert extract_final_answer("FINAL ANSWER: <think>C50</think>") == "C50"
    assert extract_final_answer("<think/>\nFINAL ANSWER: C60") == "C60"


def test_quasi_exact_match_covers_parent_protocol() -> None:
    assert match_answer("3.2;7.5", "3.2, 7.5")
    assert match_answer("pyosis.live.grade.create_highway", "engine.live.grade.create_highway")
    assert match_answer("可变参数（varargs）", "varargs", ["可变参数"])
    assert match_answer("否", "否")
    assert match_answer("no", "否")
    assert not match_answer("否", "no")


def test_score_answer_does_not_return_gold() -> None:
    result = score_answer("reasoning\nFINAL ANSWER: no", "no", ["材料编号"])
    assert result == {"pred": "no", "correct": True}
    assert "gold" not in result
