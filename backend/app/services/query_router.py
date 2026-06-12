"""Query router with Bahasa Indonesia keyword-based intent detection.

Routes queries to the appropriate TurboVec index (master or dept) based on
keyword substring matching, and executes the retrieval pipeline accordingly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.turbovec_store import TurboVecStore

from app.config import TurboVecSettings

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Result of query routing."""

    mode: str  # "master_first" or "dept_only"
    filename_filter: str | None  # "barang", "outlet", "distributor", or None
    master_top_k: int
    dept_top_k: int


class QueryRouter:
    """Routes queries to appropriate TurboVec indexes based on keyword detection.

    Inspects the user query for Bahasa Indonesia keywords and determines which
    index to query and how to filter results. Keywords are checked in priority
    order: barang, outlet, distributor.
    """

    KEYWORD_SETS: list[tuple[list[str], str]] = [
        (
            [
                "barang", "produk", "item", "sku", "kode barang", "satuan", "inventory",
                "master barang", "harga", "price", "berat", "weight", "dimensi",
                "panjang", "lebar", "tinggi", "volume", "vendor", "pd-0",
                "blue band", "sania", "olivoila", "fortune", "frytol", "kecap",
                "minyak samin", "margarine", "pastry", "btl", "jrg", "cs",
                "satk", "satb", "satt", "berisi", "harga jual", "harga_jual",
                "mahal", "murah", "termahal", "termurah",
            ],
            "barang",
        ),
        (
            [
                "outlet", "toko", "gerai", "cabang", "customer", "pelanggan",
                "wholesale", "retail", "area", "mataram", "ampenan", "jbd",
                "tipe outlet", "outlettype",
            ],
            "outlet",
        ),
        (
            [
                "distributor", "dist", "agen", "supplier", "vendor", "pd-0109",
                "pd-0110", "upfield", "sari agrotama", "supply", "disupply",
            ],
            "distributor",
        ),
    ]

    def __init__(self, settings: TurboVecSettings) -> None:
        self._settings = settings

    def _detect_intent(self, query: str) -> tuple[str, str | None]:
        """Lowercase query and match against keyword sets in priority order.

        For queries that mention vendor/distributor codes (PD-xxxx) or names,
        routes to distributor category. For customer/outlet codes, routes to outlet.
        Otherwise uses keyword matching with a fallback to master_first with no filter.

        Returns:
            A tuple of (mode, filename_filter). Mode is either "master_first"
            or "dept_only". filename_filter is the matched category or None.
        """
        lowered = query.lower()

        import re

        # Priority 1: Specific vendor/distributor codes or names → distributor
        if re.search(r'pd-\d+', lowered) and ("vendor" in lowered or "nama" in lowered or "alamat" in lowered or "lengkap" in lowered) and not ("produk" in lowered or "supply" in lowered):
            return ("master_first", "distributor")

        # Priority 1b: Queries asking about products FROM a vendor → search barang
        # (the keyword boost will also find vendor data)
        if re.search(r'pd-\d+', lowered) and ("produk" in lowered or "supply" in lowered or "disupply" in lowered or "apa saja" in lowered):
            return ("master_first", "barang")

        # Priority 1c: Queries mentioning vendor name + products → no filter (needs both sheets)
        if ("upfield" in lowered or "sari agrotama" in lowered) and ("produk" in lowered or "harga" in lowered):
            return ("master_first", None)

        # Priority 2: Customer/outlet codes → outlet
        if re.search(r'jbd\d+', lowered) or ("customer" in lowered and "kode" in lowered):
            return ("master_first", "outlet")

        # Priority 3: Keyword-based matching
        for keywords, category in self.KEYWORD_SETS:
            for keyword in keywords:
                if keyword in lowered:
                    return ("master_first", category)

        # Fallback: if the query mentions specific product-like patterns
        # (numbers with units, brand names) route to master
        if re.search(r'\d+[kgl]', lowered):  # e.g., "15k", "1l", "5l"
            return ("master_first", "barang")

        return ("master_first", None)

    def route(self, query: str) -> RoutingDecision:
        """Determine routing decision based on query keywords.

        Empty or whitespace-only queries are routed to master_first with no filter.
        Aggregate queries (min/max/count across all products) use a higher top_k
        and no filter to retrieve as many relevant rows as possible.
        """
        if not query or not query.strip():
            return RoutingDecision(
                mode="master_first",
                filename_filter=None,
                master_top_k=self._settings.master_top_k,
                dept_top_k=self._settings.dept_top_k,
            )

        mode, filename_filter = self._detect_intent(query)

        # Detect aggregate queries that need broad scanning
        lowered = query.lower()
        is_aggregate = any(kw in lowered for kw in [
            "paling mahal", "paling murah", "termahal", "termurah",
            "paling besar", "paling kecil", "terbesar", "terkecil",
            "semua produk", "seluruh produk", "apa saja",
            "berapa jumlah", "total",
        ])

        if mode == "master_first":
            # For aggregate queries, use higher top_k but KEEP the filter
            # so we get all relevant rows from the right category
            if is_aggregate and filename_filter == "barang":
                # For aggregate product queries, retrieve ALL barang rows (45 products)
                master_k = 100
            elif is_aggregate:
                master_k = self._settings.master_top_k * 3
            else:
                master_k = self._settings.master_top_k

            return RoutingDecision(
                mode="master_first",
                filename_filter=filename_filter,
                master_top_k=master_k,
                dept_top_k=self._settings.master_first_supplement_k,
            )

        return RoutingDecision(
            mode="dept_only",
            filename_filter=None,
            master_top_k=0,
            dept_top_k=self._settings.dept_top_k,
        )

    def retrieve(
        self,
        query: str,
        query_embedding: list[float],
        store: "TurboVecStore",
    ) -> list[dict]:
        """Execute the full routing + retrieval pipeline.

        Routes the query, performs similarity search against the appropriate
        index(es), and returns results in the correct order. Also performs
        keyword-based boosting for exact code matches (JBD*, PD-*, etc).

        Args:
            query: The user query string.
            query_embedding: Pre-computed embedding vector for the query.
            store: The TurboVecStore instance to search against.

        Returns:
            A list of result dicts ordered per routing mode rules.
        """
        decision = self.route(query)

        if decision.mode == "master_first":
            results = self._retrieve_master_first(query_embedding, decision, store)
        else:
            results = self._retrieve_dept_only(query_embedding, decision, store)

        # Keyword boost: extract codes/identifiers from query and boost matches
        results = self._boost_keyword_matches(query, results, store, decision)

        return results

    def _boost_keyword_matches(
        self,
        query: str,
        results: list[dict],
        store: "TurboVecStore",
        decision: RoutingDecision,
    ) -> list[dict]:
        """Boost results containing exact keyword matches from the query.

        Extracts identifiable codes (JBD*, PD-*, product codes like 8-digit numbers)
        from the query and checks if any results contain them. If not found in
        current results, performs a broader text-scan on the index to find matching rows.

        Args:
            query: The original user query.
            results: Current vector search results.
            store: The TurboVecStore to search for keyword matches.
            decision: The routing decision for context.

        Returns:
            Updated results list with keyword-matched rows prepended.
        """
        import re

        lowered = query.lower()

        # Extract potential codes from query
        codes = []
        # Customer codes: JBD0628
        codes.extend(re.findall(r'jbd\d+', lowered))
        # Vendor codes: PD-0109, PD-0110
        codes.extend(re.findall(r'pd-\d+', lowered))
        # Product barcodes: 8+ digit numbers
        codes.extend(re.findall(r'\b\d{8,}\b', lowered))

        if not codes:
            return results

        # Check if current results already contain the codes
        code_match_count = 0
        for result in results:
            content = result.get("content", "").lower()
            if any(code in content for code in codes):
                code_match_count += 1

        # If we have enough matches for a vendor code (listing query), return as-is
        # Only boost if very few or no matches found
        if code_match_count >= 3:
            return results

        # Not found — do a brute-force text scan on the master index
        # This handles cases where vector similarity doesn't surface exact code matches
        if store.master_index is not None:
            try:
                # Get all documents from master index and search for the code
                all_docs = store.master_index.similarity_search_by_vector(
                    embedding=[0.0] * 384,  # dummy vector
                    k=1000,  # get as many as possible
                )
                keyword_matches = []
                for doc in all_docs:
                    content_lower = doc.page_content.lower()
                    if any(code in content_lower for code in codes):
                        keyword_matches.append({
                            "content": doc.page_content,
                            "metadata": doc.metadata if hasattr(doc, 'metadata') else {},
                            "score": 0.99,  # High score for exact match
                        })
                        if len(keyword_matches) >= 50:
                            break

                if keyword_matches:
                    # Prepend keyword matches to results
                    return keyword_matches + results
            except Exception as e:
                logger.warning(f"Keyword boost scan failed: {e}")

        return results

    def _retrieve_master_first(
        self,
        query_embedding: list[float],
        decision: RoutingDecision,
        store: "TurboVecStore",
    ) -> list[dict]:
        """Retrieve with master_first strategy.

        Top 8 from master (with filename filter, fallback to all if filter
        returns <1 result), top 2 supplement from dept. Master results are
        ordered first, each group sorted by descending similarity.
        """
        # Try filtered search on master index
        master_results = store.similarity_search(
            query_embedding=query_embedding,
            index="master",
            top_k=decision.master_top_k,
            filename_filter=decision.filename_filter,
        )

        # Fallback: if filter returns fewer than 1 result, search all master
        if len(master_results) < 1:
            logger.info(
                f"Filtered master search returned {len(master_results)} results, "
                f"falling back to unfiltered master search"
            )
            master_results = store.similarity_search(
                query_embedding=query_embedding,
                index="master",
                top_k=decision.master_top_k,
                filename_filter=None,
            )

        # Get supplement from dept index
        dept_results = store.similarity_search(
            query_embedding=query_embedding,
            index="dept",
            top_k=decision.dept_top_k,
            filename_filter=None,
        )

        # Master ordered first, each group by descending similarity
        master_sorted = sorted(
            master_results, key=lambda r: r.get("score", 0.0), reverse=True
        )
        dept_sorted = sorted(
            dept_results, key=lambda r: r.get("score", 0.0), reverse=True
        )

        return master_sorted + dept_sorted

    def _retrieve_dept_only(
        self,
        query_embedding: list[float],
        decision: RoutingDecision,
        store: "TurboVecStore",
    ) -> list[dict]:
        """Retrieve with dept_only strategy.

        Top 5 from dept index, ordered by descending similarity score.
        """
        dept_results = store.similarity_search(
            query_embedding=query_embedding,
            index="dept",
            top_k=decision.dept_top_k,
            filename_filter=None,
        )

        return sorted(
            dept_results, key=lambda r: r.get("score", 0.0), reverse=True
        )
