"""Progress events streamed to the browser.

Nodes emit these *before* each slow call, so the UI shows a stage as in-progress
rather than only learning it happened afterwards.
"""

import json


def stage_event(key: str, status: str, **extra) -> dict:
    """A whole-pipeline stage: `questions` or `report`."""
    return {"type": "stage", "key": key, "status": status, **extra}


def question_event(index: int, status: str, **extra) -> dict:
    """One fanned-out question branch. Keyed by `index` because branches
    interleave and finish out of order."""
    return {"type": "question", "index": index, "status": status, **extra}


def error_event(message: str) -> dict:
    return {"type": "error", "message": message}


def sse(event: dict) -> str:
    """Frame one event as a Server-Sent Event."""
    return f"data: {json.dumps(event)}\n\n"
