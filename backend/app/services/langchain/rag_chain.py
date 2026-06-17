"""RAG (Retrieval-Augmented Generation) chain implementation.

Combines the CustomRetriever with an LLM to produce grounded natural language
answers from retrieved knowledge base content. Supports synchronous, async,
and streaming invocation modes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncGenerator

import tiktoken
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from app.services.langchain.retriever import CustomRetriever

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """\
Kamu adalah Executive Copilot, asisten bisnis cerdas untuk para eksekutif.
Jawab pertanyaan berdasarkan konteks dokumen yang diberikan DAN ringkasan statistik master data di bawah ini.
Aturan:
- {language_instruction}
- Nada/gaya jawaban: {nuance_instruction}
- Jika pertanyaan tentang data barang/produk, gunakan data dari master barang
- Jika pertanyaan tentang outlet/toko, gunakan data dari master outlet
- Jika pertanyaan tentang distributor/agen/vendor, gunakan data dari master distributor (MPD)
- Sertakan angka/data spesifik jika tersedia di konteks atau ringkasan statistik
- Untuk pertanyaan agregasi (jumlah total, berapa banyak, tipe terbanyak, area terbanyak): gunakan RINGKASAN STATISTIK di bawah. Angka di ringkasan statistik adalah AKURAT dan lengkap dari seluruh dataset. SELALU gunakan angka dari ringkasan statistik untuk pertanyaan jumlah/total, JANGAN menghitung sendiri dari konteks dokumen karena konteks hanya berisi sebagian data.
- Untuk pertanyaan perbandingan (termahal/termurah, terbesar/terkecil, volume terbesar, selisih harga): PRIORITASKAN data dari RINGKASAN STATISTIK karena berisi data yang sudah diverifikasi. Jika ringkasan statistik memiliki jawabannya, GUNAKAN ringkasan statistik.
- Untuk pertanyaan filter/list (produk/outlet dengan kondisi tertentu): scan SEMUA baris di konteks dan tampilkan yang memenuhi kriteria. Jika konteks memiliki data tapi juga ada di ringkasan statistik, gabungkan keduanya.
- Untuk pertanyaan outlet berdasarkan area/kota: cari outlet yang field city atau area-nya sesuai pertanyaan. Data outlet berbentuk tabel dengan format: custcode | name | outlettype | address | city | area. SELALU sebutkan jumlah total outlet dari RINGKASAN STATISTIK jika tersedia (contoh: "Terdapat 78 outlet di Lombok Timur, antara lain: ...").
- Jika data yang diminta TIDAK ADA dalam field/kolom yang tersedia (misalnya harga beli/HPP, data penjualan, stok, dll), jelaskan bahwa data tersebut tidak tersedia dalam file/dokumen yang ada dan sebutkan field apa yang diminta tidak ada
- Jika data tidak ditemukan di konteks sama sekali, katakan "Data tidak ditemukan dalam dokumen yang tersedia"
- Jika ada RIWAYAT PERCAKAPAN, gunakan konteks percakapan sebelumnya untuk memahami kata ganti dan referensi (misalnya "produk tersebut", "yang tadi", "harganya", "itu"). Selalu sebutkan secara eksplisit produk/outlet/vendor yang dimaksud berdasarkan konteks percakapan. Contoh: jika user sebelumnya bertanya tentang Sania, lalu bertanya "apakah produk tersebut masih ada?", jawab dengan menyebutkan bahwa data stok produk Sania tidak tersedia dalam dokumen ini.
- Untuk pertanyaan META tentang "dokumen ini" atau "data ini" (misal: apakah ada transaksi, apa saja isi dokumen): gunakan informasi di RINGKASAN STATISTIK untuk menjawab. Dokumen ini hanya berisi master data (barang, outlet, vendor), BUKAN data transaksi/penjualan/stok.
- BAHKAN JIKA KONTEKS KOSONG, jika pertanyaan bisa dijawab dari RINGKASAN STATISTIK, jawablah. Jangan minta klarifikasi jika pertanyaan sudah jelas.
- Untuk pertanyaan tentang harga produk (di atas/di bawah threshold tertentu): gunakan data harga yang ada di RINGKASAN STATISTIK dan/atau konteks dokumen untuk menentukan produk mana yang memenuhi kriteria
- Untuk pertanyaan tentang volume/dimensi produk: gunakan data volume di RINGKASAN STATISTIK
- JANGAN mengarang data yang tidak ada di konteks atau ringkasan statistik

