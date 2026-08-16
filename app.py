from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime
from typing import TypedDict
from dotenv import load_dotenv
load_dotenv()

# Import your existing research system
from langgraph.graph import StateGraph, START, END
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
    answers: list[str]
    report: str
    progress_log: list[str]


def generate_questions(state: ResearchState) -> ResearchState:
    topic = state["topic"]

    state["progress_log"].append(
        f"[{datetime.now().strftime('%H:%M:%S')}] Starting research on: {topic}"
    )

    question_prompt = f"""Generate 5-7 specific questions about this topic: {topic}
    Provide the questions one per line. Don't include markdown or any preamble, just a list of questions."""

    question_response = llm.invoke(question_prompt)
    questions_text = question_response.content
    questions = [q.strip() for q in questions_text.split("\n") if q.strip()]

    state["questions"] = questions
    state["progress_log"].append(
        f"[{datetime.now().strftime('%H:%M:%S')}] Generated {len(questions)} questions"
    )

    return state


def answer_questions(state: ResearchState) -> ResearchState:
    questions = state["questions"]
    all_answers = []

    for i, question in enumerate(questions, 1):
        state["progress_log"].append(
            f"[{datetime.now().strftime('%H:%M:%S')}] Researching question {i}/{len(questions)}: {question[:50]}..."
        )

        # Search the web for this question
        search_result = search_web(question)

        # Generate answer using the search result
        answer_prompt = f"""Based on this web search result, answer this question: {question}

        Web search result: {search_result}

        Provide a comprehensive answer based on the search results."""

        answer_response = llm.invoke(answer_prompt)
        answer = answer_response.content

        all_answers.append(
            f"**Question {i}:** {question}\n\n**Answer:** {answer}\n\n---\n"
        )
        state["progress_log"].append(
            f"[{datetime.now().strftime('%H:%M:%S')}] Completed research for question {i}"
        )

    state["answers"] = all_answers
    return state


def write_report(state: ResearchState) -> ResearchState:
    topic = state["topic"]
    all_answers = state["answers"]

    state["progress_log"].append(
        f"[{datetime.now().strftime('%H:%M:%S')}] Generating comprehensive report..."
    )

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

    state["report"] = final_report
    state["progress_log"].append(
        f"[{datetime.now().strftime('%H:%M:%S')}] Research completed successfully!"
    )

    return state


graph_builder = StateGraph(ResearchState)
graph_builder.add_node("generate_questions", generate_questions)
graph_builder.add_node("answer_questions", answer_questions)
graph_builder.add_node("write_report", write_report)
graph_builder.add_edge(START, "generate_questions")
graph_builder.add_edge("generate_questions", "answer_questions")
graph_builder.add_edge("answer_questions", "write_report")
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

        return jsonify(
            {
                "success": True,
                "result": final_state["report"],
                "progress": final_state["progress_log"],
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": f"Research failed: {str(e)}"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
