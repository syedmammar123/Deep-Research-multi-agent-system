"""Graph wiring: generate_questions -> fan out -> answer_question -> write_report."""

from langgraph.graph import END, START, StateGraph

from research.nodes import (
    answer_question,
    generate_questions,
    route_questions,
    write_report,
)
from research.state import ResearchState


def build_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("generate_questions", generate_questions)
    builder.add_node("answer_question", answer_question)
    builder.add_node("write_report", write_report)

    builder.add_edge(START, "generate_questions")
    builder.add_conditional_edges(
        "generate_questions", route_questions, ["answer_question"]
    )
    builder.add_edge("answer_question", "write_report")
    builder.add_edge("write_report", END)

    return builder.compile()


research_graph = build_graph()
