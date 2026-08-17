"""Graph state shared between nodes."""

import operator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, TypedDict

from research.citations import Source


@dataclass
class QAResult:
    """One answered question plus the sources its `[n]` markers refer to, still
    numbered locally until `write_report` renumbers them globally."""

    index: int
    question: str
    answer: str
    sources: list[Source] = field(default_factory=list)


class ResearchState(TypedDict):
    topic: str
    questions: list[str]
    # Answers arrive from parallel branches in completion order, so each one carries its question index and is sorted back into place before the report.
    answers: Annotated[list[QAResult], operator.add]
    report: str
    progress_log: Annotated[list[str], operator.add]


class QuestionState(TypedDict):
    """The payload one fanned-out `answer_question` branch receives."""

    topic: str
    index: int
    total: int
    question: str


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")
