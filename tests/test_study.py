import contextlib
import copy
import io
import json
import re
import uuid

import pytest
from fastapi.testclient import TestClient

import app as study


@pytest.fixture
def client(tmp_path):
    with TestClient(study.create_app(tmp_path / "study.sqlite3")) as instance:
        yield instance


def submit(client, qid="SE-01-Q01", answer=None, key=None):
    return client.post("/api/submit", json={"question_id": qid, "answer": answer or {"option": "A"},
                                           "uncertain": False, "submission_key": key or str(uuid.uuid4())})


def test_content_integrity_and_code_results():
    assert len(study.BASE_PACK['units']) == 3 and len(study.BASE_PACK['questions']) == 24
    assert len(study.ARCHIVE["questions"]) == 18
    sources = {s["id"] for s in study.PACK["sources"] + study.ARCHIVE["sources"]}
    legacy_units = {u['id']: u for u in study.BASE_PACK['units'] + study.ARCHIVE['units']}
    for uid, unit in legacy_units.items():
        assert len(study.SECTIONS[uid]) == (4 if uid.startswith('SE-') else 3)
        assert set(unit["prerequisite_ids"]) <= set(study.UNITS)
        assert set(unit["checkpoint_question_ids"]) <= set(study.QUESTIONS)
        questions = [q for q in study.QUESTIONS.values() if q["unit_id"] == uid]
        assert len(questions) == (8 if uid.startswith('SE-') else 6)
        assert all(0 <= q.get("section_index", 0) < len(study.SECTIONS[uid]) for q in questions)
    for q in study.BASE_PACK['questions'] + study.ARCHIVE['questions']:
        assert q["review_status"] == "reviewed" and q["origin_kind"] == "original"
        assert set(q["source_ids"]) <= sources and q["explanation"]
        if q["type"] == "single_choice":
            assert q["answer"] in q["options"] and len(q["options"]) == 4
            assert set(q["option_explanations"]) == set(q["options"])
        else:
            assert len({r["id"] for r in q["rubric"]}) == 3
        if "test_output" in q:
            code = q["code"].replace("____", q.get("reference_fill", ""))
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                exec(compile(code, q["id"], "exec"), {"__builtins__": {"print": print, "range": range, "len": len}})
            assert stream.getvalue() == q["test_output"], q["id"]


def test_lesson_python_examples():
    expected = {"CSF-01": ["36\n", ""], "CSF-02": ["36\n", "pass\n", "6\n"],
                "CSF-03": ["25\n", "50\n", "0 15\n1 25\n2 10\n", "4\n"]}
    for uid in expected:
        lesson = study.LESSONS[uid]
        blocks = re.findall(r"```python\n(.*?)\n```", lesson, re.S)
        assert len(blocks) == len(expected[uid])
        for code, output in zip(blocks, expected[uid]):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                exec(compile(code, uid, "exec"), {"__builtins__": {"print": print, "range": range, "len": len}})
            assert stream.getvalue() == output


@pytest.mark.parametrize("budget", [10, 25, 45])
def test_finite_session_budget(client, budget):
    session = client.post("/api/session", json={"budget": budget}).json()
    assert session["tasks"] and sum(t["minutes"] for t in session["tasks"]) <= budget
    assert session["tasks"][0]["unit_id"] == "SE-01"
    assert client.post("/api/session", json={"budget": 45}).json()["id"] == session["id"]


def test_references_hidden_until_reveal_or_submission(client):
    bootstrap = client.get("/api/bootstrap").json()
    assert all("answer" not in q and "reference_fill" not in q for q in bootstrap["pack"]["questions"])
    q = client.get("/api/question/SE-01-Q06").json()
    assert q["reference"] is None and "rubric" not in q["question"]
    assert client.post("/api/reveal/SE-01-Q06", json={}).json()["answer"]


def test_submit_idempotency_and_first_attempt_statistics(client):
    key = str(uuid.uuid4())
    a = submit(client, key=key).json()["attempt"]
    b = submit(client, key=key).json()["attempt"]
    assert a == b and a["result"] == "correct" and a["first_independent"]
    assert submit(client, key=key, answer={"option": "B"}).status_code == 409
    submit(client)
    data = client.get("/api/bootstrap").json()
    assert len(data["state"]["attempts"]) == 2
    assert data["summary"]["first_total"] == data["summary"]["first_correct"] == 1
    assert data["state"]["attempts"][-1]["assisted"]


def test_reveal_without_submission_survives_reload(client):
    client.post("/api/reveal/SE-01-Q01", json={})
    assert client.get("/api/bootstrap").json()["state"]["exposures"]["SE-01-Q01"]
    attempt = submit(client).json()["attempt"]
    assert attempt["assisted"] and not attempt["first_independent"]
    assert client.get("/api/bootstrap").json()["summary"]["first_total"] == 0


def test_later_day_unassisted_but_not_new_first_attempt(client, monkeypatch):
    monkeypatch.setattr(study, "now", lambda: "2026-09-24T03:00:00+00:00")
    client.post("/api/reveal/SE-01-Q01", json={})
    monkeypatch.setattr(study, "now", lambda: "2026-09-25T03:00:00+00:00")
    attempt = submit(client).json()["attempt"]
    assert not attempt["assisted"] and not attempt["first_independent"]


