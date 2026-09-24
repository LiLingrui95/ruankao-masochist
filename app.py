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

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from content_bank import LIBRARY, TOPICS, PAPERS, augment, published, question_card, topic_card, paginate, compatible_snapshot

ROOT = Path(__file__).resolve().parent
BASE_PACK = json.loads((ROOT / "content/archive/pack-v2.json").read_text(encoding="utf-8"))
PACK = augment(json.loads((ROOT / "content/pack.json").read_text(encoding="utf-8")))
ARCHIVE = json.loads((ROOT / "content/archive/pack-v1.json").read_text(encoding="utf-8"))
ACTIVE_UNITS = {u["id"]: u for u in PACK["units"]}
ACTIVE_QUESTIONS = {q["id"]: q for q in PACK["questions"]}
UNITS = {u["id"]: u for u in PACK["units"] + ARCHIVE["units"]}
QUESTIONS = {q["id"]: q for q in PACK["questions"] + ARCHIVE["questions"]}
QUESTIONS.update({q["id"]: q for q in LIBRARY["questions"]})
MD = MarkdownIt("commonmark", {"html": False}).enable("table")
LESSONS = {u["id"]: (ROOT / "content" / u["lesson_path"]).read_text(encoding="utf-8") for u in UNITS.values()}
SECTIONS = {}
for unit_id, lesson in LESSONS.items():
    if unit_id in TOPICS:
        SECTIONS[unit_id] = [{"title": TOPICS[unit_id]["title"], "html": MD.render(lesson), "minutes": TOPICS[unit_id]["minutes"]}]
        continue
    SECTIONS[unit_id] = [{"title": part.split("\n", 1)[0], "html": MD.render(part.split("\n", 1)[1]),
                         "minutes": UNITS[unit_id]["section_minutes"][i]}
                         for i, part in enumerate(lesson.removeprefix("## ").split("\n## "))]

for paper in LIBRARY["papers"]:
    UNITS.setdefault(paper["id"], {"id": paper["id"], "title": paper["title"], "subtitle": "历年试题材料",
                                 "source_ids": paper["source_ids"], "prerequisite_ids": [], "checkpoint_question_ids": [],
                                 "version": "1.0.0", "objectives": [], "availability": "reference"})
    LESSONS.setdefault(paper["id"], "")
    SECTIONS.setdefault(paper["id"], [])
    for qid in paper["question_ids"]:
        if qid in QUESTIONS and QUESTIONS[qid]["unit_id"] not in UNITS:
            QUESTIONS[qid]["unit_id"] = paper["id"]


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
    allowed = {"id", "title", "unit_id", "module_id", "topic_ids", "section_index", "type", "prompt", "options",
               "code", "language", "difficulty", "minutes", "version", "origin_kind", "review_status", "answer_status",
               "source_ids", "exam_anchor", "case_material", "subquestions", "assets", "paper_id", "original_number", "points"}
    result = {k: v for k, v in q.items() if k in allowed}
    result["prompt_html"] = MD.render(q["prompt"])
    if q.get("case_material"):
        result["case_html"] = MD.render(q["case_material"])
    if q.get("subquestions"):
        result["subquestions"] = [{k: item[k] for k in ("id", "prompt", "points") if k in item} for item in q["subquestions"]]
    return result


def reference(q):
    return {k: q[k] for k in ("answer", "explanation", "option_explanations", "rubric") if k in q}


def unit_checked(state, uid):
    passed = {a["question_id"] for a in state["attempts"]
              if a["result"] == "correct" and not a["assisted"] and not a["uncertain"]}
    checkpoints = set(UNITS[uid]["checkpoint_question_ids"])
    return bool(checkpoints) and checkpoints.issubset(passed)


def eligible(state, uid):
    return all(unit_checked(state, prior) or state["units"].get(prior, {}).get("override", False)
               for prior in UNITS[uid]["prerequisite_ids"])


def advance(state, kind, uid=None, section=None, qid=None, session_id=None):
    session = state["session"]
    if session_id:
        session = next((s for s in ([session] if session else []) + list(state.get("paused_sessions", {}).values()) if s["id"] == session_id), None)
    elif qid and session and session.get("mode"):
        return
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
    mode: Literal["learn", "mistakes", "test"] | None = None
    unit_id: str | None = None


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
    return {"schema_version": 3, "exported_at": now(), "content_version": LIBRARY["version"],
            "pack": PACK, "archive": ARCHIVE, "lessons": LESSONS, "library": LIBRARY, "state": state}


