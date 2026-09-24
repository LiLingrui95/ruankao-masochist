"""Authoring contracts. Exported JSON Schema and validation share these models."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="allow")


class Source(Record):
    id: str
    title: str
    url: str
    author: str
    accessed_on: str
    locator: str
    version: str
    kind: str
    reuse_policy: str
    query: str
    selection_reason: str


class Topic(Record):
    id: str
    module_id: str
    unit_id: str
    title: str
    aliases: list[str]
    objectives: list[str] = Field(min_length=1)
    prerequisite_ids: list[str]
    syllabus_refs: list[str] = Field(min_length=1)
    body_path: str
    source_ids: list[str] = Field(min_length=1)
    version: str
    review_status: Literal["reviewed", "pending"]
    minutes: int = Field(ge=1, le=45)
    exercise_target: int = Field(ge=1)
    exercise_rationale: str
    question_ids: list[str]


class TeachingUnit(Record):
    id: str
    title: str
    topic_ids: list[str]


class Module(Record):
    id: str
    title: str
    description: str
    objectives: list[str]
    units: list[TeachingUnit]
    topic_ids: list[str]
    search_rules: list[str]


class Rubric(Record):
    id: str
    text: str


class Subquestion(Record):
    id: str
    prompt: str
    points: float | None = None


class Asset(Record):
    path: str
    alt: str


class Question(Record):
    id: str
    title: str
    module_id: str
    topic_ids: list[str]
    unit_id: str
    section_index: int = 0
    type: Literal["single_choice", "short_answer", "code_fill"]
    prompt: str
    answer: str = ""
    explanation: str = ""
    source_ids: list[str]
    answer_source_ids: list[str]
    origin_kind: Literal["original", "adapted", "licensed", "past_exam", "recalled"]
    review_status: Literal["reviewed", "pending"]
    answer_status: Literal["verified", "pending", "disputed"]
    verification: str
    version: str
    difficulty: Literal["basic", "applied", "comprehensive"]
    minutes: int = Field(ge=1, le=120)
    options: dict[str, str] | None = None
    option_explanations: dict[str, str] | None = None
    rubric: list[Rubric] | None = None
    code: str | None = None
    language: str | None = None
    reference_fill: str | None = None
    case_material: str | None = None
    subquestions: list[Subquestion] | None = None
    assets: list[Asset] = []


class Paper(Record):
    id: str
    title: str
    year: int
    session: str
    subject: Literal["comprehensive", "applied"]
    batch: str
    origin_kind: str
    completeness: Literal["complete", "partial", "index_only", "missing"]
    answer_status: str
    question_ids: list[str]
    source_ids: list[str]
    notes: str | list[str]
