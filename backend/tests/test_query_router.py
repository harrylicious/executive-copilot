"""Unit tests for the QueryRouter service."""

import pytest

from app.config import TurboVecSettings
from app.services.query_router import QueryRouter, RoutingDecision


@pytest.fixture
def settings():
    """Create TurboVecSettings with defaults."""
    return TurboVecSettings()


@pytest.fixture
def router(settings):
    """Create a QueryRouter with default settings."""
    return QueryRouter(settings)


class TestRoutingDecisionDataclass:
    """Tests for the RoutingDecision dataclass."""

    def test_creates_routing_decision(self):
        decision = RoutingDecision(
            mode="master_first",
            filename_filter="barang",
            master_top_k=8,
            dept_top_k=2,
        )
        assert decision.mode == "master_first"
        assert decision.filename_filter == "barang"
        assert decision.master_top_k == 8
        assert decision.dept_top_k == 2

    def test_creates_dept_only_decision(self):
        decision = RoutingDecision(
            mode="dept_only",
            filename_filter=None,
            master_top_k=0,
            dept_top_k=5,
        )
        assert decision.mode == "dept_only"
        assert decision.filename_filter is None


class TestDetectIntent:
    """Tests for _detect_intent method."""

    def test_detects_barang_keyword(self, router):
        mode, filter_ = router._detect_intent("harga barang ABC")
        assert mode == "master_first"
        assert filter_ == "barang"

    def test_detects_produk_keyword(self, router):
        mode, filter_ = router._detect_intent("daftar produk terbaru")
        assert mode == "master_first"
        assert filter_ == "barang"

    def test_detects_item_keyword(self, router):
        mode, filter_ = router._detect_intent("cari item ini")
        assert mode == "master_first"
        assert filter_ == "barang"

    def test_detects_sku_keyword(self, router):
        mode, filter_ = router._detect_intent("SKU 12345")
        assert mode == "master_first"
        assert filter_ == "barang"

    def test_detects_kode_barang_keyword(self, router):
        mode, filter_ = router._detect_intent("cari kode barang X")
        assert mode == "master_first"
        assert filter_ == "barang"

    def test_detects_outlet_keyword(self, router):
        mode, filter_ = router._detect_intent("daftar outlet jakarta")
        assert mode == "master_first"
        assert filter_ == "outlet"

    def test_detects_toko_keyword(self, router):
        mode, filter_ = router._detect_intent("alamat toko baru")
        assert mode == "master_first"
        assert filter_ == "outlet"

    def test_detects_gerai_keyword(self, router):
        mode, filter_ = router._detect_intent("gerai mana saja?")
        assert mode == "master_first"
        assert filter_ == "outlet"

    def test_detects_distributor_keyword(self, router):
        mode, filter_ = router._detect_intent("nama distributor utama")
        assert mode == "master_first"
        assert filter_ == "distributor"

    def test_detects_dist_keyword(self, router):
        mode, filter_ = router._detect_intent("data dist area jawa")
        assert mode == "master_first"
        assert filter_ == "distributor"

    def test_detects_agen_keyword(self, router):
        mode, filter_ = router._detect_intent("daftar agen resmi")
        assert mode == "master_first"
        assert filter_ == "distributor"

    def test_no_match_returns_dept_only(self, router):
        mode, filter_ = router._detect_intent("laporan penjualan bulan ini")
        assert mode == "dept_only"
        assert filter_ is None

    def test_case_insensitive(self, router):
        mode, filter_ = router._detect_intent("BARANG MAHAL")
        assert mode == "master_first"
        assert filter_ == "barang"

    def test_priority_barang_over_outlet(self, router):
        """When query matches multiple keyword sets, barang has highest priority."""
        mode, filter_ = router._detect_intent("barang di outlet jakarta")
        assert mode == "master_first"
        assert filter_ == "barang"

    def test_priority_barang_over_distributor(self, router):
        mode, filter_ = router._detect_intent("item dari distributor X")
        assert mode == "master_first"
        assert filter_ == "barang"

    def test_priority_outlet_over_distributor(self, router):
        mode, filter_ = router._detect_intent("outlet distributor mana")
        assert mode == "master_first"
        assert filter_ == "outlet"