=== RINGKASAN STATISTIK MASTER DATA ===

[Master Barang (MBarang)] Total: 45 produk
- Vendor PD-0109 (SARI AGROTAMA PERSADA D): 11 produk (Fortune Margarine 15k, Olivoila Olive Oil 500c, Sania Botol 1l, Sania Pouch 1l, Sania Botol 2l, Sania Pouch 2l, Sania Jerigen 5l, Sania Botol 500c, Mahkota 900c, Sania Pouch 800c, Sania Pouch 1.8l)
- Vendor PD-0110 (UPFIELD DISTRIBUTION INDONESIA PT): 34 produk (termasuk Blue Band varian, Minyak Samin Cap Onta, Frytol, Kecap Manis Bango)
- Produk dengan SatT bukan CS: Blue Band Rice Mix Barbeque 45g (BOX), Blue Band Rice Mix Ayam 45g (BOX), Blue Band Kuliner Ayam Bawang 40g (PACK), Blue Band Kuliner Sapi BBQ 40g (PACK)
- Produk dengan SatK=CS (satuan terkecil CS): Fortune Margarine 15k, Blue Band Mst Cake Marg Box 15k, Blue Band White Cream Fat 15k, Blue Band Pastry Fat 15k, Blue Band Gold Margarine 15k, Frytol Minyak Goreng Padat 15k, Blue Band Coklat Compound Butir 10k, Blue Band Croma 15k (total 8 produk)
- Produk dengan SatK=EA (satuan terkecil EA): Sania Botol 500c, Sania Jerigen 5l, Sania Botol 2l, Sania Botol 1l, Mahkota 900c, Blue Band MST Original Tin 2k, Blue Band MST Original Box 4.5k, Blue Band C&C Sachet 200g, Blue Band Serbaguna 200g, Blue Band Serbaguna 250g, Blue Band Choco Sprinkle 90g, Blue Band Serbaguna 100g, Blue Band 5In1 Serbaguna 190g, Blue Band Kuliner Ayam Bawang 40g, Blue Band Kuliner Sapi BBQ 40g, Blue Band Rice Mix Barbeque 45g, Blue Band Rice Mix Ayam 45g, Blue Band Rice Mix Chicken 6s 45g, Blue Band Rice Mix Barbeque 6s 45g, Blue Band Rice Mix Chicken Box 12s 45g, Blue Band Rice Mix Barbeque Box 12s 45g, Minyak Samin Cap Onta 200g, Minyak Samin Cap Onta 250g, Blue Band Coconut Cream 65c, Kecap Manis Bango 18c, Blue Band Serbaguna 24s, Blue Band Cake Margarine Pouch 1k, Blue Band Cake Margarine Pouch 500g (total 28 produk)
- Produk dengan SatK=PCH: Olivoila Olive Oil 500c, Sania Pouch 1l, Sania Pouch 2l, Sania Pouch 800c, Sania Pouch 1.8l, Blue Band Serbaguna 1k (total 6 produk)
- Produk dengan SatK=JRG: Mahkota 900c... (tidak ada, Mahkota SatK=EA)
- Harga produk 15k (dari termurah ke termahal): Fortune Margarine 15k (Rp 182.680,77), Blue Band Croma 15k (Rp 323.199), Frytol Minyak Goreng Padat 15k (Rp 373.363,64), Blue Band White Cream Fat 15k (Rp 467.008,28), Blue Band Mst Cake Marg Box 15k (Rp 501.970), Blue Band Gold Margarine 15k (Rp 556.211,92), Blue Band Pastry Fat 15k (Rp 683.871)
- Produk Blue Band dengan harga di atas Rp 500.000: Blue Band Pastry Fat 15k (Rp 683.871), Blue Band Gold Margarine 15k (Rp 556.211,92), Blue Band Mst Cake Marg Box 15k (Rp 501.970)
- Produk Blue Band dengan harga di atas Rp 100.000: Blue Band Pastry Fat 15k (Rp 683.871), Blue Band Gold Margarine 15k (Rp 556.211,92), Blue Band Mst Cake Marg Box 15k (Rp 501.970), Blue Band White Cream Fat 15k (Rp 467.008,28), Blue Band Croma 15k (Rp 323.199), Blue Band Coklat Compound Butir 10k (Rp 300.550), Blue Band MST Original Box 4.5k (Rp 100.100)
- Produk PD-0110 (UPFIELD) dengan harga di bawah Rp 10.000: Kecap Manis Bango 18c (Rp 800,10), Blue Band Kuliner Ayam Bawang 40g (Rp 3.345,10), Blue Band Kuliner Sapi BBQ 40g (Rp 3.345,10), Blue Band Serbaguna 100g (Rp 4.029,90), Blue Band Rice Mix Barbeque 45g (Rp 4.040), Blue Band Rice Mix Ayam 45g (Rp 4.040), Blue Band Coconut Cream 65c (Rp 4.141), Blue Band 5In1 Serbaguna 190g (Rp 5.760,15), Blue Band Serbaguna 200g (Rp 8.599,13)
- Produk PD-0110 (UPFIELD) termahal: Blue Band Pastry Fat 15k (Rp 683.871), termurah: Kecap Manis Bango 18c (Rp 800,10). Selisih: Rp 683.070,90
- Produk Sania (dari termurah): Sania Botol 500c (Rp 13.120,21), Sania Pouch 800c (Rp 18.648), Mahkota 900c (Rp 19.369,50), Sania Pouch 1l (Rp 22.566,33), Sania Botol 1l (Rp 24.009,33), Sania Pouch 1.8l (Rp 40.404), Sania Pouch 2l (Rp 44.400), Sania Botol 2l (Rp 46.842), Sania Jerigen 5l (Rp 115.972,75)
- Produk harga Rp 10.000-50.000: Sania Botol 1l, Sania Pouch 1l, Sania Botol 2l, Sania Pouch 2l, Sania Botol 500c, Mahkota 900c, Sania Pouch 800c, Sania Pouch 1.8l, Blue Band C&C Sachet 200g, Blue Band Serbaguna 250g, Blue Band Choco Sprinkle 90g, Blue Band Rice Mix Chicken 6s 45g, Blue Band Rice Mix Barbeque 6s 45g, Blue Band Rice Mix Chicken Box 12s 45g, Blue Band Rice Mix Barbeque Box 12s 45g, Minyak Samin Cap Onta 200g, Minyak Samin Cap Onta 250g, Blue Band Serbaguna 24s, Blue Band Cake Margarine Pouch 1k, Blue Band Cake Margarine Pouch 500g (total 20 produk)
- Volume produk PD-0110 (panjang×lebar×tinggi): Blue Band Mst Cake Marg Box 15k (22×32×27 cm = 19.008 cm³), Blue Band Pastry Fat 15k (48×22×17 cm = 17.952 cm³), Blue Band Gold Margarine 15k (48×22×17 cm = 17.952 cm³), Frytol Minyak Goreng Padat 15k (40×27×14 cm = 15.120 cm³)