def validate_backup(data):
    if not isinstance(data, dict) or data.get("schema_version") not in (1, 2, 3):
        raise HTTPException(422, "备份格式或版本不受支持")
    current = False
    if data.get("schema_version") == 3 and compatible_snapshot(data.get("library"), LIBRARY):
        saved_pack = data.get("pack", {})
        saved_lessons = data.get("lessons", {})
        saved_library = data["library"]
        expected_pack = augment(BASE_PACK, saved_library)
        expected_lessons = {u["id"] for u in expected_pack["units"] + ARCHIVE["units"]} | {p["id"] for p in saved_library["papers"]}
        current = (data.get("archive") == ARCHIVE and data.get("content_version") == saved_library["version"]
                   and isinstance(saved_pack, dict) and isinstance(saved_lessons, dict)
                   and saved_pack == expected_pack and set(saved_lessons) == expected_lessons
                   and all(value == LESSONS.get(uid) for uid, value in saved_lessons.items()))
        if current:
            for field in ("units", "questions", "sources"):
                known = {row["id"]: row for row in PACK[field]}
                records = saved_pack.get(field, [])
                if not isinstance(records, list) or any(not isinstance(row, dict) or row != known.get(row.get("id")) for row in records):
                    current = False
                    break
            saved_ids = {q["id"] for q in saved_pack.get("questions", []) if isinstance(q, dict) and "id" in q} | {q["id"] for q in ARCHIVE["questions"]}
            state_value = data.get("state", {})
            if isinstance(state_value, dict):
                needed = {a.get("question_id") for a in state_value.get("attempts", []) if isinstance(a, dict)}
                needed |= set(state_value.get("drafts", {})) if isinstance(state_value.get("drafts"), dict) else set()
                current = current and needed <= saved_ids
    v2_lessons = {u["id"]: LESSONS[u["id"]] for u in BASE_PACK["units"] + ARCHIVE["units"]}
    v2 = data.get("schema_version") == 2 and data.get("pack") == BASE_PACK and data.get("archive") == ARCHIVE and data.get("lessons") == v2_lessons
    legacy_lessons = {u["id"]: LESSONS[u["id"]] for u in ARCHIVE["units"]}
    legacy = data.get("schema_version") == 1 and data.get("pack") == ARCHIVE and data.get("lessons") == legacy_lessons
    if not (current or legacy or v2):
        raise HTTPException(422, "备份内容版本与当前试点不一致，未更改现有记录")
    state = data.get("state")
    try:
        assert isinstance(state, dict) and set(empty_state()) <= set(state) <= set(empty_state()) | {"paused_sessions"}
        assert isinstance(state.get("paused_sessions", {}), dict)
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
        for session in ([state["session"]] if state["session"] is not None else []) + list(state.get("paused_sessions", {}).values()):
            assert isinstance(session, dict)
            assert isinstance(session["id"], str) and isinstance(session["tasks"], list)
            assert session["budget"] in (10, 25, 45)
            assert session.get("mode", "learn") in ("learn", "mistakes", "test")
            if session.get("mode") == "test":
                unit(session["unit_id"])
            assert isinstance(session.get("drafts", {}), dict)
            for qid, draft in session.get("drafts", {}).items():
                assert any(t.get("question_id") == qid for t in session["tasks"])
                validate_answer(question(qid), draft["answer"])
                assert isinstance(draft["submission_key"], str) and isinstance(draft["uncertain"], bool)
                assert draft.get("attempt_id") is None or draft["attempt_id"] in ids
            for task in session["tasks"]:
                assert isinstance(task["done"], bool) and isinstance(task["minutes"], int)
                if task["kind"] == "lesson":
                    unit(task["unit_id"])
                    assert 0 <= task["section"] < len(SECTIONS[task["unit_id"]])
                else:
                    assert task["kind"] == "question"; question(task["question_id"])
        for key, session in state.get("paused_sessions", {}).items():
            assert key == session_key(session.get("mode", "learn"), session.get("unit_id"))
    except (AssertionError, KeyError, TypeError, ValueError, HTTPException):
        raise HTTPException(422, "备份记录不完整或校验失败，未更改现有记录")
    return state


def current_session(state):
    session = state["session"]
    if session and all(t.get("unit_id") in ACTIVE_UNITS if t["kind"] == "lesson" else t.get("question_id") in ACTIVE_QUESTIONS for t in session["tasks"]):
        return session
    return None


def session_key(mode, uid=None):
    return mode + (":" + uid if mode == "test" and uid else "")


