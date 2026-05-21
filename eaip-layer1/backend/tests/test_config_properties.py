"""Property-based tests for GraphRAG configuration validation.

Property 27: Configuration validation applies defaults for out-of-range values

For any KB_-prefixed environment variable set to a value outside its valid range
or of invalid type, the system SHALL apply the documented default value for that
parameter and log a warning identifying the rejected value.

**Validates: Requirements 12.5**
"""

import os
from unittest.mock import patch

import hypothesis.strategies as st
from hypothesis import given, settings

from app.config import GraphRAGSettings


# Environment variables cannot contain null characters, so we use a safe
# alphabet for generating invalid string values.
_safe_text = st.text(
    alphabet=st.characters(blacklist_characters="\x00"),
    min_size=1,
    max_size=10,
)


def _is_numeric_string(s: str) -> bool:
    """Check if a string can be parsed as a float."""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


# --- Strategies for generating out-of-range / invalid values ---

# chunk_size valid range: 64-4096, default: 512
out_of_range_chunk_size = st.one_of(
    st.integers(max_value=63),
    st.integers(min_value=4097),
)

invalid_type_chunk_size = st.one_of(
    _safe_text.filter(lambda s: not _is_int_string(s.strip())),
    st.just("abc"),
    st.just("12.5"),
)

# chunk_overlap valid range: 0 to chunk_size//2, default: 50
# With default chunk_size=512, max overlap = 256
out_of_range_chunk_overlap = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=257),  # > 512//2 = 256
)

invalid_type_chunk_overlap = st.one_of(
    _safe_text.filter(lambda s: not _is_int_string(s.strip())),
    st.just("xyz"),
)

# top_k valid range: 1-100, default: 5
out_of_range_top_k = st.one_of(
    st.integers(max_value=0),
    st.integers(min_value=101),
)

def _is_int_string(s: str) -> bool:
    """Check if a string would be parsed as a Python int."""
    try:
        int(s)
        return True
    except (ValueError, TypeError):
        return False

invalid_type_top_k = st.one_of(
    _safe_text.filter(lambda s: not _is_int_string(s)),
    st.just("not_a_number"),
)

# max_context_tokens valid range: 256-16384, default: 2048
out_of_range_max_context_tokens = st.one_of(
    st.integers(max_value=255),
    st.integers(min_value=16385),
)

invalid_type_max_context_tokens = st.one_of(
    _safe_text.filter(lambda s: not s.strip().lstrip("-").isdigit()),
    st.just("invalid"),
)

# community_resolution valid range: 0.1-10.0, default: 1.0
out_of_range_community_resolution = st.one_of(
    st.floats(max_value=0.09, allow_nan=False, allow_infinity=False),
    st.floats(min_value=10.01, max_value=1e6, allow_nan=False, allow_infinity=False),
)

invalid_type_community_resolution = st.one_of(
    _safe_text.filter(lambda s: not _is_numeric_string(s)),
    st.just("not_float"),
)

# max_community_size valid range: 2-10000, default: 100
out_of_range_max_community_size = st.one_of(
    st.integers(max_value=1),
    st.integers(min_value=10001),
)

invalid_type_max_community_size = st.one_of(
    _safe_text.filter(lambda s: not _is_int_string(s.strip())),
    st.just("bad_value"),
)

# entity_extraction_method: only "rule-based" or "llm-based", default: "rule-based"
invalid_entity_extraction_method = _safe_text.filter(
    lambda s: s.strip().lower() not in {"rule-based", "llm-based"}
)


def _create_settings(**kwargs) -> GraphRAGSettings:
    """Create GraphRAGSettings with given overrides, bypassing env vars."""
    env_overrides = {}
    for key, value in kwargs.items():
        env_overrides[f"KB_{key.upper()}"] = str(value)

    # Clear any existing KB_ env vars that might interfere
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("KB_")}
    clean_env.update(env_overrides)

    with patch.dict(os.environ, clean_env, clear=True):
        return GraphRAGSettings()


class TestProperty27ChunkSize:
    """Property 27: Out-of-range chunk_size values get default 512."""

    @given(value=out_of_range_chunk_size)
    @settings(max_examples=100)
    def test_out_of_range_chunk_size_gets_default(self, value: int):
        """For any out-of-range chunk_size, the default 512 is applied."""
        config = _create_settings(chunk_size=value)
        assert config.chunk_size == 512

    @given(value=invalid_type_chunk_size)
    @settings(max_examples=100)
    def test_invalid_type_chunk_size_gets_default(self, value: str):
        """For any non-integer chunk_size, the default 512 is applied."""
        config = _create_settings(chunk_size=value)
        assert config.chunk_size == 512


