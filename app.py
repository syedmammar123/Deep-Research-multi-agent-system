from flask import Flask, render_template, request, jsonify
import os
import operator
from datetime import datetime
from typing import Annotated, TypedDict
from dotenv import load_dotenv
load_dotenv()

# Import your existing research system
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_groq import ChatGroq
from tavily import TavilyClient

app = Flask(__name__)

import os

groq_api_key = os.getenv("GROQ_API_KEY")
tvly_api_key = os.getenv("TVLY_API_KEY")

llm = ChatGroq(model="llama-3.1-8b-instant", api_key=groq_api_key)


def search_web(query: str) -> str:
    """Useful for using the web to answer questions."""
    try:
        client = TavilyClient(api_key=tvly_api_key)
        # Limit results to 5 to save tokens
        response = client.search(query, search_depth="advanced", max_results=5)

        # Parse and format only the necessary information
        results = response.get("results", [])
        formatted_output = []

        for result in results:
            title = result.get("title", "No title")
            url = result.get("url", "No URL")
            content = result.get("content", "")

            # # Truncate content to avoid token overflow (max 500 chars per result)
            # if len(content) > 500:
            #     content = content[:500] + "..."

            formatted_output.append(f"Title: {title}\nURL: {url}\nContent: {content}")

        return "\n\n".join(formatted_output)
    except Exception as e:
        return f"Search failed: {str(e)}"


class ResearchState(TypedDict):
    topic: str
    questions: list[str]
    # Answers arrive from parallel branches in completion order, so each one
    # carries its question index and is sorted back into place before the report.
    answers: Annotated[list[tuple[int, str]], operator.add]
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


def generate_questions(state: ResearchState) -> dict:
    topic = state["topic"]

    question_prompt = f"""Generate 3-4 specific questions about this topic: {topic}
    Provide the questions one per line. Don't include markdown or any preamble, just a list of questions."""

    question_response = llm.invoke(question_prompt)
    questions_text = question_response.content
    questions = [q.strip() for q in questions_text.split("\n") if q.strip()]

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

    progress_log = [
        f"[{timestamp()}] Researching question {i}/{state['total']}: {question[:50]}..."
    ]

    try:
        # Search the web for this question
        search_result = search_web(question)

        # Generate answer using the search result
        answer_prompt = f"""Based on this web search result, answer this question: {question}

        Web search result: {search_result}

        Provide a comprehensive answer based on the search results."""

        answer_response = llm.invoke(answer_prompt)
        answer = answer_response.content
    except Exception as e:
        # One failed branch shouldn't discard the work the others already finished.
        answer = f"_This question could not be researched: {e}_"

    progress_log.append(f"[{timestamp()}] Completed research for question {i}")

    return {
        "answers": [
            (i, f"**Question {i}:** {question}\n\n**Answer:** {answer}\n\n---\n")
        ],
        "progress_log": progress_log,
    }


def write_report(state: ResearchState) -> dict:
    topic = state["topic"]
    all_answers = [text for _, text in sorted(state["answers"])]
    report_started_at = timestamp()

    report_prompt = f"""You are writing a comprehensive research report on: {topic}

    Here are the questions and answers that were researched:

    {''.join(all_answers)}

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

    report_response = llm.invoke(report_prompt)
    final_report = report_response.content

    # Ensure it starts with a proper title
    if not final_report.startswith("#"):
        final_report = f"# Research Report: {topic}\n\n{final_report}"

    return {
        "report": final_report,
        "progress_log": [
            f"[{report_started_at}] Generating comprehensive report...",
            f"[{timestamp()}] Research completed successfully!",
        ],
    }


graph_builder = StateGraph(ResearchState)
graph_builder.add_node("generate_questions", generate_questions)
graph_builder.add_node("answer_question", answer_question)
graph_builder.add_node("write_report", write_report)
graph_builder.add_edge(START, "generate_questions")
# Fan out: one concurrent branch per question. `write_report` waits for all of them.
graph_builder.add_conditional_edges(
    "generate_questions", route_questions, ["answer_question"]
)
graph_builder.add_edge("answer_question", "write_report")
graph_builder.add_edge("write_report", END)
research_graph = graph_builder.compile()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start_research", methods=["POST"])
def start_research():
    data = request.get_json()
    topic = data.get("topic")

    if not topic:
        return jsonify({"success": False, "message": "Please enter a research topic"})

    try:
        initial_state: ResearchState = {
            "topic": topic,
            "questions": [],
            "answers": [],
            "report": "",
            "progress_log": [],
        }

        final_state = research_graph.invoke(initial_state)

        # Parallel branches append out of order; sort by the [HH:MM:SS] prefix.
        progress = sorted(final_state["progress_log"], key=lambda line: line[1:9])

        return jsonify(
            {
                "success": True,
                "result": final_state["report"],
                "progress": progress,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": f"Research failed: {str(e)}"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
