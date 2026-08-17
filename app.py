import logging
import os
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from research import ResearchState, research_graph
from research.events import error_event, sse

logger = logging.getLogger(__name__)

app = FastAPI(title="Deep Research Multi-Agent System")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.middleware("http")
async def no_store(request: Request, call_next):
    """Caching is disabled in both directions: a cached app.js otherwise runs
    stale code against a changed backend."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/start_research")
async def start_research(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = None

    topic = (payload or {}).get("topic") if isinstance(payload, dict) else None
    if not topic:
        
        return JSONResponse(
            {"success": False, "message": "Please enter a research topic"}
        )

   
    return StreamingResponse(
        research_events(topic),
        media_type="text/event-stream",
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
    import uvicorn

    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