def test_subjective_pending_rubric_and_original_answer(client):
    answer = {"text": "时间和单价相乘得到费用。"}
    attempt = submit(client, "SE-01-Q07", answer).json()["attempt"]
    assert attempt["result"] == "pending"
    assert attempt["id"] in client.get("/api/bootstrap").json()["summary"]["pending"]
    url = "/api/assessment/" + attempt["id"]
    assert client.post(url, json={"ratings": {"R1": "full"}}).status_code == 422
    ratings = {"R1": "full", "R2": "full", "R3": "full"}
    result = client.post(url, json={"ratings": ratings}).json()
    assert result["result"] == "correct" and result["answer"] == answer
    assert client.post(url, json={"ratings": ratings}).status_code == 200
    assert client.post(url, json={"ratings": {**ratings, "R1": "missed"}}).status_code == 409
    assert client.get("/api/bootstrap").json()["summary"]["first_total"] == 0


def test_resume_older_pending_assessment(client):
    old = submit(client, "SE-01-Q07", {"text": "第一次回答"}).json()["attempt"]
    submit(client, "SE-01-Q07", {"text": "第二次回答"})
    assert client.post("/api/resume-assessment/" + old["id"], json={}).status_code == 200
    response = client.get("/api/question/SE-01-Q07").json()
    assert response["attempt"]["id"] == old["id"]
    assert response["draft"]["answer"]["text"] == "第一次回答"


def test_draft_note_position_and_restart(tmp_path):
    db = tmp_path / "persistent.sqlite3"
    first = TestClient(study.create_app(db))
    draft = {"question_id": "SE-03-Q08", "answer": {"blank": "values[index]", "explanation": "暂时写到这里"},
             "uncertain": True, "submission_key": "draft-key"}
    assert first.post("/api/draft", json=draft).status_code == 200
    first.post("/api/note/SE-01", json={"text": '<script>alert("x")</script>'})
    first.post("/api/position", json={"position": "learn/SE-01/1"})
    second = TestClient(study.create_app(db))
    data = second.get("/api/bootstrap").json()
    assert data["state"]["notes"]["SE-01"].startswith("<script>")
    assert data["state"]["position"] == "learn/SE-01/1"
    assert second.get("/api/question/SE-03-Q08").json()["draft"]["answer"] == draft["answer"]
    assert "<script>" not in study.MD.render('<script>alert("x")</script>')


def test_prerequisites_and_override(client):
    assert not client.get("/api/bootstrap").json()["summary"]["eligible"]["CSF-02"]
    for i in range(3):
        client.post("/api/read", json={"unit_id": "CSF-01", "section": i})
    assert not client.get("/api/bootstrap").json()["summary"]["eligible"]["CSF-02"]
    client.post("/api/override/CSF-01", json={})
    data = client.get("/api/bootstrap").json()
    assert data["summary"]["eligible"]["CSF-02"] and not data["summary"]["unit_checked"]["CSF-01"]


def test_backup_restore_and_corruption_no_data_loss(client, tmp_path):
    submit(client)
    client.post("/api/note/SE-01", json={"text": "输入、处理、输出"})
    client.post("/api/feedback", json={"text": "第一课讲解清楚"})
    backup = client.get("/api/backup").json()
    original = copy.deepcopy(backup["state"])
    assert client.post("/api/backup/check", json=backup).status_code == 200
    client.post("/api/note/SE-01", json={"text": "新笔记"})
    restored = client.post("/api/backup/restore", json=backup)
    assert restored.status_code == 200
    previous_path = restored.json()["previous_backup"]
    assert json.loads(__import__('pathlib').Path(previous_path).read_text(encoding="utf-8"))["state"]["notes"]["SE-01"] == "新笔记"
    assert client.get("/api/bootstrap").json()["state"] == original
    for bad in [{}, {**backup, "schema_version": 99}, {**backup, "lessons": {}},
                {**backup, "state": {**original, "attempts": [{"question_id": "missing"}]}}]:
        assert client.post("/api/backup/restore", json=bad).status_code == 422
        assert client.get("/api/bootstrap").json()["state"] == original


def test_invalid_answers_and_cross_origin_are_rejected(client):
    assert submit(client, answer={"option": "Z"}).status_code == 422
    assert submit(client, "SE-01-Q07", {"text": " "}).status_code == 422
    assert client.post("/api/read", json={"unit_id": "SE-01", "section": 9}).status_code == 422
    assert client.post("/api/session", json={"budget": 10}, headers={"origin": "https://other.example"}).status_code == 403


def test_session_completes_with_actual_read_and_answers(client):
    session = client.post("/api/session", json={"budget": 10}).json()
    client.post("/api/read", json={"unit_id": "SE-01", "section": 0})
    submit(client)
    submit(client, "SE-01-Q02", {"option": "D"})
    state = client.get("/api/bootstrap").json()["state"]
    assert state["session"]["completed_at"] and all(t["done"] for t in state["session"]["tasks"])
    following = client.post("/api/session", json={"budget": 10}).json()
    assert following["id"] != session["id"] and following["tasks"][0]["section"] == 1


def test_checkpoint_session_opens_new_attempt_without_erasing_history(client):
    for section in range(4):
        client.post("/api/read", json={"unit_id": "SE-01", "section": section})
    for q in study.QUESTIONS.values():
        if q["unit_id"] != "SE-01":
            continue
        answer = {"option": "A"} if q["type"] == "single_choice" else (
            {"text": "自己的理解"} if q["type"] == "short_answer" else {"blank": "quantity", "explanation": "45"})
        attempt = submit(client, q["id"], answer).json()["attempt"]
        if q["type"] != "single_choice":
            client.post("/api/assessment/" + attempt["id"], json={"ratings": {"R1": "full", "R2": "full", "R3": "full"}})
    session = client.post("/api/session", json={"budget": 10}).json()
    assert session["tasks"] and all(t["kind"] == "question" for t in session["tasks"])
    for task in session["tasks"]:
        assert client.get("/api/question/" + task["question_id"]).json()["attempt"] is None
    assert len(client.get("/api/bootstrap").json()["state"]["attempts"]) == 8
