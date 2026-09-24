import copy

import app as study
from test_study import client, submit


def preview(client, mode, uid=None):
    params = {"mode": mode}
    if uid:
        params["unit_id"] = uid
    response = client.get('/api/session/preview', params=params)
    assert response.status_code == 200, response.text
    return response.json()


def begin(client, mode, uid=None):
    response = client.post('/api/session', json={"mode": mode, "unit_id": uid})
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_is_read_only_and_matches_started_tasks(client):
    before = client.get('/api/backup').json()['state']
    plan = preview(client, 'learn')
    assert sum(t['kind'] == 'lesson' for t in plan['tasks']) == 1
    assert all(t.get('question_id', '').startswith('SE-01') for t in plan['tasks'] if t['kind'] == 'question')
    assert plan['minutes'] == sum(t['minutes'] for t in plan['tasks'])
    assert all(t['title'] for t in plan['tasks'])
    assert preview(client, 'mistakes')['tasks'] == []
    assert preview(client, 'test')['test_units'] == []
    assert client.get('/api/backup').json()['state'] == before
    assert begin(client, 'learn')['tasks'] == plan['tasks']


def test_empty_modes_do_not_replace_active_task(client):
    session = begin(client, 'learn')
    for mode in ('mistakes', 'test'):
        assert client.post('/api/session', json={'mode': mode}).status_code == 422
    assert client.get('/api/bootstrap').json()['state']['session']['id'] == session['id']
    assert client.get('/api/session/preview?mode=test&unit_id=SE-03').status_code == 422


def test_switch_modes_preserves_progress_and_scopes_drafts(client):
    learn = begin(client, 'learn')
    client.post('/api/read', json={'unit_id': 'SE-01', 'section': 0})
    payload = {'question_id': 'SE-01-Q01', 'answer': {'option': 'B'}, 'uncertain': True, 'submission_key': 'learning-draft'}
    client.post('/api/draft', json=payload)
    test = begin(client, 'test', 'SE-01')
    assert test['id'] != learn['id']
    assert client.get('/api/question/SE-01-Q01').json()['draft'] is None
    submit(client, 'SE-01-Q01', {'option': 'A'})
    assert preview(client, 'learn')['resuming']
    resumed = begin(client, 'learn')
    assert resumed['id'] == learn['id'] and resumed['tasks'][0]['done']
    draft = client.get('/api/question/SE-01-Q01').json()['draft']
    assert draft['answer'] == payload['answer'] and draft['submission_key'] == payload['submission_key']
    assert begin(client, 'test', 'SE-01')['id'] == test['id']
    assert client.get('/api/question/SE-01-Q01').json()['attempt']['result'] == 'correct'


def test_mistakes_use_latest_answer_and_begin_fresh(client):
    old = submit(client, 'SE-01-Q01', {'option': 'B'}).json()['attempt']
    submit(client, 'SE-01-Q02', {'option': 'A'})
    submit(client, 'SE-01-Q02', {'option': 'C'})
    plan = preview(client, 'mistakes')
    assert plan['mistake_count'] == 1
    assert [t['question_id'] for t in plan['tasks']] == ['SE-01-Q01']
    session = begin(client, 'mistakes')
    assert client.get('/api/question/SE-01-Q01').json()['attempt'] is None
    new = submit(client, 'SE-01-Q01', {'option': 'A'}).json()['attempt']
    state = client.get('/api/bootstrap').json()['state']
    assert old in state['attempts'] and new in state['attempts']
    assert new['session_id'] == session['id'] and state['session']['completed_at']
    assert preview(client, 'mistakes')['mistake_count'] == 0


def test_test_coverage_completion_and_independent_unit_sessions(client):
    for uid in ('SE-01', 'SE-02'):
        client.post('/api/read', json={'unit_id': uid, 'section': 0})
    plan = preview(client, 'test', 'SE-01')
    questions = [study.QUESTIONS[t['question_id']] for t in plan['tasks']]
    assert len(questions) == 5 and len({q['section_index'] for q in questions}) == 4
    assert {'single_choice', 'short_answer'} <= {q['type'] for q in questions}
    session = begin(client, 'test', 'SE-01')
    other = begin(client, 'test', 'SE-02')
    assert other['id'] != session['id']
    assert begin(client, 'test', 'SE-01')['id'] == session['id']
    for q in questions:
        answer = {'option': q['answer']} if q['type'] == 'single_choice' else {'text': '自测作答'}
        attempt = submit(client, q['id'], answer).json()['attempt']
        if attempt['result'] == 'pending':
            client.post('/api/assessment/' + attempt['id'], json={'ratings': {r['id']: 'full' for r in q['rubric']}})
    state = client.get('/api/bootstrap').json()['state']
    assert state['session']['completed_at']
    assert all(t['done'] for t in state['session']['tasks'])
    assert len([a for a in state['attempts'] if a['session_id'] == session['id']]) == 5


def test_mode_backup_restore_and_nested_draft_validation(client):
    begin(client, 'learn')
    client.post('/api/read', json={'unit_id': 'SE-01', 'section': 0})
    client.post('/api/draft', json={'question_id': 'SE-01-Q01', 'answer': {'option': 'B'}, 'uncertain': False, 'submission_key': 'preserved'})
    begin(client, 'test', 'SE-01')
    backup = client.get('/api/backup').json()
    assert client.post('/api/backup/check', json=backup).status_code == 200
    assert client.post('/api/backup/restore', json=backup).status_code == 200
    begin(client, 'learn')
    assert client.get('/api/question/SE-01-Q01').json()['draft']['submission_key'] == 'preserved'
    bad = copy.deepcopy(backup)
    bad['state']['paused_sessions']['learn']['drafts']['SE-01-Q01']['answer']['option'] = 'INVALID'
    assert client.post('/api/backup/check', json=bad).status_code == 422


def test_legacy_session_can_pause_and_resume_unchanged(client):
    old = client.post('/api/session', json={'budget': 25}).json()
    submit(client, 'SE-01-Q01', {'option': 'B'})
    begin(client, 'mistakes')
    resumed = begin(client, 'learn')
    assert resumed['id'] == old['id']
    assert client.get('/api/question/SE-01-Q01').json()['attempt']['result'] == 'incorrect'


def test_pending_assessment_does_not_finish_another_sessions_question(client):
    client.post('/api/read', json={'unit_id': 'SE-01', 'section': 3})
    original = begin(client, 'test', 'SE-01')
    attempt = submit(client, 'SE-01-Q07', {'text': '待自评'}).json()['attempt']
    submit(client, 'SE-01-Q01', {'option': 'B'})
    begin(client, 'mistakes')
    response = client.post('/api/assessment/' + attempt['id'], json={'ratings': {'R1': 'full', 'R2': 'full', 'R3': 'full'}})
    assert response.status_code == 200
    resumed = begin(client, 'test', 'SE-01')
    assert resumed['id'] == original['id']
    assert next(t for t in resumed['tasks'] if t.get('question_id') == 'SE-01-Q07')['done']
