"""Source tracking and inline `[n]` citation plumbing.

The model only ever sees a numbered list and writes `[n]` markers; every URL is
put back by code, so it has no way to express a fabricated citation.
"""

import re
from dataclasses import dataclass

MARKER = re.compile(r"([ \t]*)\[(\d+)\]")
GROUPED = re.compile(r"\[(\d+(?:\s*,\s*\d+)+)\]")


@dataclass(frozen=True)
class Source:
    id: int
    title: str
    url: str
    content: str = ""  # search snippet, for the prompt only


def format_for_prompt(sources: list[Source]) -> str:
    """The numbered block the model cites against."""
    return "\n\n".join(
        f"[{source.id}] {source.title} — {source.url}\n{source.content}"
        for source in sources
    )


def normalize_markers(text: str) -> str:
    """Split `[1, 2]` into `[1][2]`, since models use either style and a grouped
    marker would otherwise match nothing and be dropped."""
    return GROUPED.sub(
        lambda m: "".join(f"[{n.strip()}]" for n in m.group(1).split(",")), text
    )


def keep_valid_markers(text: str, valid_ids: set[int]) -> str:
    """Strip every `[n]` that doesn't name a real source."""
    return MARKER.sub(lambda m: m.group(0) if int(m.group(2)) in valid_ids else "", text)


def build_registry(qa_results: list) -> tuple[list[Source], dict[tuple[int, int], int]]:
    """Merge every branch's sources into one global numbering, deduped by URL.

    Returns the registry plus a `(question_index, local_id) -> global_id` map.
    """
    registry: list[Source] = []
    by_url: dict[str, int] = {}
    mapping: dict[tuple[int, int], int] = {}

    for result in qa_results:
        for source in result.sources:
            global_id = by_url.get(source.url)
            if global_id is None:
                global_id = len(registry) + 1
                by_url[source.url] = global_id
                registry.append(Source(id=global_id, title=source.title, url=source.url))
            mapping[(result.index, source.id)] = global_id

    return registry, mapping


def remap(text: str, mapping: dict[int, int]) -> str:
    """Renumber one answer's markers to their global ids. One pass, deliberately:
    renumbering in place would let an already remapped marker shift twice."""
    return MARKER.sub(
        lambda m: (
            f"{m.group(1)}[{mapping[int(m.group(2))]}]"
            if int(m.group(2)) in mapping
            else ""
        ),
        text,
    )


def linkify(text: str, registry: list[Source]) -> str:
    """Turn `[n]` into `[[n]](url)` - markdown whose link text is literally `[n]`.

    Runs only after the report call; the model would mangle URLs it could see.
    """
    urls = {source.id: source.url for source in registry}
    return MARKER.sub(
        lambda m: (
            f"{m.group(1)}[[{m.group(2)}]]({urls[int(m.group(2))]})"
            if int(m.group(2)) in urls
            else m.group(0)
        ),
        text,
    )


def cited_ids(text: str) -> set[int]:
    return {int(m.group(2)) for m in MARKER.finditer(text)}


def render_references(registry: list[Source]) -> str:
    """The trailing References block. Bullets, not an ordered list: markdown
    renumbers those, which would break the mapping if an id goes uncited."""
    if not registry:
        return ""
    entries = "\n".join(
        f"- **[{source.id}]** [{source.title}]({source.url})" for source in registry
    )
    return f"\n\n## References\n\n{entries}\n"