class TestProperty27ChunkOverlap:
    """Property 27: Out-of-range chunk_overlap values get default 50."""

    @given(value=out_of_range_chunk_overlap)
    @settings(max_examples=100)
    def test_out_of_range_chunk_overlap_gets_default(self, value: int):
        """For any out-of-range chunk_overlap (with default chunk_size=512), default 50 is applied."""
        config = _create_settings(chunk_overlap=value)
        assert config.chunk_overlap == 50

    @given(value=invalid_type_chunk_overlap)
    @settings(max_examples=100)
    def test_invalid_type_chunk_overlap_gets_default(self, value: str):
        """For any non-integer chunk_overlap, the default 50 is applied."""
        config = _create_settings(chunk_overlap=value)
        assert config.chunk_overlap == 50


class TestProperty27TopK:
    """Property 27: Out-of-range top_k values get default 5."""

    @given(value=out_of_range_top_k)
    @settings(max_examples=100)
    def test_out_of_range_top_k_gets_default(self, value: int):
        """For any out-of-range top_k, the default 5 is applied."""
        config = _create_settings(top_k=value)
        assert config.top_k == 5

    @given(value=invalid_type_top_k)
    @settings(max_examples=100)
    def test_invalid_type_top_k_gets_default(self, value: str):
        """For any non-integer top_k, the default 5 is applied."""
        config = _create_settings(top_k=value)
        assert config.top_k == 5


class TestProperty27MaxContextTokens:
    """Property 27: Out-of-range max_context_tokens values get default 2048."""

    @given(value=out_of_range_max_context_tokens)
    @settings(max_examples=100)
    def test_out_of_range_max_context_tokens_gets_default(self, value: int):
        """For any out-of-range max_context_tokens, the default 2048 is applied."""
        config = _create_settings(max_context_tokens=value)
        assert config.max_context_tokens == 2048

    @given(value=invalid_type_max_context_tokens)
    @settings(max_examples=100)
    def test_invalid_type_max_context_tokens_gets_default(self, value: str):
        """For any non-integer max_context_tokens, the default 2048 is applied."""
        config = _create_settings(max_context_tokens=value)
        assert config.max_context_tokens == 2048


class TestProperty27CommunityResolution:
    """Property 27: Out-of-range community_resolution values get default 1.0."""

    @given(value=out_of_range_community_resolution)
    @settings(max_examples=100)
    def test_out_of_range_community_resolution_gets_default(self, value: float):
        """For any out-of-range community_resolution, the default 1.0 is applied."""
        config = _create_settings(community_resolution=value)
        assert config.community_resolution == 1.0

    @given(value=invalid_type_community_resolution)
    @settings(max_examples=100)
    def test_invalid_type_community_resolution_gets_default(self, value: str):
        """For any non-numeric community_resolution, the default 1.0 is applied."""
        config = _create_settings(community_resolution=value)
        assert config.community_resolution == 1.0


class TestProperty27MaxCommunitySize:
    """Property 27: Out-of-range max_community_size values get default 100."""

    @given(value=out_of_range_max_community_size)
    @settings(max_examples=100)
    def test_out_of_range_max_community_size_gets_default(self, value: int):
        """For any out-of-range max_community_size, the default 100 is applied."""
        config = _create_settings(max_community_size=value)
        assert config.max_community_size == 100

    @given(value=invalid_type_max_community_size)
    @settings(max_examples=100)
    def test_invalid_type_max_community_size_gets_default(self, value: str):
        """For any non-integer max_community_size, the default 100 is applied."""
        config = _create_settings(max_community_size=value)
        assert config.max_community_size == 100


class TestProperty27EntityExtractionMethod:
    """Property 27: Invalid entity_extraction_method values get default 'rule-based'."""

    @given(value=invalid_entity_extraction_method)
    @settings(max_examples=100)
    def test_invalid_entity_extraction_method_gets_default(self, value: str):
        """For any invalid entity_extraction_method, the default 'rule-based' is applied."""
        config = _create_settings(entity_extraction_method=value)
        assert config.entity_extraction_method == "rule-based"
