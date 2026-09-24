"""Reject damaged authoring input before publishing generated indexes."""
import json
import shutil
from pathlib import Path

import pytest

from scripts import build_content as builder


@pytest.fixture
def content_copy(tmp_path, monkeypatch):
    destination = tmp_path / 'content'
    shutil.copytree(builder.CONTENT, destination, ignore=shutil.ignore_patterns('generated', '__pycache__'))
    monkeypatch.setattr(builder, 'CONTENT', destination)
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    return destination


def edit_json(path, change):
    value = json.loads(path.read_text(encoding='utf-8'))
    change(value)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def test_rejects_cycle_and_dangling_source(content_copy, capsys):
    path = content_copy / 'modules/B01/topics/B01-T01.json'
    edit_json(path, lambda value: value.update(prerequisite_ids=['B01-T01'], source_ids=['MISSING-SOURCE']))
    assert builder.build(check=True) == 1
    report = capsys.readouterr().out
    assert 'prerequisite cycle' in report and 'MISSING-SOURCE' in report
    assert not (content_copy / 'generated/library.json').exists()


def test_rejects_answerless_published_question_and_empty_full_paper(content_copy, capsys):
    edit_json(content_copy / 'modules/B01/exercises/B01-T01-Q01.json', lambda value: value.update(answer=''))
    paper = next((content_copy / 'exams').glob('**/paper.json'))
    edit_json(paper, lambda value: value.update(completeness='complete', question_ids=[]))
    assert builder.build(check=True) == 1
    report = capsys.readouterr().out
    assert 'verified answer lacks evidence' in report and 'empty complete paper' in report


def test_rejects_grouped_question_files(content_copy, capsys):
    path = content_copy / 'modules/B01/exercises/B01-T01-Q01.json'
    question = json.loads(path.read_text(encoding='utf-8'))
    path.write_text(json.dumps([question]), encoding='utf-8')
    assert builder.build(check=True) == 1
    assert 'one record per file' in capsys.readouterr().out
