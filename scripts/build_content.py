"""Validate canonical content, then atomically publish deterministic indexes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from content_models import Module, Paper, Question, Source, Topic

CONTENT = ROOT / "content"
HEADINGS = ["考查目标", "必要概念", "原理与条件", "推导例题", "易错点与反例", "自查", "关联练习", "出处"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def build(check=False, partial=False):
    errors, gaps = [], []
    bank = {"schema_version": 1, "modules": [], "topics": [], "questions": [], "papers": [], "sources": []}
    curriculum = read(CONTENT / "curriculum.json")
    bank["curriculum"] = curriculum
    bank["syllabus_map"] = read(CONTENT / "syllabus-map.json")
    legacy = read(CONTENT / "pack.json")
    legacy_ids = {q["id"] for q in legacy["questions"]}

    def load(path, model, bucket):
        try:
            raw = read(path)
            if model in (Question, Topic):
                if not isinstance(raw, dict) or path.stem != raw.get("id"):
                    raise ValueError("one record per file; filename must match stable ID")
            for value in raw if isinstance(raw, list) else [raw]:
                model.model_validate(value)
                bank[bucket].append(value)
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")

    for entry in curriculum["modules"]:
        directory = CONTENT / "modules" / entry["id"]
        if not (directory / "module.json").exists():
            (gaps if partial else errors).append(f"{entry['id']}: missing module")
            continue
        load(directory / "module.json", Module, "modules")
        load(directory / "sources.json", Source, "sources")
        for path in sorted((directory / "topics").glob("*.json")):
            load(path, Topic, "topics")
        for path in sorted((directory / "exercises").glob("*.json")):
            load(path, Question, "questions")
    for path in sorted((CONTENT / "exams").glob("**/paper.json")):
        load(path, Paper, "papers")
        load(path.parent / "sources.json", Source, "sources")
        for question in sorted((path.parent / "questions").glob("*.json")):
            load(question, Question, "questions")
    exam_coverage = CONTENT / "exams/coverage.json"
    bank["exam_coverage"] = read(exam_coverage) if exam_coverage.exists() else {"entries": [], "summary": "尚未完成检索"}
    if curriculum["syllabus"]["status"] == "publisher_verified_full_outline_pending":
        gaps.append("Official full syllabus text pending; chapter mapping uses a disclosed secondary transcription.")
    if not any(p["question_ids"] for p in bank["papers"]):
        gaps.append("Exam catalog has source records only; no past-exam question text or verified answers collected.")
    mappings = {}
    for bucket in ("modules", "topics", "questions", "papers", "sources"):
        mappings[bucket] = {}
        for record in bank[bucket]:
            if record["id"] in mappings[bucket]:
                errors.append(f"duplicate {bucket} ID: {record['id']}")
            mappings[bucket][record["id"]] = record
    topics, questions, sources = (mappings[k] for k in ("topics", "questions", "sources"))
    source_ids = set(sources) | {s["id"] for s in legacy["sources"]}
    for entry in bank["syllabus_map"]["entries"]:
        missing = set(entry["topic_ids"]) - set(topics)
        if missing:
            (gaps if partial else errors).append(f"{entry['id']}: missing mapped topics {sorted(missing)}")

    def references(record, field, allowed):
        missing = set(record.get(field, [])) - set(allowed)
        if missing:
            errors.append(f"{record['id']} {field}: unresolved {sorted(missing)}")

    def local_file(relative):
        path = (CONTENT / relative).resolve()
        if not path.is_relative_to(CONTENT.resolve()) or not path.is_file():
            raise ValueError(f"missing/unsafe asset: {relative}")
        return path

    for module in bank["modules"]:
        references(module, "topic_ids", topics)
        actual = [t["id"] for t in bank["topics"] if t["module_id"] == module["id"]]
        expected = [t["id"] for m in curriculum["modules"] if m["id"] == module["id"] for t in m["topics"]]
        if set(actual) != set(expected) or set(actual) != set(module["topic_ids"]):
            errors.append(f"{module['id']}: registry/topic mismatch")
        members = [tid for u in module["units"] for tid in u["topic_ids"]]
        if sorted(members) != sorted(actual):
            errors.append(f"{module['id']}: teaching units must cover each topic once")
    for topic in bank["topics"]:
        if len(set(topic["question_ids"])) != len(topic["question_ids"]):
            errors.append(f"{topic['id']}: duplicate question reference")
        module = mappings["modules"].get(topic["module_id"], {})
        if not any(u["id"] == topic["unit_id"] and topic["id"] in u["topic_ids"] for u in module.get("units", [])):
            errors.append(f"{topic['id']}: invalid teaching unit")
        for field, allowed in [("prerequisite_ids", topics), ("source_ids", source_ids), ("question_ids", set(questions) | legacy_ids)]:
            references(topic, field, allowed)
        try:
            body = local_file(topic["body_path"]).read_text(encoding="utf-8-sig")
            topic["body"] = body
            if any("## " + heading not in body for heading in HEADINGS):
                errors.append(f"{topic['id']}: missing required lesson heading")
        except Exception as exc:
            errors.append(str(exc))
        valid = [qid for qid in topic["question_ids"] if qid in legacy_ids or (qid in questions and questions[qid]["review_status"] == "reviewed" and questions[qid]["answer_status"] == "verified" and topic["id"] in questions[qid]["topic_ids"])]
        if len(set(valid)) < topic["exercise_target"]:
            errors.append(f"{topic['id']}: {len(set(valid))}/{topic['exercise_target']} verified exercises")
    for q in bank["questions"]:
        for field, allowed in [("source_ids", source_ids), ("answer_source_ids", source_ids), ("topic_ids", topics)]:
            references(q, field, allowed)
        if q["id"] in legacy_ids:
            errors.append(f"{q['id']}: overwrites legacy question")
        if q["origin_kind"] not in ("past_exam", "recalled"):
            if not q["topic_ids"] or q["unit_id"] not in q["topic_ids"]:
                errors.append(f"{q['id']}: exercise needs its primary topic as runtime unit")
            if any(topics[tid]["module_id"] != q["module_id"] for tid in q["topic_ids"] if tid in topics):
                errors.append(f"{q['id']}: cross-module topic belongs in a reference, not duplicated ownership")
        if q["answer_status"] == "verified":
            if not all(q.get(k) for k in ("answer", "explanation", "verification", "source_ids", "answer_source_ids")):
                errors.append(f"{q['id']}: verified answer lacks evidence")
            if q["type"] == "single_choice":
                if q["answer"] not in q.get("options", {}) or set(q.get("option_explanations", {})) != set(q.get("options", {})):
                    errors.append(f"{q['id']}: invalid options/answer/explanations")
            elif len(q.get("rubric") or []) < 2 or len({r["id"] for r in q["rubric"]}) != len(q["rubric"]):
                errors.append(f"{q['id']}: invalid rubric")
            if q["type"] == "code_fill" and not all(q.get(k) for k in ("code", "language", "reference_fill")):
                errors.append(f"{q['id']}: incomplete code exercise")
        for asset in q.get("assets", []):
            try:
                local_file(asset["path"])
            except Exception as exc:
                errors.append(str(exc))
        if q.get("subquestions") and not q.get("case_material"):
            errors.append(f"{q['id']}: case lacks shared material")
    for paper in bank["papers"]:
        references(paper, "question_ids", questions)
        references(paper, "source_ids", source_ids)
        if paper["completeness"] == "complete" and not paper["question_ids"]:
            errors.append(f"{paper['id']}: empty complete paper")
        if len(set(paper["question_ids"])) != len(paper["question_ids"]):
            errors.append(f"{paper['id']}: duplicated original position")
    case_groups = {"dfd": ["B05-T11"], "database": ["B04-T10"], "algorithm": [f"B03-T{i:02d}" for i in range(7, 13)], "uml": ["B06-T10"], "cpp_patterns": ["B06-T11"]}
    case_counts = {name: sum(bool(q.get("subquestions")) and bool(set(q["topic_ids"]) & set(ids)) for q in questions.values()) for name, ids in case_groups.items()}
    for name, count in case_counts.items():
        if count < 3:
            (gaps if partial else errors).append(f"{name}: {count}/3 complete cases")
    visiting, visited = set(), set()

    def visit(tid):
        if tid in visiting:
            errors.append(f"prerequisite cycle at {tid}")
            return
        if tid in visited or tid not in topics:
            return
        visiting.add(tid)
        for parent in topics[tid]["prerequisite_ids"]:
            visit(parent)
        visiting.remove(tid)
        visited.add(tid)
    for tid in topics:
        visit(tid)
    report = {"modules": len(bank["modules"]), "topics": len(topics), "questions": len(questions),
              "cases": sum(bool(q.get("subquestions")) for q in questions.values()),
              "case_groups": case_counts,
              "papers": len(bank["papers"]), "exam_questions": sum(len(p["question_ids"]) for p in bank["papers"]),
              "complete_papers": sum(p["completeness"] == "complete" for p in bank["papers"]),
              "syllabus_status": curriculum["syllabus"]["status"], "gaps": gaps, "errors": errors,
              "syllabus_entries": len(bank["syllabus_map"]["entries"]),
              "syllabus_coverage": [{**e, "available_topics": sum(tid in topics for tid in e["topic_ids"])} for e in bank["syllabus_map"]["entries"]],
              "by_module": [{"id": m["id"], "topics": sum(t["module_id"] == m["id"] for t in topics.values()), "questions": sum(q["module_id"] == m["id"] for q in questions.values())} for m in bank["modules"]]}
    if errors:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    bank["version"] = hashlib.sha256(json.dumps(bank, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    bank["report"] = report
    if not check:
        for name, model in [("module", Module), ("topic", Topic), ("question", Question), ("paper", Paper), ("source", Source)]:
            write(CONTENT / "schemas" / f"{name}.schema.json", model.model_json_schema())
        write(CONTENT / "generated/library.json", bank)
        write(CONTENT / "generated/coverage.json", report)
        write(CONTENT / "generated/search.json", [{"id": t["id"], "title": t["title"], "module_id": t["module_id"], "text": " ".join([t["title"], *t["aliases"], t["body"]])} for t in bank["topics"]])
    print(json.dumps({k: v for k, v in report.items() if k != "syllabus_coverage"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--partial", action="store_true", help="allow modules not started yet")
    options = parser.parse_args()
    raise SystemExit(build(options.check, options.partial))
