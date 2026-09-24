import copy
import json
import hashlib

import pytest

import app as study
from content_bank import LIBRARY, TOPICS, PAPERS
from test_study import client, submit


def test_bootstrap_is_summary_not_full_content(client):
    data = client.get('/api/bootstrap').json()
    assert data['counts']['questions'] == len(study.ACTIVE_QUESTIONS)
    assert not data['pack']['questions']
    assert all('html' not in section for sections in data['sections'].values() for section in sections)
    assert 'body' not in json.dumps(data['modules'], ensure_ascii=False)


def test_knowledge_search_and_lesson_are_on_demand(client):
    assert TOPICS, 'Build content before testing'
    topic = next(iter(TOPICS.values()))
    result = client.get('/api/topics', params={'q': topic['title'], 'module': topic['module_id']}).json()
    assert topic['id'] in {t['id'] for t in result['items']}
    assert all('body' not in t for t in result['items'])
    details = client.get('/api/topic/' + topic['id']).json()
    assert '推导例题' in details['html']
    lesson = client.get('/api/lesson/' + topic['id']).json()
    assert details['html'] == lesson['sections'][0]['html']
    assert client.get('/api/topic/not-found').status_code == 404
    assert client.get('/api/topics?page=0').status_code == 422


def test_pagination_combined_filters_and_no_solution_leak(client):
    choice = next(q for q in LIBRARY['questions'] if q['type'] == 'single_choice')
    args = {'module': choice['module_id'], 'topic': choice['topic_ids'][0], 'type': 'single_choice', 'origin': choice['origin_kind'], 'page_size': 1}
    first = client.get('/api/questions', params=args).json()
    assert first['total'] > 0 and len(first['items']) == 1
    if first['total'] > 1:
        second = client.get('/api/questions', params={**args, 'page': 2}).json()
        assert first['items'][0]['id'] != second['items'][0]['id']
    for card in first['items']:
        assert card['module_id'] == choice['module_id']
        assert not {'answer', 'explanation', 'verification', 'reference_fill', 'rubric'} & card.keys()
    detail = client.get('/api/question/' + choice['id']).json()
    assert detail['reference'] is None
    assert not {'answer', 'option_explanations', 'verification', 'answer_source_ids'} & detail['question'].keys()
    outcome = submit(client, choice['id'], {'option': choice['answer']}).json()
    assert outcome['attempt']['result'] == 'correct'
    assert outcome['reference']['explanation']


def test_pending_questions_are_read_only(client, monkeypatch):
    q = copy.deepcopy(next(iter(study.ACTIVE_QUESTIONS.values())))
    q.update(id='TEST-PENDING', review_status='pending', answer_status='disputed')
    monkeypatch.setitem(study.QUESTIONS, q['id'], q)
    visible = client.get('/api/question/' + q['id']).json()
    assert visible['question']['answer_status'] == 'disputed'
    assert visible['reference'] is None
    result = client.post('/api/submit', json={'question_id': q['id'], 'answer': {'option': 'A'}, 'uncertain': False, 'submission_key': 'pending-key'})
    assert result.status_code == 422
    assert not any(a['question_id'] == q['id'] for a in client.get('/api/bootstrap').json()['state']['attempts'])


def test_cases_keep_shared_material_and_hide_reference(client):
    cases = [q for q in LIBRARY['questions'] if q.get('subquestions')]
    for q in cases:
        detail = client.get('/api/question/' + q['id']).json()['question']
        assert detail['case_material'] == q['case_material']
        assert len(detail['subquestions']) == len(q['subquestions'])
        assert 'rubric' not in detail and 'answer' not in detail
        response = submit(client, q['id'], {'text': '独立分析案例与条件'}).json()
        assert response['attempt']['result'] == 'pending'
        ratings = {r['id']: 'full' for r in q['rubric']}
        rated = client.post('/api/assessment/' + response['attempt']['id'], json={'ratings': ratings}).json()
        assert rated['result'] == 'correct' and rated['assessment_method'] == 'self-rated'


