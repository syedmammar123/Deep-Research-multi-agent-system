"""Environment, logging, and the shared LLM client."""

import logging
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from research.resilience import groq_retry

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TVLY_API_KEY = os.getenv("TVLY_API_KEY")


_missing = [
    name
    for name, value in (("GROQ_API_KEY", GROQ_API_KEY), ("TVLY_API_KEY", TVLY_API_KEY))
    if not value
]
if _missing:
    raise RuntimeError(
        f"Missing required environment variable(s): {', '.join(_missing)}. "
        "Copy .env.example to .env and fill them in."
    )

llm = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY)


@groq_retry
def invoke_llm(prompt: str) -> str:
    """Every LLM call goes through here so retries apply uniformly."""
    return llm.invoke(prompt).content
