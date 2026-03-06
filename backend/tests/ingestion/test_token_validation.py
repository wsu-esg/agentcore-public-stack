"""Tests for the token validation safety net in bedrock_embeddings."""

import tiktoken

from apis.app_api.documents.ingestion.embeddings.bedrock_embeddings import (
    _count_tokens,
    _hard_split,
    _split_oversized_chunk,
    _validate_and_split_chunks,
)


def test_count_tokens():
    assert _count_tokens("hello") > 0
    assert _count_tokens("") == 0


def test_validate_chunks_passes_small_chunks():
    chunks = ["small chunk one", "small chunk two"]
    result = _validate_and_split_chunks(chunks, max_tokens=100)
    assert result == chunks


def test_validate_chunks_splits_oversized():
    # Build a chunk that exceeds 50 tokens
    big_chunk = "word " * 200  # ~200 tokens
    small_chunk = "tiny"
    chunks = [small_chunk, big_chunk]

    result = _validate_and_split_chunks(chunks, max_tokens=50)

    assert len(result) > 2  # big_chunk got split
    assert result[0] == small_chunk
    for chunk in result:
        assert _count_tokens(chunk) <= 50


def test_split_oversized_by_paragraphs():
    para1 = "First paragraph. " * 10
    para2 = "Second paragraph. " * 10
    text = para1.strip() + "\n\n" + para2.strip()

    result = _split_oversized_chunk(text, max_tokens=50)

    assert len(result) >= 2
    for piece in result:
        assert _count_tokens(piece) <= 50


def test_hard_split():
    enc = tiktoken.get_encoding("cl100k_base")
    text = "token " * 100  # ~100 tokens

    pieces = _hard_split(text, max_tokens=30, enc=enc)

    assert len(pieces) >= 3
    for piece in pieces:
        assert _count_tokens(piece) <= 30
