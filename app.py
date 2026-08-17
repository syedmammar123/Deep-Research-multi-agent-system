import logging
import os
from datetime import datetime

from flask import Flask, Response, jsonify, make_response, render_template, request

from research import ResearchState, research_graph
from research.events import error_event, sse

logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.route("/")
def index():
    response = make_response(render_template("index.html"))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/start_research", methods=["POST"])
def start_research():
    topic = (request.get_json() or {}).get("topic")
    if not topic:
        return jsonify({"success": False, "message": "Please enter a research topic"})

    return Response(
        research_events(topic),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def research_events(topic: str):
    """Run the graph, forwarding each node's progress events as they happen."""
    initial_state: ResearchState = {
        "topic": topic,
        "questions": [],
        "answers": [],
        "report": "",
        "progress_log": [],
    }

    report = ""
    progress_log: list[str] = []

    try:
        for mode, chunk in research_graph.stream(
            initial_state, stream_mode=["custom", "updates"]
        ):
            if mode == "custom":
                yield sse(chunk)
            elif mode == "updates":

                for node_output in chunk.values():
                    if not isinstance(node_output, dict):
                        continue
                    progress_log.extend(node_output.get("progress_log", []))
                    if node_output.get("report"):
                        report = node_output["report"]

        # Parallel branches append out of order; sort by the [HH:MM:SS] prefix.
        yield sse(
            {
                "type": "done",
                "report": report,
                "progress": sorted(progress_log, key=lambda line: line[1:9]),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.exception("Research failed for %r", topic)
        yield sse(error_event(f"Research failed: {e}"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