def question_drafts(state, qid):
    session = current_session(state)
    if session and session.get("mode") and any(t.get("question_id") == qid for t in session["tasks"]):
        return session.setdefault("drafts", {})
    return state["drafts"]


def study_plan(state, mode, uid=None):
    """Preview and start use the same deterministic plan; preview does not mutate state."""
    latest = {a["question_id"]: a for a in state["attempts"]}
    studied = [u for u in ACTIVE_UNITS.values() if SECTIONS[u["id"]] and
               (state["units"].get(u["id"], {}).get("read_sections") or
                any(QUESTIONS[qid]["unit_id"] == u["id"] for qid in latest))]
    choices = [{"id": u["id"], "title": u["title"]} for u in studied]
    if mode == "test":
        uid = uid or (choices[0]["id"] if choices else None)
        if uid and uid not in {u["id"] for u in choices}:
            raise HTTPException(422, "请先学习或练习这个单元，再进行自测")
    key = session_key(mode, uid)
    active = current_session(state)
    saved = active if active and session_key(active.get("mode", "learn"), active.get("unit_id")) == key else state.get("paused_sessions", {}).get(key)
    tasks, reason = [], ""
    if saved and not saved.get("completed_at"):
        tasks = copy.deepcopy(saved["tasks"])
    elif mode == "learn":
        for unit_id in ACTIVE_UNITS:
            if not eligible(state, unit_id):
                continue
            read = state["units"].get(unit_id, {}).get("read_sections", [])
            for index, section in enumerate(SECTIONS[unit_id]):
                questions = [q for q in ACTIVE_QUESTIONS.values() if q["unit_id"] == unit_id
                             and q.get("section_index", 0) == index and q["id"] not in latest]
                if index not in read or questions:
                    if index not in read:
                        tasks.append({"kind": "lesson", "unit_id": unit_id, "section": index, "minutes": section["minutes"], "done": False})
                    tasks += [{"kind": "question", "question_id": q["id"], "minutes": q["minutes"], "done": False} for q in questions[:3]]
                    break
            if tasks:
                break
        reason = "当前可学习内容已完成，可以错题再练或进行单元自测。"
    else:
        if mode == "mistakes":
            questions = [ACTIVE_QUESTIONS[qid] for qid, a in latest.items() if qid in ACTIVE_QUESTIONS and
                         (a["result"] == "incorrect" or a["uncertain"]) and a["result"] != "pending"]
            reason = "暂无待巩固题目。答错或标记不确定的题目会出现在这里；待自评题请先完成自评。"
        else:
            pool = [q for q in ACTIVE_QUESTIONS.values() if q["unit_id"] == uid]
            questions, covered_sections, covered_types = [], set(), set()
            for q in pool:
                if q.get("section_index", 0) not in covered_sections:
                    questions.append(q); covered_sections.add(q.get("section_index", 0)); covered_types.add(q["type"])
            for q in pool:
                if q["type"] not in covered_types and q not in questions:
                    questions.append(q); covered_types.add(q["type"])
            questions += [q for q in pool if q not in questions]
            reason = "先读一个单元或完成一道练习，再来检查掌握情况。" if not choices else "这个单元暂无可自测题目。"
        tasks = [{"kind": "question", "question_id": q["id"], "minutes": q["minutes"], "done": False} for q in questions[:5]]
    for task in tasks:
        task["title"] = SECTIONS[task["unit_id"]][task["section"]]["title"] if task["kind"] == "lesson" else QUESTIONS[task["question_id"]]["title"]
    return {"mode": mode, "unit_id": uid, "tasks": tasks, "resuming": bool(saved and not saved.get("completed_at")),
            "minutes": sum(t["minutes"] for t in tasks if not t["done"]), "test_units": choices,
            "mistake_count": sum(qid in ACTIVE_QUESTIONS and a["result"] != "pending" and (a["result"] == "incorrect" or a["uncertain"]) for qid, a in latest.items()),
            "empty_reason": reason if not tasks else ""}


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
            if int(request.headers.get("content-length", "0")) > 64_000_000:
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
            ids = {a["question_id"] for a in state["attempts"]} | set(state["drafts"])
            ids |= {t["question_id"] for t in (current_session(state) or {}).get("tasks", []) if t["kind"] == "question"}
            ids |= {state["position"].split("/")[1]} if state["position"].startswith("practice/") else set()
            return {"pack": {**PACK, "questions": [question_card(QUESTIONS[qid]) for qid in sorted(ids) if qid in ACTIVE_QUESTIONS]},
                    "archive": {**ARCHIVE, "questions": [question_card(QUESTIONS[qid]) for qid in sorted(ids) if qid in QUESTIONS and qid not in ACTIVE_QUESTIONS]},
                    "sections": {uid: [{"title": s["title"], "minutes": s["minutes"]} for s in items] for uid, items in SECTIONS.items()},
                    "reference_units": [u for uid, u in UNITS.items() if uid not in ACTIVE_UNITS and uid not in {a['id'] for a in ARCHIVE['units']}],
                    "counts": {"questions": len(ACTIVE_QUESTIONS), "units": len(ACTIVE_UNITS),
                               "by_unit": {uid: sum(q["unit_id"] == uid for q in ACTIVE_QUESTIONS.values()) for uid in ACTIVE_UNITS}},
                    "modules": LIBRARY["modules"], "report": LIBRARY["report"],
                    "state": {**state, "session": current_session(state)}, "summary": summary(state)}

    @app.get("/api/catalog")
    def catalog():
        return {"modules": LIBRARY["modules"], "topics": [topic_card(t) for t in TOPICS.values()], "report": LIBRARY["report"], "syllabus": LIBRARY["curriculum"]["syllabus"]}

    @app.get("/api/topics")
    def topics(q: str = "", module: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        words = q.casefold().split()
        items = [topic_card(t) for t in TOPICS.values() if (not module or t["module_id"] == module)
                 and all(word in (t["title"] + " " + " ".join(t["aliases"]) + " " + t["body"]).casefold() for word in words)]
        return paginate(items, page, page_size)

    @app.get("/api/topic/{tid}")
    def topic_detail(tid: str):
        if tid not in TOPICS:
            raise HTTPException(404, "考点不存在")
        return {**topic_card(TOPICS[tid]), "html": MD.render(TOPICS[tid]["body"])}

    @app.get("/api/lesson/{uid}")
    def lesson_detail(uid: str):
        unit(uid)
        return {"sections": SECTIONS[uid]}

    @app.get("/api/questions")
    def questions(q: str = "", module: str = "", topic: str = "", unit_id: str = "", type: str = "", difficulty: str = "",
                  origin: str = "", status: str = "published", mistakes: bool = False, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        with store() as state:
            mistakes_ids = set(summary(state)["mistakes"]) if mistakes else set()
        words = q.casefold().split()
        items = [question_card(item) for item in QUESTIONS.values()
                 if (status == "all" or published(item)) and (unit_id.startswith("CSF-") or not item["id"].startswith("CSF-"))
                 and (not module or item.get("module_id") == module)
                 and (not topic or topic in item.get("topic_ids", [])) and (not unit_id or item["unit_id"] == unit_id)
                 and (not type or item["type"] == type) and (not difficulty or item.get("difficulty") == difficulty)
                 and (not origin or item.get("origin_kind") == origin) and (not mistakes or item["id"] in mistakes_ids)
                 and all(word in (item["title"] + " " + item["prompt"] + " " + (item.get("case_material") or "") + " " + (item.get("code") or "")).casefold() for word in words)]
        return paginate(items, page, page_size)

    @app.get("/api/papers")
    def papers(year: int | None = None, session: str = "", subject: str = "", batch: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        items = [p for p in sorted(PAPERS.values(), key=lambda p: (p["year"], p["session"], p["id"]), reverse=True)
                 if (year is None or p["year"] == year) and (not session or p["session"] == session)
                 and (not subject or p["subject"] == subject) and (not batch or p["batch"] == batch)]
        return {**paginate(items, page, page_size), "coverage": LIBRARY["exam_coverage"]}

    @app.get("/api/paper/{pid}")
    def paper_detail(pid: str):
        if pid not in PAPERS:
            raise HTTPException(404, "试卷不存在")
        paper = PAPERS[pid]
        return {**paper, "questions": [question_card(QUESTIONS[qid]) for qid in paper["question_ids"]],
                "sources": [s for s in LIBRARY["sources"] if s["id"] in paper["source_ids"]]}

    @app.get("/content-assets/{asset_path:path}")
    def content_asset(asset_path: str):
        path = (ROOT / "content" / asset_path).resolve()
        root = (ROOT / "content").resolve()
        if not path.is_relative_to(root) or "assets" not in path.relative_to(root).parts or not path.is_file() or path.suffix.lower() not in (".svg", ".png", ".jpg", ".jpeg", ".webp"):
            raise HTTPException(404, "附件不存在")
        return FileResponse(path)

    @app.post("/api/session")
    def begin(payload: Begin):
        with store() as state:
            if payload.mode:
                plan = study_plan(state, payload.mode, payload.unit_id)
                if not plan["tasks"]:
                    raise HTTPException(422, plan["empty_reason"])
                key = session_key(payload.mode, plan["unit_id"])
                active = current_session(state)
                paused = state.setdefault("paused_sessions", {})
                if active:
                    active_key = session_key(active.get("mode", "learn"), active.get("unit_id"))
                    if active_key == key and not active.get("completed_at"):
                        return active
                    if not active.get("completed_at"):
                        paused[active_key] = active
                saved = paused.pop(key, None)
                if saved and not saved.get("completed_at"):
                    state["session"] = saved
                else:
                    drafts = {}
                    if payload.mode == "learn":
                        drafts = {t["question_id"]: copy.deepcopy(state["drafts"][t["question_id"]]) for t in plan["tasks"]
                                  if t["kind"] == "question" and t["question_id"] in state["drafts"] and not state["drafts"][t["question_id"]].get("attempt_id")}
                    state["session"] = {"id": str(uuid.uuid4()), "mode": payload.mode, "unit_id": plan["unit_id"],
                                        "budget": 25, "tasks": plan["tasks"], "drafts": drafts,
                                        "started_at": now(), "completed_at": None}
                return state["session"]
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
                             for q in ACTIVE_QUESTIONS.values() if q["unit_id"] == uid and q["id"] not in seen]
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

    @app.get("/api/session/preview")
    def preview(mode: Literal["learn", "mistakes", "test"] = "learn", unit_id: str | None = None):
        with store() as state:
            return study_plan(state, mode, unit_id)

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
            draft = question_drafts(state, qid).get(qid)
            attempt = next((a for a in state["attempts"] if draft and a["id"] == draft.get("attempt_id")), None)
            return {"question": public_question(q), "draft": draft, "attempt": attempt,
                    "reference": reference(q) if attempt else None}

    @app.post("/api/draft")
    def save_draft(payload: Draft):
        validate_answer(question(payload.question_id), payload.answer)
        with store() as state:
            drafts = question_drafts(state, payload.question_id)
            current = drafts.get(payload.question_id)
            if current and current.get("attempt_id"):
                raise HTTPException(409, "这次作答已经提交；点击重新作答可创建新记录")
            drafts[payload.question_id] = payload.model_dump(exclude={"question_id"})
        return {"saved": True}

    @app.post("/api/retry/{qid}")
    def retry(qid: str):
        question(qid)
        with store() as state:
            question_drafts(state, qid).pop(qid, None)
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
        if not published(q):
            raise HTTPException(422, "这道题仍待核验，仅供查阅，暂不计分")
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
                       "session_id": state["session"]["id"] if state["session"] and any(t.get("question_id") == q["id"] for t in state["session"]["tasks"]) else None,
                       "submission_key": payload.submission_key, "answer": payload.answer, "uncertain": payload.uncertain,
                       "assisted": assisted, "first_independent": first, "result": result,
                       "assessment_method": "automatic" if q["type"] == "single_choice" else "self-rated",
                       "submitted_at": stamp, "assessed_at": stamp if result != "pending" else None, "ratings": {}}
            state["attempts"].append(attempt)
            question_drafts(state, q["id"])[q["id"]] = {**payload.model_dump(exclude={"question_id"}), "attempt_id": attempt["id"]}
            state["exposures"][q["id"]] = {"first": exposure["first"] if exposure else stamp, "last": stamp}
            if result != "pending":
                advance(state, "question", qid=q["id"], session_id=attempt["session_id"])
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
            advance(state, "question", qid=q["id"], session_id=attempt["session_id"])
            return attempt

    @app.post("/api/resume-assessment/{attempt_id}")
    def resume_assessment(attempt_id: str):
        with store() as state:
            attempt = next((a for a in state["attempts"] if a["id"] == attempt_id), None)
            if not attempt or attempt["result"] != "pending":
                raise HTTPException(404, "没有找到待自评记录")
            active = current_session(state)
            if active and active.get("mode") and active["id"] != attempt.get("session_id"):
                paused = state.setdefault("paused_sessions", {})
                if not active.get("completed_at"):
                    paused[session_key(active["mode"], active.get("unit_id"))] = active
                key = next((key for key, saved in paused.items() if saved["id"] == attempt.get("session_id")), None)
                state["session"] = paused.pop(key) if key else None
            question_drafts(state, attempt["question_id"])[attempt["question_id"]] = {"answer": attempt["answer"], "uncertain": attempt["uncertain"],
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