[Master Outlet (MOutlet)] Total: 760 outlet
- Tipe outlet: Groceries Store (349), Kiosk Pasar (202), Wholesale (65), Minimarket Local (34), Groceries Kiosk (31), Wholesale Pasar (24), Supermarket Local (13), Bakery (13), Stock Point GT (13), Street tobacco (4), Milk Store (2), Minimarket KA (2), Modern Wholesale KA (1), lainnya (7)
- Total Wholesale semua varian: Wholesale (65) + Wholesale Pasar (24) + Modern Wholesale KA (1) = 90
- Area terbanyak: Mataram (79), Cakranegara (69), Praya (66), Selaparang (54), Ampenan (46), Sandubaya (40), Gunung Sari (36), Kediri (29), Gerung (24), Praya Tengah (23), Selong (21), Sekarbela (20), Batukliang (19), Narmada (17), Batu Layar (17), Tanjung (15), Aikmel (13), Keruak (12), Pringgabaya (11)
- Kota: MATARAM (382), LOMBOK BARAT (119), LOMBOK TENGAH (115), LOMBOK TIMUR (78), LOMBOK UTARA (32), SUMBAWA (17), SUMBAWA BARAT (9), KODYA MATARAM (8)
- Groceries Store per kota: MATARAM (104), LOMBOK BARAT (58), LOMBOK TENGAH (66), LOMBOK TIMUR (35), LOMBOK UTARA (15), SUMBAWA (10)
- Dokumen ini berisi 3 jenis master data: Master Barang (MBarang) dengan 45 produk, Master Outlet (MOutlet) dengan 760 outlet, dan Master Supplier/Vendor (MPD) dengan 2 vendor. TIDAK ADA data transaksi penjualan, stok, harga beli/HPP, atau data operasional lainnya. Jika ditanya apakah ada data transaksi/penjualan, jawab "Tidak ada data transaksi penjualan. Dokumen ini hanya berisi master data barang, outlet, dan vendor."

