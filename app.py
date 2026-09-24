"""Local, single-user study pilot. Run with: python app.py."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal
import copy
import json
import os
import sqlite3
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parent
PACK = json.loads((ROOT / "content/pack.json").read_text(encoding="utf-8"))
ARCHIVE = json.loads((ROOT / "content/archive/pack-v1.json").read_text(encoding="utf-8"))
ACTIVE_UNITS = {u["id"]: u for u in PACK["units"]}
ACTIVE_QUESTIONS = {q["id"]: q for q in PACK["questions"]}
UNITS = {u["id"]: u for u in PACK["units"] + ARCHIVE["units"]}
QUESTIONS = {q["id"]: q for q in PACK["questions"] + ARCHIVE["questions"]}
MD = MarkdownIt("commonmark", {"html": False}).enable("table")
LESSONS = {u["id"]: (ROOT / "content" / u["lesson_path"]).read_text(encoding="utf-8") for u in UNITS.values()}
SECTIONS = {}
for unit_id, lesson in LESSONS.items():
    SECTIONS[unit_id] = [{"title": part.split("\n", 1)[0], "html": MD.render(part.split("\n", 1)[1]),
                         "minutes": UNITS[unit_id]["section_minutes"][i]}
                        for i, part in enumerate(lesson.removeprefix("## ").split("\n## "))]


def now():
    return datetime.now(timezone.utc).isoformat()


def local_day(timestamp):
    return datetime.fromisoformat(timestamp).astimezone(timezone(timedelta(hours=8))).date()


def empty_state():
    return {"attempts": [], "exposures": {}, "drafts": {}, "notes": {}, "units": {},
            "session": None, "position": "", "feedback": [], "budget": 25}


def question(qid):
    if qid not in QUESTIONS:
        raise HTTPException(404, "没有找到这道题")
    return QUESTIONS[qid]


def unit(uid):
    if uid not in UNITS:
        raise HTTPException(404, "没有找到这个单元")
    return UNITS[uid]


def public_question(q):
    hidden = {"answer", "explanation", "option_explanations", "rubric", "reference_fill", "test_output"}
    return {k: v for k, v in q.items() if k not in hidden}


def reference(q):
    return {k: q[k] for k in ("answer", "explanation", "option_explanations", "rubric") if k in q}


def unit_checked(state, uid):
    passed = {a["question_id"] for a in state["attempts"]
              if a["result"] == "correct" and not a["assisted"] and not a["uncertain"]}
    return set(UNITS[uid]["checkpoint_question_ids"]).issubset(passed)


def eligible(state, uid):
    return all(unit_checked(state, prior) or state["units"].get(prior, {}).get("override", False)
               for prior in UNITS[uid]["prerequisite_ids"])


def advance(state, kind, uid=None, section=None, qid=None):
    session = state["session"]
    if not session:
        return
    for task in session["tasks"]:
        if task["kind"] == kind and ((kind == "lesson" and task["unit_id"] == uid and task["section"] == section)
                                      or (kind == "question" and task["question_id"] == qid)):
            task["done"] = True
    if all(t["done"] for t in session["tasks"]):
        session["completed_at"] = now()


def summary(state):
    first = {}
    latest = {}
    for attempt in state["attempts"]:
        q = QUESTIONS[attempt["question_id"]]
        latest[q["id"]] = attempt
        if q["id"] in ACTIVE_QUESTIONS and q["type"] == "single_choice" and q["id"] not in first:
            first[q["id"]] = attempt
    independent = [a for a in first.values() if a["first_independent"]]
    mistakes = [qid for qid, a in latest.items() if qid in ACTIVE_QUESTIONS and (a["result"] == "incorrect" or a["uncertain"])]
    return {"answered": len(set(latest) & set(ACTIVE_QUESTIONS)), "first_correct": sum(a["result"] == "correct" for a in independent),
            "first_total": len(independent), "mistakes": mistakes,
            "pending": [a["id"] for a in state["attempts"] if a["result"] == "pending"],
            "unit_checked": {uid: unit_checked(state, uid) for uid in UNITS},
            "eligible": {uid: eligible(state, uid) for uid in UNITS},
            "latest": latest}


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Draft(Payload):
    question_id: str
    answer: dict
    uncertain: bool = False
    submission_key: str = Field(min_length=1, max_length=100)


class Submit(Draft):
    pass


class Assessment(Payload):
    ratings: dict[str, Literal["full", "partial", "missed"]]


class Begin(Payload):
    budget: Literal[10, 25, 45] = 25


class Read(Payload):
    unit_id: str
    section: int


class Text(Payload):
    text: str = Field(max_length=15000)


class Position(Payload):
    position: str = Field(max_length=150)


def validate_answer(q, answer, required=False):
    allowed = {"option"} if q["type"] == "single_choice" else ({"text"} if q["type"] == "short_answer" else {"blank", "explanation"})
    if set(answer) - allowed or any(not isinstance(v, str) or len(v) > 15000 for v in answer.values()):
        raise HTTPException(422, "作答格式不正确")
    if q["type"] == "single_choice":
        if answer.get("option") and answer["option"] not in q["options"]:
            raise HTTPException(422, "选项不存在")
        valid = bool(answer.get("option"))
    else:
        valid = all(answer.get(k, "").strip() for k in allowed)
    if required and not valid:
        raise HTTPException(422, "请先完成作答，再提交")


def backup_payload(state):
    return {"schema_version": 2, "exported_at": now(), "pack": PACK, "archive": ARCHIVE, "lessons": LESSONS, "state": state}


def validate_backup(data):
    if not isinstance(data, dict) or data.get("schema_version") not in (1, 2):
        raise HTTPException(422, "备份格式或版本不受支持")
    current = data.get("schema_version") == 2 and data.get("pack") == PACK and data.get("archive") == ARCHIVE and data.get("lessons") == LESSONS
    legacy_lessons = {u["id"]: LESSONS[u["id"]] for u in ARCHIVE["units"]}
    legacy = data.get("schema_version") == 1 and data.get("pack") == ARCHIVE and data.get("lessons") == legacy_lessons
    if not (current or legacy):
        raise HTTPException(422, "备份内容版本与当前试点不一致，未更改现有记录")
    state = data.get("state")
    try:
        assert isinstance(state, dict) and set(state) == set(empty_state())
        assert state["budget"] in (10, 25, 45) and isinstance(state["position"], str)
        for field in ("exposures", "drafts", "notes", "units"):
            assert isinstance(state[field], dict)
        assert isinstance(state["attempts"], list) and isinstance(state["feedback"], list)
        ids, keys = set(), set()
        for a in state["attempts"]:
            q = question(a["question_id"])
            assert a["question_version"] == q["version"]
            assert isinstance(a["id"], str) and a["id"] not in ids
            assert isinstance(a["submission_key"], str) and a["submission_key"] not in keys
            ids.add(a["id"]); keys.add(a["submission_key"])
            validate_answer(q, a["answer"], required=True)
            assert a["result"] in ("correct", "incorrect", "pending")
            assert a["assessment_method"] in ("automatic", "self-rated")
            for flag in ("assisted", "uncertain", "first_independent"):
                assert isinstance(a[flag], bool)
            local_day(a["submitted_at"])
            if q["type"] == "single_choice":
                assert a["result"] == ("correct" if a["answer"]["option"] == q["answer"] else "incorrect")
            elif a["result"] != "pending":
                assert set(a["ratings"]) == {r["id"] for r in q["rubric"]}
                assert all(v in ("full", "partial", "missed") for v in a["ratings"].values())
                assert a["result"] == ("correct" if all(v == "full" for v in a["ratings"].values()) else "incorrect")
        for qid, exposure in state["exposures"].items():
            question(qid); local_day(exposure["first"]); local_day(exposure["last"])
        for qid, draft in state["drafts"].items():
            validate_answer(question(qid), draft["answer"])
            assert isinstance(draft["submission_key"], str) and isinstance(draft["uncertain"], bool)
            assert draft.get("attempt_id") is None or draft["attempt_id"] in ids
        for uid, note in state["notes"].items():
            unit(uid); assert isinstance(note, str) and len(note) <= 15000
        for uid, progress in state["units"].items():
            unit(uid)
            assert isinstance(progress["read_sections"], list)
            assert all(isinstance(i, int) and 0 <= i < len(SECTIONS[uid]) for i in progress["read_sections"])
            assert isinstance(progress.get("override", False), bool)
        for item in state["feedback"]:
            assert isinstance(item["text"], str) and len(item["text"]) <= 15000
            local_day(item["created_at"])
        if state["session"] is not None:
            session = state["session"]
            assert isinstance(session["id"], str) and isinstance(session["tasks"], list)
            assert session["budget"] in (10, 25, 45)
            for task in session["tasks"]:
                assert isinstance(task["done"], bool) and isinstance(task["minutes"], int)
                if task["kind"] == "lesson":
                    unit(task["unit_id"])
                    assert 0 <= task["section"] < len(SECTIONS[task["unit_id"]])
                else:
                    assert task["kind"] == "question"; question(task["question_id"])
    except (AssertionError, KeyError, TypeError, ValueError, HTTPException):
        raise HTTPException(422, "备份记录不完整或校验失败，未更改现有记录")
    return state


def current_session(state):
    session = state["session"]
    if session and all(t.get("unit_id") in ACTIVE_UNITS if t["kind"] == "lesson" else t.get("question_id") in ACTIVE_QUESTIONS for t in session["tasks"]):
        return session
    return None


def create_app(db_path=None):
    db_path = Path(db_path or os.environ.get("STUDY_DB", ROOT / "data/study.sqlite3"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute("CREATE TABLE IF NOT EXISTS study_state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
        con.execute("INSERT OR IGNORE INTO study_state VALUES (1, ?)", (json.dumps(empty_state()),))

    @contextmanager
    def store():
        con = sqlite3.connect(db_path, timeout=10)
        try:
            con.execute("BEGIN IMMEDIATE")
            state = json.loads(con.execute("SELECT body FROM study_state WHERE id=1").fetchone()[0])
            yield state
            con.execute("UPDATE study_state SET body=? WHERE id=1", (json.dumps(state, ensure_ascii=False),))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    app = FastAPI(title="软考虐待狂 · 软件设计师学习台", docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")

    @app.middleware("http")
    async def local_writes(request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin")
            if origin and origin not in ("http://127.0.0.1:8765", "http://localhost:8765", "http://127.0.0.1:8766"):
                return JSONResponse({"detail": "只接受本机学习页面的操作"}, status_code=403)
            if int(request.headers.get("content-length", "0")) > 8_000_000:
                return JSONResponse({"detail": "文件过大"}, status_code=413)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request=request, name="index.html", context={})

    @app.get("/api/bootstrap")
    def bootstrap():
        with store() as state:
            return {"pack": {**PACK, "questions": [public_question(q) for q in PACK["questions"]]},
                    "archive": {**ARCHIVE, "questions": [public_question(q) for q in ARCHIVE["questions"]]},
                    "sections": SECTIONS, "state": {**state, "session": current_session(state)}, "summary": summary(state)}

    @app.post("/api/session")
    def begin(payload: Begin):
        with store() as state:
            state["budget"] = payload.budget
            if current_session(state) and not state["session"].get("completed_at"):
                return state["session"]
            candidates = []
            seen = {a["question_id"] for a in state["attempts"] if a["result"] != "pending"}
            for uid in ACTIVE_UNITS:
                if not eligible(state, uid):
                    continue
                read = state["units"].get(uid, {}).get("read_sections", [])
                remaining = [{"kind": "lesson", "unit_id": uid, "section": i, "minutes": s["minutes"], "done": False}
                             for i, s in enumerate(SECTIONS[uid]) if i not in read]
                questions = [{"kind": "question", "question_id": q["id"], "minutes": q["minutes"], "done": False}
                             for q in QUESTIONS.values() if q["unit_id"] == uid and q["id"] not in seen]
                if remaining or questions:
                    # Interleave a section with its questions; never schedule a future section's quiz first.
                    pending_sections = {t["section"]: t for t in remaining}
                    for i in range(len(SECTIONS[uid])):
                        if i in pending_sections:
                            candidates.append(pending_sections[i])
                        candidates.extend(t for t in questions if QUESTIONS[t["question_id"]]["section_index"] == i)
                    break
                if not unit_checked(state, uid):
                    candidates = [{"kind": "question", "question_id": qid, "minutes": QUESTIONS[qid]["minutes"], "done": False}
                                  for qid in UNITS[uid]["checkpoint_question_ids"]]
                    break
            tasks, minutes = [], 0
            for task in candidates:
                if minutes + task["minutes"] <= payload.budget:
                    tasks.append(task); minutes += task["minutes"]
                else:
                    break
            for task in tasks:
                if task["kind"] == "question":
                    draft = state["drafts"].get(task["question_id"])
                    attempt = next((a for a in state["attempts"] if draft and a["id"] == draft.get("attempt_id")), None)
                    if attempt and attempt["result"] != "pending":
                        state["drafts"].pop(task["question_id"], None)
            state["session"] = {"id": str(uuid.uuid4()), "budget": payload.budget, "tasks": tasks,
                                "started_at": now(), "completed_at": None if tasks else now()}
            return state["session"]

    @app.post("/api/position")
    def position(payload: Position):
        with store() as state:
            state["position"] = payload.position
        return {"saved": True}

    @app.post("/api/read")
    def read(payload: Read):
        unit(payload.unit_id)
        if not 0 <= payload.section < len(SECTIONS[payload.unit_id]):
            raise HTTPException(422, "小节不存在")
        with store() as state:
            progress = state["units"].setdefault(payload.unit_id, {"read_sections": [], "override": False})
            if payload.section not in progress["read_sections"]:
                progress["read_sections"].append(payload.section)
            advance(state, "lesson", uid=payload.unit_id, section=payload.section)
        return {"saved": True}

    @app.post("/api/override/{uid}")
    def override(uid: str):
        unit(uid)
        with store() as state:
            state["units"].setdefault(uid, {"read_sections": []})["override"] = True
        return {"saved": True}

    @app.get("/api/question/{qid}")
    def get_question(qid: str):
        q = question(qid)
        with store() as state:
            draft = state["drafts"].get(qid)
            attempt = next((a for a in state["attempts"] if draft and a["id"] == draft.get("attempt_id")), None)
            return {"question": public_question(q), "draft": draft, "attempt": attempt,
                    "reference": reference(q) if attempt else None}

    @app.post("/api/draft")
    def save_draft(payload: Draft):
        validate_answer(question(payload.question_id), payload.answer)
        with store() as state:
            current = state["drafts"].get(payload.question_id)
            if current and current.get("attempt_id"):
                raise HTTPException(409, "这次作答已经提交；点击重新作答可创建新记录")
            state["drafts"][payload.question_id] = payload.model_dump(exclude={"question_id"})
        return {"saved": True}

    @app.post("/api/retry/{qid}")
    def retry(qid: str):
        question(qid)
        with store() as state:
            state["drafts"].pop(qid, None)
        return {"saved": True}

    @app.post("/api/reveal/{qid}")
    def reveal(qid: str):
        q = question(qid)
        with store() as state:
            stamp = now()
            exposure = state["exposures"].setdefault(qid, {"first": stamp, "last": stamp})
            exposure["last"] = stamp
        return reference(q)

    @app.post("/api/submit")
    def submit(payload: Submit):
        q = question(payload.question_id)
        validate_answer(q, payload.answer, required=True)
        with store() as state:
            previous = next((a for a in state["attempts"] if a["submission_key"] == payload.submission_key), None)
            if previous:
                if previous["question_id"] != q["id"] or previous["answer"] != payload.answer:
                    raise HTTPException(409, "提交标识已被使用，请重新打开题目")
                return {"attempt": previous, "reference": reference(q)}
            stamp = now()
            exposure = state["exposures"].get(q["id"])
            assisted = bool(exposure and local_day(exposure["last"]) == local_day(stamp))
            first = not exposure and not any(a["question_id"] == q["id"] for a in state["attempts"])
            result = ("correct" if payload.answer["option"] == q["answer"] else "incorrect") if q["type"] == "single_choice" else "pending"
            attempt = {"id": str(uuid.uuid4()), "question_id": q["id"], "question_version": q["version"],
                       "session_id": state["session"]["id"] if state["session"] else None,
                       "submission_key": payload.submission_key, "answer": payload.answer, "uncertain": payload.uncertain,
                       "assisted": assisted, "first_independent": first, "result": result,
                       "assessment_method": "automatic" if q["type"] == "single_choice" else "self-rated",
                       "submitted_at": stamp, "assessed_at": stamp if result != "pending" else None, "ratings": {}}
            state["attempts"].append(attempt)
            state["drafts"][q["id"]] = {**payload.model_dump(exclude={"question_id"}), "attempt_id": attempt["id"]}
            state["exposures"][q["id"]] = {"first": exposure["first"] if exposure else stamp, "last": stamp}
            if result != "pending":
                advance(state, "question", qid=q["id"])
            return {"attempt": attempt, "reference": reference(q)}

    @app.post("/api/assessment/{attempt_id}")
    def assessment(attempt_id: str, payload: Assessment):
        with store() as state:
            attempt = next((a for a in state["attempts"] if a["id"] == attempt_id), None)
            if not attempt:
                raise HTTPException(404, "作答记录不存在")
            q = question(attempt["question_id"])
            if q["type"] == "single_choice" or set(payload.ratings) != {r["id"] for r in q["rubric"]}:
                raise HTTPException(422, "请评价每一个要点")
            if attempt["result"] != "pending":
                if attempt["ratings"] == payload.ratings:
                    return attempt
                raise HTTPException(409, "自评已保存；重新作答会产生新的记录")
            attempt["ratings"] = payload.ratings
            attempt["result"] = "correct" if all(v == "full" for v in payload.ratings.values()) else "incorrect"
            attempt["assessed_at"] = now()
            advance(state, "question", qid=q["id"])
            return attempt

    @app.post("/api/resume-assessment/{attempt_id}")
    def resume_assessment(attempt_id: str):
        with store() as state:
            attempt = next((a for a in state["attempts"] if a["id"] == attempt_id), None)
            if not attempt or attempt["result"] != "pending":
                raise HTTPException(404, "没有找到待自评记录")
            state["drafts"][attempt["question_id"]] = {"answer": attempt["answer"], "uncertain": attempt["uncertain"],
                                                         "submission_key": attempt["submission_key"], "attempt_id": attempt_id}
        return {"saved": True}

    @app.post("/api/note/{uid}")
    def note(uid: str, payload: Text):
        unit(uid)
        with store() as state:
            state["notes"][uid] = payload.text
        return {"saved": True}

    @app.post("/api/feedback")
    def feedback(payload: Text):
        if not payload.text.strip():
            raise HTTPException(422, "请先写一点反馈")
        with store() as state:
            state["feedback"].append({"text": payload.text, "created_at": now(), "position": state["position"]})
        return {"saved": True}

    @app.get("/api/backup")
    def backup():
        with store() as state:
            return JSONResponse(backup_payload(state), headers={"Content-Disposition": 'attachment; filename="zhixu-study-backup.json"'})

    @app.post("/api/backup/check")
    def check_backup(data: dict):
        state = validate_backup(data)
        return {"attempts": len(state["attempts"]), "notes": len(state["notes"]), "feedback": len(state["feedback"]),
                "exported_at": data.get("exported_at", ""), "pack_version": PACK["version"]}

    @app.post("/api/backup/restore")
    def restore(data: dict):
        replacement = validate_backup(data)
        with store() as state:
            directory = db_path.parent / "backups"
            directory.mkdir(exist_ok=True)
            path = directory / ("before-restore-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
            path.write_text(json.dumps(backup_payload(state), ensure_ascii=False, indent=2), encoding="utf-8")
            state.clear(); state.update(copy.deepcopy(replacement))
        return {"saved": True, "previous_backup": str(path)}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("STUDY_PORT", "8765")))