class TestRoute:
    """Tests for route method."""

    def test_routes_barang_query(self, router):
        decision = router.route("harga barang ABC")
        assert decision.mode == "master_first"
        assert decision.filename_filter == "barang"
        assert decision.master_top_k == 8
        assert decision.dept_top_k == 2

    def test_routes_outlet_query(self, router):
        decision = router.route("daftar outlet jakarta")
        assert decision.mode == "master_first"
        assert decision.filename_filter == "outlet"
        assert decision.master_top_k == 8
        assert decision.dept_top_k == 2

    def test_routes_distributor_query(self, router):
        decision = router.route("nama distributor utama")
        assert decision.mode == "master_first"
        assert decision.filename_filter == "distributor"
        assert decision.master_top_k == 8
        assert decision.dept_top_k == 2

    def test_routes_no_match_to_dept_only(self, router):
        decision = router.route("laporan penjualan")
        assert decision.mode == "dept_only"
        assert decision.filename_filter is None
        assert decision.master_top_k == 0
        assert decision.dept_top_k == 5

    def test_empty_query_routes_dept_only(self, router):
        decision = router.route("")
        assert decision.mode == "dept_only"
        assert decision.filename_filter is None
        assert decision.dept_top_k == 5

    def test_whitespace_query_routes_dept_only(self, router):
        decision = router.route("   ")
        assert decision.mode == "dept_only"
        assert decision.filename_filter is None
        assert decision.dept_top_k == 5

    def test_uses_settings_top_k_values(self):
        custom_settings = TurboVecSettings(
            master_top_k=10,
            dept_top_k=7,
            master_first_supplement_k=3,
        )
        router = QueryRouter(custom_settings)
        decision = router.route("harga barang")
        assert decision.master_top_k == 10
        assert decision.dept_top_k == 3


class TestRetrieve:
    """Tests for retrieve method using a mock store."""

    class FakeStore:
        """Minimal fake store for testing retrieve logic."""

        def __init__(self, master_results=None, dept_results=None):
            self._master_results = master_results or []
            self._dept_results = dept_results or []
            self.calls = []

        def similarity_search(
            self, query_embedding, index, top_k, filename_filter=None
        ):
            self.calls.append(
                {
                    "index": index,
                    "top_k": top_k,
                    "filename_filter": filename_filter,
                }
            )
            if index == "master":
                return self._master_results
            return self._dept_results

    def test_master_first_retrieves_from_both_indexes(self, router):
        store = self.FakeStore(
            master_results=[{"text": "m1", "score": 0.9}],
            dept_results=[{"text": "d1", "score": 0.7}],
        )
        results = router.retrieve("harga barang", [0.1, 0.2], store)
        assert len(results) == 2
        # Master results appear first
        assert results[0]["text"] == "m1"
        assert results[1]["text"] == "d1"

    def test_master_first_uses_filename_filter(self, router):
        store = self.FakeStore(
            master_results=[{"text": "m1", "score": 0.9}],
            dept_results=[{"text": "d1", "score": 0.7}],
        )
        router.retrieve("cari outlet baru", [0.1], store)
        # First call should be to master with "outlet" filter
        assert store.calls[0]["index"] == "master"
        assert store.calls[0]["filename_filter"] == "outlet"

    def test_master_first_fallback_when_filter_returns_empty(self, router):
        call_count = {"n": 0}

        class FallbackStore:
            def similarity_search(self, query_embedding, index, top_k, filename_filter=None):
                call_count["n"] += 1
                if index == "master" and filename_filter is not None:
                    return []  # Filter returns nothing
                if index == "master" and filename_filter is None:
                    return [{"text": "fallback", "score": 0.5}]
                return [{"text": "dept", "score": 0.3}]

        results = router.retrieve("harga barang", [0.1], FallbackStore())
        # Should have called master twice (filtered then unfiltered) + dept
        assert call_count["n"] == 3
        assert results[0]["text"] == "fallback"

    def test_dept_only_retrieves_from_dept(self, router):
        store = self.FakeStore(
            dept_results=[
                {"text": "d1", "score": 0.9},
                {"text": "d2", "score": 0.8},
            ],
        )
        results = router.retrieve("laporan penjualan", [0.1], store)
        assert len(results) == 2
        assert results[0]["score"] == 0.9
        assert results[1]["score"] == 0.8
        # Should only call dept
        assert all(c["index"] == "dept" for c in store.calls)

    def test_dept_only_results_sorted_descending(self, router):
        store = self.FakeStore(
            dept_results=[
                {"text": "d1", "score": 0.5},
                {"text": "d2", "score": 0.9},
                {"text": "d3", "score": 0.7},
            ],
        )
        results = router.retrieve("laporan", [0.1], store)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_master_first_results_ordered_master_then_dept(self, router):
        store = self.FakeStore(
            master_results=[
                {"text": "m1", "score": 0.6},
                {"text": "m2", "score": 0.8},
            ],
            dept_results=[
                {"text": "d1", "score": 0.95},
            ],
        )
        results = router.retrieve("harga barang", [0.1], store)
        # Master first (sorted desc within group), then dept
        assert results[0]["text"] == "m2"  # 0.8
        assert results[1]["text"] == "m1"  # 0.6
        assert results[2]["text"] == "d1"  # 0.95 but comes after master

    def test_empty_query_routes_to_dept(self, router):
        store = self.FakeStore(
            dept_results=[{"text": "d1", "score": 0.5}],
        )
        results = router.retrieve("", [0.1], store)
        assert len(results) == 1
        assert store.calls[0]["index"] == "dept"
