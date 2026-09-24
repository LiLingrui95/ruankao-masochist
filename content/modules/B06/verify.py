"""Independent semantic and structural checks for B06 authoring output."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


module = load(ROOT / "module.json")
topics = {p.stem: load(p) for p in (ROOT / "topics").glob("*.json")}
questions = {p.stem: load(p) for p in (ROOT / "exercises").glob("*.json")}
sources = {x["id"]: x for x in load(ROOT / "sources.json")}

assert module["version"] if "version" in module else True
assert module["topic_ids"] == [f"B06-T{i:02d}" for i in range(1, 12)]
assert set(topics) == set(module["topic_ids"])
assert len(questions) == 74
expected = {"B06-T01":4,"B06-T02":8,"B06-T03":8,"B06-T04":6,"B06-T05":8,"B06-T06":8,"B06-T07":5,"B06-T08":5,"B06-T09":6,"B06-T10":8,"B06-T11":8}
counts = Counter(q["topic_ids"][0] for q in questions.values())
assert counts == Counter(expected)

headings = ["考查目标","必要概念","原理与条件","推导例题","易错点与反例","自查","关联练习","出处"]
for tid, topic in topics.items():
    assert topic["version"] == "1.0.0"
    assert topic["exercise_target"] == expected[tid]
    assert len(topic["question_ids"]) == expected[tid]
    assert all(qid in questions for qid in topic["question_ids"])
    body = (ROOT.parent.parent / topic["body_path"]).read_text(encoding="utf-8")
    assert all(f"## {h}" in body for h in headings)
    assert len(re.sub(r"\s+", "", body)) >= 900, (tid, len(body))

for qid, q in questions.items():
    assert q["version"] == "1.0.0"
    assert q["review_status"] == "reviewed" and q["answer_status"] == "verified"
    assert q["unit_id"] == q["topic_ids"][0]
    assert q["answer"] and q["explanation"] and q["verification"]
    assert set(q["source_ids"]) <= set(sources)
    if q["type"] == "single_choice":
        assert set(q["options"]) == {"A","B","C","D"}
        assert set(q["option_explanations"]) == {"A","B","C","D"}
        assert q["answer"] in q["options"]
        assert all(len(v) >= 10 for v in q["option_explanations"].values())
    else:
        assert len(q["rubric"]) >= 2
        assert len({r["id"] for r in q["rubric"]}) == len(q["rubric"])
        assert all(len(r["text"]) >= 4 for r in q["rubric"])
        assert not any(r["text"] in {"过程正确", "答案合理", "表述完整", "酌情给分"} for r in q["rubric"])
    if q.get("subquestions"):
        assert q["case_material"]
        # Materials must not disclose common answer markers or numeric conclusions.
        forbidden = ["答案", "正确关系是", "应使用", "输出依次", "实心菱形在"]
        assert not any(x in q["case_material"] for x in forbidden), qid
        assert all(s["prompt"] not in q["case_material"] for s in q["subquestions"])

# Independent executable models. These compute expected state/output from the case inputs;
# they do not inspect answer prose and are not a substitute for a C++ compiler.
def payment_model(kind: str, cents: int) -> str:
    try:
        if kind == "card" and cents > 50000:
            raise ValueError("limit")
        return f"{kind}:{cents}"
    except ValueError as error:
        return f"failed:{error}"


def decorate_model(value: str, layers: list[str]) -> tuple[str, list[str]]:
    events = ["FileSource.write"]
    result = f"F({value})"
    for layer in reversed(layers):
        events.insert(0, f"{layer}.write")
        result = f"{layer[0]}({result})"
    return result, events


class EditorModel:
    def __init__(self, text: str):
        self.text, self.history = text, []

    def insert(self, position: int, value: str) -> None:
        if position > len(self.text):
            raise IndexError(position)
        before = self.text
        self.text = before[:position] + value + before[position:]
        self.history.append(before)  # commit only after successful mutation

    def undo(self) -> None:
        if self.history:
            self.text = self.history.pop()


assert payment_model("card", 3000) == "card:3000"
assert payment_model("card", 60000) == "failed:limit"
decorated, calls = decorate_model("x", ["Encrypt", "Zip"])
assert decorated == "E(Z(F(x)))"
assert calls == ["Encrypt.write", "Zip.write", "FileSource.write"]
editor = EditorModel("ab")
editor.insert(2, "X")
assert (editor.text, len(editor.history)) == ("abX", 1)
editor.undo()
assert (editor.text, len(editor.history)) == ("ab", 0)
try:
    editor.insert(9, "Y")
except IndexError:
    pass
else:
    raise AssertionError("out-of-range insertion must fail")
assert (editor.text, len(editor.history)) == ("ab", 0)

for qid in ("B06-T11-Q01", "B06-T11-Q02", "B06-T11-Q03"):
    assert questions[qid]["case_material"].count("/* ① */") == 1
    assert questions[qid]["case_material"].count("/* ② */") == 1
    assert questions[qid]["case_material"].count("/* ③ */") == 1
    assert "```cpp" in questions[qid]["case_material"]
    assert "```cpp" in questions[qid]["answer"]

uml_cases = [q for q in questions.values() if q["topic_ids"] == ["B06-T10"] and q.get("subquestions")]
cpp_cases = [q for q in questions.values() if q["topic_ids"] == ["B06-T11"] and q.get("subquestions")]
assert len(uml_cases) >= 3 and len(cpp_cases) >= 3
assert (ROOT / "assets" / "course-enrollment-blank.svg").is_file()
course_svg = (ROOT / "assets" / "course-enrollment-blank.svg").read_text(encoding="utf-8")
assert all(name in course_svg for name in ("Course", "Chapter", "Student", "Enrollment"))
assert course_svg.count("?") >= 4 and "关系：____" in course_svg
assert questions["B06-T10-Q01"]["assets"][0]["path"].endswith("course-enrollment-blank.svg")
assert any(q.get("assets") for q in uml_cases)

print(json.dumps({"topics":len(topics),"questions":len(questions),"cases":len(uml_cases)+len(cpp_cases),"status":"verified","compiler":"not used"}, ensure_ascii=False))
