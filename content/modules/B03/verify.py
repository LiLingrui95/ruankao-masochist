import json
import heapq
from pathlib import Path

ROOT=Path(__file__).parent
topics=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT/'topics').glob('*.json'))]
questions=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT/'exercises').glob('*.json'))]
assert len(topics)==12 and len(questions)==84
assert sum(bool(q.get('subquestions')) for q in questions)>=3
assert all(q['version']=='1.0.0' and q['unit_id']==q['topic_ids'][0] for q in questions)
assert all(len(t['question_ids'])==t['exercise_target'] for t in topics)
assert sum(range(1,10))==45
assert (1-3+5)%5==3
a=[3,8,12,17,21,30]; lo,hi=0,len(a)-1
while lo<=hi:
    mid=(lo+hi)//2
    if a[mid]<17: lo=mid+1
    elif a[mid]>17: hi=mid-1
    else: break
assert a[mid]==17
edges=sorted([(1,'A','B'),(4,'A','C'),(2,'B','C'),(5,'B','D'),(1,'C','D')]); parent={x:x for x in 'ABCD'}
def find(x):
    while parent[x]!=x: x=parent[x]
    return x
total=0
for w,u,v in edges:
    a1,b1=find(u),find(v)
    if a1!=b1: parent[a1]=b1; total+=w
assert total==4
dp=[0]*6
for w,v in [(2,3),(3,4),(4,5)]:
    for c in range(5,w-1,-1): dp[c]=max(dp[c],dp[c-w]+v)
assert dp[5]==7
subs=[]
for mask in range(8):
    s=[i+1 for i in range(3) if mask>>i&1]
    if sum(s)==3: subs.append(s)
assert subs==[[1,2],[3]]
# Rebuild the tree from preorder/inorder, then replay both traversals.
def build(pre, ino):
    if not pre: return None
    root=pre[0]; k=ino.index(root)
    return (root,build(pre[1:1+k],ino[:k]),build(pre[1+k:],ino[k+1:]))
tree=build('ABDCE','DBAEC')
def preorder(t): return '' if t is None else t[0]+preorder(t[1])+preorder(t[2])
def inorder(t): return '' if t is None else inorder(t[1])+t[0]+inorder(t[2])
def postorder(t): return '' if t is None else postorder(t[1])+postorder(t[2])+t[0]
assert tree[1][1][0]=='D' and tree[1][2] is None
assert preorder(tree)=='ABDCE' and inorder(tree)=='DBAEC' and postorder(tree)=='DBECA'
# Huffman WPL by independent min-heap merging.
h=[5,7,10,15]; heapq.heapify(h); wpl=0
while len(h)>1:
    s=heapq.heappop(h)+heapq.heappop(h); wpl+=s; heapq.heappush(h,s)
assert wpl==71
# Six revised cases: independent expected answers.
edges2=[(2,'A','B'),(6,'A','C'),(3,'B','C'),(5,'B','D'),(1,'C','D'),(4,'C','E'),(2,'D','E')]
par={x:x for x in 'ABCDE'}
def f2(x):
    if par[x]!=x: par[x]=f2(par[x])
    return par[x]
mst=0
for w,u,v in sorted(edges2):
    a2,b2=f2(u),f2(v)
    if a2!=b2: par[a2]=b2; mst+=w
assert mst==8
records=[(2,'A'),(1,'B'),(2,'C'),(1,'D'),(3,'E')]
assert sorted(records,key=lambda x:x[0])==[(1,'B'),(1,'D'),(2,'A'),(2,'C'),(3,'E')]
tasks=[7,2,5,10,8]
def feasible(cap):
    servers=1; used=0
    for x in tasks:
        if used+x>cap: servers+=1; used=0
        used+=x
    return servers<=2
assert not feasible(17) and feasible(18)
acts=[(1,4,'A'),(3,5,'B'),(0,6,'C'),(5,7,'D'),(3,9,'E'),(5,9,'F'),(6,10,'G'),(8,11,'H'),(8,12,'I'),(2,14,'J'),(12,16,'K')]
chosen=[]; end=-1
for s,e,n in sorted(acts,key=lambda x:x[1]):
    if s>=end: chosen.append(n); end=e
assert chosen==['A','D','H','K']
dp2=[0]*8
rows=[]
for w,v in [(1,1),(3,4),(4,5),(5,7)]:
    for c in range(7,w-1,-1): dp2[c]=max(dp2[c],dp2[c-w]+v)
    rows.append(''.join(map(str,dp2)))
assert rows==['01111111','01145555','01145669','01145789']
vals=[1,1,2,3,4]; combos=set()
for mask in range(1<<len(vals)):
    choice=tuple(vals[i] for i in range(len(vals)) if mask>>i&1)
    if sum(choice)==5 and not (2 in choice and 3 in choice): combos.add(choice)
assert combos=={(1,4),(1,1,3)}
for q in questions:
    if q.get('subquestions'):
        assert '答案' not in q['case_material'] and 'dp[5]=7' not in q['case_material']
        assert len(q['rubric'])==len(q['subquestions'])==3
for q in questions:
    assert q['answer'] and q['explanation'] and q['verification']
    if q['type']=='single_choice':
        assert set(q['options'])==set('ABCD') and q['answer'] in q['options']
    else: assert len(q['rubric'])>=2
print(json.dumps({'module':'B03','topics':len(topics),'questions':len(questions),'cases':sum(bool(q.get('subquestions')) for q in questions),'numeric_checks':'passed','tree_rebuild':'passed','huffman':'passed','six_case_models':'passed'},ensure_ascii=False))
