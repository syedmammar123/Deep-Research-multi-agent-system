"""The graph nodes: plan questions, answer them in parallel, write the report."""

import logging

from langgraph.config import get_stream_writer
from langgraph.types import Send

from research.citations import (
    build_registry,
    cited_ids,
    format_for_prompt,
    keep_valid_markers,
    linkify,
    normalize_markers,
    remap,
    render_references,
)
from research.config import invoke_llm
from research.events import question_event, stage_event
from research.search import search_web
from research.state import QAResult, QuestionState, ResearchState, timestamp

logger = logging.getLogger(__name__)


def generate_questions(state: ResearchState) -> dict:
    topic = state["topic"]
    writer = get_stream_writer()
    writer(stage_event("questions", "start", topic=topic))

    prompt = f"""Generate 2-3 specific questions about this topic: {topic}
    Provide the questions one per line. Don't include markdown or any preamble, just a list of questions."""

    response = invoke_llm(prompt)
    questions = [q.strip() for q in response.split("\n") if q.strip()]
    logger.info("Generated %d questions for %r", len(questions), topic)

    writer(stage_event("questions", "done", questions=questions))

    return {
        "questions": questions,
        "progress_log": [
            f"[{timestamp()}] Starting research on: {topic}",
            f"[{timestamp()}] Generated {len(questions)} questions",
        ],
    }


def route_questions(state: ResearchState) -> list[Send]:
    """Dispatch one concurrent `answer_question` branch per question."""
    total = len(state["questions"])
    return [
        Send(
            "answer_question",
            {"topic": state["topic"], "index": i, "total": total, "question": question},
        )
        for i, question in enumerate(state["questions"], 1)
    ]


def answer_question(state: QuestionState) -> dict:
    i = state["index"]
    question = state["question"]
    writer = get_stream_writer()

    progress_log = [
        f"[{timestamp()}] Researching question {i}/{state['total']}: {question[:50]}..."
    ]

    sources = []
    try:
        writer(question_event(i, "searching", question=question))
        sources = search_web(question)

        writer(question_event(i, "answering", sources=len(sources)))
        prompt = f"""Based on these web search results, answer this question: {question}

        Sources:

        {format_for_prompt(sources)}

        Provide a comprehensive answer based on the search results. Cite every
        factual claim inline as [1], [2] and so on, using only the numbers listed
        above — never invent a number, a title, or a URL."""

        answer = invoke_llm(prompt)
        answer = keep_valid_markers(
            normalize_markers(answer), {source.id for source in sources}
        )
        found = len(sources)
        sources = [source for source in sources if source.id in cited_ids(answer)]
        logger.info("Question %d: %d sources found, %d cited", i, found, len(sources))
        writer(question_event(i, "done", sources=len(sources), found=found))
    except Exception as e:
        # One failed branch shouldn't discard the work the others already finished.
        logger.exception("Question %d failed", i)
        answer = f"_This question could not be researched: {e}_"
        sources = []
        writer(question_event(i, "error", message=str(e)))

    progress_log.append(f"[{timestamp()}] Completed research for question {i}")

    return {
        "answers": [QAResult(index=i, question=question, answer=answer, sources=sources)],
        "progress_log": progress_log,
    }


def write_report(state: ResearchState) -> dict:
    topic = state["topic"]
    results = sorted(state["answers"], key=lambda result: result.index)
    report_started_at = timestamp()

    writer = get_stream_writer()
    writer(stage_event("report", "start"))
    logger.info("Writing report for %r from %d answers", topic, len(results))

    registry, mapping = build_registry(results)
    all_answers = [
        "**Question {}:** {}\n\n**Answer:** {}\n\n---\n".format(
            result.index,
            result.question,
            remap(
                result.answer,
                {
                    source.id: mapping[(result.index, source.id)]
                    for source in result.sources
                },
            ),
        )
        for result in results
    ]

    prompt = f"""You are writing a comprehensive research report on: {topic}

    Here are the questions and answers that were researched:

    {''.join(all_answers)}

    The answers contain inline citation markers like [1] and [2], numbered against
    this source list:

    {format_for_prompt(registry)}

    Keep those markers exactly as they appear when you carry a claim into the
    report. Never introduce a number that isn't on the list above, and don't write
    out URLs — the reference list is added for you afterwards.

    Please write a clear, thorough report that combines all this information into a comprehensive analysis of the topic.
    Structure it well with clear sections using markdown formatting:

    - Use # for main title
    - Use ## for section headers
    - Use ### for subsection headers
    - Use bullet points for lists
    - Use **bold** for emphasis
    - Use blockquotes for important quotes
    - Structure it with Executive Summary, Key Findings, Detailed Analysis, and Conclusion sections

    Make it professional and well-formatted for easy reading."""

    final_report = invoke_llm(prompt)
    if not final_report.startswith("#"):
        final_report = f"# Research Report: {topic}\n\n{final_report}"

    final_report = keep_valid_markers(final_report, {s.id for s in registry})
    surviving = [source for source in registry if source.id in cited_ids(final_report)]
    final_report = linkify(final_report, surviving) + render_references(surviving)
    logger.info("Report cites %d of %d sources", len(surviving), len(registry))

    return {
        "report": final_report,
        "progress_log": [
            f"[{report_started_at}] Generating comprehensive report...",
            f"[{timestamp()}] Research completed successfully!",
        ],
    }