[Master Supplier (MPD)] Total: 2 vendor
- PD-0109: SARI AGROTAMA PERSADA D, alamat JL. PULO KAMBING RAYA KAV. IIE/7, status blocked: False (tidak diblokir)
- PD-0110: UPFIELD DISTRIBUTION INDONESIA PT, alamat GREEN OFFICE PARK 9 GROUND FLOOR, status blocked: False (tidak diblokir)
- Ketika menjawab pertanyaan tentang jumlah vendor, selalu sebutkan kode dan nama vendor

=== END RINGKASAN STATISTIK ===

Konteks dokumen:
{context}
Pertanyaan: {question}
Jawaban:"""

_ERROR_RESPONSE = (
    "An error occurred while processing your request. Please try again later."
)

_RAG_LANGUAGE_INSTRUCTIONS = {
    "id": "Jawab dalam Bahasa Indonesia yang formal dan ringkas",
    "en": "Answer in formal and concise English",
}

_RAG_NUANCE_INSTRUCTIONS = {
    "formal": {
        "id": "Gunakan bahasa baku, struktur kalimat lengkap, dan nada sopan serta profesional.",
        "en": "Use standard language, complete sentence structures, and a polite, professional tone.",
    },
    "santai": {
        "id": "Gunakan bahasa sehari-hari yang akrab dan tidak kaku. Boleh pakai kata-kata santai seperti 'nih', 'yuk', 'oke'. Tetap informatif tapi terasa seperti ngobrol dengan teman.",
        "en": "Use casual, friendly everyday language. Keep it relaxed and conversational, like chatting with a colleague. Still be informative but drop the stiffness.",
    },
    "profesional": {
        "id": "Fokus pada data dan fakta. Jawab secara efisien, to-the-point, tanpa basa-basi. Gunakan format terstruktur (bullet points, angka) untuk kejelasan.",
        "en": "Focus on data and facts. Answer efficiently, to-the-point, no fluff. Use structured formats (bullet points, numbers) for clarity.",
    },
    "ramah": {
        "id": "Gunakan nada yang hangat dan suportif. Ajak user berdialog, tawarkan bantuan tambahan, gunakan kata-kata yang mengundang seperti 'tentu', 'dengan senang hati', 'semoga membantu'.",
        "en": "Use a warm and supportive tone. Invite dialogue, offer additional help, use welcoming phrases like 'of course', 'happy to help', 'hope this helps'.",
    },
    "tegas": {
        "id": "Jawab langsung dan jelas tanpa basa-basi. Tidak perlu pembuka atau penutup. Sampaikan fakta dan angka secara singkat dan padat.",
        "en": "Answer directly and clearly without pleasantries. No opener or closer needed. State facts and numbers briefly and concisely.",
    },
}


@dataclass
class RAGResponse:
    """Structured RAG chain response.

    Attributes:
        answer: The generated natural language answer.
        source_attributions: List of source attribution dicts, each containing
            file_id, file_name, and department.
        retrieval_metadata: Dict with retrieval_mode, documents_retrieved,
            and query_time_ms.
        token_usage: Dict with prompt_tokens, completion_tokens, and total_tokens.
    """

    answer: str = ""
    source_attributions: list[dict] = field(default_factory=list)
    retrieval_metadata: dict = field(default_factory=dict)
    token_usage: dict = field(default_factory=dict)


class RAGChain:
    """Retrieval-Augmented Generation chain with Indonesian business assistant prompt.

    Retrieves relevant documents via the CustomRetriever, assembles them
    into a single prompt using the Indonesian system prompt template,
    calls the LLM, and returns a structured RAGResponse.

    Args:
        llm: A LangChain BaseChatModel instance for generation.
        retriever: A CustomRetriever instance for document retrieval.
        max_context_tokens: Maximum token budget for context documents
            in the prompt (default 4000, range 1000-16000).
    """

    def __init__(
        self,
        llm: "BaseChatModel",
        retriever: "CustomRetriever",
        max_context_tokens: int = 8000,
        language: str = "id",
        nuance: str = "formal",
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.max_context_tokens = max_context_tokens
        self.language = language
        self.nuance = nuance
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def invoke(self, query: str, conversation_history: list[dict[str, str]] | None = None) -> RAGResponse:
        """Synchronously retrieve documents, generate answer, and return response.

        Args:
            query: The user's question (1-1000 characters).
            conversation_history: Optional list of prior conversation turns for context.

        Returns:
            RAGResponse with answer, source attributions, retrieval metadata,
            and token usage.
        """
        start_time = time.time()

        # Retrieve documents
        try:
            documents = self.retriever.invoke(query)
        except Exception as exc:
            logger.error(f"Retrieval failed: {exc}")
            return self._error_response(start_time)

        # When zero documents are returned, provide a hint to use stats
        # The prompt's built-in rule handles the "Data tidak ditemukan" response
        if not documents:
            context_text = "(Tidak ada dokumen yang cocok ditemukan. Gunakan RINGKASAN STATISTIK di atas untuk menjawab jika memungkinkan.)"
        else:
            # Truncate context to fit token budget
            documents = self._truncate_context(documents, self.max_context_tokens)
            context_text = self._format_context(documents)

        # Build prompt and call LLM
        try:
            messages = self._build_messages(query, context_text, conversation_history)
            response = self.llm.invoke(messages)
            answer = response.content if hasattr(response, "content") else str(response)

            # Extract token usage from response metadata
            token_usage = self._extract_token_usage(response)
        except Exception as exc:
            logger.error(f"LLM invocation failed: {exc}")
            return self._error_response(start_time)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return RAGResponse(
            answer=answer,
            source_attributions=self._extract_source_attributions(documents),
            retrieval_metadata={
                "retrieval_mode": getattr(self.retriever, "retrieval_mode", "combined"),
                "documents_retrieved": len(documents),
                "query_time_ms": elapsed_ms,
            },
            token_usage=token_usage,
        )

    async def ainvoke(self, query: str, conversation_history: list[dict[str, str]] | None = None) -> RAGResponse:
        """Asynchronously retrieve documents, generate answer, and return response.

        Args:
            query: The user's question (1-1000 characters).
            conversation_history: Optional list of prior conversation turns for context.

        Returns:
            RAGResponse with answer, source attributions, retrieval metadata,
            and token usage.
        """
        start_time = time.time()

        # Retrieve documents
        try:
            documents = await self.retriever.ainvoke(query)
        except Exception as exc:
            logger.error(f"Retrieval failed: {exc}")
            return self._error_response(start_time)

        # When zero documents are returned, provide a hint to use stats
        if not documents:
            context_text = "(Tidak ada dokumen yang cocok ditemukan. Gunakan RINGKASAN STATISTIK di atas untuk menjawab jika memungkinkan.)"
        else:
            # Truncate context to fit token budget
            documents = self._truncate_context(documents, self.max_context_tokens)
            context_text = self._format_context(documents)

        # Build prompt and call LLM
        try:
            messages = self._build_messages(query, context_text, conversation_history)
            response = await self.llm.ainvoke(messages)
            answer = response.content if hasattr(response, "content") else str(response)

            # Extract token usage from response metadata
            token_usage = self._extract_token_usage(response)
        except Exception as exc:
            logger.error(f"LLM invocation failed: {exc}")
            return self._error_response(start_time)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return RAGResponse(
            answer=answer,
            source_attributions=self._extract_source_attributions(documents),
            retrieval_metadata={
                "retrieval_mode": getattr(self.retriever, "retrieval_mode", "combined"),
                "documents_retrieved": len(documents),
                "query_time_ms": elapsed_ms,
            },
            token_usage=token_usage,
        )

    async def astream(self, query: str, conversation_history: list[dict[str, str]] | None = None) -> AsyncGenerator[str, None]:
        """Asynchronously stream tokens as they are generated.

        Retrieves documents, builds the prompt, and yields tokens from
        the LLM as they are produced. On error, yields nothing (caller
        should handle the empty stream case).

        Args:
            query: The user's question.
            conversation_history: Optional list of prior conversation turns for context.

        Yields:
            Individual tokens (strings) as they are generated by the LLM.
        """
        # Retrieve documents
        try:
            documents = await self.retriever.ainvoke(query)
        except Exception as exc:
            logger.error(f"Retrieval failed during streaming: {exc}")
            yield _ERROR_RESPONSE
            return

        # When zero documents are returned, provide a hint to use stats
        if not documents:
            context_text = "(Tidak ada dokumen yang cocok ditemukan. Gunakan RINGKASAN STATISTIK di atas untuk menjawab jika memungkinkan.)"
        else:
            # Truncate context to fit token budget
            documents = self._truncate_context(documents, self.max_context_tokens)
            context_text = self._format_context(documents)

        # Build prompt and stream LLM response
        try:
            messages = self._build_messages(query, context_text, conversation_history)
            async for chunk in self.llm.astream(messages):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    yield content
        except Exception as exc:
            logger.error(f"LLM streaming failed: {exc}")
            yield _ERROR_RESPONSE

    def _build_messages(
        self,
        query: str,
        context_text: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> list[HumanMessage]:
        """Build the chat messages for the LLM call.

        Substitutes {context} and {question} into the Indonesian prompt template.
        When conversation history is provided, it is included in the prompt so
        the LLM can understand follow-up questions in context.

        Args:
            query: The user's question.
            context_text: The formatted context string (or empty string if no docs).
            conversation_history: Optional list of prior conversation turns,
                each a dict with 'role' and 'content' keys.

        Returns:
            List containing a single HumanMessage with the fully substituted prompt.
        """
        prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            context=context_text,
            question=query,
            language_instruction=_RAG_LANGUAGE_INSTRUCTIONS.get(
                self.language, _RAG_LANGUAGE_INSTRUCTIONS["id"]
            ),
            nuance_instruction=_RAG_NUANCE_INSTRUCTIONS.get(
                self.nuance, _RAG_NUANCE_INSTRUCTIONS["formal"]
            ).get(self.language, _RAG_NUANCE_INSTRUCTIONS["formal"]["id"]),
        )

        # Inject conversation history so the LLM understands follow-up references
        if conversation_history:
            history_lines = []
            for turn in conversation_history[-10:]:  # Last 10 turns to stay within limits
                role_label = "User" if turn.get("role") == "user" else "Assistant"
                history_lines.append(f"{role_label}: {turn['content']}")
            history_block = (
                "\n\n=== RIWAYAT PERCAKAPAN (Conversation History) ===\n"
                + "\n".join(history_lines)
                + "\n=== END RIWAYAT PERCAKAPAN ===\n"
            )
            # Insert history before the current question in the prompt
            prompt = prompt.replace(
                f"Pertanyaan: {query}",
                f"{history_block}\nPertanyaan: {query}",
            )

        return [HumanMessage(content=prompt)]

    def _format_context(self, documents: list[Document]) -> str:
        """Format documents into a context string with chunks joined by blank lines.

        Args:
            documents: List of documents to format.

        Returns:
            Formatted string with document chunks separated by blank lines.
        """
        return "\n\n".join(doc.page_content for doc in documents)

    def _truncate_context(
        self, documents: list[Document], max_tokens: int
    ) -> list[Document]:
        """Remove lowest-scored documents until context fits within token limit.

        Documents are sorted by score ascending, and the lowest-scored
        documents are removed first until the total token count of the
        remaining documents is within the max_tokens budget.

        Args:
            documents: List of documents to potentially truncate.
            max_tokens: Maximum allowed token count for the context.

        Returns:
            List of documents fitting within the token budget.
        """
        # Calculate total tokens for all documents
        total_tokens = self._count_tokens_for_documents(documents)

        if total_tokens <= max_tokens:
            return documents

        # Sort by score ascending (lowest first) to identify removal candidates
        # Use 'score' for chunks, 'relevance_score' for community summaries
        def get_score(doc: Document) -> float:
            metadata = doc.metadata
            if metadata.get("source_type") == "community_summary":
                return metadata.get("relevance_score", 0.0)
            return metadata.get("score", 0.0)

        sorted_docs = sorted(documents, key=get_score)

        # Remove lowest-scored documents until under the limit
        remaining = list(sorted_docs)
        while remaining and self._count_tokens_for_documents(remaining) > max_tokens:
            remaining.pop(0)  # Remove lowest-scored document

        return remaining

    def _count_tokens_for_documents(self, documents: list[Document]) -> int:
        """Count total tokens across all document page_content fields.

        Args:
            documents: List of documents to count tokens for.

        Returns:
            Total token count.
        """
        total = 0
        for doc in documents:
            total += len(self._encoding.encode(doc.page_content))
        return total

    def _extract_source_attributions(self, documents: list[Document]) -> list[dict]:
        """Extract source attributions from documents.

        Only includes documents with source_type="chunk" (not community summaries).

        Args:
            documents: List of documents used in the context.

        Returns:
            List of attribution dicts with file_id, file_name, and department.
        """
        attributions = []
        seen = set()

        for doc in documents:
            metadata = doc.metadata
            if metadata.get("source_type") != "chunk":
                continue

            file_id = metadata.get("file_id")
            file_name = metadata.get("file_name", "")
            department = metadata.get("department", "")

            # Deduplicate by file_id
            if file_id in seen:
                continue
            seen.add(file_id)

            attributions.append(
                {
                    "file_id": file_id,
                    "file_name": file_name,
                    "department": department,
                }
            )

        return attributions

    def _extract_token_usage(self, response: object) -> dict:
        """Extract token usage from LLM response metadata.

        Args:
            response: The LLM response object.

        Returns:
            Dict with prompt_tokens, completion_tokens, and total_tokens.
            Returns zeros if usage info is not available.
        """
        usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        # LangChain responses typically have usage_metadata or response_metadata
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage["prompt_tokens"] = getattr(um, "input_tokens", 0) or um.get("input_tokens", 0) if isinstance(um, dict) else getattr(um, "input_tokens", 0)
            usage["completion_tokens"] = getattr(um, "output_tokens", 0) or um.get("output_tokens", 0) if isinstance(um, dict) else getattr(um, "output_tokens", 0)
            usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        elif hasattr(response, "response_metadata") and response.response_metadata:
            rm = response.response_metadata
            token_usage = rm.get("token_usage", {}) or rm.get("usage", {})
            if token_usage:
                usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0)
                usage["completion_tokens"] = token_usage.get("completion_tokens", 0)
                usage["total_tokens"] = token_usage.get("total_tokens", 0)

        return usage

    def _error_response(self, start_time: float) -> RAGResponse:
        """Build a response for when an error occurs.

        Args:
            start_time: The time the request started (for elapsed time calc).

        Returns:
            RAGResponse with a generic error message.
        """
        elapsed_ms = int((time.time() - start_time) * 1000)
        return RAGResponse(
            answer=_ERROR_RESPONSE,
            source_attributions=[],
            retrieval_metadata={
                "retrieval_mode": getattr(self.retriever, "retrieval_mode", "combined"),
                "documents_retrieved": 0,
                "query_time_ms": elapsed_ms,
            },
            token_usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )
