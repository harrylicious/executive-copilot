"""AI suggestion service for file tag and rename recommendations.

Uses the LangChain LLM (via the global ServiceContainer) to analyze
a file's extracted_text and produce tag/rename suggestions.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.models.file import File
from app.services.langchain.dependencies import get_service_container

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 3000  # Limit extracted text sent to LLM to control token usage

_TAG_PROMPT_TEMPLATE = """\
You are a document classification assistant. Analyze the following document text \
and suggest up to 5 relevant tags that describe the document's content, topic, \
and category. Return ONLY a JSON array of lowercase tag strings, nothing else.

Document file name: {file_name}
Department: {department}

Document text (excerpt):
{text}

Respond with a JSON array of up to 5 tags. Example: ["finance", "quarterly-report", "revenue", "2024", "summary"]
"""

_RENAME_PROMPT_TEMPLATE = """\
You are a file naming assistant. Based on the document content below, suggest up to 3 \
descriptive file names following the naming convention: [department]_[topic]_[date].[ext]

Rules:
- Use lowercase with underscores for spaces
- Department: {department}
- Current file extension: {extension}
- If a date is mentioned in the content, include it as YYYYMMDD or YYYYMM
- If no date is found, omit the date segment
- The topic should be 1-3 words summarizing the document's main subject
- Return ONLY a JSON array of filename strings, nothing else

Document file name: {file_name}
Document text (excerpt):
{text}

Respond with a JSON array of up to 3 suggested filenames. \
Example: ["finance_quarterly_report_202401.pdf", "finance_budget_summary.pdf", "finance_revenue_analysis_2024.pdf"]
"""


def _get_llm() -> "BaseChatModel | None":
    """Retrieve the LLM instance from the global service container."""
    container = get_service_container()
    if not container.is_llm_available:
        return None
    return container.llm


def _truncate_text(text: str, max_chars: int = _MAX_TEXT_CHARS) -> str:
    """Truncate text to a maximum character count."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _parse_json_list(response_text: str) -> list[str]:
    """Parse a JSON array from the LLM response text.

    Handles cases where the LLM wraps the array in markdown code fences.
    Returns an empty list on parse failure.
    """
    text = response_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [str(item) for item in result if item]
        return []
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Failed to parse LLM response as JSON array: {text[:200]}")
        return []


def suggest_tags(file_id: int, db: Session) -> list[str]:
    """Suggest up to 5 relevant tags for a file based on its extracted text.

    Args:
        file_id: The ID of the file to analyze.
        db: SQLAlchemy database session.

    Returns:
        A list of up to 5 tag strings, or an empty list if the file is not
        found, has no extracted text, or the LLM is unavailable.
    """
    file = db.query(File).filter(File.id == file_id, File.is_deleted == False).first()
    if file is None:
        logger.warning(f"suggest_tags: file_id={file_id} not found")
        return []

    if not file.extracted_text or not file.extracted_text.strip():
        logger.info(f"suggest_tags: file_id={file_id} has no extracted text")
        return []

    llm = _get_llm()
    if llm is None:
        logger.warning("suggest_tags: LLM is not available")
        return []

    prompt = _TAG_PROMPT_TEMPLATE.format(
        file_name=file.name or "",
        department=file.department or "unknown",
        text=_truncate_text(file.extracted_text),
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content if hasattr(response, "content") else str(response)
        tags = _parse_json_list(content)
        return tags[:5]
    except Exception as exc:
        logger.error(f"suggest_tags: LLM invocation failed for file_id={file_id}: {exc}")
        return []


def suggest_rename(file_id: int, db: Session) -> list[str]:
    """Suggest up to 3 file name alternatives based on extracted text.

    Follows the naming convention: [department]_[topic]_[date].[ext]

    Args:
        file_id: The ID of the file to analyze.
        db: SQLAlchemy database session.

    Returns:
        A list of up to 3 suggested file name strings, or an empty list if
        the file is not found, has no extracted text, or the LLM is unavailable.
    """
    file = db.query(File).filter(File.id == file_id, File.is_deleted == False).first()
    if file is None:
        logger.warning(f"suggest_rename: file_id={file_id} not found")
        return []

    if not file.extracted_text or not file.extracted_text.strip():
        logger.info(f"suggest_rename: file_id={file_id} has no extracted text")
        return []

    llm = _get_llm()
    if llm is None:
        logger.warning("suggest_rename: LLM is not available")
        return []

    # Extract extension from current file name
    extension = ""
    if file.name and "." in file.name:
        extension = file.name.rsplit(".", 1)[-1].lower()

    prompt = _RENAME_PROMPT_TEMPLATE.format(
        file_name=file.name or "",
        department=(file.department or "unknown").lower().replace(" ", "_"),
        extension=extension or "txt",
        text=_truncate_text(file.extracted_text),
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content if hasattr(response, "content") else str(response)
        suggestions = _parse_json_list(content)
        return suggestions[:3]
    except Exception as exc:
        logger.error(
            f"suggest_rename: LLM invocation failed for file_id={file_id}: {exc}"
        )
        return []
