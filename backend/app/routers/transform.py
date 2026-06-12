"""Transform router endpoint for converting chat responses into structured formats.

Provides POST /api/transform to convert a text response into table or chart-ready
formats using the LLM directly (no RAG retrieval). This is a lightweight call
that reformats existing data without querying the knowledge base.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.services.langchain.dependencies import get_service_container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transform", tags=["transform"])


# ─── Schemas ──────────────────────────────────────────────────────────────────


class TransformFormat(str, Enum):
    """Supported output formats for transformation."""

    table = "table"
    bar = "bar"
    line = "line"
    pie = "pie"
    donut = "donut"


class TransformRequest(BaseModel):
    """Request schema for the transform endpoint."""

    content: str = Field(..., min_length=1, max_length=10000, description="The source text content to transform")
    format: TransformFormat = Field(..., description="Target format for transformation")
    language: str = Field(default="id", description="Language code (id or en)")


class TransformResponse(BaseModel):
    """Response schema for the transform endpoint."""

    transformed: str = Field(..., description="The transformed content in the requested format")
    format: str = Field(..., description="The format that was applied")
    success: bool = Field(default=True)


# ─── Prompt Templates ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Kamu adalah asisten yang mengubah data/teks menjadi format terstruktur.
Aturan:
- Langsung tampilkan hasilnya tanpa penjelasan tambahan
- Jangan hilangkan data apapun dari input
- Pastikan format output sesuai yang diminta
- Gunakan angka asli tanpa mengubah nilainya"""

_FORMAT_INSTRUCTIONS = {
    "table": """\
Ubah data berikut menjadi format tabel markdown yang rapi dan lengkap.
Gunakan header kolom yang jelas. Jika ada kategori/label dan nilai, pisahkan ke kolom yang sesuai.
Langsung tampilkan tabel markdown tanpa teks tambahan.

Data:
{content}""",
    "bar": """\
Ubah data berikut menjadi tabel markdown 2 kolom untuk bar chart.
Kolom pertama: Label (nama item/kategori)
Kolom kedua: Value (angka saja, tanpa simbol mata uang atau satuan)

Jika ada beberapa nilai numerik per item, pilih yang paling relevan (misal harga, jumlah, atau total).
Langsung tampilkan tabel markdown tanpa teks tambahan.

Data:
{content}""",
    "line": """\
Ubah data berikut menjadi tabel markdown 2 kolom untuk line chart.
Kolom pertama: Label (urutan waktu, nama item, atau kategori berurutan)
Kolom kedua: Value (angka saja, tanpa simbol mata uang atau satuan)

Urutkan data secara logis (kronologis atau dari kecil ke besar).
Langsung tampilkan tabel markdown tanpa teks tambahan.

Data:
{content}""",
    "pie": """\
Ubah data berikut menjadi tabel markdown 2 kolom untuk pie chart.
Kolom pertama: Label (nama item/kategori)
Kolom kedua: Value (angka saja, tanpa simbol mata uang atau satuan)

Langsung tampilkan tabel markdown tanpa teks tambahan.

Data:
{content}""",
    "donut": """\
Ubah data berikut menjadi tabel markdown 2 kolom untuk donut chart.
Kolom pertama: Label (nama item/kategori)
Kolom kedua: Value (angka saja, tanpa simbol mata uang atau satuan)

Langsung tampilkan tabel markdown tanpa teks tambahan.

Data:
{content}""",
}


# ─── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("", response_model=TransformResponse)
async def transform(body: TransformRequest) -> TransformResponse:
    """Transform text content into a structured format using the LLM.

    This endpoint does NOT perform RAG retrieval. It simply asks the LLM
    to reformat the given content into the requested structure (table, chart data).

    Returns:
        TransformResponse with the transformed content.

    Raises:
        HTTPException 503: LLM not configured or packages missing.
        HTTPException 500: LLM invocation failed.
    """
    container = get_service_container()
    if not container.is_llm_available:
        raise HTTPException(
            status_code=503,
            detail="LLM service is not available.",
        )

    # Build prompt
    format_instruction = _FORMAT_INSTRUCTIONS.get(body.format.value, _FORMAT_INSTRUCTIONS["table"])
    user_prompt = format_instruction.format(content=body.content)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = await container.llm.ainvoke(messages)
        transformed = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.exception("Transform LLM invocation failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to transform content. Please try again.",
        )

    return TransformResponse(
        transformed=transformed.strip(),
        format=body.format.value,
        success=True,
    )
