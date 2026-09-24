import itertools
import sqlite3

import pytest

import app as study
from test_study import client, submit


def test_exam_units_and_tasks_do_not_depend_on_legacy_prerequisites(client):
    data = client.get('/api/bootstrap').json()
    assert all(data['summary']['eligible'][u['id']] for u in study.BASE_PACK['units'])
    assert data['counts']['questions'] == len(study.ACTIVE_QUESTIONS)
    assert len(study.ARCHIVE['questions']) == 18
    assert data['pack']['questions'] == []  # No full question bank in bootstrap.
    assert not any('answer' in q for q in data['archive']['questions'])
    session = client.post('/api/session', json={'budget': 25}).json()
    learned = set()
    for task in session['tasks']:
        if task['kind'] == 'lesson':
            learned.add((task['unit_id'], task['section']))
        else:
            q = study.QUESTIONS[task['question_id']]
            assert (q['unit_id'], q['section_index']) in learned


def test_legacy_backup_and_history_survive_curriculum_change(client):
    attempt = submit(client, 'CSF-01-Q01', {'option': 'C'}).json()['attempt']
    client.post('/api/note/CSF-01', json={'text': '旧笔记需要保留'})
    state = client.get('/api/backup').json()['state']
    state['session'] = {'id':'old-session', 'tasks':[{'kind':'lesson','unit_id':'CSF-01','section':1,'minutes':5,'done':False}],
                        'budget':10, 'started_at':study.now(), 'completed_at':None}
    old_backup = {'schema_version':1, 'pack':study.ARCHIVE,
                  'lessons':{u['id']:study.LESSONS[u['id']] for u in study.ARCHIVE['units']}, 'state':state}
    assert client.post('/api/backup/restore', json=old_backup).status_code == 200
    restored = client.get('/api/bootstrap').json()
    assert restored['state']['session'] is None
    assert restored['state']['attempts'] == [attempt]
    assert restored['state']['notes']['CSF-01'] == '旧笔记需要保留'
    assert restored['summary']['answered'] == restored['summary']['first_total'] == 0
    assert client.get('/api/question/CSF-01-Q01').json()['attempt'] == attempt
    new_session = client.post('/api/session',json={'budget':10}).json()
    assert new_session['tasks'][0]['unit_id'] == 'SE-01'
    backup = client.get('/api/backup').json()
    assert backup['archive'] == study.ARCHIVE and backup['state']['attempts'] == [attempt]
    assert client.post('/api/backup/check', json=backup).status_code == 200


def test_system_calculation_answers():
    q = study.ACTIVE_QUESTIONS
    assert int('11101000',2) == 232 and int('11101000',2)-256 == -24
    assert 70+80 > 127 and ((70+80)&255)-256 == -106
    assert 5+(1-0.9)*80 == pytest.approx(13)
    assert (128//32)*(32//8) == 16
    assert sum([3,2,4])+(12-1)*4 == 53
    assert (8192//32).bit_length()-1 == 8
    assert 32-5-8 == 19
    assert 120*0.25+120*0.75/3 == 60 and 1/0.25 == 4
    assert [q[f'SE-01-Q{i:02}']['answer'] for i in range(1,7)] == list('ACBDCB')


def test_stack_and_tree_answers():
    def legal(sequence):
        stack=[]; next_value=1
        for wanted in sequence:
            while next_value<=4 and (not stack or stack[-1]!=wanted):
                stack.append(next_value); next_value+=1
            if not stack or stack.pop()!=wanted:return False
        return True
    assert [legal(a) for a in [(2,1,4,3),(3,2,1,4),(4,3,2,1),(3,1,2,4)]] == [True,True,True,False]
    def post(pre,ino):
        if not pre:return ''
        middle=ino.index(pre[0])
        return post(pre[1:middle+1],ino[:middle])+post(pre[middle+1:],ino[middle+1:])+pre[0]
    assert post('ABDCEF','DBAECF') == 'DBEFCA'


def test_algorithm_reference_logic_and_boundaries():
    # Independent Python models validate the reference reasoning, not C compilation.
    def search(a,target):
        low,high=0,len(a)-1; trace=[]
        while low<=high:
            mid=low+(high-low)//2; trace.append(mid)
            if a[mid]==target:return mid,trace
            if a[mid]<target:low=mid+1
            else:high=mid-1
        return -1,trace
    assert search([2,7,12,18,25],18)==(3,[2,3])
    for n in range(16):
        a=list(range(0,n*2,2))
        for target in range(-1,n*2+1):
            assert search(a,target)[0] == (a.index(target) if target in a else -1)
    assert sum(len(search(list(range(7)),target)[1]) for target in range(7)) == 17
    def best_sum(a):
        ending=best=a[0]
        for value in a[1:]:
            joined=ending+value
            ending=joined if joined>value else value
            best=max(best,ending)
        return best
    for length in range(1,6):
        for a in itertools.product([-2,0,3],repeat=length):
            assert best_sum(a)==max(sum(a[i:j]) for i in range(length) for j in range(i+1,length+1))
    assert best_sum([-4,5,-1,4,-7])==8
    assert best_sum([-6,-3,-8])==-3
    assert study.QUESTIONS['SE-02-Q08']['reference_fill'] == 'joined > a[i]'


def test_database_closure_and_lossy_decomposition():
    closure={'A'}
    rules=[({'A'},{'B'}),({'B'},{'C'}),({'A','C'},{'D'})]
    while True:
        before=closure.copy()
        for left,right in rules:
            if left<=closure:closure|=right
        if before==closure:break
    assert closure==set('ABCD')
    rows={(1,'x','p'),(2,'x','q')}
    left={(a,b) for a,b,c in rows};right={(b,c) for a,b,c in rows}
    joined={(a,b,c) for a,b in left for b2,c in right if b==b2}
    assert joined-rows == {(1,'x','q'),(2,'x','p')}


def test_sql_fill_and_lesson_queries():
    con=sqlite3.connect(':memory:')
    con.executescript('''CREATE TABLE Student(student_id INTEGER PRIMARY KEY,student_name TEXT);
    CREATE TABLE Course(course_id TEXT PRIMARY KEY,course_name TEXT);
    CREATE TABLE Enrollment(student_id INTEGER NOT NULL,course_id TEXT NOT NULL,score INTEGER,PRIMARY KEY(student_id,course_id));
    INSERT INTO Student VALUES(1,'Lin'),(2,'Zhou'),(3,'Wu'),(4,'Qin');
    INSERT INTO Course VALUES('A','Algorithms'),('B','Database'),('C','Networks');
    INSERT INTO Enrollment VALUES(1,'A',80),(2,'A',70),(1,'B',90),(3,'C',60);''')
    q=study.QUESTIONS['SE-03-Q08']
    assert con.execute(q['code'].replace('____',q['reference_fill'])).fetchall()==[('A',2)]
    import re
    sql=re.findall(r'```sql\n(.*?)\n```',study.LESSONS['SE-03'],re.S)
    assert set(con.execute(sql[0]).fetchall()) == {('Lin','Algorithms',80),('Lin','Database',90)}
    assert con.execute(sql[1]).fetchall() == [('A',2)]
    assert con.execute('SELECT COUNT(e.course_id),COUNT(*) FROM Student s LEFT JOIN Enrollment e ON e.student_id=s.student_id WHERE s.student_id=4').fetchone() == (0,1)
