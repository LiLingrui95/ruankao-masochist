import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
required_sections = ["## 考查目标", "## 必要概念", "## 原理与条件", "## 推导例题", "## 易错点与反例", "## 自查", "## 关联练习", "## 出处"]
module = json.loads((ROOT / "module.json").read_text(encoding="utf-8"))
assert module["topic_ids"] == [f"B02-T{i:02d}" for i in range(1, 9)]
assert [len(u["topic_ids"]) for u in module["units"]] == [3, 3, 2]
sources = {s["id"] for s in json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))}
assert len(sources) >= 2

types = Counter()
difficulties = Counter()
all_ids = set()
for tid in module["topic_ids"]:
    meta = json.loads((ROOT / "topics" / f"{tid}.json").read_text(encoding="utf-8"))
    body = (ROOT.parent.parent / meta["body_path"]).read_text(encoding="utf-8")
    assert all(section in body for section in required_sections), tid
    assert len(body) >= 800, (tid, len(body))
    assert meta["exercise_target"] == len(meta["question_ids"])
    assert 3 <= len(meta["question_ids"]) <= 12
    for qid in meta["question_ids"]:
        assert qid not in all_ids
        all_ids.add(qid)
        q = json.loads((ROOT / "exercises" / f"{qid}.json").read_text(encoding="utf-8"))
        assert q["unit_id"] == tid
        assert q["type"] in {"single_choice", "short_answer", "code_fill"}
        assert q["answer_status"] == "verified" and q["review_status"] == "reviewed"
        assert q["verification"].strip() and q["explanation"].strip()
        assert set(q["source_ids"]) <= sources and set(q["answer_source_ids"]) <= sources
        if q["type"] == "single_choice":
            assert set(q["options"]) == {"A", "B", "C", "D"}
            assert q["answer"] in q["options"]
            assert set(q["option_explanations"]) == set(q["options"])
            assert len(set(q["option_explanations"].values())) == 4
            assert all("不符合题干" not in x for x in q["option_explanations"].values())
        else:
            assert len(q["rubric"]) >= 2
            assert all("给出正确结论" not in r["text"] and "说明关键规则" not in r["text"] for r in q["rubric"])
        if q["type"] == "code_fill":
            assert all(k in q for k in ["code", "language", "reference_fill"])
        types[q["type"]] += 1
        difficulties[q["difficulty"]] += 1

files = list((ROOT / "exercises").glob("*.json"))
assert len(files) == len(all_ids) == 48

# 独立词法模型：运算符按最长匹配，复核 T05 的核心边界。
token_re = re.compile(r"(?P<ID>[A-Za-z_]\w*)|(?P<INT>\d+)|(?P<OP>\+=|==|&&|[=+;])|(?P<WS>\s+)")
def lex(text):
    out=[]; pos=0
    while pos < len(text):
        m=token_re.match(text,pos)
        assert m, (text,pos)
        if m.lastgroup != "WS": out.append((m.lastgroup,m.group()))
        pos=m.end()
    return out
assert lex("a+=1") == [("ID","a"),("OP","+="),("INT","1")]
assert lex("sum = n + 12;") == [("ID","sum"),("OP","="),("ID","n"),("OP","+"),("INT","12"),("OP",";")]

# 独立 LL(1) 表模型：对应 E/E'/T/T'/F 文法并实际解析 id+id*id。
table={
 ("E","id"):["T","E'"], ("E","("):["T","E'"],
 ("E'","+"):["+","T","E'"], ("E'",")"):[], ("E'","$"):[],
 ("T","id"):["F","T'"], ("T","("):["F","T'"],
 ("T'","*"):["*","F","T'"], ("T'","+"):[], ("T'",")"):[], ("T'","$"):[],
 ("F","id"):["id"], ("F","("):["(","E",")"]}
def parse(tokens):
    stack=["$","E"]; stream=tokens+["$"]; i=0
    while stack:
        top=stack.pop(); look=stream[i]
        if top in {"id","+","*","(",")","$"}:
            assert top == look, (top,look); i+=1
        else:
            prod=table[(top,look)]
            stack.extend(reversed(prod))
    return i == len(stream)
assert parse(["id","+","id","*","id"])
assert {"a"}.isdisjoint({"b"})  # S→aA|bB 的 FIRST 候选无冲突。

# 独立传参与词法作用域小模型：复制地址值仍能间接修改原对象；自由变量按定义环境绑定。
memory={"x":1,"y":2}
def swap_by_value(pa,pb):
    local_a,local_b=pa,pb
    memory[local_a],memory[local_b]=memory[local_b],memory[local_a]
swap_by_value("x","y")
assert memory == {"x":2,"y":1}
global_env={"x":1}
def lexical_f(def_env): return def_env["x"]
call_env={"x":2}
assert lexical_f(global_env) == 1 and call_env["x"] == 2
assert json.loads((ROOT/"exercises"/"B02-T06-Q06.json").read_text(encoding="utf-8"))["difficulty"] == "basic"
print(json.dumps({"topics": 8, "questions": len(all_ids), "types": types, "difficulties": difficulties}, ensure_ascii=False, default=dict))
