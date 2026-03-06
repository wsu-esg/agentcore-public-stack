"""Tests for CSV-specific chunker."""

import csv
import io

import tiktoken

from apis.app_api.documents.ingestion.processors.csv_chunker import chunk_csv


def _count_tokens(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _make_csv_bytes(header: list[str], rows: list[list[str]]) -> bytes:
    """Helper to build CSV bytes from header + rows."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


class TestChunkCSVSmall:
    """Small CSVs that fit in a single chunk."""

    def test_small_csv_single_chunk(self):
        header = ["name", "age", "city"]
        rows = [["Alice", "30", "Portland"], ["Bob", "25", "Seattle"]]
        data = _make_csv_bytes(header, rows)

        chunks = chunk_csv(data, max_tokens=900)

        assert len(chunks) == 1
        # Chunk should contain the header
        assert "name,age,city" in chunks[0]
        # Chunk should contain both rows
        assert "Alice" in chunks[0]
        assert "Bob" in chunks[0]

    def test_small_csv_token_count_under_limit(self):
        header = ["col1", "col2"]
        rows = [["val1", "val2"]]
        data = _make_csv_bytes(header, rows)

        chunks = chunk_csv(data, max_tokens=900)

        for chunk in chunks:
            assert _count_tokens(chunk) <= 900


class TestChunkCSVLarge:
    """Large CSVs that must be split across multiple chunks."""

    def test_large_csv_produces_multiple_chunks(self):
        header = ["id", "name", "description"]
        rows = [[str(i), f"item_{i}", f"This is a description for item number {i}"] for i in range(200)]
        data = _make_csv_bytes(header, rows)

        chunks = chunk_csv(data, max_tokens=100)

        assert len(chunks) > 1

    def test_every_chunk_starts_with_header(self):
        header = ["id", "name", "value"]
        rows = [[str(i), f"name_{i}", f"value_{i}"] for i in range(100)]
        data = _make_csv_bytes(header, rows)

        chunks = chunk_csv(data, max_tokens=50)

        for chunk in chunks:
            # csv.writer uses \r\n; strip to handle both
            first_line = chunk.split("\n")[0].rstrip("\r")
            assert first_line == "id,name,value", f"Chunk missing header: {chunk[:80]}"

    def test_all_chunks_under_token_limit(self):
        header = ["id", "name", "description"]
        rows = [[str(i), f"item_{i}", f"Description text for item {i} with more words"] for i in range(200)]
        data = _make_csv_bytes(header, rows)
        max_tokens = 100

        chunks = chunk_csv(data, max_tokens=max_tokens)

        for i, chunk in enumerate(chunks):
            token_count = _count_tokens(chunk)
            assert token_count <= max_tokens, f"Chunk {i} has {token_count} tokens (limit {max_tokens})"


class TestChunkCSVEdgeCases:
    """Edge cases: empty, header-only, oversized rows."""

    def test_empty_csv_returns_empty(self):
        chunks = chunk_csv(b"", max_tokens=900)
        assert chunks == []

    def test_header_only_returns_empty(self):
        data = b"name,age,city\n"
        chunks = chunk_csv(data, max_tokens=900)
        assert chunks == []

    def test_wide_row_gets_truncated(self):
        header = ["id", "data"]
        # Create a row with a very long value
        long_value = "word " * 2000  # ~2000 tokens
        rows = [[str(1), long_value]]
        data = _make_csv_bytes(header, rows)
        max_tokens = 100

        chunks = chunk_csv(data, max_tokens=max_tokens)

        assert len(chunks) >= 1
        for chunk in chunks:
            token_count = _count_tokens(chunk)
            assert token_count <= max_tokens, f"Chunk has {token_count} tokens (limit {max_tokens})"

    def test_csv_with_quoted_commas(self):
        header = ["name", "address"]
        rows = [["Alice", "123 Main St, Suite 4"], ["Bob", "456 Oak Ave, Apt 2"]]
        data = _make_csv_bytes(header, rows)

        chunks = chunk_csv(data, max_tokens=900)

        assert len(chunks) >= 1
        # The quoted values should be preserved
        full_text = "\n".join(chunks)
        assert "123 Main St, Suite 4" in full_text

    def test_csv_with_quoted_newlines(self):
        header = ["name", "bio"]
        rows = [["Alice", "Line 1\nLine 2"], ["Bob", "Single line"]]
        data = _make_csv_bytes(header, rows)

        chunks = chunk_csv(data, max_tokens=900)

        assert len(chunks) >= 1

    def test_single_column_csv(self):
        data = b"value\nfoo\nbar\nbaz\n"
        chunks = chunk_csv(data, max_tokens=900)

        assert len(chunks) == 1
        assert "value" in chunks[0]
        assert "foo" in chunks[0]


class TestChunkCSVTokenBudget:
    """Verify token budgets are respected with the default max_tokens=900."""

    def test_default_max_tokens(self):
        header = ["id", "text"]
        rows = [[str(i), f"Row {i} content with some extra padding text to use tokens"] for i in range(500)]
        data = _make_csv_bytes(header, rows)

        chunks = chunk_csv(data)  # uses default max_tokens=900

        assert len(chunks) > 1
        for chunk in chunks:
            assert _count_tokens(chunk) <= 900
