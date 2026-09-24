"""Read the validated library and adapt topics to the existing study workflow."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
LIBRARY = json.loads((CONTENT / "generated/library.json").read_text(encoding="utf-8"))
TOPICS = {t["id"]: t for t in LIBRARY["topics"]}
PAPERS = {p["id"]: p for p in LIBRARY["papers"]}


def published(q):
    return q.get("review_status") == "reviewed" and q.get("answer_status", "verified") == "verified"


def augment(pack, library=LIBRARY):
    pack = copy.deepcopy(pack)
    pack["version"] = "3.0.0+" + library["version"]
    pack["title"] = "软件设计师 · 结构化知识库"
    pack["scope"] = "按考点学习；原创、转载、真题与回忆题分别标识。缺口见覆盖报告。"
    pack["sources"] += library["sources"]
    for topic in library["topics"]:
        if topic["review_status"] != "reviewed":
            continue
        pack["units"].append({"id": topic["id"], "title": topic["title"], "subtitle": "；".join(topic["objectives"]),
                              "tag": topic["module_id"], "module_id": topic["module_id"], "objectives": topic["objectives"],
                              "section_minutes": [topic["minutes"]], "source_ids": topic["source_ids"],
                              "version": topic["version"], "prerequisite_ids": topic["prerequisite_ids"],
                              "checkpoint_question_ids": topic["question_ids"][:3], "lesson_path": topic["body_path"],
                              "review_status": topic["review_status"], "availability": "active"})
    pack["questions"] += [q for q in library["questions"] if published(q)]
    pack["roadmap"] = []
    return pack


def question_card(q):
    fields = ("id", "title", "unit_id", "module_id", "topic_ids", "type", "difficulty", "minutes", "section_index",
              "origin_kind", "review_status", "answer_status", "paper_id", "original_number", "language")
    return {key: q[key] for key in fields if key in q}


def topic_card(t):
    return {key: value for key, value in t.items() if key != "body"}


def paginate(items, page, page_size):
    return {"items": items[(page - 1) * page_size:page * page_size], "total": len(items), "page": page, "page_size": page_size}


def compatible_snapshot(snapshot, current):
    """Accept an older, unmodified subset after additive content updates."""
    if not isinstance(snapshot, dict):
        return False
    original = {k: v for k, v in snapshot.items() if k not in ("version", "report")}
    digest = hashlib.sha256(json.dumps(original, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    if digest != snapshot.get("version"):
        return False
    for field in ("modules", "topics", "questions", "papers", "sources"):
        known = {row["id"]: row for row in current[field]}
        records = snapshot.get(field, [])
        if not isinstance(records, list) or any(not isinstance(row, dict) or row != known.get(row.get("id")) for row in records):
            return False
        if len({row["id"] for row in records}) != len(records):
            return False
    return True