def test_paper_filters_order_and_honest_completeness(client):
    assert PAPERS
    result = client.get('/api/papers', params={'year': 2005, 'session': 'H1', 'subject': 'applied'}).json()
    assert result['items']
    paper = result['items'][0]
    assert (paper['year'], paper['session'], paper['subject']) == (2005, 'H1', 'applied')
    details = client.get('/api/paper/' + paper['id']).json()
    assert [q['id'] for q in details['questions']] == paper['question_ids']
    assert details['sources']
    if not details['questions']:
        assert paper['completeness'] != 'complete'
    assert client.get('/api/papers?page_size=101').status_code == 422


def test_v2_and_v3_backup_compatibility_and_tamper_rejection(client):
    attempt = submit(client).json()['attempt']
    v3 = client.get('/api/backup').json()
    assert v3['schema_version'] == 3 and v3['library']['version'] == v3['content_version']
    v2 = {'schema_version': 2, 'exported_at': v3['exported_at'], 'pack': study.BASE_PACK, 'archive': study.ARCHIVE,
          'lessons': {u['id']: study.LESSONS[u['id']] for u in study.BASE_PACK['units'] + study.ARCHIVE['units']}, 'state': copy.deepcopy(v3['state'])}
    assert client.post('/api/backup/check', json=v2).status_code == 200
    assert client.post('/api/backup/restore', json=v2).status_code == 200
    assert client.post('/api/backup/restore', json=v3).status_code == 200
    bad = copy.deepcopy(v3)
    bad['library']['version'] = 'tampered'
    assert client.post('/api/backup/restore', json=bad).status_code == 422
    assert client.get('/api/bootstrap').json()['state']['attempts'] == [attempt]


def test_assets_cannot_expose_content_answers(client):
    assert client.get('/content-assets/pack.json').status_code == 404
    assert client.get('/content-assets/modules/B01/exercises/B01-T01-Q01.json').status_code == 404
    assert client.get('/content-assets/assets/%2e%2e/pack.json').status_code == 404


def test_older_v3_snapshot_after_additive_update(client):
    submit(client)
    backup = client.get('/api/backup').json()
    snapshot = backup['library']
    # Model a backup created before B08 was added. Its old content is unchanged.
    snapshot['modules'] = [m for m in snapshot['modules'] if m['id'] != 'B08']
    snapshot['topics'] = [t for t in snapshot['topics'] if t['module_id'] != 'B08']
    snapshot['questions'] = [q for q in snapshot['questions'] if q['module_id'] != 'B08']
    snapshot['sources'] = [s for s in snapshot['sources'] if not s['id'].startswith('B08-')]
    canonical = {k: v for k, v in snapshot.items() if k not in ('version', 'report')}
    snapshot['version'] = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    backup['content_version'] = snapshot['version']
    backup['pack'] = study.augment(study.BASE_PACK, snapshot)
    lesson_ids = {u['id'] for u in backup['pack']['units'] + study.ARCHIVE['units']} | {p['id'] for p in snapshot['papers']}
    backup['lessons'] = {uid: body for uid, body in backup['lessons'].items() if uid in lesson_ids}
    assert client.post('/api/backup/restore', json=backup).status_code == 200
    baseline = client.get('/api/bootstrap').json()['state']
    for broken in ({**backup, 'lessons': {}}, {**backup, 'state': {'attempts': []}}):
        assert client.post('/api/backup/restore', json=broken).status_code == 422
        assert client.get('/api/bootstrap').json()['state'] == baseline


def test_case_subquestions_cannot_smuggle_solutions(client, monkeypatch):
    q = copy.deepcopy(next(q for q in LIBRARY['questions'] if q.get('subquestions')))
    q['subquestions'][0]['answer'] = 'hidden solution'
    q['subquestions'][0]['explanation'] = 'hidden reasoning'
    monkeypatch.setitem(study.QUESTIONS, q['id'], q)
    detail = client.get('/api/question/' + q['id']).json()['question']
    assert all(set(s) <= {'id', 'prompt', 'points'} for s in detail['subquestions'])
