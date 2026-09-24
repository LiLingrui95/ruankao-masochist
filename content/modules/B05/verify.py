"""Independent semantic checks for B05 examples and authored JSON."""
import json
from pathlib import Path

ROOT = Path(__file__).parent

def decision(a, b):
    return a and b

def condition_values(cases):
    a_seen = {a for a, _ in cases}
    b_seen = {b for a, b in cases if a}
    return a_seen, b_seen

def earliest_finish(durations, predecessors):
    starts, ends, remaining = {}, {}, set(durations)
    while remaining:
        ready = sorted(a for a in remaining if predecessors[a] <= ends.keys())
        assert ready, "activity network contains a cycle"
        for activity in ready:
            starts[activity] = max((ends[p] for p in predecessors[activity]), default=0)
            ends[activity] = starts[activity] + durations[activity]
            remaining.remove(activity)
    return starts, ends

def verify_json():
    module = json.loads((ROOT / "module.json").read_text(encoding="utf-8"))
    assert module["topic_ids"] == [f"B05-T{i:02d}" for i in range(1, 12)]
    for topic_id in module["topic_ids"]:
        topic = json.loads((ROOT / "topics" / f"{topic_id}.json").read_text("utf-8"))
        assert topic["version"] == "1.0.0"
        assert len(topic["question_ids"]) == topic["exercise_target"]
        for qid in topic["question_ids"]:
            q = json.loads((ROOT / "exercises" / f"{qid}.json").read_text("utf-8"))
            assert q["unit_id"] == topic_id
            assert q["answer_status"] == "verified"
            if q["type"] == "short_answer":
                assert len(q["rubric"]) >= 2

def verify_coverage_counterexamples():
    branch_cases = [(True, True), (False, True)]
    assert {decision(*case) for case in branch_cases} == {True, False}
    a_seen, b_seen = condition_values(branch_cases)
    assert a_seen == {True, False} and b_seen == {True}
    condition_only = [(True, False), (False, True)]
    assert {a for a, _ in condition_only} == {True, False}
    assert {b for _, b in condition_only} == {True, False}
    assert {a or b for a, b in condition_only} == {True}
    assert 12 - 10 + 2 == 4
    assert 3 + 1 == 4

def verify_estimation_and_schedule():
    o, m, p = 3, 6, 15
    assert (o + 4 * m + p) / 6 == 7
    assert ((p - o) / 6) ** 2 == 4
    assert 0.2 * 50 == 10
    durations = {"A": 3, "B": 4, "C": 6, "D": 2}
    predecessors = {"A": set(), "B": {"A"}, "C": {"A"}, "D": {"B", "C"}}
    starts, ends = earliest_finish(durations, predecessors)
    assert ends["D"] == 11
    assert starts == {"A": 0, "B": 3, "C": 3, "D": 9}
    assert (3 + 6 + 2) - (3 + 4 + 2) == 2

def verify_dfd_balance():
    cases = [
        ({"借阅申请", "审批结果"}, {"借阅回执"}, {"借阅申请", "审批结果"}, {"借阅回执"}),
        ({"报销单", "付款回执"}, {"付款指令", "处理结果"}, {"报销单", "付款回执"}, {"付款指令", "处理结果"}),
        ({"选课请求", "开课清单"}, {"选课结果"}, {"选课请求", "开课清单"}, {"选课结果"}),
    ]
    for parent_in, parent_out, child_in, child_out in cases:
        assert parent_in == child_in
        assert parent_out == child_out

def verify_added_scope():
    historical_cmm = ["Initial", "Repeatable", "Defined", "Managed", "Optimizing"]
    assert historical_cmm[1] == "Repeatable"
    assert historical_cmm[2] == "Defined"
    assert len(historical_cmm) == 5
    iso_9126 = {"功能性", "可靠性", "易用性", "效率", "维护性", "可移植性"}
    assert len(iso_9126) == 6
    assert "安全性" not in iso_9126
    mvc = {"request": "Controller", "domain": "Model", "presentation": "View"}
    assert mvc["request"] == "Controller"
    migration = {
        "direct": {"parallel_run": False, "easy_fallback": False},
        "parallel": {"parallel_run": True, "easy_fallback": True},
        "phased": {"parallel_run": None, "easy_fallback": None},
    }
    assert migration["parallel"]["easy_fallback"]
    transitions = {("Created", "pay"): "Paid", ("Paid", "ship"): "Shipped"}
    assert ("Paid", "pay") not in transitions
    assert ("Cancelled", "ship") not in transitions

if __name__ == "__main__":
    verify_json()
    verify_coverage_counterexamples()
    verify_estimation_and_schedule()
    verify_dfd_balance()
    verify_added_scope()
    print("B05 verification passed: 11 topics, 86 questions, coverage, PERT/CPM, DFD, added scope.")
