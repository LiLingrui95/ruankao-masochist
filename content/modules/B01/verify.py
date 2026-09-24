import json
from pathlib import Path

R=Path(__file__).parent
module=json.loads((R/'module.json').read_text(encoding='utf-8'))
assert module['topic_ids']==[f'B01-T{i:02d}' for i in range(1,11)]
required_md=['## 考查目标','## 必要概念','## 原理与条件','## 推导例题','## 易错点与反例','## 自查','## 关联练习','## 出处']
count=0
choice_count=0
for tid in module['topic_ids']:
    meta=json.loads((R/'topics'/f'{tid}.json').read_text(encoding='utf-8'))
    body=(R/'topics'/f'{tid}.md').read_text(encoding='utf-8')
    assert all(h in body for h in required_md)
    assert len(meta['question_ids'])==meta['exercise_target']
    for qid in meta['question_ids']:
        q=json.loads((R/'exercises'/f'{qid}.json').read_text(encoding='utf-8'))
        assert q['unit_id']==tid and q['answer_status']=='verified' and q['review_status']=='reviewed'
        assert q['verification'] and q['answer'] and q['explanation']
        if q['type']=='single_choice':
            choice_count+=1
            assert set(q['options'])==set('ABCD')
            assert set(q['option_explanations'])==set('ABCD')
            assert q['answer'] in 'ABCD'
            assert all(q['option_explanations'][k].strip() for k in 'ABCD')
        else:
            assert q['type']=='short_answer' and len(q['rubric'])>=2
            assert q['answer'] in q['rubric'][0]['text']
            assert q['explanation'] in q['rubric'][1]['text']
        count+=1
assert count==83 and choice_count==20
# Independent arithmetic checks for error-prone topics.
def signed8(x): return x-256 if x&128 else x
assert signed8((90+50)&255)==-116
assert (32-5-8, 8192//32)==(19,256)
assert (5+20-1)*2==48
empty,full=4,0
for _ in range(3): empty-=1; full+=1
full-=1; empty+=1
assert (empty,full)==(2,2)
work=3
alloc=[3,2,2]; need=[4,2,4]
order=[]
for i in [1,0,2]:
    assert need[i]<=work; work+=alloc[i]; order.append(i+1)
assert order==[2,1,3]
addr=0x2C3A
assert divmod(addr,1024)==(11,58) and 7*1024+58==7226
frames=[]; faults=0
for p in [1,2,3,1,4]:
    if p not in frames:
        faults+=1
        if len(frames)==3: frames.pop(0)
        frames.append(p)
assert faults==4
pos=50; movement=0
for req in [10,40,90,55]: movement+=abs(req-pos); pos=req
assert movement==155
assert 4*3==12 and 2*3//2==3
assert (6-1)*2==10 and (6-2)*2==8 and 4*2//2==4
print(f'B01 verification passed: 10 topics, {count} exercises ({choice_count} single-choice)')
