"""Independent structural and representative numerical checks for B08."""
from __future__ import annotations

from itertools import product
import json
import math
from pathlib import Path

ROOT = Path(__file__).parent
HEADINGS = ("考查目标", "必要概念", "原理与条件", "推导例题", "易错点与反例", "自查", "关联练习", "出处")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    module = load(ROOT / "module.json")
    sources = load(ROOT / "sources.json")
    source_ids = {item["id"] for item in sources}
    assert module["id"] == "B08"
    assert len(module["topic_ids"]) == 9
    assert [len(unit["topic_ids"]) for unit in module["units"]] == [3, 3, 3]

    questions = {}
    type_counts = {"single_choice": 0, "short_answer": 0}
    exercise_paths = sorted((ROOT / "exercises").glob("*.json"))
    assert len(exercise_paths) == 56, "each question must be stored in its own JSON file"
    forbidden = ("与题设定义或计算不符", "写出适用定义、公式或规则", "给出正确推导过程与最终结论")
    for path in exercise_paths:
        question = load(path)
        assert isinstance(question, dict), f"{path.name} must contain one JSON object"
        assert path.stem == question["id"]
        assert not any(phrase in json.dumps(question, ensure_ascii=False) for phrase in forbidden)
        if True:
            assert question["id"] not in questions
            questions[question["id"]] = question
            assert question["version"] == "1.0.0"
            assert question["unit_id"] == question["topic_ids"][0]
            assert set(question["source_ids"]) <= source_ids
            assert set(question["answer_source_ids"]) <= source_ids
            assert question["answer"] and question["explanation"] and question["verification"]
            type_counts[question["type"]] += 1
            if question["type"] == "single_choice":
                assert set(question["options"]) == {"A", "B", "C", "D"}
                assert set(question["option_explanations"]) == {"A", "B", "C", "D"}
                assert question["answer"] in question["options"]
            else:
                assert len(question["rubric"]) >= 2
                assert len({row["id"] for row in question["rubric"]}) == len(question["rubric"])
                assert all(len(row["text"]) >= 14 for row in question["rubric"])

    targets = [8, 8, 8, 6, 4, 6, 5, 5, 6]
    for index, topic_id in enumerate(module["topic_ids"]):
        topic = load(ROOT / "topics" / f"{topic_id}.json")
        body = (ROOT / "topics" / f"{topic_id}.md").read_text(encoding="utf-8-sig")
        assert topic["version"] == "1.0.0"
        assert topic["exercise_target"] == targets[index]
        assert len(topic["question_ids"]) == targets[index]
        assert all(question_id in questions for question_id in topic["question_ids"])
        assert all(f"## {heading}" in body for heading in HEADINGS)

    assert len(questions) == 56
    assert type_counts == {"single_choice": 18, "short_answer": 38}

    # Independent representative calculations; these do not parse answer prose.
    assert math.comb(8, 3) * 3 == 168
    assert math.ceil(math.log2(37)) == 6
    assert sum(1 for bits in product((0, 1), repeat=6)) == 64
    posterior = (0.1 * 0.8) / (0.1 * 0.8 + 0.9 * 0.2)
    assert math.isclose(posterior, 4 / 13)
    values = (1, 3)
    mean = sum(values) / 2
    variance = sum((value - mean) ** 2 for value in values) / 2
    assert variance == 1
    vertices = ((0, 0), (3, 0), (3, 1), (0, 4))
    assert max((2 * x + y, (x, y)) for x, y in vertices) == (7, (3, 1))
    assert 1920 * 1080 * 24 // 8 == 6_220_800
    assert 44_100 * 16 * 2 * 60 // 8 == 10_584_000
    assert 1280 * 720 * 24 * 30 == 663_552_000
    assert 25 * 8 / 10 == 20
    # Legal and English corrections are guarded against regression.
    legal_body = (ROOT / "topics" / "B08-T06.md").read_text(encoding="utf-8-sig")
    english_body = (ROOT / "topics" / "B08-T07.md").read_text(encoding="utf-8-sig")
    assert "第十六条" in legal_body and "必要修改" in legal_body and "不得向第三方提供修改后的软件" in legal_body
    assert "`it` 指前述复用行为，不是 stored response" in english_body
    print("B08 verification passed: 9 topics, 56 questions (18 single-choice, 38 short-answer).")


if __name__ == "__main__":
    main()
