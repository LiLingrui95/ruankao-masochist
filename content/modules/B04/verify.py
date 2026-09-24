from __future__ import annotations
import json, sqlite3
from pathlib import Path

ROOT=Path(__file__).parent

def closure(attrs, fds):
    out=set(attrs)
    while True:
        old=set(out)
        for left,right in fds:
            if set(left)<=out: out.update(right)
        if out==old:return out

def acyclic(edges):
    nodes={x for e in edges for x in e}
    while nodes:
        ready={n for n in nodes if not any(v==n and u in nodes for u,v in edges)}
        if not ready:return False
        nodes-=ready
    return True

def main():
    topics=list((ROOT/"topics").glob("*.json")); qs=list((ROOT/"exercises").glob("*.json"))
    assert len(topics)==10 and len(qs)==67
    data=[json.loads(p.read_text(encoding="utf-8")) for p in qs]
    assert all(q["rubric"][0]["text"] != "答案正确" for q in data)
    assert sum(bool(q.get("case_material")) for q in data)>=3
    assert closure("A",[("A","B"),("B","C"),("AC","D")])==set("ABCD")
    assert closure("AC",[("A","B"),("C","D")])==set("ABCD")
    # 二元分解 AB/AC 在 A→B 下无损；AB/BC 在仅 AB→C 下不满足判据。
    assert set("AB") <= closure("A",[("A","B")])
    assert not (set("AB")<=closure("B",[("AB","C")]) or set("BC")<=closure("B",[("AB","C")]))
    assert acyclic({("T1","T2"),("T1","T3"),("T2","T3")})
    assert not acyclic({("T1","T2"),("T2","T1")})
    # 实际执行正文使用的可移植 PostgreSQL 18 SQL 子集，核对外连接零计数、HAVING 和 NOT EXISTS。
    db=sqlite3.connect(":memory:")
    db.executescript("CREATE TABLE course(course_id TEXT PRIMARY KEY); CREATE TABLE enrollment(student_id TEXT,course_id TEXT,score INT); CREATE TABLE student(student_id TEXT PRIMARY KEY); INSERT INTO course VALUES('C1'),('C2'),('C3'); INSERT INTO student VALUES('S1'),('S2'),('S3'); INSERT INTO enrollment VALUES('S1','C1',80),('S2','C1',50),('S1','C2',90);")
    rows=db.execute("SELECT c.course_id, COUNT(e.student_id) FROM course c LEFT JOIN enrollment e ON e.course_id=c.course_id AND e.score>=60 GROUP BY c.course_id ORDER BY c.course_id").fetchall()
    assert rows==[("C1",1),("C2",1),("C3",0)]
    assert db.execute("SELECT course_id FROM enrollment GROUP BY course_id HAVING COUNT(DISTINCT student_id)>=2").fetchall()==[("C1",)]
    assert db.execute("SELECT s.student_id FROM student s WHERE NOT EXISTS (SELECT 1 FROM enrollment e WHERE e.student_id=s.student_id)").fetchall()==[("S3",)]
    print(json.dumps({"topics":10,"questions":len(qs),"cases":3,"closure_checks":2,"lossless_checks":2,"schedule_checks":2,"sql_assertions":3},ensure_ascii=False))

if __name__=="__main__":main()
